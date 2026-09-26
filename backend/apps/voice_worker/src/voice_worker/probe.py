"""Latency probe: measure, from *this* machine, the network costs a voice turn pays.

    python -m voice_worker.probe          # uses the same env vars as the worker

Run it on your Mac, in the Hugging Face Space, or on a trial VPS, and compare. It
answers "where should the backend live?" with numbers instead of guesses (ADR-0012/16):

- LLM time to first token (streaming chat completion), several runs
- STT round trip for a short spoken phrase (synthesised locally with Kokoro when its
  files are present, otherwise a short silent clip)
- LiveKit: HTTPS round trip to the LiveKit host
"""

import io
import os
import statistics
import time
import wave
from collections.abc import Callable

import httpx

RUNS = 5


def _stats(samples: list[float]) -> str:
    if not samples:
        return "no successful runs"
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    return f"p50 {statistics.median(ordered):6.0f} ms   p95 {p95:6.0f} ms   (n={len(ordered)})"


def _timed(fn: Callable[[], None], runs: int = RUNS) -> tuple[list[float], list[str]]:
    times, errors = [], []
    for _ in range(runs):
        start = time.perf_counter()
        try:
            fn()
            times.append((time.perf_counter() - start) * 1000)
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {str(exc)[:100]}")
    return times, errors


def _wav(samples_int16: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples_int16)
    return buf.getvalue()


def _speech_clip() -> tuple[bytes, str]:
    kokoro_dir = os.environ.get("KOKORO_DIR", "/data/models/kokoro")
    try:
        from voice_worker.kokoro_tts import KokoroTTS, load_kokoro, to_pcm16

        engine = KokoroTTS(load_kokoro(kokoro_dir, "kokoro-v1.0.onnx"))
        return _wav(to_pcm16(engine.render("What is my account balance?")), 24000), "speech"
    except Exception:
        return _wav(b"\x00\x00" * 16000, 16000), "1 s of silence"


def main() -> None:
    llm_url = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    llm_key = os.environ.get("LLM_API_KEY", "")
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")
    stt_url = os.environ.get("STT_BASE_URL", llm_url).rstrip("/")
    stt_key = os.environ.get("STT_API_KEY") or llm_key
    stt_model = os.environ.get("STT_MODEL", "whisper-large-v3-turbo")
    livekit = (
        os.environ.get("LIVEKIT_URL", "").replace("wss://", "https://").replace("ws://", "http://")
    )

    http = httpx.Client(timeout=30)

    def llm_ttft() -> None:
        body = {
            "model": llm_model,
            "stream": True,
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "Say hello in three words."}],
        }
        with http.stream(
            "POST",
            f"{llm_url}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {llm_key}"},
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data:") and '"content"' in line:
                    return  # first token arrived
        raise RuntimeError("no tokens")

    clip, clip_kind = _speech_clip()

    def stt() -> None:
        r = http.post(
            f"{stt_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {stt_key}"},
            data={"model": stt_model, "language": "en"},
            files={"file": ("probe.wav", clip, "audio/wav")},
        )
        r.raise_for_status()

    def livekit_rtt() -> None:
        http.get(livekit, timeout=10)

    print(f"LLM  {llm_model} @ {httpx.URL(llm_url).host}")
    times, errors = _timed(llm_ttft)
    print(f"  time to first token   {_stats(times)}")
    for e in errors[:2]:
        print(f"  ! {e}")

    print(f"STT  {stt_model} @ {httpx.URL(stt_url).host}  ({clip_kind})")
    times, errors = _timed(stt, runs=3)
    print(f"  transcription         {_stats(times)}")
    for e in errors[:2]:
        print(f"  ! {e}")

    if livekit:
        print(f"LiveKit  {httpx.URL(livekit).host}")
        times, errors = _timed(livekit_rtt)
        print(f"  HTTPS round trip      {_stats(times)}")
        for e in errors[:2]:
            print(f"  ! {e}")
    else:
        print("LiveKit  LIVEKIT_URL not set; skipped")


if __name__ == "__main__":
    main()

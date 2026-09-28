"""Kokoro as a LiveKit TTS plugin: local, free, no API key (ADR-0018).

Non-streaming: LiveKit wraps it with a sentence tokenizer, so the first short sentence
("Sure.") is synthesised and played while the rest is still being generated.
Synthesis runs in a worker thread so the audio loop never blocks.
"""

import asyncio
import logging
import re
import uuid
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from kokoro_onnx import Kokoro
from kokoro_onnx.config import SAMPLE_RATE
from livekit.agents import APIConnectOptions, tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

log = logging.getLogger(__name__)

RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
VOICES_FILE = "voices-v1.0.bin"


def ensure_model_files(directory: str, model_file: str) -> tuple[Path, Path]:
    """Download the model and voices once; later starts reuse them (mount a volume)."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    paths = (root / model_file, root / VOICES_FILE)
    for path in paths:
        if path.exists() and path.stat().st_size > 0:
            continue
        log.info("downloading kokoro file", extra={"file": path.name})
        partial = path.with_suffix(path.suffix + ".part")
        with httpx.stream("GET", f"{RELEASE}/{path.name}", follow_redirects=True, timeout=600) as r:
            r.raise_for_status()
            with partial.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
        partial.rename(path)  # atomic: never leave a half-written model behind
    return paths


def load_kokoro(directory: str, model_file: str) -> Kokoro:
    model, voices = ensure_model_files(directory, model_file)
    return Kokoro(str(model), str(voices))


MAX_PIECE_CHARS = 120
_CLAUSE_END = re.compile(r"(?<=[,;:—])\s+")


def speakable_pieces(text: str, max_chars: int = MAX_PIECE_CHARS) -> list[str]:
    """Split text into pieces short enough to start playing quickly.

    LiveKit already splits sentences; this splits *long* sentences at clause breaks, then
    at spaces, so no single piece holds up the first audio.
    """
    pieces: list[str] = []
    for clause in _CLAUSE_END.split(text.strip()):
        while len(clause) > max_chars:
            cut = clause.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            pieces.append(clause[:cut].strip())
            clause = clause[cut:]
        if clause.strip():
            pieces.append(clause.strip())
    return pieces


def to_pcm16(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return bytes((clipped * 32767).astype(np.int16).tobytes())


class KokoroTTS(tts.TTS[Any]):
    def __init__(self, engine: Kokoro, voice: str = "af_heart", speed: float = 1.0) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
        )
        self._engine = engine
        self._voice = voice
        self._speed = speed
        # Kokoro's English voices start with a/b (US/UK); h* voices are Hindi.
        self._lang = (
            "hi" if voice.startswith("h") else "en-gb" if voice.startswith("b") else "en-us"
        )

    @property
    def model(self) -> str:
        return "kokoro-v1.0"

    @property
    def provider(self) -> str:
        return "kokoro-onnx"

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts.ChunkedStream:
        return _KokoroStream(tts=self, input_text=text, conn_options=conn_options)

    def render(self, text: str) -> np.ndarray:
        samples, _ = self._engine.create(
            text, voice=self._voice, speed=self._speed, lang=self._lang
        )
        return samples


class _KokoroStream(tts.ChunkedStream):
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        engine: KokoroTTS = self._tts  # type: ignore[assignment]
        output_emitter.initialize(
            request_id=uuid.uuid4().hex,
            sample_rate=SAMPLE_RATE,
            num_channels=1,
            mime_type="audio/pcm",
        )
        # Push audio piece by piece: time to first audio is the first *clause*, not the
        # whole sentence (measured: a long run-on reply took 8 s to start speaking).
        for piece in speakable_pieces(self._input_text):
            samples = await asyncio.to_thread(engine.render, piece)
            output_emitter.push(to_pcm16(samples))
        output_emitter.flush()

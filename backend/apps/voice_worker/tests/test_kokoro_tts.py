"""Kokoro plugin tests. Synthesis runs if the model files are available locally:
KOKORO_TEST_DIR=/path/with/kokoro-v1.0.onnx+voices-v1.0.bin uv run pytest
"""

import os
from pathlib import Path

import numpy as np
import pytest

from voice_worker.kokoro_tts import (
    VOICES_FILE,
    KokoroTTS,
    ensure_model_files,
    speakable_pieces,
    to_pcm16,
)

MODEL_DIR = os.environ.get("KOKORO_TEST_DIR")


def test_pcm16_conversion_clips_and_scales() -> None:
    pcm = np.frombuffer(to_pcm16(np.array([0.0, 1.0, -1.0, 2.0], dtype=np.float32)), np.int16)
    assert pcm.tolist() == [0, 32767, -32767, 32767]


def test_existing_model_files_are_not_downloaded_again(tmp_path: Path) -> None:
    for name in ("model.onnx", VOICES_FILE):
        (tmp_path / name).write_bytes(b"x")
    assert ensure_model_files(str(tmp_path), "model.onnx") == (
        tmp_path / "model.onnx",
        tmp_path / VOICES_FILE,
    )


@pytest.mark.skipif(not MODEL_DIR, reason="KOKORO_TEST_DIR not set")
async def test_synthesises_speech_frames() -> None:
    from voice_worker.kokoro_tts import load_kokoro

    assert MODEL_DIR
    tts = KokoroTTS(load_kokoro(MODEL_DIR, "kokoro-v1.0.onnx"), voice="af_heart")
    frames = []
    async with tts.synthesize("Your card is now blocked.") as stream:
        async for audio in stream:
            frames.append(audio.frame)
    seconds = sum(f.samples_per_channel for f in frames) / 24000
    assert frames and frames[0].sample_rate == 24000
    assert 0.8 < seconds < 5


def test_short_sentences_stay_whole() -> None:
    assert speakable_pieces("Your card is now blocked.") == ["Your card is now blocked."]


def test_long_sentences_split_at_clauses_then_spaces() -> None:
    text = "Sure, I found it: the charge of ₹1,999 on 25 September was StreamPlus, " + "a " * 80
    pieces = speakable_pieces(text, max_chars=60)
    assert pieces[0] == "Sure,"
    assert all(len(p) <= 60 for p in pieces)
    assert " ".join(pieces).split() == text.split()

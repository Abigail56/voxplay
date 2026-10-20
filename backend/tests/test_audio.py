import shutil

import numpy as np
import pytest

from app.audio import SAMPLE_RATE, AudioError, decode_to_mono_16k, preprocess, trim_silence

from .helpers import tone_wav

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def test_trim_silence_removes_leading_and_trailing_silence():
    speech = 0.5 * np.sin(2 * np.pi * 200 * np.arange(SAMPLE_RATE) / SAMPLE_RATE)
    silence = np.zeros(SAMPLE_RATE)
    trimmed = trim_silence(np.concatenate([silence, speech, silence]).astype(np.float32))
    # ~1 s of speech plus a little padding, instead of 3 s.
    assert 0.95 < trimmed.size / SAMPLE_RATE < 1.3


def test_trim_silence_on_pure_silence_returns_empty():
    assert trim_silence(np.zeros(SAMPLE_RATE, dtype=np.float32)).size == 0


def test_trim_silence_ignores_quiet_hiss():
    hiss = np.random.default_rng(0).normal(scale=1e-4, size=SAMPLE_RATE).astype(np.float32)
    assert trim_silence(hiss).size == 0


@needs_ffmpeg
def test_decode_resamples_to_16k_mono():
    audio = decode_to_mono_16k(tone_wav(300, seconds=2.0, sample_rate=44_100))
    assert audio.dtype == np.float32
    assert abs(audio.size - 2 * SAMPLE_RATE) < 200


@needs_ffmpeg
def test_decode_rejects_garbage():
    with pytest.raises(AudioError):
        decode_to_mono_16k(b"this is not audio")


@needs_ffmpeg
def test_preprocess_trims_and_reports_durations():
    prepared = preprocess(tone_wav(250, seconds=2.0, silence=1.0))
    assert prepared.original_seconds == pytest.approx(4.0, abs=0.05)
    assert 1.9 < prepared.speech_seconds < 2.3
    assert np.max(np.abs(prepared.samples)) == pytest.approx(0.95, abs=0.01)


@needs_ffmpeg
def test_preprocess_rejects_too_little_speech():
    with pytest.raises(AudioError, match="speech"):
        preprocess(tone_wav(250, seconds=0.4, silence=1.0), min_speech_seconds=1.0)

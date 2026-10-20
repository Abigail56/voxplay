"""Test helpers: synthetic audio and a fake embedder (no PyTorch needed)."""

import io
import wave

import numpy as np

from app.matching import l2_normalize


def tone_wav(freq_hz: float, seconds: float = 2.0, sample_rate: int = 22_050, silence: float = 0.0) -> bytes:
    """A sine 'voice' at freq_hz, optionally padded with silence on both sides.

    The odd sample rate (22.05 kHz) checks that resampling to 16 kHz works.
    """
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    tone = 0.5 * np.sin(2 * np.pi * freq_hz * t)
    pad = np.zeros(int(silence * sample_rate))
    signal = np.concatenate([pad, tone, pad])
    pcm = (signal * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


class FakeEmbedder:
    """Maps the dominant pitch of a clip to a 192-d vector.

    Clips with the same pitch get the same "voiceprint", very different pitches
    get unrelated ones - just like a real speaker model, but deterministic.
    """

    def embed(self, samples: np.ndarray) -> np.ndarray:
        spectrum = np.abs(np.fft.rfft(samples))
        freq = np.argmax(spectrum) * 16_000 / len(samples)
        centre = freq / 50.0  # one "dimension" per 50 Hz
        x = np.arange(192)
        return l2_normalize(np.exp(-0.5 * ((x - centre) / 1.5) ** 2) + 1e-6)

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


class FakeTranscriber:
    """Speech-to-text stand-in: 'hears' whatever the test puts in .text."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.prompts: list[str | None] = []  # the vocabulary hints it was given

    def transcribe(self, samples: np.ndarray, prompt: str | None = None) -> str:
        self.prompts.append(prompt)
        return self.text


class FakeGeocoder:
    """A tiny gazetteer instead of OpenStreetMap."""

    PLACES = {
        ("yaba, lagos", "NG"): ("Yaba, Lagos", 6.50682, 3.37549),
        ("ikeja", "NG"): ("Ikeja, Lagos", 6.60184, 3.35149),
        ("westlands, nairobi", "KE"): ("Westlands, Nairobi", -1.26800, 36.81100),
        ("camden, london", "GB"): ("Camden, London", 51.54000, -0.14300),
    }

    down = False  # set True to act like OpenStreetMap isn't answering

    async def search(self, query, country):
        from app.geocode import GeocoderUnavailable, Place

        if self.down:
            raise GeocoderUnavailable("offline")

        hit = self.PLACES.get((query.strip().lower(), country.upper()))
        return Place(hit[0], country.upper(), hit[1], hit[2]) if hit else None

    async def reverse(self, lat, lon):
        from app.geocode import Place

        # Snaps any point to the nearest known area (like Nominatim at neighbourhood zoom).
        name, country, plat, plon = min(
            ((n, c, la, lo) for (_, c), (n, la, lo) in self.PLACES.items()),
            key=lambda p: (p[2] - lat) ** 2 + (p[3] - lon) ** 2,
        )
        return Place(name, country, plat, plon)

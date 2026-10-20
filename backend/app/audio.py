"""Audio preprocessing: any common format -> clean 16 kHz mono float32 samples.

Steps
-----
1. decode_to_mono_16k: FFmpeg decodes wav / mp3 / webm (browser recordings) /
   ogg / m4a / flac, mixes to mono and resamples to 16 kHz, which is what the
   ECAPA model was trained on.
2. voiced_mask / trim_silence: a simple energy-based voice activity detector
   finds (and drops) quiet frames (leading/trailing silence and long pauses) so the voiceprint is built
   from speech, not from room noise.
3. preprocess: runs both and rejects clips with too little speech.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 16_000


class AudioError(ValueError):
    """Raised for audio we cannot use. The message is safe to show to users."""


def decode_to_mono_16k(data: bytes) -> np.ndarray:
    """Decode audio bytes of (almost) any format with FFmpeg."""
    if not data:
        raise AudioError("The audio file is empty.")

    # Write to a temp file instead of piping: some containers (mp4/m4a from
    # Safari) keep their index at the end and need a seekable input.
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-i", path,
                "-vn",  # ignore any video stream
                "-ac", "1",  # mono
                "-ar", str(SAMPLE_RATE),  # 16 kHz
                "-f", "f32le", "pipe:1",  # raw 32-bit float samples to stdout
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioError("Decoding the audio took too long.") from exc
    finally:
        os.unlink(path)

    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="ignore").strip().splitlines()
        raise AudioError(f"Could not decode audio ({detail[-1] if detail else 'unknown format'}).")

    audio = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    if audio.size == 0:
        raise AudioError("The file contains no audio samples.")
    return audio


FRAME_MS = 30


def voiced_mask(
    audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    frame_ms: int = FRAME_MS,
    top_db: float = 35.0,
    floor_db: float = -55.0,
    pad_frames: int = 3,
) -> np.ndarray:
    """One True/False per `frame_ms` frame: does this frame contain speech?

    A frame counts as speech when its loudness (RMS in dB) is within `top_db`
    of the loudest frame AND above an absolute `floor_db` (so pure hiss is never
    "speech"). Each speech frame keeps `pad_frames` neighbours on both sides so
    that soft word endings are not chopped off.
    """
    frame_len = int(sample_rate * frame_ms / 1000)
    n_frames = audio.size // frame_len
    if n_frames == 0:
        return np.zeros(0, dtype=bool)

    audio = audio - float(np.mean(audio))  # remove DC offset
    frames = audio[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)

    threshold = max(float(db.max()) - top_db, floor_db)
    voiced = db > threshold
    if voiced.any() and pad_frames > 0:
        # Dilate the voiced mask by pad_frames on each side.
        kernel = np.ones(2 * pad_frames + 1, dtype=int)
        voiced = np.convolve(voiced.astype(int), kernel, mode="same") > 0
    return voiced


def trim_silence(audio: np.ndarray, sample_rate: int = SAMPLE_RATE, frame_ms: int = FRAME_MS, **vad) -> np.ndarray:
    """Keep only the frames that contain speech (see voiced_mask)."""
    voiced = voiced_mask(audio, sample_rate, frame_ms, **vad)
    if not voiced.any():
        return audio[:0]
    frame_len = int(sample_rate * frame_ms / 1000)
    audio = audio - float(np.mean(audio))
    frames = audio[: voiced.size * frame_len].reshape(voiced.size, frame_len)
    return frames[voiced].reshape(-1).astype(np.float32)


@dataclass(frozen=True)
class ClipQuality:
    """How good a recording is for learning someone's voice, with advice when it isn't.

    Measured on the clip as recorded (before any normalising):
    - speech_seconds: how much actual speech there is.
    - loudness_db: average level of the speech (0 dB = the loudest possible).
    - clipped: share of samples at the very top of the range (distortion from shouting or a hot mic).
    - snr_db: speech level vs the room's background noise (bigger = cleaner).
    """

    speech_seconds: float
    loudness_db: float
    clipped: float
    snr_db: float
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


# Limits for enrollment clips. Chosen so clean phone/laptop recordings pass easily
# (tested on LibriSpeech and on browser recordings with noise suppression on).
ENROLL_MIN_SPEECH = 3.0
MIN_LOUDNESS_DB = -38.0
MAX_CLIPPED = 0.01
MIN_SNR_DB = 12.0


def clip_quality(audio: np.ndarray, sample_rate: int = SAMPLE_RATE, frame_ms: int = FRAME_MS) -> ClipQuality:
    voiced = voiced_mask(audio, sample_rate, frame_ms)
    frame_len = int(sample_rate * frame_ms / 1000)
    n = voiced.size
    if n == 0 or not voiced.any():
        return ClipQuality(0.0, -100.0, 0.0, 0.0, ("We couldn't hear any speech. Check your microphone and speak up.",))
    centred = audio - float(np.mean(audio))
    frames = centred[: n * frame_len].reshape(n, frame_len)
    db = 20 * np.log10(np.sqrt(np.mean(frames**2, axis=1) + 1e-12))
    speech_seconds = float(voiced.sum()) * frame_ms / 1000
    loudness = float(np.mean(db[voiced]))
    # Speech level (loud part of the speech) vs background (quietest part of the whole clip).
    snr = float(np.percentile(db[voiced], 90) - np.percentile(db, 10))
    clipped = float(np.mean(np.abs(audio) >= 0.99))

    problems = []
    if speech_seconds < ENROLL_MIN_SPEECH:
        problems.append(f"Too short: we heard {speech_seconds:.1f}s of speech. Read the whole sentence (at least 3 seconds).")
    if loudness < MIN_LOUDNESS_DB:
        problems.append("Too quiet: move closer to the microphone or speak up.")
    if clipped > MAX_CLIPPED:
        problems.append("Too loud, the sound is distorted: move the phone a little further away.")
    if snr < MIN_SNR_DB:
        problems.append("Too noisy: find a quieter spot (no TV, music or chatter in the background).")
    return ClipQuality(round(speech_seconds, 2), round(loudness, 1), round(clipped, 4), round(snr, 1), tuple(problems))


@dataclass(frozen=True)
class PreparedAudio:
    samples: np.ndarray  # speech only, peak-normalised: what the speaker model sees
    decoded: np.ndarray  # the whole clip, pauses included: what speech-to-text hears
    original_seconds: float
    speech_seconds: float
    quality: ClipQuality


def preprocess(
    data: bytes,
    min_speech_seconds: float = 1.0,
    max_seconds: float = 60.0,
) -> PreparedAudio:
    """Decode, trim silence and validate one uploaded clip."""
    audio = decode_to_mono_16k(data)
    original_seconds = audio.size / SAMPLE_RATE
    if original_seconds > max_seconds:
        raise AudioError(f"Clip is {original_seconds:.0f}s long; the maximum is {max_seconds:.0f}s.")

    speech = trim_silence(audio)
    speech_seconds = speech.size / SAMPLE_RATE
    if speech_seconds < min_speech_seconds:
        raise AudioError(
            f"Only {speech_seconds:.1f}s of speech found; please record at least "
            f"{min_speech_seconds:.0f}s of clear speech."
        )

    # Peak-normalise so very quiet recordings are not penalised.
    peak = float(np.max(np.abs(speech)))
    if peak > 0:
        speech = (speech / peak * 0.95).astype(np.float32)

    return PreparedAudio(speech, audio, round(original_seconds, 2), round(speech_seconds, 2), clip_quality(audio))

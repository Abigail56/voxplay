"""Audio preprocessing: any common format -> clean 16 kHz mono float32 samples.

Steps
-----
1. decode_to_mono_16k: FFmpeg decodes wav / mp3 / webm (browser recordings) /
   ogg / m4a / flac, mixes to mono and resamples to 16 kHz, which is what the
   ECAPA model was trained on.
2. trim_silence: a simple energy-based voice activity detector drops quiet
   frames (leading/trailing silence and long pauses) so the voiceprint is built
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


def trim_silence(
    audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    frame_ms: int = 30,
    top_db: float = 35.0,
    floor_db: float = -55.0,
    pad_frames: int = 3,
) -> np.ndarray:
    """Keep only the frames that contain speech.

    A frame counts as speech when its loudness (RMS in dB) is within `top_db`
    of the loudest frame AND above an absolute `floor_db` (so pure hiss is never
    "speech"). Each speech frame keeps `pad_frames` neighbours on both sides so
    that soft word endings are not chopped off.
    """
    frame_len = int(sample_rate * frame_ms / 1000)
    if audio.size < frame_len:
        return audio[:0]

    audio = audio - float(np.mean(audio))  # remove DC offset
    n_frames = audio.size // frame_len
    frames = audio[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)

    threshold = max(float(db.max()) - top_db, floor_db)
    voiced = db > threshold
    if not voiced.any():
        return audio[:0]

    # Dilate the voiced mask by pad_frames on each side.
    if pad_frames > 0:
        kernel = np.ones(2 * pad_frames + 1, dtype=int)
        voiced = np.convolve(voiced.astype(int), kernel, mode="same") > 0

    return frames[voiced].reshape(-1).astype(np.float32)


@dataclass(frozen=True)
class PreparedAudio:
    samples: np.ndarray
    original_seconds: float
    speech_seconds: float


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

    return PreparedAudio(speech, round(original_seconds, 2), round(speech_seconds, 2))

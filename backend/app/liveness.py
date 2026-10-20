"""Liveness check: "say this phrase" so a recording can't be replayed.

A voiceprint alone can't tell a live person from a recording of them: play
Ada's voice note from a phone and the speaker model happily says "Ada". So
before identifying, the server hands out a random phrase of digits such as
"four seven two nine one six". The clip only counts if

1. speech-to-text (Whisper) hears that phrase in it, and
2. the challenge is fresh (valid for a short time) and used only once.

A recording made earlier can't contain a phrase nobody knew yet, and the same
answer can't be sent twice. What this does NOT stop: someone who clones a
voice with AI and makes it say the phrase within the time limit. Catching that
needs a dedicated anti-spoofing model (see README).

Pure logic plus a thin layer over the shared store (Redis), so it is easy to test.
"""

from __future__ import annotations

import re
import secrets
import threading
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .store import Store

# Digits only, like bank voice checks. Tested with Whisper base.en: random digits were heard
# right far more often than random words ("nine" in a list of words often became "pine"),
# see README "Liveness check". No zero, so nobody wonders whether to say "zero" or "oh".
DIGITS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")

# How speech-to-text may spell what was said, mapped back to the digit words.
SPELLINGS = {
    **{str(i): w for i, w in enumerate(("zero", *DIGITS))},
    "won": "one", "to": "two", "too": "two", "for": "four", "fore": "four", "ate": "eight",
}


class Transcriber(Protocol):
    """Anything that turns 16 kHz mono samples into text. Tests use a fake one."""

    def transcribe(self, samples: np.ndarray) -> str: ...


class WhisperTranscriber:
    """faster-whisper (a fast CPU build of OpenAI's Whisper), English only."""

    def __init__(self, model: str, download_root: str, num_threads: int = 2) -> None:
        # Imported here so that tests (and importing this module) don't need it.
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            model, device="cpu", compute_type="int8", cpu_threads=num_threads, download_root=download_root
        )
        self._lock = threading.Lock()

    def transcribe(self, samples: np.ndarray) -> str:
        with self._lock:
            # No prompt with the expected words: that would nudge Whisper into
            # "hearing" the phrase even when it wasn't said.
            segments, _ = self._model.transcribe(
                np.ascontiguousarray(samples, dtype=np.float32),
                language="en",
                beam_size=5,
                condition_on_previous_text=False,
            )
            return " ".join(s.text.strip() for s in segments).strip()


def make_phrase(length: int = 6) -> str:
    """Random digits written as words, e.g. 'four seven two nine one six'.

    With 6 digits there are 9**6 (about 530,000) different phrases.
    """
    return " ".join(secrets.choice(DIGITS) for _ in range(length))


def normalise(text: str) -> list[str]:
    """Lower-case words with punctuation removed and digits spelled out ('4-7-2' -> four seven two)."""
    tokens = []
    for token in re.findall(r"[a-z]+|\d", text.lower()):
        tokens.append(SPELLINGS.get(token, token))
    return tokens


def phrase_match(expected: str, heard: str) -> float:
    """Share of the expected words that were heard, in the right order (0..1).

    Uses the longest common subsequence, so extra words ("um", "okay") and a
    single misheard word only cost a little, but saying the words in a
    different order doesn't count.
    """
    want, got = normalise(expected), normalise(heard)
    if not want:
        return 0.0
    # Classic dynamic-programming LCS on words.
    prev = [0] * (len(got) + 1)
    for w in want:
        cur = [0]
        for j, g in enumerate(got):
            cur.append(prev[j] + 1 if w == g else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1] / len(want)


@dataclass(frozen=True)
class Challenge:
    id: str
    phrase: str
    expires_in_seconds: int


class ChallengeStore:
    """Hands out one-time phrases and checks them off.

    They live in the shared store (Redis when configured): Redis deletes them
    when they expire, and reading one deletes it (GETDEL), so a phrase can be
    answered once, by one request, on any API instance.
    """

    def __init__(self, store: Store, ttl_seconds: int = 120) -> None:
        self.store = store
        self.ttl = ttl_seconds

    async def issue(self) -> Challenge:
        challenge = Challenge(secrets.token_urlsafe(16), make_phrase(), self.ttl)
        await self.store.put(f"challenge:{challenge.id}", challenge.phrase, self.ttl)
        return challenge

    async def take(self, challenge_id: str) -> str | None:
        """Use up a challenge and return its phrase. None if unknown, already used or expired."""
        return await self.store.take(f"challenge:{challenge_id}")

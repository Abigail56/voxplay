"""Word Bomb's dictionary: is this a real word, does it contain the letters, and is it one we'll show?

- ENABLE (public domain, ~173,000 English words), the list word games have long used
- plus data/words/naija.txt: Nigerian and African words ENABLE doesn't know (jollof, danfo, wahala…)
- minus data/words/blocked.txt: slurs and crude words, so nothing hateful ends up on a party screen
"""

from __future__ import annotations

import gzip
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

WORDS_DIR = Path(__file__).parent / "data" / "words"
MIN_LETTERS = 3


def _lines(path: Path) -> set[str]:
    return {w.strip() for w in path.read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")}


@lru_cache(maxsize=1)
def dictionary() -> frozenset[str]:
    with gzip.open(WORDS_DIR / "enable.txt.gz", "rt", encoding="ascii") as f:
        words = {w.strip() for w in f}
    return frozenset(words | _lines(WORDS_DIR / "naija.txt"))


@lru_cache(maxsize=1)
def blocked() -> frozenset[str]:
    return frozenset(_lines(WORDS_DIR / "blocked.txt"))


def is_blocked(word: str) -> bool:
    stems = {word}
    for end in ("s", "es", "ed", "ing", "er", "ers"):
        if word.endswith(end) and len(word) > len(end) + 2:
            stems.add(word[: -len(end)])
    return bool(stems & blocked())


@dataclass
class Check:
    word: str | None  # the word that counts, or None
    verdict: str  # correct | wrong | duplicate
    note: str  # what to tell the player


def plain_words(text: str) -> list[str]:
    """Lower case, no accents or punctuation. (Unlike quiz answers, number words stay words: "ten" has EN.)"""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c)).replace("'", "").replace("’", "")
    return re.findall(r"[a-z]+", text)


def check(said: str, chunk: str, used: list[str]) -> Check:
    """Find a word in what was said (typed, or heard by speech-to-text: "Um, bangle!") that is real, long
    enough, contains the chunk and hasn't been used this game. The longest such word counts, so "it's a
    kite" with IT is KITE, not ITS."""
    chunk = chunk.lower()
    with_chunk = sorted({w for w in plain_words(said) if chunk in w}, key=lambda w: (-len(w), w))
    if not with_chunk:
        return Check(None, "wrong", f"No {chunk.upper()} in that.")
    for w in with_chunk:
        if is_blocked(w):
            return Check(None, "wrong", "Let's keep it friendly. Try another word!")
    real = [w for w in with_chunk if len(w) >= MIN_LETTERS and w in dictionary()]
    if not real:
        short = all(len(w) < MIN_LETTERS for w in with_chunk)
        return Check(None, "wrong", f"At least {MIN_LETTERS} letters!" if short else f"“{with_chunk[0]}” isn't in our dictionary.")
    fresh = [w for w in real if w not in used]
    if not fresh:
        return Check(None, "duplicate", f"“{real[0]}” was already used this game.")
    return Check(fresh[0], "correct", f"{fresh[0].upper()}! Bomb passed.")

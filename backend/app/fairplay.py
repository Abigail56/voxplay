"""The fair-play detector: spots answers that look like cheating, for the host to judge.

It combines two kinds of evidence:

- What the AI hears. In Beat Drop the hum is run through Whisper (speech-to-text); a hummer who
  just *says* the song title instead of humming it is caught. In Story Forge a line copied from
  earlier in the story is caught by comparing the text.
- How the answer was given. The browser reports a few facts about each typed answer: how long the
  player had the game hidden (switched to another tab or app, where they could look it up), whether
  the answer was pasted, and how long the typing took. The server adds what it knows itself: how
  fast the answer came after the question appeared, and whether a player on the other team sent the
  same unusual answer just before (someone reading over a shoulder).

Each sign has a weight, roughly "how likely is this to be cheating on its own". The signs are
combined like independent probabilities: suspicion = 1 - (1 - w1)(1 - w2)... An answer at or
above FLAG_AT is flagged: its points are held, every player sees why, and the host (or, when the
host is the one flagged, the other team) allows or voids it. Nobody is punished automatically, so
a false alarm costs nothing but a tap.
"""

from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

FLAG_AT = 0.6


class Signals(BaseModel):
    """What the browser saw while the player answered. All optional: older screens send nothing."""

    away_ms: int = Field(default=0, ge=0, le=3_600_000)  # game hidden (another tab or app) since the question appeared
    pasted: bool = False  # the answer was pasted into the box
    typing_ms: int | None = Field(default=None, ge=0, le=3_600_000)  # first key press to Send
    voice: bool = False  # answered by voice (typing signs don't apply)


class Sign(BaseModel):
    reason: str
    weight: float


def suspicion(signs: list[Sign]) -> float:
    clean = 1.0
    for s in signs:
        clean *= 1 - s.weight
    return round(1 - clean, 2)


def answer_signs(
    signals: Signals,
    said: str,
    correct: bool,
    opened_at: datetime,
    received: datetime,
    rival_same: str | None = None,
) -> list[Sign]:
    """Signs of cheating on a typed or spoken answer. Wrong answers are never flagged: there's nothing to gain.

    `rival_same` names a player on the other team who sent the same answer in this round.
    """
    if not correct:
        return []
    signs: list[Sign] = []
    away = signals.away_ms / 1000
    if away >= 10:
        signs.append(Sign(reason=f"Left the game for {away:.0f}s before answering", weight=0.55))
    elif away >= 4:
        signs.append(Sign(reason=f"Left the game for {away:.0f}s before answering", weight=0.35))
    if not signals.voice:
        chars = len(said.strip())
        if signals.pasted:
            signs.append(Sign(reason="Pasted the answer instead of typing it", weight=0.5))
        elif signals.typing_ms is not None and chars >= 8:
            per_second = chars / max(signals.typing_ms / 1000, 0.05)
            if per_second > 18:  # very fast typists manage about 12 characters a second
                signs.append(Sign(reason=f"Typed {chars} characters in {signals.typing_ms / 1000:.1f}s, faster than anyone can", weight=0.5))
        took = (received - opened_at).total_seconds()
        if chars >= 6 and took < 1.2:
            signs.append(Sign(reason=f"Answered {took:.1f}s after the question appeared, before it could be read", weight=0.45))
    if rival_same:
        signs.append(Sign(reason=f"Sent the same answer as {rival_same} from the other team", weight=0.4))
    return signs


def hum_signs(title_words: list[str], heard: list[str]) -> list[Sign]:
    """Beat Drop: did the hummer say the title instead of humming it?

    `title_words` and `heard` are already normalised tokens (see brain_clash.tokens). Humming comes
    out of Whisper as nothing, "mm hmm", or a few made-up words; the title's own words are the giveaway.
    """
    important = [w for w in title_words if len(w) >= 3] or title_words
    if not important or not heard:
        return []
    hits = sum(any(w == h or (len(w) >= 5 and SequenceMatcher(None, w, h).ratio() >= 0.85) for h in heard) for w in important)
    if hits == len(important):
        return [Sign(reason=f"The AI heard the title being said, not hummed: “{' '.join(heard)[:80]}”", weight=0.9)]
    if hits and hits / len(important) >= 0.5:
        return [Sign(reason=f"The AI heard part of the title in the hum: “{' '.join(heard)[:80]}”", weight=0.65)]
    return []


def line_signs(line: str, earlier: list[str], signals: Signals) -> list[Sign]:
    """Story Forge: a line copied from earlier in the story, or pasted in from somewhere else."""
    signs: list[Sign] = []
    norm = " ".join(line.lower().split())
    for old in earlier:
        if SequenceMatcher(None, norm, " ".join(old.lower().split())).ratio() >= 0.85:
            signs.append(Sign(reason="Copied a line that's already in the story", weight=0.7))
            break
    if signals.pasted and not signals.voice:
        signs.append(Sign(reason="Pasted the line instead of writing it", weight=0.45))
    if signals.away_ms >= 15_000:
        signs.append(Sign(reason=f"Left the game for {signals.away_ms / 1000:.0f}s while writing", weight=0.3))
    return signs

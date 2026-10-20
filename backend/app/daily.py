"""The daily challenge: one tongue-twister a day, the same for everyone.

Say it in your own voice: the score is how much you sound like you, times how
much of the phrase the speech-to-text heard. Three tries a day, the best one
counts, and playing on consecutive days builds a streak.

Days are UTC days, so everyone in the world gets the new phrase at the same moment.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone

ATTEMPTS_PER_DAY = 3
MIN_PHRASE_MATCH = 0.5  # say at least half of the phrase or the try scores 0

PHRASES = (
    "She sells sea shells by the sea shore",
    "Red lorry, yellow lorry, red lorry, yellow lorry",
    "Peter Piper picked a peck of pickled peppers",
    "How much wood would a woodchuck chuck",
    "Fresh fried fish, fish fresh fried",
    "Unique New York, you know you need unique New York",
    "Six slippery snails slid slowly seaward",
    "Big black bugs bleed blue black blood",
    "A proper copper coffee pot",
    "Fuzzy Wuzzy was a bear, Fuzzy Wuzzy had no hair",
    "I scream, you scream, we all scream for ice cream",
    "Betty bought a bit of better butter",
    "Toy boat, toy boat, toy boat",
    "Eleven benevolent elephants",
    "Four furious friends fought for the phone",
    "Lesser leather never weathered wetter weather better",
    "Truly rural, truly rural",
    "Can you can a can as a canner can can a can",
    "The thirty three thieves thought that they thrilled the throne",
    "Black background, brown background",
    "Green glass globes glow greenly",
    "Willy's real rear wheel",
    "A big bug bit the little beetle",
    "Many mumbling mice are making midnight music",
    "Rolling red wagons rattle and roll",
    "Clean clams crammed in clean cans",
    "Nine nice night nurses nursing nicely",
    "Sheep should sleep in a shed",
    "Two tried and true tridents",
    "Kitty caught the kitten in the kitchen",
)


def today() -> date:
    return datetime.now(timezone.utc).date()


def phrase_for(day: date) -> str:
    return PHRASES[day.toordinal() % len(PHRASES)]


def seconds_left(day: date) -> int:
    """Until the next UTC midnight, when the new phrase arrives."""
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    return max(0, int((end - datetime.now(timezone.utc)).total_seconds()))


def score(voice_score: float, phrase_match: float) -> int:
    if phrase_match < MIN_PHRASE_MATCH:
        return 0
    return max(0, round(voice_score * 100 * phrase_match))


def streak(days: Iterable[date], on: date) -> int:
    """Consecutive days played, ending today (or yesterday: today isn't over yet)."""
    played = set(days)
    day = on if on in played else on - timedelta(days=1)
    count = 0
    while day in played:
        count += 1
        day -= timedelta(days=1)
    return count


def best_streak(days: Iterable[date]) -> int:
    played = sorted(set(days))
    best = run = 0
    for i, d in enumerate(played):
        run = run + 1 if i and d - played[i - 1] == timedelta(days=1) else 1
        best = max(best, run)
    return best

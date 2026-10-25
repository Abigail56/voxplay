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
    # Naija flavour
    "Tunde tried to teach ten tortoises to tango",
    "Danfo drivers dodge dozens of daring donkeys",
    "Bola bought bigger bags of beans for Bisi",
    "Pepper soup simmers slowly on a sleepy Sunday",
    "Kemi keeps cooking crunchy cassava cakes",
    "Funke found five fresh fish at the farm",
    "Mama made moi moi for many merry neighbours",
    "Lagos lights look lovely late at night",
    "Ngozi knits neat nets near the narrow river",
    "Sade sells sweet suya on the side street",
    "A plate of plantain pleases plenty of people",
    "Chika chose cheap cheese and chips for church",
    "Bright blue buses bounce along bumpy roads",
    "Jolly Joy juggles jollof in a giant jar",
    "Okada riders rarely ride right round the roundabout",
    # More classics
    "Fred fed Ted bread and Ted fed Fred bread",
    "I saw Susie sitting in a shoeshine shop",
    "Rubber baby buggy bumpers",
    "Which witch is which",
    "A skunk sat on a stump and thunk the stump stunk",
    "Crisp crusts crackle crunchily",
    "Three free throws for three fresh friends",
    "Six sick slick slim sycamore saplings",
    "Greek grapes, Greek grapes, Greek grapes",
    "An Irish wristwatch and a Swiss wristwatch",
    "Seventy seven benevolent elephants",
    "Gobbling gargoyles gobbled gobbling goblins",
    "Fuzzy feathers flutter freely in the fall",
    "Slick silk socks sit silently in the sock shop",
    "Quick kiss, quick kiss, quick kiss",
)


def today() -> date:
    return datetime.now(timezone.utc).date()


# Shifts the rotation so that adding phrases (30 -> 60 on 25 October 2026) didn't change that day's phrase
# for people already playing it.
ROTATION_OFFSET = 30


def phrase_for(day: date) -> str:
    return PHRASES[(day.toordinal() - ROTATION_OFFSET) % len(PHRASES)]


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

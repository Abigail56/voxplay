import os

import pytest

from app.liveness import DIGITS, ChallengeStore, make_phrase, normalise, phrase_match
from app.store import MemoryStore, RedisStore


def test_phrase_is_six_random_digits():
    words = make_phrase().split()
    assert len(words) == 6 and all(w in DIGITS for w in words)
    assert len({make_phrase() for _ in range(50)}) > 45  # random


def test_normalise_spells_digits_and_drops_punctuation():
    # The ways Whisper writes the same answer.
    for heard in ["Four, seven, two, nine, one, six.", "472916", "4-7-2-9-1-6", "4 7 2, 9 1 6"]:
        assert normalise(heard) == ["four", "seven", "two", "nine", "one", "six"]
    assert normalise("for to won") == ["four", "two", "one"]


@pytest.mark.parametrize(
    ("heard", "expected"),
    [
        ("four seven two nine one six", 1.0),
        ("4, 7, 2, 9, 1, 6.", 1.0),
        ("um, four seven two nine one six, okay", 1.0),  # extra words are fine
        ("for seven too nine one six", 1.0),
        ("four seven two pine one six", 5 / 6),  # one digit misheard: still passes at 0.8
        ("six one nine two seven four", 1 / 6),  # wrong order: a shuffled guess doesn't pass
        ("hello this is Ada, call me back", 0.0),  # an old recording of something else
        ("", 0.0),
    ],
)
def test_phrase_match(heard, expected):
    assert phrase_match("four seven two nine one six", heard) == pytest.approx(expected)


async def test_challenges_work_once():
    challenges = ChallengeStore(MemoryStore(), ttl_seconds=60)
    c = await challenges.issue()
    assert await challenges.take(c.id) == c.phrase
    assert await challenges.take(c.id) is None  # replaying the same answer fails
    assert await challenges.take("made-up") is None


async def test_challenges_expire():
    challenges = ChallengeStore(MemoryStore(), ttl_seconds=0)
    c = await challenges.issue()
    assert await challenges.take(c.id) is None


@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="TEST_REDIS_URL not set")
async def test_redis_store():
    store = RedisStore(os.environ["TEST_REDIS_URL"])
    try:
        challenges = ChallengeStore(store, ttl_seconds=60)
        c = await challenges.issue()
        assert await challenges.take(c.id) == c.phrase
        assert await challenges.take(c.id) is None

        key = f"rate:test:{c.id}"
        assert [await store.incr(key, 60) for _ in range(3)] == [1, 2, 3]
        assert 0 < await store._redis.ttl(key) <= 60
    finally:
        await store.close()

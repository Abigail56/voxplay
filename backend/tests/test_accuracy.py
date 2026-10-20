"""Recognition accuracy: recording quality checks, learning from play, threshold tuning."""

import numpy as np
import pytest
from sqlalchemy import text

from app import accuracy
from app.adaptation import inconsistent_takes
from app.audio import SAMPLE_RATE, clip_quality

from .helpers import FakeEmbedder, tone_wav
from .test_game import ADA, BAYO, client, needs_db, signup, takes, turn, with_voice  # noqa: F401


def tone(seconds=4.0, amp=0.5, silence=0.5, freq=220.0):
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    pad = np.zeros(int(silence * SAMPLE_RATE))
    return np.concatenate([pad, amp * np.sin(2 * np.pi * freq * t), pad]).astype(np.float32)


# ---------- recording quality ----------


def test_a_good_take_passes():
    q = clip_quality(tone())
    assert q.ok and q.speech_seconds > 3.5 and q.snr_db > 30


@pytest.mark.parametrize(
    ("audio", "problem"),
    [
        (tone(seconds=1.5), "Too short"),
        (tone(amp=0.004), "Too quiet"),
        (np.clip(tone(amp=3.0), -1, 1), "Too loud"),
        (tone() + np.random.default_rng(0).normal(scale=0.15, size=tone().size).astype(np.float32), "Too noisy"),
        (np.zeros(SAMPLE_RATE * 3, dtype=np.float32), "couldn't hear any speech"),
    ],
)
def test_bad_takes_get_advice(audio, problem):
    q = clip_quality(audio)
    assert not q.ok and any(problem in p for p in q.problems)


def test_a_take_that_sounds_like_someone_else_is_caught():
    emb = FakeEmbedder()
    same = [emb.embed(tone(freq=f)) for f in (200, 202, 204)]
    assert inconsistent_takes(same, 0.4) == []
    mixed = same[:2] + [emb.embed(tone(freq=900))]
    assert inconsistent_takes(mixed, 0.4) == [2]


# ---------- threshold tuning maths ----------


def test_rates_and_recommendation():
    rng = np.random.default_rng(1)
    genuine = rng.normal(0.7, 0.08, 200)
    impostor = rng.normal(0.15, 0.1, 200)
    pairs = list(zip(genuine, impostor))
    r = accuracy.report(pairs, current=0.40)
    assert r.enough_data and r.current.far < 0.02 and r.current.frr < 0.01 and r.current.recognition > 0.98
    assert r.current.wrong == 0.0
    # The recommendation keeps false accepts at or under 1%, at the lowest such threshold.
    assert r.recommended.far <= accuracy.TARGET_FAR
    assert accuracy.rates(pairs, r.recommended.threshold - 0.01).far > accuracy.TARGET_FAR
    assert sum(g for _, g, _ in r.histogram) == 200 and sum(i for _, _, i in r.histogram) == 200


def test_wrong_player_vs_stranger_test():
    # The closest other player scores high, but the real speaker scores higher: right person named.
    close = accuracy.rates([(0.8, 0.5)], 0.4)
    assert close.recognition == 1.0 and close.wrong == 0.0 and close.far == 1.0  # a stranger like this would be misnamed
    mixed = accuracy.rates([(0.45, 0.6)], 0.4)
    assert mixed.wrong == 1.0 and mixed.recognition == 0.0


def test_no_recommendation_without_enough_data():
    r = accuracy.report([(0.7, 0.1)] * 5, current=0.4)
    assert not r.enough_data and r.recommended is None and r.current.recognition == 1.0


# ---------- the API ----------


@needs_db
async def test_check_a_take(client):
    h = await signup(client, "ada")
    good = await client.post("/me/voice/check", headers=h, files={"file": ("t.wav", tone_wav(ADA, seconds=4, silence=0.5), "audio/wav")})
    assert good.json()["ok"] is True and good.json()["problems"] == []
    short = await client.post("/me/voice/check", headers=h, files={"file": ("t.wav", tone_wav(ADA, seconds=1.5, silence=0.5), "audio/wav")})
    assert short.json()["ok"] is False and "Too short" in short.json()["problems"][0]
    tiny = await client.post("/me/voice/check", headers=h, files={"file": ("t.wav", tone_wav(ADA, seconds=0.5, silence=0.5), "audio/wav")})
    assert tiny.status_code == 200 and "Too short" in tiny.json()["problems"][0]  # advice, not an error


@needs_db
async def test_enrollment_rejects_bad_and_odd_takes(client):
    h = await signup(client, "ada")
    files = takes(ADA)[:2] + [("files", ("short.wav", tone_wav(ADA, seconds=1.5, silence=0.5), "audio/wav"))]
    r = await client.post("/me/voice", headers=h, data={"consent": "true"}, files=files)
    assert r.status_code == 422 and r.json()["detail"].startswith("Take 3: Too short")

    files = takes(ADA)[:2] + takes(BAYO)[:1]  # someone else read take 3
    r = await client.post("/me/voice", headers=h, data={"consent": "true"}, files=files)
    assert r.status_code == 422 and "Take 3 doesn't sound like the others" in r.json()["detail"]


@needs_db
async def test_voice_learns_from_confident_turns_only(client):
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = (await client.post("/rooms", headers=ada, json={"rounds": 2})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    await client.post(f"/rooms/{code}/start", headers=ada)

    await turn(client, ada, code, ADA)  # clearly ada: learned
    await turn(client, bayo, code, ADA)  # bayo plays ada's voice: not recognised as bayo, not learned
    await turn(client, ada, code, ADA, say_phrase=False)  # failed live check: not learned
    assert (await client.get("/me", headers=ada)).json()["learned_samples"] == 1
    assert (await client.get("/me", headers=bayo)).json()["learned_samples"] == 0

    async with client.app.state.sessionmaker() as s:
        rows = (await s.exec(text("SELECT genuine, impostor, source FROM score_samples ORDER BY id"))).all()
    assert len(rows) == 2  # the two turns that passed the live check
    assert rows[0][0] > 0.9 and rows[0][1] < 0.1 and rows[0][2] == "game"  # ada vs ada / vs bayo
    assert rows[1][0] < 0.1  # bayo's turn sounded nothing like bayo


@needs_db
async def test_learned_clips_are_capped(client):
    client.app.state.settings.max_learned_samples = 2
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = (await client.post("/rooms", headers=ada, json={"rounds": 4})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    await client.post(f"/rooms/{code}/start", headers=ada)
    for _ in range(4):
        await turn(client, ada, code, ADA)
        await turn(client, bayo, code, BAYO)
    me = (await client.get("/me", headers=ada)).json()
    assert me["learned_samples"] == 2 and me["voice_samples"] == 5  # 3 enrolled + the 2 newest learned


@needs_db
async def test_admin_tunes_the_threshold(client):
    boss = await with_voice(client, "boss", 3000)
    ada = await with_voice(client, "ada", ADA)
    assert (await client.get("/admin/accuracy", headers=ada)).status_code == 403

    async with client.app.state.sessionmaker() as s:  # pretend lots of real turns happened
        rng = np.random.default_rng(2)
        for g, i in zip(rng.normal(0.62, 0.1, 60), rng.normal(0.18, 0.1, 60)):
            await s.exec(text(f"INSERT INTO score_samples (genuine, impostor, source) VALUES ({g:.4f}, {i:.4f}, 'game')"))
        await s.commit()

    acc = (await client.get("/admin/accuracy", headers=boss)).json()
    assert acc["enough_data"] and acc["genuine_count"] == 60 and acc["recommended"]["far"] <= 0.01
    assert acc["current"]["threshold"] == 0.5  # the test app's threshold

    new = acc["recommended"]["threshold"]
    try:
        acc = (await client.post("/admin/accuracy/threshold", headers=boss, json={"threshold": new})).json()
        assert acc["current"]["threshold"] == new
        assert client.app.state.settings.match_threshold == new  # used from the next turn on
        async with client.app.state.sessionmaker() as s:
            assert (await s.exec(text("SELECT value FROM app_settings WHERE key = 'match_threshold'"))).one()[0] == f"{new:.2f}"
        assert (await client.post("/admin/accuracy/threshold", headers=boss, json={"threshold": 0.05})).status_code == 422
    finally:
        # The saved threshold is loaded when an app starts: don't let it leak into other tests.
        async with client.app.state.sessionmaker() as s:
            await s.exec(text("DELETE FROM app_settings"))
            await s.commit()

"""API tests against a real PostgreSQL + pgvector database, with a fake embedder.

Run inside Docker:  docker compose run --rm api pytest
They are skipped when TEST_DATABASE_URL is not set.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import Settings
from app.main import create_app

from .helpers import FakeEmbedder, FakeGeocoder, FakeTranscriber, tone_wav

TEST_DB = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")


async def make_client(**overrides):
    settings = Settings(
        database_url=TEST_DB, match_threshold=0.5, **{"require_liveness": False, "redis_url": "", "seed_sample_voices": False, **overrides}
    )
    app = create_app(settings, embedder=FakeEmbedder(), transcriber=FakeTranscriber(), geocoder=FakeGeocoder())
    async with app.router.lifespan_context(app):
        async with app.state.sessionmaker() as s:
            await s.exec(text("TRUNCATE speakers, voice_samples, game_plays, users RESTART IDENTITY CASCADE"))
            await s.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            c.transcriber = app.state.transcriber
            c.app = app
            yield c


@pytest.fixture
async def client():
    async for c in make_client():
        yield c


@pytest.fixture
async def live_client():
    """Liveness on, as in production."""
    async for c in make_client(require_liveness=True):
        yield c


def wav(name, freq, **kw):
    return ("files", (name, tone_wav(freq, **kw), "audio/wav"))


async def enroll(client, name, *freqs, consent="true"):
    files = [wav(f"{name}{i}.wav", f) for i, f in enumerate(freqs)]
    return await client.post("/speakers", data={"name": name, "consent": consent}, files=files)


async def test_enroll_list_identify_delete(client):
    r = await enroll(client, "Ada", 200, 205)
    assert r.status_code == 201, r.text
    ada = r.json()
    assert ada["name"] == "Ada" and ada["sample_count"] == 2

    assert (await enroll(client, "Bayo", 600)).status_code == 201

    speakers = (await client.get("/speakers")).json()
    assert {s["name"] for s in speakers} == {"Ada", "Bayo"}

    # A new clip at Ada's "pitch" (with silence around it) -> Ada.
    r = await client.post("/identify", files={"file": ("q.wav", tone_wav(200, silence=0.5), "audio/wav")})
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["label"] == "Ada" and body["is_match"] is True
    assert body["score"] > 0.9
    assert body["candidates"][0]["name"] == "Ada"

    # A voice nobody enrolled with -> unknown.
    r = await client.post("/identify", files={"file": ("q.wav", tone_wav(1500), "audio/wav")})
    assert r.json()["label"] == "unknown" and r.json()["is_match"] is False

    # Delete Ada: her voice is no longer recognised.
    assert (await client.delete(f"/speakers/{ada['id']}")).status_code == 204
    assert (await client.get(f"/speakers/{ada['id']}")).status_code == 404
    r = await client.post("/identify", files={"file": ("q.wav", tone_wav(200), "audio/wav")})
    assert r.json()["label"] == "unknown"


async def test_enroll_requires_consent(client):
    r = await enroll(client, "Ada", 200, consent="false")
    assert r.status_code == 400
    assert "Consent" in r.json()["detail"]


async def test_duplicate_name_is_rejected(client):
    await enroll(client, "Ada", 200)
    assert (await enroll(client, "ada", 300)).status_code == 409


async def test_bad_audio_is_rejected(client):
    r = await client.post(
        "/speakers", data={"name": "X", "consent": "true"}, files=[("files", ("x.wav", b"nope", "audio/wav"))]
    )
    assert r.status_code == 422


async def test_add_samples_updates_count(client):
    ada = (await enroll(client, "Ada", 200)).json()
    r = await client.post(f"/speakers/{ada['id']}/samples", files=[wav("more.wav", 210)])
    assert r.status_code == 200 and r.json()["sample_count"] == 2


async def test_identify_with_no_speakers(client):
    r = await client.post("/identify", files={"file": ("q.wav", tone_wav(200), "audio/wav")})
    assert r.json()["label"] == "unknown"
    assert r.json()["candidates"] == []


async def test_health(client):
    body = (await client.get("/health")).json()
    assert body["status"] == "ok" and body["model_loaded"] is True and body["threshold"] == 0.5


async def test_health_reports_liveness(live_client):
    assert (await live_client.get("/health")).json()["liveness_required"] is True


# ---------- liveness: "say this phrase" ----------


async def identify_live(client, phrase_said, challenge_id=None, freq=200):
    if challenge_id is None:
        challenge_id = (await client.get("/challenge")).json()["challenge_id"]
    client.transcriber.text = phrase_said
    return await client.post(
        "/identify",
        data={"challenge_id": challenge_id},
        files={"file": ("q.wav", tone_wav(freq), "audio/wav")},
    )


async def test_liveness_required_without_phrase(live_client):
    await enroll(live_client, "Ada", 200)
    r = await live_client.post("/identify", files={"file": ("q.wav", tone_wav(200), "audio/wav")})
    assert r.status_code == 422 and "/challenge" in r.json()["detail"]


async def test_saying_the_phrase_passes(live_client):
    await enroll(live_client, "Ada", 200)
    challenge = (await live_client.get("/challenge")).json()
    assert len(challenge["phrase"].split()) == 6 and challenge["expires_in_seconds"] > 0

    r = await identify_live(live_client, challenge["phrase"].capitalize() + ".", challenge["challenge_id"])
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["label"] == "Ada" and body["is_match"] is True
    assert body["liveness"]["passed"] is True and body["liveness"]["match"] == 1.0


async def test_replayed_recording_fails_and_reveals_nothing(live_client):
    await enroll(live_client, "Ada", 200)
    # Ada's voice, but saying something recorded earlier instead of the phrase.
    body = (await identify_live(live_client, "hi it's Ada, call me back")).json()
    assert body["label"] == "unknown" and body["is_match"] is False
    assert body["liveness"]["passed"] is False
    assert "Liveness check failed" in body["reason"]
    assert body["candidates"] == [] and body["score"] == 0.0  # no hints for an attacker


async def test_phrase_works_only_once(live_client):
    await enroll(live_client, "Ada", 200)
    challenge = (await live_client.get("/challenge")).json()
    assert (await identify_live(live_client, challenge["phrase"], challenge["challenge_id"])).status_code == 200
    again = await identify_live(live_client, challenge["phrase"], challenge["challenge_id"])
    assert again.status_code == 422 and "already used" in again.json()["detail"]


async def test_unknown_challenge_is_rejected(live_client):
    r = await identify_live(live_client, "anything", challenge_id="not-a-real-id")
    assert r.status_code == 422

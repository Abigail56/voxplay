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

from .helpers import FakeEmbedder, tone_wav

TEST_DB = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")


@pytest.fixture
async def client():
    app = create_app(Settings(database_url=TEST_DB, match_threshold=0.5), embedder=FakeEmbedder())
    async with app.router.lifespan_context(app):
        async with app.state.sessionmaker() as s:
            await s.execute(text("TRUNCATE speakers, voice_samples RESTART IDENTITY CASCADE"))
            await s.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
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

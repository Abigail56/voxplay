"""The online voice game: accounts, voices, rooms, server-side scoring, dashboard, live updates.

Real PostgreSQL, fake voice model and fake speech-to-text (see helpers.py).
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from starlette.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.rooms import RoomPlayer, plan_turns, score_impersonation, score_yourself

from app.geocode import short_name

from .helpers import FakeEmbedder, FakeGeocoder, FakeTranscriber, tone_wav

TEST_DB = os.getenv("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")

ADA, BAYO, CHI = 200, 600, 1500  # each player's "voice" (the fake model hears pitch)


def make_app():
    settings = Settings(
        database_url=TEST_DB, match_threshold=0.5, redis_url="", jwt_secret="test-secret", admin_usernames="boss"
    )
    return create_app(settings, embedder=FakeEmbedder(), transcriber=FakeTranscriber(), geocoder=FakeGeocoder())


@pytest.fixture
async def client():
    app = make_app()
    async with app.router.lifespan_context(app):
        async with app.state.sessionmaker() as s:
            await s.exec(text("TRUNCATE speakers, voice_samples, game_plays, users, score_samples, app_settings RESTART IDENTITY CASCADE"))
            await s.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            c.app = app
            yield c


HOME = {"country": "NG", "place": "Yaba, Lagos"}


async def signup(client, name, password="correct horse", **where):
    r = await client.post("/auth/signup", json={"username": name, "password": password, **(where or HOME)})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def takes(freq, n=3):
    """n good enrollment takes: 4 s of 'speech' with a little quiet around it, like a real recording."""
    return [("files", (f"take{i}.wav", tone_wav(freq, seconds=4.0, silence=0.5), "audio/wav")) for i in range(n)]


async def with_voice(client, name, freq, **where):
    h = await signup(client, name, **where)
    r = await client.post("/me/voice", headers=h, data={"consent": "true"}, files=takes(freq))
    assert r.status_code == 200, r.text
    return h


async def turn(client, h, code, freq, say_phrase=True):
    challenge = (await client.get("/challenge")).json()
    client.app.state.transcriber.text = challenge["phrase"] if say_phrase else "hello it's me"
    return await client.post(
        f"/rooms/{code}/turn",
        headers=h,
        data={"challenge_id": challenge["challenge_id"]},
        files={"file": ("t.wav", tone_wav(freq), "audio/wav")},
    )


# ---------- pure game logic ----------


def test_plan_gives_everyone_a_turn_each_round():
    players = [RoomPlayer(user_id=i, username=f"p{i}", speaker_id=i) for i in range(1, 5)]
    plan = plan_turns(players, "yourself", rounds=2)
    assert [t.player_id for t in plan] == [1, 2, 3, 4, 1, 2, 3, 4]
    assert all(t.player_id == t.target_id for t in plan)
    imp = plan_turns(players, "impersonate", rounds=3)
    assert all(t.player_id != t.target_id for t in imp)  # never impersonate yourself


def test_scoring():
    assert score_yourself("ada", 1, 1, "ada", 0.82) == (82, "That's ada! 82 points. Unmistakably you!")
    assert score_yourself("ada", 1, 2, "bayo", 0.9)[0] == 0  # recognised as someone else
    assert score_yourself("ada", 1, None, "unknown", 0.2)[0] == 0
    assert score_impersonation("bayo", "ada", 0.3, fooled=False) == (30, "bayo sounds 30% like ada. 30 points.")
    assert score_impersonation("bayo", "ada", 0.6, fooled=True)[0] == 110  # +50 bonus


# ---------- accounts ----------


@needs_db
async def test_signup_login_and_me(client):
    h = await signup(client, "  Ada ")  # tidied to "ada"
    me = (await client.get("/me", headers=h)).json()
    assert me["username"] == "ada" and me["has_voice"] is False and me["share_location"] is True

    assert (await client.post("/auth/signup", json={"username": "ada", "password": "another one", **HOME})).status_code == 409
    assert (await client.post("/auth/signup", json={"username": "x", "password": "long enough", **HOME})).status_code == 422
    assert (await client.post("/auth/signup", json={"username": "bob", "password": "short", **HOME})).status_code == 422
    nowhere = {"username": "bob", "password": "long enough", "country": "NG", "place": "Atlantis"}
    r = await client.post("/auth/signup", json=nowhere)
    assert r.status_code == 422 and "couldn't find" in r.json()["detail"]
    assert (await client.post("/auth/signup", json={"username": "bob", "password": "long enough"})).status_code == 422

    ok = await client.post("/auth/login", json={"username": "ADA", "password": "correct horse"})
    assert ok.status_code == 200 and ok.json()["user"]["username"] == "ada"
    bad = await client.post("/auth/login", json={"username": "ada", "password": "wrong"})
    nobody = await client.post("/auth/login", json={"username": "nobody", "password": "wrong"})
    assert bad.status_code == nobody.status_code == 401 and bad.json() == nobody.json()  # no hint which one

    assert (await client.get("/me")).status_code == 401
    assert (await client.get("/me", headers={"Authorization": "Bearer forged"})).status_code == 401


@needs_db
async def test_password_is_not_stored(client):
    await signup(client, "ada", "my secret pass")
    async with client.app.state.sessionmaker() as s:
        stored = (await s.exec(text("SELECT password_hash FROM users"))).one()[0]
    assert "my secret pass" not in stored and stored.startswith("scrypt$")


@needs_db
async def test_enroll_my_voice(client):
    h = await signup(client, "ada")
    no = await client.post("/me/voice", headers=h, data={"consent": "false"}, files=takes(ADA))
    assert no.status_code == 400
    assert (await client.post("/me/voice", headers=h, data={"consent": "true"}, files=takes(ADA, 2))).status_code == 422

    me = (await client.post("/me/voice", headers=h, data={"consent": "true"}, files=takes(ADA))).json()
    assert me["has_voice"] and me["voice_samples"] == 3 and me["learned_samples"] == 0
    # Re-recording replaces the old voice.
    me = (await client.post("/me/voice", headers=h, data={"consent": "true"}, files=takes(ADA + 3))).json()
    assert me["voice_samples"] == 3
    files = takes(ADA)

    # The voice lab lists it, but can't delete or change it.
    lab = {s["name"]: s for s in (await client.get("/speakers")).json()}
    assert (await client.delete(f"/speakers/{lab['ada']['id']}")).status_code == 403
    # And a lab speaker can't take a player's name.
    r = await client.post("/speakers", data={"name": "Ada", "consent": "true"}, files=files[:1])
    assert r.status_code == 409


def test_short_place_names():
    assert short_name({"suburb": "Yaba", "city": "Lagos", "state": "Lagos"}, "x") == "Yaba, Lagos"
    assert short_name({"town": "Ikeja", "state": "Lagos State"}, "x") == "Ikeja, Lagos State"
    assert short_name({"city": "Nairobi"}, "x") == "Nairobi"
    assert short_name({}, "typed text") == "typed text"


@needs_db
async def test_signup_puts_you_on_the_map(client):
    h = await signup(client, "ada")
    me = (await client.get("/me", headers=h)).json()
    assert (me["country"], me["place"], me["lat"], me["lon"]) == ("NG", "Yaba, Lagos", 6.50682, 3.37549)
    assert me["share_location"] is True and me["is_admin"] is False

    other = await with_voice(client, "bayo", BAYO, country="KE", place="Westlands, Nairobi")
    await client.post("/me/voice", headers=h, data={"consent": "true"}, files=takes(ADA))
    seen = {p["username"]: p for p in (await client.get("/dashboard", headers=other)).json()["players"]}
    assert (seen["ada"]["place"], seen["ada"]["lat"]) == ("Yaba, Lagos", 6.50682)
    assert seen["bayo"]["country"] == "KE"


@needs_db
async def test_move_and_hide_your_pin(client):
    h = await with_voice(client, "ada", ADA)
    me = (await client.put("/me/location", headers=h, json={"country": "NG", "place": "Ikeja"})).json()
    assert me["place"] == "Ikeja, Lagos"
    assert (await client.put("/me/location", headers=h, json={"country": "NG", "place": "Atlantis"})).status_code == 422

    me = (await client.put("/me/location", headers=h, json={"share": False})).json()
    assert me["share_location"] is False and me["place"] == "Ikeja, Lagos"  # you still see it
    other = await with_voice(client, "bayo", BAYO)
    seen = {p["username"]: p for p in (await client.get("/dashboard", headers=other)).json()["players"]}
    assert seen["ada"]["lat"] is None and seen["ada"]["place"] is None  # other players don't
    assert seen["ada"]["country"] == "NG"


@needs_db
async def test_place_lookups(client):
    r = await client.get("/places/search", params={"q": "Westlands, Nairobi", "country": "ke"})
    assert r.json() == {"name": "Westlands, Nairobi", "country": "KE", "lat": -1.268, "lon": 36.811}
    assert (await client.get("/places/search", params={"q": "Atlantis", "country": "NG"})).status_code == 422
    # "Use my current location": a GPS point becomes its area, not the point itself.
    here = (await client.get("/places/here", params={"lat": 6.5101, "lon": 3.3702})).json()
    assert here["name"] == "Yaba, Lagos" and (here["lat"], here["lon"]) == (6.50682, 3.37549)


@needs_db
async def test_map_service_down_is_not_unknown_place(client):
    client.app.state.geocoder.down = True
    r = await client.post("/auth/signup", json={"username": "ada", "password": "correct horse", **HOME})
    assert r.status_code == 503 and "try again" in r.json()["detail"]  # not "we couldn't find that place"
    assert (await client.get("/places/search", params={"q": "Yaba, Lagos", "country": "NG"})).status_code == 503


@needs_db
async def test_old_turn_locations_are_forgotten(client):
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = (await client.post("/rooms", headers=ada, json={"rounds": 1})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    await client.post(f"/rooms/{code}/start", headers=ada)
    await turn(client, ada, code, ADA)
    async with client.app.state.sessionmaker() as s:
        assert (await s.exec(text("SELECT lat FROM game_plays"))).one()[0] == 6.50682
        await s.exec(text("UPDATE game_plays SET created_at = now() - interval '31 days'"))
        await s.commit()
    await client.get("/dashboard", headers=ada)
    async with client.app.state.sessionmaker() as s:
        assert (await s.exec(text("SELECT lat FROM game_plays"))).one()[0] is None


# ---------- rooms ----------


@needs_db
async def test_full_game_be_yourself(client):
    ada = await with_voice(client, "ada", ADA)
    bayo = await with_voice(client, "bayo", BAYO)
    chi = await with_voice(client, "chi", CHI)
    await client.put("/me/location", headers=bayo, json={"share": False})
    await client.put("/me/location", headers=chi, json={"share": False})

    room = (await client.post("/rooms", headers=ada, json={"mode": "yourself", "rounds": 1})).json()
    code = room["code"]
    assert room["status"] == "lobby" and [p["username"] for p in room["players"]] == ["ada"]
    assert (await client.post(f"/rooms/{code}/start", headers=ada)).status_code == 409  # alone

    for h in (bayo, chi):
        assert (await client.post(f"/rooms/{code.lower()}/join", headers=h)).status_code == 200  # codes ignore case
    assert (await client.post(f"/rooms/{code}/start", headers=bayo)).status_code == 403  # only the host
    room = (await client.post(f"/rooms/{code}/start", headers=ada)).json()
    assert room["status"] == "playing" and room["current_turn"]["player_id"] == room["players"][0]["user_id"]

    late = await with_voice(client, "dan", 3000)
    assert (await client.post(f"/rooms/{code}/join", headers=late)).status_code == 409  # already started
    assert (await turn(client, bayo, code, BAYO)).status_code == 403  # not bayo's turn

    room = (await turn(client, ada, code, ADA)).json()  # ada is ada
    assert room["last_result"]["points"] > 90 and "That's ada" in room["last_result"]["message"]

    room = (await turn(client, bayo, code, BAYO, say_phrase=False)).json()  # cheats
    assert room["last_result"]["points"] == 0 and room["last_result"]["liveness"]["passed"] is False

    room = (await turn(client, chi, code, ADA)).json()  # chi plays ada's voice: recognised as ada
    assert room["last_result"]["points"] == 0 and "thinks that was ada" in room["last_result"]["message"]

    assert room["status"] == "finished" and room["winner_ids"] == [room["players"][0]["user_id"]]

    dash = (await client.get("/dashboard", headers=bayo)).json()
    totals = {p["username"]: (p["total_points"], p["turns"]) for p in dash["players"]}
    assert totals["ada"][0] > 90 and totals["bayo"] == (0, 1) and totals["dan"] == (0, 0)
    assert [p["username"] for p in dash["recent_plays"]] == ["chi", "bayo", "ada"]
    async with client.app.state.sessionmaker() as s:
        located = dict((await s.exec(text("SELECT u.username, g.lat FROM game_plays g JOIN users u ON u.id = g.user_id"))).all())
    assert located == {"ada": 6.50682, "bayo": None, "chi": None}  # bayo and chi hid their pins

    # Rematch with the same players: scores start again.
    room = (await client.post(f"/rooms/{code}/start", headers=ada)).json()
    assert room["status"] == "playing" and all(p["points"] == 0 for p in room["players"])


@needs_db
async def test_impersonation_bonus(client):
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = (await client.post("/rooms", headers=ada, json={"mode": "impersonate", "rounds": 1})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    await client.post(f"/rooms/{code}/start", headers=ada)

    room = (await turn(client, ada, code, ADA)).json()  # ada must sound like bayo, but sounds like ada
    assert room["last_result"]["target"] == "bayo" and room["last_result"]["points"] < 50
    room = (await turn(client, bayo, code, ADA)).json()  # a perfect impression of ada
    assert "fooled the machine" in room["last_result"]["message"] and room["last_result"]["points"] >= 100


@needs_db
async def test_rooms_need_a_voice_and_hosts_hand_over(client):
    nobody = await signup(client, "novoice")
    assert (await client.post("/rooms", headers=nobody, json={})).status_code == 409

    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = (await client.post("/rooms", headers=ada, json={})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    assert (await client.patch(f"/rooms/{code}", headers=bayo, json={"mode": "impersonate"})).status_code == 403

    room = (await client.post(f"/rooms/{code}/leave", headers=ada)).json()
    assert room["host_id"] == room["players"][0]["user_id"] and room["players"][0]["username"] == "bayo"
    assert (await client.post(f"/rooms/{code}/leave", headers=bayo)).json() is None  # last one out
    assert (await client.get(f"/rooms/{code}", headers=bayo)).status_code == 404

    # Creating a new game leaves the old one.
    first = (await client.post("/rooms", headers=ada, json={})).json()["code"]
    second = (await client.post("/rooms", headers=ada, json={})).json()["code"]
    assert (await client.get(f"/rooms/{first}", headers=ada)).status_code == 404
    rooms = (await client.get("/dashboard", headers=ada)).json()["rooms"]
    assert [r["code"] for r in rooms] == [second]


@needs_db
async def test_leaving_mid_game_skips_your_turns(client):
    ada = await with_voice(client, "ada", ADA)
    bayo = await with_voice(client, "bayo", BAYO)
    chi = await with_voice(client, "chi", CHI)
    code = (await client.post("/rooms", headers=ada, json={"rounds": 1})).json()["code"]
    for h in (bayo, chi):
        await client.post(f"/rooms/{code}/join", headers=h)
    await client.post(f"/rooms/{code}/start", headers=ada)
    await turn(client, ada, code, ADA)
    room = (await client.post(f"/rooms/{code}/leave", headers=bayo)).json()  # bayo was next
    assert room["current_turn"]["player_id"] == next(p["user_id"] for p in room["players"] if p["username"] == "chi")


@needs_db
async def test_delete_my_account(client):
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = (await client.post("/rooms", headers=ada, json={})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)

    assert (await client.delete("/me", headers=bayo)).status_code == 204
    assert (await client.get("/me", headers=bayo)).status_code == 401
    assert [s["name"] for s in (await client.get("/speakers")).json()] == ["ada"]  # voice gone
    assert [p["username"] for p in (await client.get(f"/rooms/{code}", headers=ada)).json()["players"]] == ["ada"]


# ---------- live updates ----------


@needs_db
def test_websocket_tells_players_what_changed():
    app = make_app()
    name = f"ws{uuid.uuid4().hex[:8]}"
    with TestClient(app) as c:
        token = c.post("/auth/signup", json={"username": name, "password": "correct horse", **HOME}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        c.post("/me/voice", headers=h, data={"consent": "true"}, files=takes(ADA))

        with c.websocket_connect(f"/ws?token={token}") as ws:
            assert ws.receive_json() == {"type": "dashboard"}  # "someone came online" (us)
            assert c.get("/dashboard", headers=h).json()["online"] >= 1
            code = c.post("/rooms", headers=h, json={}).json()["code"]
            assert ws.receive_json() == {"type": "dashboard"}

        with c.websocket_connect(f"/ws?token={token}&room={code}") as ws:
            ws.receive_json()  # came online
            c.patch(f"/rooms/{code}", headers=h, json={"mode": "impersonate", "rounds": 3})
            got = {ws.receive_json()["type"], ws.receive_json()["type"]}
            assert got == {"room", "dashboard"}
            ws.send_json({"type": "ping"})

        with pytest.raises(Exception):
            with c.websocket_connect("/ws?token=forged") as ws:
                ws.receive_json()
        c.delete("/me", headers=h)


# ---------- admin ----------


@needs_db
async def test_admin_sees_everything(client):
    boss = await with_voice(client, "boss", 3000)
    ada = await with_voice(client, "ada", ADA)
    bayo = await with_voice(client, "bayo", BAYO, country="KE", place="Westlands, Nairobi")
    await client.put("/me/location", headers=bayo, json={"share": False})

    for path in ("/admin/overview", "/admin/players", "/admin/plays", "/admin/rooms"):
        assert (await client.get(path, headers=ada)).status_code == 403  # players can't
        assert (await client.get(path)).status_code == 401
    assert (await client.get("/me", headers=boss)).json()["is_admin"] is True

    code = (await client.post("/rooms", headers=ada, json={"rounds": 1})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    await client.post(f"/rooms/{code}/start", headers=ada)
    await turn(client, ada, code, ADA)
    await turn(client, bayo, code, BAYO, say_phrase=False)  # a cheat attempt

    o = (await client.get("/admin/overview", headers=boss)).json()
    assert (o["players"], o["with_voice"], o["countries"], o["turns_total"], o["cheat_attempts"]) == (3, 3, 2, 2, 1)
    assert o["games_total"] == 1 and o["games_live"] == 0  # the game finished

    players = {p["username"]: p for p in (await client.get("/admin/players", headers=boss)).json()}
    assert players["bayo"]["place"] == "Westlands, Nairobi"  # admins see the place name in the table
    assert players["bayo"]["lat"] is None and players["bayo"]["lon"] is None  # but a hidden pin stays off the map
    assert players["ada"]["lat"] is not None
    assert players["bayo"]["cheat_attempts"] == 1 and players["ada"]["total_points"] > 0
    cheats = (await client.get("/admin/plays", headers=boss, params={"cheats_only": True})).json()
    assert [(c["username"], c["live_passed"]) for c in cheats] == [("bayo", False)]
    assert [r["code"] for r in (await client.get("/admin/rooms", headers=boss)).json()] == [code]


@needs_db
async def test_admin_actions(client):
    boss = await with_voice(client, "boss", 3000)
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = (await client.post("/rooms", headers=ada, json={})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    await client.post(f"/rooms/{code}/start", headers=ada)

    assert (await client.post(f"/rooms/{code}/end", headers=ada)).status_code == 404  # not an admin route for players
    assert (await client.post(f"/admin/rooms/{code}/end", headers=ada)).status_code == 403
    ended = (await client.post(f"/admin/rooms/{code}/end", headers=boss)).json()
    assert ended["status"] == "finished"

    ids = {p["username"]: p["user_id"] for p in (await client.get("/admin/players", headers=boss)).json()}
    assert (await client.delete(f"/admin/players/{ids['boss']}", headers=boss)).status_code == 400
    assert (await client.delete(f"/admin/players/{ids['bayo']}", headers=boss)).status_code == 204
    assert (await client.get("/me", headers=bayo)).status_code == 401
    assert "bayo" not in [s["name"] for s in (await client.get("/speakers")).json()]


@needs_db
async def test_voice_twins(client):
    ada = await with_voice(client, "ada", ADA)
    await with_voice(client, "sis", ADA + 5)  # sounds almost like ada
    await with_voice(client, "bayo", BAYO)
    lab = await client.post("/speakers", data={"name": "Lab", "consent": "true"}, files=takes(CHI, 2))
    assert lab.status_code == 201, lab.text

    assert (await client.get("/voice-twins")).status_code == 401
    body = (await client.get("/voice-twins", headers=ada)).json()
    by_name = {s["name"]: s for s in body["speakers"]}
    assert set(by_name) == {"ada", "sis", "bayo"}  # players only, not voice-lab speakers
    assert body["me"] == by_name["ada"]["speaker_id"]
    assert by_name["ada"]["twin"]["name"] == "sis"
    assert all(-1 <= s["x"] <= 1 and -1 <= s["y"] <= 1 for s in body["speakers"])
    assert len(body["samples"]) == 9  # 3 takes each
    assert "embedding" not in by_name["ada"]  # positions only, never the voiceprint


@needs_db
async def test_voice_twins_before_you_record(client):
    h = await signup(client, "newbie")
    assert (await client.get("/voice-twins", headers=h)).json() == {"me": None, "speakers": [], "samples": []}

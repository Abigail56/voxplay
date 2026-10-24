"""The fun features: daily challenge, badges, Guess Who, speed rounds, reactions, leaderboards."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from starlette.testclient import TestClient

from app import daily
from app.badges import Stats, badges
from app.rooms import Room, RoomPlayer, plan_turns, ranks, reveal, speed_bonus, start_game, timed_out

from .helpers import tone_wav
from .test_game import ADA, BAYO, CHI, HOME, client, make_app, needs_db, signup, takes, turn, with_voice  # noqa: F401

D = date(2026, 10, 20)


# ---------- pure logic ----------


def test_daily_phrase_is_the_same_all_day_and_changes_daily():
    assert daily.phrase_for(D) == daily.phrase_for(D)
    assert daily.phrase_for(D) != daily.phrase_for(D + timedelta(days=1))


def test_daily_score_needs_the_phrase():
    assert daily.score(0.8, 1.0) == 80
    assert daily.score(0.8, 0.5) == 40
    assert daily.score(0.9, 0.4) == 0  # didn't say the phrase


def test_streaks():
    days = [D - timedelta(days=i) for i in (0, 1, 2, 5, 6)]
    assert daily.streak(days, D) == 3
    assert daily.streak(days[1:], D) == 2  # not played today yet: yesterday's streak still counts
    assert daily.streak([D - timedelta(days=3)], D) == 0
    assert daily.best_streak(days) == 3


def test_badges_show_progress():
    got = {b.id: b for b in badges(Stats(turns=4, wins=3, best_yourself=93, countries_met=2))}
    assert got["first_words"].earned and got["winner"].earned and got["perfect"].earned
    assert not got["champion"].earned and (got["champion"].progress, got["champion"].goal) == (3, 10)
    assert not got["globetrotter"].earned and got["globetrotter"].progress == 2


def make_room(*names):
    stamp = datetime.now(timezone.utc)
    players = [RoomPlayer(user_id=i, username=n, speaker_id=i) for i, n in enumerate(names, 1)]
    return Room(code="TEST-1", host_id=1, players=players, created_at=stamp, updated_at=stamp)


def test_guess_who_plan_shuffles_but_everyone_speaks_once_a_round():
    players = [RoomPlayer(user_id=i, username=f"p{i}", speaker_id=i) for i in range(1, 6)]
    plan = plan_turns(players, "guess", rounds=3)
    for r in range(3):
        assert sorted(t.player_id for t in plan[r * 5 : r * 5 + 5]) == [1, 2, 3, 4, 5]


def test_reveal_scores_voters_and_speaker():
    room = make_room("ada", "bayo", "chi", "dan")
    room.mode = "guess"
    start_game(room)
    speaker = room.active_turn().player_id
    others = [p.user_id for p in room.players if p.user_id != speaker]
    room.phase = "vote"
    room.votes = {others[0]: speaker, others[1]: speaker, others[2]: others[0]}  # 2 right, 1 fooled
    points = reveal(room)
    assert points[others[0]] == points[others[1]] == 50 and others[2] not in points
    assert points[speaker] == 25
    assert room.turn_index == 1 and room.phase == "speak" and room.last_result.votes


def test_ranks_share_places_on_ties():
    room = make_room("ada", "bayo", "chi")
    for p, pts in zip(room.players, (50, 80, 50)):
        p.points = pts
    assert ranks(room) == {2: 1, 1: 2, 3: 2}


def test_speed_bonus_and_timeout():
    room = make_room("ada", "bayo")
    room.speed = True
    start_game(room)
    t0 = room.turn_started_at
    assert speed_bonus(room, 70, t0 + timedelta(seconds=6)) == 14
    assert speed_bonus(room, 0, t0 + timedelta(seconds=2)) == 0  # no bonus for a 0
    assert speed_bonus(room, 70, t0 + timedelta(seconds=40)) == 0
    assert not timed_out(room, t0 + timedelta(seconds=22))  # a grace period for the upload
    assert timed_out(room, t0 + timedelta(seconds=26))


# ---------- daily challenge ----------


async def daily_try(client, h, freq, say=True):
    client.app.state.transcriber.text = daily.phrase_for(daily.today()) if say else "hello"
    return await client.post("/daily", headers=h, files={"file": ("d.wav", tone_wav(freq), "audio/wav")})


@needs_db
async def test_daily_challenge(client):
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    state = (await client.get("/daily", headers=ada)).json()
    assert state["phrase"] == daily.phrase_for(daily.today()) and state["attempts_left"] == 3 and state["streak"] == 0

    r = (await daily_try(client, ada, ADA)).json()
    assert r["last_attempt"]["score"] > 90 and r["attempts_left"] == 2 and r["streak"] == 1
    r = (await daily_try(client, ada, ADA, say=False)).json()
    assert r["last_attempt"]["score"] == 0 and "Say the whole thing" in r["last_attempt"]["message"]
    r = (await daily_try(client, ada, BAYO)).json()  # not her voice: low score
    assert r["last_attempt"]["score"] < 50 and r["best"] > 90  # the best try counts
    assert (await daily_try(client, ada, ADA)).status_code == 409  # 3 tries a day

    await daily_try(client, bayo, BAYO)
    board = (await client.get("/daily", headers=bayo)).json()["leaderboard"]
    assert [e["username"] for e in board] == ["ada", "bayo"] or [e["username"] for e in board] == ["bayo", "ada"]
    assert all(e["score"] > 90 for e in board)

    # Played yesterday too: a 2-day streak.
    async with client.app.state.sessionmaker() as s:
        await s.exec(text("INSERT INTO daily_attempts (user_id, day, score, voice_score, phrase_match) "
                          "SELECT id, current_date - 1, 50, 0.5, 1 FROM users WHERE username = 'ada'"))
        await s.commit()
    assert (await client.get("/daily", headers=ada)).json()["streak"] == 2


# ---------- Guess Who ----------


@needs_db
async def test_guess_who(client):
    hs = {"ada": await with_voice(client, "ada", ADA), "bayo": await with_voice(client, "bayo", BAYO), "chi": await with_voice(client, "chi", CHI)}
    voice = {"ada": ADA, "bayo": BAYO, "chi": CHI}
    code = (await client.post("/rooms", headers=hs["ada"], json={"mode": "guess", "rounds": 1})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=hs["bayo"])
    assert (await client.post(f"/rooms/{code}/start", headers=hs["ada"])).status_code == 409  # needs 3
    await client.post(f"/rooms/{code}/join", headers=hs["chi"])
    await client.post(f"/rooms/{code}/start", headers=hs["ada"])

    expected = {n: 0 for n in hs}
    for _ in range(3):
        views = {n: (await client.get(f"/rooms/{code}", headers=h)).json() for n, h in hs.items()}
        speakers = [n for n, v in views.items() if v["you_speak"]]
        assert len(speakers) == 1  # exactly one player knows they're the speaker...
        speaker = speakers[0]
        for n, v in views.items():
            assert "plan" not in v and "clip_key" not in v
            if n != speaker:
                assert v["current_turn"] is None  # ...and nobody else can tell who

        ids = {p["username"]: p["user_id"] for p in views[speaker]["players"]}
        others = [n for n in hs if n != speaker]
        assert (await client.post(f"/rooms/{code}/vote", headers=hs[others[0]], json={"suspect_id": ids[speaker]})).status_code == 409  # nothing recorded yet
        room = (await turn(client, hs[speaker], code, voice[speaker])).json()
        assert room["phase"] == "vote" and room["has_clip"]

        clip = await client.get(f"/rooms/{code}/clip", headers=hs[others[0]])
        assert clip.status_code == 200 and clip.content.startswith(b"RIFF")  # the recording, to listen to
        assert (await client.post(f"/rooms/{code}/vote", headers=hs[speaker], json={"suspect_id": ids[others[0]]})).status_code == 409

        # One guesses right, the other names the wrong person.
        await client.post(f"/rooms/{code}/vote", headers=hs[others[0]], json={"suspect_id": ids[speaker]})
        room = (await client.post(f"/rooms/{code}/vote", headers=hs[others[1]], json={"suspect_id": ids[others[0]]})).json()
        result = room["last_result"]
        assert result["player"] == speaker and result["ai_guess"] == speaker  # the AI recognised them
        assert result["points_by_player"] == {others[0]: 50, speaker: 25}
        expected[others[0]] += 50
        expected[speaker] += 25
        assert (await client.get(f"/rooms/{code}/clip", headers=hs[others[0]])).status_code == 404  # deleted at the reveal

    assert room["status"] == "finished"
    assert {p["username"]: p["points"] for p in room["players"]} == expected


# ---------- speed rounds ----------


@needs_db
async def test_speed_round(client):
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = (await client.post("/rooms", headers=ada, json={"rounds": 1, "speed": True})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    room = (await client.post(f"/rooms/{code}/start", headers=ada)).json()
    assert room["speed"] and room["deadline"]

    room = (await turn(client, ada, code, ADA)).json()  # answered straight away
    assert room["last_result"]["speed_bonus"] >= 15 and "for speed" in room["last_result"]["message"]

    assert (await client.post(f"/rooms/{code}/advance", headers=ada)).status_code == 409  # bayo still has time
    rooms = client.app.state.rooms
    r = await rooms.get(code)
    r.turn_started_at -= timedelta(seconds=60)  # bayo dawdles
    await rooms.save(r)
    room = (await client.post(f"/rooms/{code}/advance", headers=ada)).json()
    assert "ran out of time" in room["last_result"]["message"] and room["status"] == "finished"


# ---------- results, badges, leaderboards ----------


@needs_db
async def test_wins_badges_and_leaderboards(client):
    ada = await with_voice(client, "ada", ADA)
    bayo = await with_voice(client, "bayo", BAYO, country="KE", place="Westlands, Nairobi")
    code = (await client.post("/rooms", headers=ada, json={"rounds": 1, "speed": True})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    await client.post(f"/rooms/{code}/start", headers=ada)
    await turn(client, ada, code, ADA)
    await turn(client, bayo, code, BAYO, say_phrase=False)

    me = (await client.get("/me", headers=ada)).json()
    got = {b["id"]: b for b in me["badges"]}
    assert me["wins"] == 1
    assert got["first_words"]["earned"] and got["winner"]["earned"] and got["speed"]["earned"] and got["perfect"]["earned"]
    assert got["globetrotter"]["progress"] == 2 and not got["globetrotter"]["earned"]  # NG + KE so far
    assert not (await client.get("/me", headers=bayo)).json()["wins"]

    await daily_try(client, bayo, BAYO)
    boards = (await client.get("/leaderboards", headers=ada)).json()
    assert [c["country"] for c in boards["countries"]][:2] in (["NG", "KE"], ["KE", "NG"])
    top = {e["username"]: e for e in boards["weekly_top"]}
    assert top["ada"]["wins"] == 1 and top["ada"]["points"] > 100  # turn + speed bonus
    assert top["bayo"]["points"] > 90  # his daily score counts this week
    assert boards["last_week_champion"] is None and boards["week_ends_in_seconds"] > 0


# ---------- reactions ----------


@needs_db
def test_reactions_float_to_everyone():
    import uuid

    app = make_app()
    with TestClient(app) as c:
        heads = []
        for _ in range(2):
            name = f"r{uuid.uuid4().hex[:8]}"
            token = c.post("/auth/signup", json={"username": name, "password": "correct horse", **HOME}).json()["token"]
            h = {"Authorization": f"Bearer {token}"}
            c.post("/me/voice", headers=h, data={"consent": "true"}, files=takes(ADA))
            heads.append((token, h))
        code = c.post("/rooms", headers=heads[0][1], json={}).json()["code"]
        c.post(f"/rooms/{code}/join", headers=heads[1][1])
        with c.websocket_connect(f"/ws?token={heads[1][0]}&room={code}") as ws:
            ws.receive_json()  # came online
            assert c.post(f"/rooms/{code}/react", headers=heads[0][1], json={"emoji": "🔥"}).status_code == 204
            got = ws.receive_json()
            while got["type"] != "reaction":
                got = ws.receive_json()
            assert got["reaction"] == "🔥"
        assert c.post(f"/rooms/{code}/react", headers=heads[0][1], json={"emoji": "💩"}).status_code == 422
        for _, h in heads:
            c.delete("/me", headers=h)

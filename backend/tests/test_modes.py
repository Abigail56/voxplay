"""The newer ways to play: silly lines, disguise, broken telephone, humans vs AI, twists,
the double final round, the replay and its highlights, and solo play against the built-in voices."""

import random
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.demo import sample_folder, seed_sample_voices
from app.liveness import LINE_GLUE, LINE_PATTERNS, is_line, line_match, make_line, phrase_match, same_word
from app.rooms import (
    TWISTS,
    Room,
    RoomPlayer,
    TurnResult,
    apply_turn,
    highlights,
    plan_turns,
    relink_chain,
    score_disguise,
    start_game,
)

from .helpers import tone_wav
from .test_game import ADA, BAYO, CHI, client, needs_db, signup, turn, with_voice  # noqa: F401

SOLO = 3000  # far above any reader's pitch, so the fake voice model never mixes them up

# ---------- pure logic ----------


def test_lines_are_silly_random_and_checked_like_digits():
    lines = [make_line() for _ in range(400)]
    assert len(set(lines)) == 400 and all(line == line.lower() and "{" not in line for line in lines)
    starts = {" ".join(line.split()[:2]) for line in lines}
    assert len(starts) >= 7  # many shapes, not one sentence with the words swapped
    # Every line has at least 5 random words, so one misheard word never fails it.
    assert all(sum(w not in LINE_GLUE for w in line.split()) >= 5 for line in lines)
    duo = [line for line in lines if " and the " in line]
    assert duo and all(line.split()[1] != line.split()[4] for line in duo)  # two different characters
    assert len(LINE_PATTERNS) >= 8
    line = "the sleepy penguin stole my shiny pizzas"
    assert is_line(line) and not is_line("four seven two nine one six")
    assert phrase_match(line, "The sleepy penguin stole my shiny pizzas!") == 1.0
    assert phrase_match(line, "the sleepy pelican stole my shiny pizzas") == pytest.approx(6 / 7)  # still passes at 0.7
    assert phrase_match(line, "The sleeping penguin stole my shiny pizza.") == 1.0  # how Whisper usually slips
    assert phrase_match(line, "hello it's me") == 0.0


def test_lines_are_scored_on_their_random_words_only():
    line = "at the market the hungry pirate tickled my sandals"
    assert line_match(line, "At the market, the hungry pirate tickled my sandals.") == 1.0
    assert line_match(line, "market hungry pirate tickled sandals") == 1.0  # only the random words count
    # An old recording of another line in the same pattern gets nothing for "at the … the … my".
    other = "at the airport the sleepy wizard painted my rabbits"
    assert phrase_match(line, other) >= 0.4 and line_match(line, other) == 0.0
    assert line_match(line, "at the market the hungry pirate stole my wallets") == pytest.approx(3 / 5)  # fails at 0.7


def test_near_misses_count_for_long_words_only():
    assert same_word("umbrellas", "umbrella") and same_word("sleepy", "sleeping") and same_word("rusty", "rusted")
    assert not same_word("nine", "pine")  # digits stay exact
    assert not same_word("goat", "got") and not same_word("pizzas", "pianos")


def players(n):
    return [RoomPlayer(user_id=i, username=f"p{i}", speaker_id=i) for i in range(1, n + 1)]


def test_telephone_chains_pass_the_voice_along():
    plan = plan_turns(players(3), "telephone", rounds=2)
    assert [(t.player_id, t.target_id, t.chain_start) for t in plan] == [
        (1, 1, True), (2, 1, False), (3, 2, False),  # round 1: p1 starts, p2 copies p1, p3 copies p2
        (2, 2, True), (3, 2, False), (1, 3, False),  # round 2 starts with the next player
    ]


def test_leaving_mid_chain_keeps_the_chain_together():
    plan = plan_turns(players(4), "telephone", rounds=1)  # 1 -> 2 -> 3 -> 4
    todo = relink_chain(plan, 2)
    assert [(t.player_id, t.target_id) for t in todo] == [(1, 1), (3, 1), (4, 3)]  # p3 copies p1 instead
    todo = relink_chain(plan_turns(players(4), "telephone", rounds=1), 1)
    assert todo[0].player_id == 2 and todo[0].chain_start  # the starter left: the next one starts


def test_twists_and_the_double_final_round():
    plan = plan_turns(players(2), "yourself", rounds=3, rng=random.Random(1), twists=True, double_final=True)
    assert all(t.twist in TWISTS for t in plan)
    assert [t.double for t in plan] == [False, False, False, False, True, True]
    assert not any(t.double for t in plan_turns(players(2), "yourself", rounds=1, double_final=True))  # 1 round: nothing to double


def make_room(mode="yourself", **options):
    stamp = datetime.now(timezone.utc)
    return Room(code="TEST-1", host_id=1, mode=mode, players=players(2), created_at=stamp, updated_at=stamp, **options)


def test_twist_and_double_multiply_the_turn():
    room = make_room(twists=True, double_final=True, rounds=2)
    start_game(room)
    for t in room.plan:
        t.twist = "🤫 Whisper it"
    apply_turn(room, 60, "That's p1!", None)
    assert room.last_result.points == 90 and "x1.5" in room.last_result.message
    apply_turn(room, 0, "No points.", None)
    apply_turn(room, 60, "That's p1!", None, bonus=10)  # final round: x1.5, then x2, then the speed bonus
    assert room.last_result.points == 190 and room.last_result.double


def test_disguise_scoring():
    assert score_disguise("ada", 0.15, None) == (85, "ada sounds 15% like ada. 85 points. Nobody would know!")
    assert score_disguise("ada", 0.3, "bayo")[0] == 95  # 70 + framing bayo
    assert score_disguise("ada", 0.9, None)[0] == 10


def result(n, player, score, **kw):
    return TurnResult(turn_number=n, player_id=1, player=player, target=kw.pop("target", player), points=0, message="", score=score, **kw)


def test_highlights():
    room = make_room("impersonate")
    room.history = [
        result(1, "p1", 0.9, target="p2", stars={"p2": 1}, has_clip=True),  # the machine loved it, the crowd didn't
        result(2, "p2", 0.08, target="p1", stars={"p1": 3}),
        result(3, "p1", None, target="p2", speed_bonus=12),  # timed out or failed: no voice award
    ]
    got = {h.title: h for h in highlights(room)}
    assert got["Best impression"].player == "p1" and got["Best impression"].has_clip
    assert got["Worst impression"].player == "p2"
    assert got["Crowd favourite"].player == "p2" and got["Crowd favourite"].detail == "3.0 stars"
    assert got["Humans vs machine"].player == "p1"
    assert got["Quickest draw"].turn_number == 3


# ---------- the API ----------


async def line_turn(client, h, code, freq, say=True):
    challenge = (await client.get("/challenge", params={"kind": "line"})).json()
    assert is_line(challenge["phrase"])
    client.app.state.transcriber.text = challenge["phrase"] if say else "something else entirely"
    return await client.post(
        f"/rooms/{code}/turn",
        headers=h,
        data={"challenge_id": challenge["challenge_id"]},
        files={"file": ("t.wav", tone_wav(freq), "audio/wav")},
    )


async def game(client, hosts, mode, **options):
    code = (await client.post("/rooms", headers=hosts[0], json={"mode": mode, "rounds": 1, **options})).json()["code"]
    for h in hosts[1:]:
        await client.post(f"/rooms/{code}/join", headers=h)
    r = await client.post(f"/rooms/{code}/start", headers=hosts[0])
    assert r.status_code == 200, r.text
    return code


@needs_db
async def test_disguise_game_with_lines(client):
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = await game(client, [ada, bayo], "disguise")
    room = (await line_turn(client, ada, code, BAYO)).json()  # ada puts on bayo's voice
    r = room["last_result"]
    assert r["points"] > 100 and "thinks that was bayo" in r["message"]  # framed bayo: +25
    assert list(r["sounded_like"]) == ["bayo", "ada"] and r["sounded_like"]["bayo"] > 90
    room = (await line_turn(client, bayo, code, BAYO, say=False)).json()
    assert room["last_result"]["points"] == 0 and "live check failed" in room["last_result"]["message"]
    assert room["status"] == "finished" and {h["title"] for h in room["highlights"]} == {"Best disguise"}


@needs_db
async def test_broken_telephone(client):
    hs = [await with_voice(client, n, f) for n, f in (("ada", ADA), ("bayo", BAYO), ("chi", CHI))]
    code = (await client.post("/rooms", headers=hs[0], json={"mode": "telephone", "rounds": 1})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=hs[1])
    assert (await client.post(f"/rooms/{code}/start", headers=hs[0])).status_code == 409  # needs 3
    await client.post(f"/rooms/{code}/join", headers=hs[2])
    await client.post(f"/rooms/{code}/start", headers=hs[0])

    assert (await client.get(f"/rooms/{code}/clip", headers=hs[1])).status_code == 404  # nothing to copy yet
    room = (await line_turn(client, hs[0], code, ADA)).json()
    assert room["last_result"]["points"] == 20 and room["has_clip"]
    clip = await client.get(f"/rooms/{code}/clip", headers=hs[1])  # bayo hears ada's voice...
    assert clip.status_code == 200 and clip.content.startswith(b"RIFF")
    room = (await line_turn(client, hs[1], code, ADA)).json()  # ...and copies it perfectly
    assert room["last_result"]["points"] >= 95 and room["last_result"]["drift"] >= 95
    room = (await line_turn(client, hs[2], code, CHI)).json()  # chi doesn't even try
    r = room["last_result"]
    assert r["points"] < 10 and r["chain_from"] == "ada" and "who started it" in r["message"]
    assert room["status"] == "finished" and not room["has_clip"]
    titles = {h["title"]: h for h in room["highlights"]}
    assert titles["Perfect copy"]["player"] == "bayo" and titles["Lost in the line"]["player"] == "chi"

    # The replay: every turn's clip, for the players in the game.
    assert (await client.get(f"/rooms/{code}/replay/2", headers=hs[2])).status_code == 200
    assert (await client.get(f"/rooms/{code}/replay/9", headers=hs[2])).status_code == 404
    outsider = await signup(client, "dan")
    assert (await client.get(f"/rooms/{code}/replay/2", headers=outsider)).status_code == 403


@needs_db
async def test_without_the_replay_clips_go_straight_away(client):
    hs = [await with_voice(client, n, f) for n, f in (("ada", ADA), ("bayo", BAYO), ("chi", CHI))]
    code = await game(client, hs, "telephone", replay=False)
    await line_turn(client, hs[0], code, ADA)
    await line_turn(client, hs[1], code, ADA)
    store = client.app.state.rooms.store
    room = await client.app.state.rooms.get(code)
    assert await store.get(f"clip:{code}:1:1") is None  # ada's clip went once bayo had copied it
    assert await store.get(room.clip_key) is not None  # bayo's is still needed by chi
    room = (await line_turn(client, hs[2], code, CHI)).json()
    assert not any(r["has_clip"] for r in room["history"])
    assert all([await store.get(f"clip:{code}:1:{n}") is None for n in (1, 2, 3)])


@needs_db
async def test_humans_vs_ai(client):
    ada, bayo, chi = [await with_voice(client, n, f) for n, f in (("ada", ADA), ("bayo", BAYO), ("chi", CHI))]
    code = await game(client, [ada, bayo, chi], "impersonate", crowd=True)
    room = (await line_turn(client, ada, code, CHI)).json()  # a terrible impression of whoever ada got
    assert room["phase"] == "rate" and room["has_clip"] and room["last_result"] is None  # verdict hidden
    assert room["deadline_seconds"] == 25
    assert (await client.post(f"/rooms/{code}/rate", headers=ada, json={"stars": 5})).status_code == 409  # not your own
    assert (await client.post(f"/rooms/{code}/rate", headers=bayo, json={"stars": 9})).status_code == 422
    assert (await client.get(f"/rooms/{code}/clip", headers=bayo)).status_code == 200
    room = (await client.post(f"/rooms/{code}/rate", headers=bayo, json={"stars": 4})).json()
    assert room["phase"] == "rate" and room["my_vote"] == 4
    room = (await client.post(f"/rooms/{code}/rate", headers=chi, json={"stars": 5})).json()
    r = room["last_result"]
    assert room["phase"] == "speak" and r["stars"] == {"bayo": 4, "chi": 5} and r["crowd_points"] == 45
    assert r["points"] == r["ai_points"] + 45 and "4.5 stars" in r["message"]
    me = (await client.get("/me", headers=ada)).json()
    assert me["total_points"] == r["points"]


@needs_db
async def test_the_last_rater_leaving_reveals_at_once(client):
    ada, bayo, chi = [await with_voice(client, n, f) for n, f in (("ada", ADA), ("bayo", BAYO), ("chi", CHI))]
    code = await game(client, [ada, bayo, chi], "impersonate", crowd=True)
    state = await client.app.state.rooms.get(code)
    target = state.player(state.active_turn().target_id).username
    # The one ada impersonates rates; the other leaves (a target leaving drops the turn instead).
    rater, leaver = ("bayo", "chi") if target == "bayo" else ("chi", "bayo")
    hs = {"bayo": bayo, "chi": chi}
    await line_turn(client, ada, code, CHI)
    await client.post(f"/rooms/{code}/rate", headers=hs[rater], json={"stars": 4})
    await client.post(f"/rooms/{code}/leave", headers=hs[leaver])  # the only one left to rate walks out
    room = (await client.get(f"/rooms/{code}", headers=ada)).json()
    assert room["phase"] == "speak" and room["last_result"]["stars"] == {rater: 4}  # no waiting out the clock


@needs_db
async def test_twists_and_double_final_in_a_game(client):
    ada, bayo = await with_voice(client, "ada", ADA), await with_voice(client, "bayo", BAYO)
    code = (await client.post("/rooms", headers=ada, json={"rounds": 2, "twists": True, "double_final": True})).json()["code"]
    await client.post(f"/rooms/{code}/join", headers=bayo)
    room = (await client.post(f"/rooms/{code}/start", headers=ada)).json()
    assert room["current_turn"]["twist"] in TWISTS and room["twists"] and room["double_final"]
    for h, f in ((ada, ADA), (bayo, BAYO), (ada, ADA)):
        room = (await turn(client, h, code, f)).json()
    r = room["last_result"]
    assert r["double"] and r["points"] == round(round(r["score"] * 100) * 1.5) * 2  # x1.5 twist, x2 final round


# ---------- solo play ----------


@pytest.fixture
async def solo_client(client):
    app = client.app
    async with app.state.sessionmaker() as s:
        await s.exec(text("TRUNCATE game_plays RESTART IDENTITY CASCADE"))
        await s.commit()
    await seed_sample_voices(app.state.sessionmaker, app.state.embedder, sample_folder(app.state.settings))
    return client


@needs_db
async def test_solo_guess_the_voice(solo_client):
    client = solo_client
    ada = await with_voice(client, "ada", SOLO)
    info = (await client.get("/solo", headers=ada)).json()
    assert len(info["voices"]) >= 4 and info["voices"][0]["name"].startswith("Reader ")
    assert (await client.get(f"/solo/voices/{info['voices'][0]['speaker_id']}/intro", headers=ada)).status_code == 200

    rnd = (await client.post("/solo/guess", headers=ada)).json()
    assert len(rnd["options"]) == 4
    assert (await client.get(f"/solo/guess/{rnd['round_id']}/clip", headers=ada)).headers["content-type"] == "audio/webm"
    other = await with_voice(client, "bayo", BAYO)
    assert (await client.get(f"/solo/guess/{rnd['round_id']}/clip", headers=other)).status_code == 404  # not yours

    # Try every option across rounds until one is right (the answer is random).
    picked = await client.post(f"/solo/guess/{rnd['round_id']}", headers=ada, json={"speaker_id": rnd["options"][0]["speaker_id"]})
    got = picked.json()
    assert got["right"] == (got["answer"]["speaker_id"] == rnd["options"][0]["speaker_id"])
    assert got["points"] == (30 if got["right"] else 0) and got["ai_guess"]
    assert (await client.post(f"/solo/guess/{rnd['round_id']}", headers=ada, json={"speaker_id": 1})).status_code == 404  # once
    rnd = (await client.post("/solo/guess", headers=ada)).json()
    await client.post(f"/solo/guess/{rnd['round_id']}", headers=ada, json={"speaker_id": 0})  # a wrong pick still counts as a round
    info = (await client.get("/solo", headers=ada)).json()
    assert info["rounds"] == 2 and info["right"] == int(got["right"])


@needs_db
async def test_solo_impersonate_and_disguise(solo_client):
    client = solo_client
    ada = await with_voice(client, "ada", SOLO)
    reader = (await client.get("/solo", headers=ada)).json()["voices"][0]

    async def solo_turn(mode, **form):
        challenge = (await client.get("/challenge", params={"kind": "line"})).json()
        client.app.state.transcriber.text = challenge["phrase"]
        return await client.post(
            "/solo/turn",
            headers=ada,
            data={"mode": mode, "challenge_id": challenge["challenge_id"], **form},
            files={"file": ("t.wav", tone_wav(SOLO), "audio/wav")},
        )

    r = (await solo_turn("impersonate", speaker_id=reader["speaker_id"])).json()
    assert f"like {reader['name']}" in r["message"] and r["liveness"]["passed"] and "ada" in r["sounded_like"]
    assert (await solo_turn("impersonate", speaker_id=999)).status_code == 422
    r = (await solo_turn("disguise")).json()
    assert r["points"] <= 5  # ada's own voice: no disguise at all
    me = (await client.get("/me", headers=ada)).json()
    assert me["turns"] == 2
    boards = (await client.get("/leaderboards", headers=ada)).json()
    assert boards["weekly_top"] == []  # solo doesn't count for the weekly cup

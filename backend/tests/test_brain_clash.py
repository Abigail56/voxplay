"""Brain Clash: answer checking, every mode's rules, the clock, ties, and the rooms API."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from app import brain_clash as bc
from app.routers.brain_clash import QUESTIONS_FILE

from .helpers import tone_wav
from .test_game import HOME, client, make_app, needs_db, signup  # noqa: F401

T0 = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def sec(n: float) -> datetime:
    return T0 + timedelta(seconds=n)


def q(id="q1", answer="Kilimanjaro", *accepted, difficulty="medium", kind="question", items=(), target=None):
    return bc.Question(id=id, kind=kind, category="african_general", difficulty=difficulty, prompt="?", answer=answer,
                       accepted=list(accepted), items=[list(i) for i in items], target=target)


def room(mode="battle", players=(("ada", "A"), ("bayo", "B")), questions=None, **settings):
    r = bc.BrainClashRoom(code="NOVA-11", host_id=1, settings=bc.RoomSettings(mode=mode, **settings), created_at=T0, updated_at=T0,
                          players=[bc.Player(user_id=i, name=n, team=t) for i, (n, t) in enumerate(players, 1)])
    pool = questions or [q(f"q{i}", f"answer{i}") for i in range(12)]
    r.plan = pool[: r.settings.rounds + 1] if len(pool) > r.settings.rounds else pool * 2
    r.status, r.game_no = "playing", 1
    bc.open_round(r, T0)
    return r


# ---------- answer checking ----------


def test_tokens_drop_fillers_accents_and_spell_numbers():
    assert bc.tokens("Um, I think it's the Côte d'Ivoire!") == ["cote", "divoire"]
    assert bc.tokens("One hundred and forty four") == ["144"]
    assert bc.tokens("fifty-four countries") == ["54", "countries"]
    assert bc.tokens("Abeg, the answer is Lagos please") == ["lagos"]


def test_judging_answers():
    k = q("k", "Kilimanjaro", "mount kilimanjaro")
    assert bc.judge_answer(k, "kilimanjiro")  # a small slip
    assert bc.judge_answer(k, "I think it's Mount Kilimanjaro")
    assert not bc.judge_answer(k, "Kenya")
    n = q("n", "Nigeria")
    assert not bc.judge_answer(n, "Ghana or Nigeria")  # no hedging with two answers
    assert bc.judge_answer(q("y", "1960", "nineteen sixty"), "nineteen sixty")
    assert bc.judge_answer(q("b", "A bulldozer", "bulldozer"), "bull dozer")
    assert not bc.judge_answer(q("s", "36"), "63")


def test_name_it_fast_finds_several_items_at_once():
    countries = q("c", kind="list", items=[["Ghana"], ["Kenya"], ["Togo"], ["Ivory Coast", "Cote d'Ivoire"], ["Nigeria"]])
    assert bc.find_items(countries, "Ghana, Kenya and Togo!") == [0, 1, 2]
    assert bc.find_items(countries, "Côte d'Ivoire") == [3]
    assert bc.find_items(countries, "France") == []
    congo = q("k", kind="list", items=[["DR Congo", "DRC"], ["Republic of the Congo", "Congo"], ["Niger"], ["Nigeria"]])
    assert bc.find_items(congo, "DR Congo") == [0]  # not the other Congo as well
    assert bc.find_items(congo, "Nigeria") == [3] and bc.find_items(congo, "Niger and Nigeria") == [2, 3]
    assert not bc.judge_answer(q("p", "Nigeria"), "Niger")


def test_every_question_in_the_bank_is_valid_and_answerable():
    bank = json.loads(QUESTIONS_FILE.read_text())["questions"]
    ids = [x["id"] for x in bank]
    assert len(ids) == len(set(ids))
    parsed = [bc.Question(**x) for x in bank]
    for x in parsed:
        assert x.category in bc.CATEGORIES
        if x.kind == "question":
            for form in [x.answer, *x.accepted]:
                assert bc.judge_answer(x, form), (x.id, form)
        else:
            assert x.items, x.id
            for i, item in enumerate(x.items):
                if x.kind == "list":
                    assert i in bc.find_items(x, item[0]), (x.id, item)
                else:
                    assert bc.judge_answer(x, item[0]), (x.id, item)
    active = [x for x, raw in zip(parsed, bank) if raw.get("active", True)]
    for cat in bc.CATEGORIES:  # every category can run a Brain Battle
        assert any(x.category == cat and x.kind == "question" for x in active), cat
    assert sum(x.kind == "list" for x in active) >= 10 and sum(x.kind == "association" for x in active) >= 15
    assert all(x.as_of and x.source for x in parsed if x.category == "current_affairs")


# ---------- Brain Battle ----------


def test_brain_battle_turns_and_steals():
    r = room("battle")
    assert r.round.turn_team == "A"
    with pytest.raises(bc.GameError, match="Team Nova's turn"):
        bc.submit_answer(r, 2, "answer0", 1, sec(1))  # bayo is on team B
    for _ in range(bc.MAX_TEAM_ATTEMPTS - 1):
        assert bc.submit_answer(r, 1, "wrong", 1, sec(2)).verdict == "wrong"
    bc.submit_answer(r, 1, "still wrong", 1, sec(3))
    assert r.round.phase == "steal" and r.round.turn_team == "B"  # three misses: B may steal
    steal = bc.submit_answer(r, 2, "answer0", 1, sec(4))
    assert steal.verdict == "steal" and steal.points == 5 and r.scores == {"A": 0, "B": 5}
    assert r.round.phase == "reveal"
    with pytest.raises(bc.GameError):
        bc.submit_answer(r, 2, "answer0", 1, sec(5))  # no double scoring
    with pytest.raises(bc.GameError, match="Not yet"):
        bc.advance(r, sec(5))
    bc.advance(r, sec(5), by_host=True)  # the host may skip the reveal
    assert r.round.number == 2 and r.round.turn_team == "B"


def test_hard_questions_score_more_and_time_runs_out():
    r = room("battle", questions=[q(f"h{i}", "Accra", difficulty="hard") for i in range(4)])
    assert bc.submit_answer(r, 1, "accra", 1, sec(3)).points == 20
    bc.advance(r, sec(3), by_host=True)
    with pytest.raises(bc.GameError, match="Time's up"):
        bc.submit_answer(r, 2, "accra", 2, sec(3 + 31))  # after the 30 s round (and its grace)
    with pytest.raises(bc.GameError, match="Not yet"):
        bc.advance(r, sec(3 + 20))
    bc.advance(r, sec(3 + 32))
    assert r.round.phase == "steal" and r.round.turn_team == "A"  # nobody answered: A gets a steal
    bc.advance(r, r.round.closes_at + timedelta(seconds=2))
    assert r.round.phase == "reveal" and r.history[-1].scored == {}


def test_answers_for_an_old_round_are_refused():
    r = room("battle")
    bc.submit_answer(r, 1, "answer0", 1, sec(1))
    bc.advance(r, sec(1), by_host=True)
    with pytest.raises(bc.GameError, match="already gone"):
        bc.submit_answer(r, 2, "answer0", 1, sec(2))  # replaying round 1's answer in round 2


# ---------- the other modes ----------


def test_quick_fire_speed_bonus_and_one_try_each():
    r = room("quickfire", players=(("ada", "A"), ("chi", "A"), ("bayo", "B")))
    assert bc.submit_answer(r, 1, "nope", 1, sec(1)).verdict == "wrong"
    with pytest.raises(bc.GameError, match="had your go"):
        bc.submit_answer(r, 1, "answer0", 1, sec(2))
    hit = bc.submit_answer(r, 3, "answer0", 1, sec(3))  # 3 s into a 12 s round
    assert hit.points == 10 + round(5 * 9 / 12) and r.round.winner_team == "B" and r.round.phase == "reveal"


def test_quick_fire_closes_when_everyone_has_tried():
    r = room("quickfire")
    bc.submit_answer(r, 1, "nope", 1, sec(1))
    bc.submit_answer(r, 2, "nah", 1, sec(2))
    assert r.round.phase == "reveal"


def test_name_it_fast_scores_unique_items_up_to_the_target():
    items = [[c] for c in ("Ghana", "Kenya", "Togo", "Mali", "Chad", "Niger")]
    r = room("namefast", questions=[q(f"l{i}", "e.g.", kind="list", items=items, target=3) for i in range(3)])
    first = bc.submit_answer(r, 1, "Ghana and Kenya", 1, sec(1))
    assert first.verdict == "item" and first.items == ["Ghana", "Kenya"] and first.points == 10
    assert bc.submit_answer(r, 1, "Kenya", 1, sec(2)).verdict == "duplicate"  # no extra points for a repeat
    assert bc.submit_answer(r, 2, "Kenya", 1, sec(2)).points == 5  # but the other team may name it too
    bc.submit_answer(r, 1, "Togo, Mali, Chad", 1, sec(3))
    assert r.scores["A"] == 15  # the third item fills the target of 3; the rest don't count
    with pytest.raises(bc.GameError, match="named enough"):
        bc.submit_answer(r, 1, "Niger", 1, sec(4))


def test_word_association_one_score_per_team():
    word = q("w", "umbrella", kind="association", items=[["umbrella"], ["cloud", "clouds"], ["thunder"]])
    r = room("association", players=(("ada", "A"), ("chi", "A"), ("bayo", "B")), questions=[word, word, word])
    assert bc.submit_answer(r, 1, "clouds", 1, sec(1)).points == 10
    with pytest.raises(bc.GameError, match="already scored"):
        bc.submit_answer(r, 2, "thunder", 1, sec(2))
    assert bc.submit_answer(r, 3, "sunshine", 1, sec(2)).verdict == "wrong"
    assert r.round.phase == "reveal"  # B's only player has tried


# ---------- the end of a match ----------


def play_out(r):
    while r.status == "playing":
        if r.round.phase != "reveal":
            bc.advance(r, r.round.closes_at + timedelta(seconds=5))
        else:
            bc.advance(r, r.round.reveal_until + timedelta(seconds=1))


def test_a_level_game_gets_a_tie_breaker_then_a_draw():
    r = room("quickfire", rounds=2)
    play_out(r)
    assert r.winner == "draw" and r.history[-1].tiebreak and r.finish_reason == "Tie-breaker"


def test_tie_breaker_decides_the_winner():
    r = room("battle", rounds=1)
    play_out_until = lambda: bc.advance(r, r.round.closes_at + timedelta(seconds=5))  # noqa: E731
    play_out_until()  # A's time runs out: B's steal
    play_out_until()  # B misses too
    bc.advance(r, sec(100), by_host=True)
    assert r.round.tiebreak and r.round.turn_team is None  # open to both teams
    bc.submit_answer(r, 2, r.round.question.answer, r.round.number, r.round.opened_at + timedelta(seconds=1))
    bc.advance(r, r.round.reveal_until + timedelta(seconds=1))
    assert r.status == "finished" and r.winner == "B"


def test_win_score_ends_the_match_early():
    r = room("battle", rounds=10, win_score=10)
    bc.submit_answer(r, 1, "answer0", 1, sec(1))
    bc.advance(r, sec(1), by_host=True)
    assert r.status == "finished" and r.winner == "A" and r.finish_reason == "Win score reached"


def test_a_team_with_nobody_left_ends_the_match():
    r = room("battle", players=(("ada", "A"), ("bayo", "B"), ("chi", "B")))
    bc.remove_player(r, 1)
    assert r.status == "finished" and "Team Nova has no players left" in r.finish_reason and r.host_id == 2


def test_choosing_questions_spreads_categories_and_keeps_a_reserve():
    pool = [bc.Question(id=f"{c}{i}", kind="question", category=c, prompt="?", answer="x") for c in ("a", "b") for i in range(10)]
    plan = bc.choose_questions(pool, 6)
    assert len(plan) == 7 and abs(sum(p.category == "a" for p in plan) - 3.5) <= 1


# ---------- the API ----------


async def bc_room(client, host, **settings):
    r = await client.post("/brain-clash/rooms", headers=host, json={"settings": {"rounds": 3, **settings}})
    assert r.status_code == 201, r.text
    return r.json()


def send(client, h, code, round_no, said=None, audio=None, answer_id=None):
    data = {"round": str(round_no), "answer_id": answer_id or uuid.uuid4().hex}
    if said is not None:
        data["text"] = said
    files = {"file": ("a.wav", audio, "audio/wav")} if audio else None
    return client.post(f"/brain-clash/rooms/{code}/answer", headers=h, data=data, files=files)


async def cheat_answer(client, code):
    """The test peeks at the server's room to know the right answer."""
    room = await client.app.state.bc_rooms.get(code)
    return room.round.question.answer


@needs_db
async def test_rooms_teams_and_permissions(client):
    ada, bayo, chi = [await signup(client, n) for n in ("ada", "bayo", "chi")]  # no voice needed
    room = await bc_room(client, ada)
    code = room["code"]
    assert room["players"][0]["team"] == "A" and room["settings"]["team_names"] == {"A": "Team Nova", "B": "Team Pulse"}
    r = (await client.post(f"/brain-clash/rooms/{code}/join", headers=bayo, json={"name": "Bayo B"})).json()
    assert {p["name"]: p["team"] for p in r["players"]} == {"ada": "A", "Bayo B": "B"}  # balanced automatically
    await client.post(f"/brain-clash/rooms/{code.lower()}/join", headers=chi, json={})
    assert (await client.patch(f"/brain-clash/rooms/{code}/settings", headers=bayo, json={"mode": "quickfire"})).status_code == 403
    ids = {p["name"]: p["user_id"] for p in r["players"]}
    assert (await client.post(f"/brain-clash/rooms/{code}/team", headers=bayo, json={"user_id": ids["ada"], "team": "B"})).status_code == 403
    r = await client.post(f"/brain-clash/rooms/{code}/team", headers=ada, json={"user_id": ids["Bayo B"], "team": "A"})
    assert r.status_code == 200
    assert (await client.post(f"/brain-clash/rooms/{code}/start", headers=ada)).status_code == 409  # everyone is on team A
    await client.post(f"/brain-clash/rooms/{code}/shuffle", headers=ada)
    bad = await client.patch(f"/brain-clash/rooms/{code}/settings", headers=ada, json={"categories": ["astrology"]})
    assert bad.status_code == 422
    assert (await client.get("/brain-clash/rooms/NOPE-00", headers=ada)).status_code == 404
    cats = (await client.get("/brain-clash/categories")).json()
    assert len(cats) == 16 and all(c["counts"]["battle"] > 0 for c in cats)


@needs_db
async def test_a_full_quick_fire_match(client):
    ada, bayo = await signup(client, "ada"), await signup(client, "bayo")
    code = (await bc_room(client, ada, mode="quickfire", categories=["everyday"], rounds=2))["code"]
    await client.post(f"/brain-clash/rooms/{code}/join", headers=bayo, json={})
    room = (await client.post(f"/brain-clash/rooms/{code}/start", headers=ada)).json()
    assert room["status"] == "playing" and room["round"]["question"]["category"] == "everyday"
    assert "answer" not in json.dumps(room["round"]["question"]) and room["round"]["reveal"] is None  # no peeking

    answer_id = uuid.uuid4().hex
    right = await cheat_answer(client, code)
    res = (await send(client, ada, code, 1, said=right, answer_id=answer_id)).json()
    assert res["feedback"]["verdict"] == "correct" and res["feedback"]["points"] >= 10
    assert res["room"]["round"]["phase"] == "reveal" and res["room"]["round"]["reveal"]["answer"] == right
    assert (await send(client, ada, code, 1, said=right, answer_id=answer_id)).status_code == 409  # replayed
    assert (await send(client, bayo, code, 1, said=right)).status_code == 409  # the round is over

    assert (await client.post(f"/brain-clash/rooms/{code}/advance", headers=bayo)).status_code == 409  # reveal still showing
    await client.post(f"/brain-clash/rooms/{code}/advance", headers=ada)  # the host skips ahead
    # Bayo answers by voice: the fake speech-to-text "hears" the answer.
    client.app.state.transcriber.text = await cheat_answer(client, code)
    res = (await send(client, bayo, code, 2, audio=tone_wav(300))).json()
    assert res["feedback"]["verdict"] == "correct" and res["feedback"]["said"] == client.app.state.transcriber.text
    client.app.state.transcriber.text = ""
    assert (await send(client, ada, code, 2, audio=tone_wav(300))).status_code == 409  # round already won
    room = (await client.post(f"/brain-clash/rooms/{code}/advance", headers=ada)).json()
    if room["status"] == "playing":  # level: a tie-breaker
        assert room["round"]["tiebreak"]
        await client.post(f"/brain-clash/rooms/{code}/end", headers=ada)
    async with client.app.state.sessionmaker() as s:
        rows = (await s.exec(text("SELECT mode, winner, players FROM bc_results WHERE room_code = :c").bindparams(c=code))).all()
    assert len(rows) == 1 and rows[0][0] == "quickfire" and len(rows[0][2]) == 2


@needs_db
async def test_name_it_fast_hides_the_other_teams_list(client):
    ada, bayo = await signup(client, "ada"), await signup(client, "bayo")
    code = (await bc_room(client, ada, mode="namefast", categories=["african_general"]))["code"]
    await client.post(f"/brain-clash/rooms/{code}/join", headers=bayo, json={})
    await client.post(f"/brain-clash/rooms/{code}/start", headers=ada)
    stored = await client.app.state.bc_rooms.get(code)
    first = stored.round.question.items[0][0]
    res = (await send(client, ada, code, 1, said=first)).json()
    assert res["feedback"]["verdict"] == "item" and res["room"]["round"]["found"]["A"] == [first]
    other = (await client.get(f"/brain-clash/rooms/{code}", headers=bayo)).json()
    assert other["round"]["found"]["A"] == [] and other["round"]["found_count"]["A"] == 1
    assert other["feed"][-1]["said"] == "…"
    assert (await send(client, ada, code, 1, said="")).status_code == 422  # nothing said


@needs_db
async def test_time_runs_out_on_the_server_clock(client):
    ada, bayo = await signup(client, "ada"), await signup(client, "bayo")
    code = (await bc_room(client, ada, mode="battle", steals=False))["code"]
    await client.post(f"/brain-clash/rooms/{code}/join", headers=bayo, json={})
    await client.post(f"/brain-clash/rooms/{code}/start", headers=ada)
    assert (await client.post(f"/brain-clash/rooms/{code}/advance", headers=bayo)).status_code == 409  # not yet
    rooms = client.app.state.bc_rooms
    r = await rooms.get(code)
    r.round.opened_at -= timedelta(seconds=60)
    r.round.closes_at -= timedelta(seconds=60)
    await rooms.save(r)
    assert (await send(client, ada, code, 1, said=r.round.question.answer)).status_code == 409  # too late
    room = (await client.post(f"/brain-clash/rooms/{code}/advance", headers=bayo)).json()
    assert room["round"]["phase"] == "reveal" and room["scores"] == {"A": 0, "B": 0}


@needs_db
def test_live_updates_and_reconnecting():
    app = make_app()
    with TestClient(app) as c:
        tokens = []
        for _ in range(2):
            name = f"bc{uuid.uuid4().hex[:8]}"
            tokens.append(c.post("/auth/signup", json={"username": name, "password": "correct horse", **HOME}).json()["token"])
        h = [{"Authorization": f"Bearer {t}"} for t in tokens]
        code = c.post("/brain-clash/rooms", headers=h[0], json={}).json()["code"]
        with c.websocket_connect(f"/ws?token={tokens[1]}&bc={code}") as ws:
            ws.receive_json()  # came online
            c.post(f"/brain-clash/rooms/{code}/join", headers=h[1], json={})
            got = ws.receive_json()
            while got["type"] != "brain_clash":
                got = ws.receive_json()
        room = c.get(f"/brain-clash/rooms/{code}", headers=h[0]).json()
        assert [p["online"] for p in room["players"]] == [False, True]  # only the WebSocket player pinged
        # Leaving the page and coming back keeps your team.
        again = c.post(f"/brain-clash/rooms/{code}/join", headers=h[1], json={}).json()
        assert len(again["players"]) == 2
        for x in h:
            c.delete("/me", headers=x)

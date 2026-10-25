"""Brain Clash (and Beat Drop and Story Forge, which share its rooms): answer checking, every mode's
rules, the clock, ties, streaks, the fair-play detector, and the rooms API."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from app import brain_clash as bc
from app import fairplay
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


def test_nigerian_english_and_pidgin_answers():
    a = q("a", "Abuja")
    for said in ("na Abuja", "Na Abuja, oh.", "Abuja o", "Abuja sha", "Abuja abi?", "e be Abuja", "na im be Abuja",
                 "I tink na Abuja", "na Abuja jare", "Oya, Abuja", "Ehn, Abuja", "it should be Abuja", "I believe it's Abuja",
                 "Abuja now", "my guy na Abuja", "e fit be Abuja", "I'm sure it's Abuja", "Abeg na Abuja",
                 "the answer na Abuja", "na Abuja be di answer", "Abuja, Abuja!", "Oh, Abuja."):
        assert bc.judge_answer(a, said), said
    for said in ("na Lagos", "Lagos o", "Abuja or Lagos", "not Abuja", "is it not Abuja"):
        assert not bc.judge_answer(a, said), said
    assert bc.judge_answer(q("l", "Last Last"), "Last Last")  # a repeated title isn't halved
    assert not bc.judge_answer(q("l", "Last Last"), "Last")
    song = q("s", "Essence", kind="song", items=[["Wizkid"]])
    assert bc.judge_answer(song, "na Essence by Wizkid o")
    countries = q("c", kind="list", items=[["Ghana"], ["Kenya"], ["Togo"]])
    assert bc.find_items(countries, "na Ghana, Kenya and Togo o") == [0, 1, 2]


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
        assert x.category in bc.ALL_CATEGORIES
        assert bc.GAME_FOR_MODE[next(m for m, k in bc.KIND_FOR_MODE.items() if k == x.kind)] in bc.GAME_CATEGORIES
        if x.kind in ("question", "song"):
            for form in [x.answer, *x.accepted]:
                assert bc.judge_answer(x, form), (x.id, form)
            if x.kind == "song":  # "Essence by Wizkid" counts too
                assert bc.judge_answer(x, f"{x.answer} by {x.items[0][0]}"), x.id
                assert x.category in bc.HUM_CATEGORIES and x.answer in x.prompt
        elif x.kind == "spark":
            assert x.category in bc.STORY_CATEGORIES and x.prompt.startswith("Twist:")
            for form in [x.answer, *x.accepted]:
                assert bc.uses_spark(x, f"And then came the {form} we feared."), (x.id, form)
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
    for cat in bc.HUM_CATEGORIES:
        assert sum(x.category == cat and x.kind == "song" for x in active) >= 8, cat
    for cat in bc.STORY_CATEGORIES:
        assert sum(x.category == cat and x.kind == "spark" for x in active) >= 8, cat
        assert bc.STORY_OPENERS[cat], cat
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
        bc.submit_answer(r, 2, "accra", 2, sec(3 + 21))  # after the 20 s round (and its grace)
    with pytest.raises(bc.GameError, match="Not yet"):
        bc.advance(r, sec(3 + 15))
    bc.advance(r, sec(3 + 22))
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
    hit = bc.submit_answer(r, 3, "answer0", 1, sec(3))  # 3 s into a 20 s round
    assert hit.points == 10 + round(5 * 17 / 20) and r.round.winner_team == "B" and r.round.phase == "reveal"


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


def test_vocabulary_hint_hides_the_answer_among_others():
    pool = [q(f"x{i}", a) for i, a in enumerate(["Abuja", "Lagos", "Kano", "Benue", "Naira", "Jos"])]
    hint = bc.vocabulary_hint(pool[0], pool)
    assert hint.startswith("Quiz answers:") and all(a in hint for a in ("Abuja", "Lagos", "Jos"))
    countries = q("c", kind="list", items=[["Ghana"], ["Kenya"]])
    assert "Ghana" in bc.vocabulary_hint(countries, [])


def test_choosing_questions_spreads_categories_and_keeps_a_reserve():
    pool = [bc.Question(id=f"{c}{i}", kind="question", category=c, prompt="?", answer="x") for c in ("a", "b") for i in range(10)]
    plan = bc.choose_questions(pool, 6)
    assert len(plan) == 7 and abs(sum(p.category == "a" for p in plan) - 3.5) <= 1


# ---------- streaks ----------


def test_every_game_runs_on_a_20_second_clock():
    for mode in bc.KIND_FOR_MODE:
        assert bc.RoomSettings(mode=mode).round_seconds() == 20, mode
    assert bc.HUM_SECONDS == 20


def test_three_rounds_in_a_row_puts_a_team_on_fire():
    r = room("quickfire", rounds=6)
    for n in range(1, 5):
        at = r.round.opened_at + timedelta(seconds=3)
        bc.submit_answer(r, 1, f"answer{n - 1}", n, at)
        bc.advance(r, at + timedelta(seconds=1), by_host=True)
    assert r.streaks["A"] == 4 and r.history[2].scored["A"] > r.history[1].scored["A"]  # round 3 and 4 get +5
    assert [f.verdict for f in r.feed].count("streak") == 2
    bc.advance(r, r.round.closes_at + timedelta(seconds=2))  # nobody scores round 5: the streak breaks
    assert r.streaks["A"] == 0


# ---------- Beat Drop ----------


def song(id="s1", title="Essence", artists=("Wizkid", "Tems")):
    return bc.Question(id=id, kind="song", category="hum_afrobeats", difficulty="easy", prompt=f"{title} ({artists[0]})", answer=title,
                       items=[[a] for a in artists])


def test_song_titles_with_or_without_the_artist():
    s = song()
    for said in ("Essence", "essence by wizkid", "Wizkid Essence", "I think it's Essence by Wizkid and Tems"):
        assert bc.judge_answer(s, said), said
    assert not bc.judge_answer(s, "Fall") and not bc.judge_answer(s, "Wizkid")


def test_beat_drop_hum_then_teammates_guess_and_the_hummer_earns_a_bonus():
    r = room("hum", players=(("ada", "A"), ("bayo", "B"), ("chidi", "A")), questions=[song(f"s{i}") for i in range(4)])
    assert r.round.phase == "hum" and r.round.performer_id == 1 and r.round.turn_team == "A"
    with pytest.raises(bc.GameError, match="Wait for the hum"):
        bc.submit_answer(r, 3, "essence", 1, sec(1))
    with pytest.raises(bc.GameError, match="not your turn"):
        bc.submit_hum(r, 3, 1, "", sec(2))
    assert bc.submit_hum(r, 1, 1, "mm hmm mm", sec(5)) is None  # a real hum: no flag
    assert r.round.phase == "open" and r.round.has_clip
    with pytest.raises(bc.GameError, match="hummer"):
        bc.submit_answer(r, 1, "essence", 1, sec(6))
    with pytest.raises(bc.GameError, match="turn to guess"):
        bc.submit_answer(r, 2, "essence", 1, sec(6))
    hit = bc.submit_answer(r, 3, "Essence by Wizkid", 1, sec(9))
    assert hit.verdict == "correct" and r.scores == {"A": 15, "B": 0}  # 10 for Chidi's guess, +5 for Ada's hum
    bc.advance(r, sec(10), by_host=True)
    assert r.round.performer_id == 2 and r.round.turn_team == "B"  # team B hums next


def test_a_hummer_without_teammates_hums_for_the_other_team():
    r = room("hum", questions=[song(f"s{i}") for i in range(4)])
    bc.submit_hum(r, 1, 1, "", sec(3))
    assert r.round.turn_team == "B"
    assert bc.submit_answer(r, 2, "essence", 1, sec(5)).points == 10 and r.scores == {"A": 5, "B": 10}


def test_saying_the_title_instead_of_humming_is_flagged_and_judged_by_the_other_team():
    r = room("hum", players=(("ada", "A"), ("bayo", "B"), ("chidi", "A")), questions=[song(f"s{i}") for i in range(4)])
    flag = bc.submit_hum(r, 1, 1, "Essence! It's Essence", sec(3))  # Whisper heard the title
    assert flag and flag.kind == "hum" and flag.suspicion >= fairplay.FLAG_AT and "title" in flag.reasons[0]
    item = bc.submit_answer(r, 3, "essence", 1, sec(5))
    assert item.flag_id == flag.id and r.scores == {"A": 0, "B": 0} and flag.held == {"A": 15}  # held, not scored
    with pytest.raises(bc.GameError, match="other team"):
        bc.decide_flag(r, 1, flag.id, True)  # Ada is the host, but she's the one flagged
    bc.decide_flag(r, 2, flag.id, False)  # Bayo, on the other team, voids it
    assert flag.status == "voided" and r.scores == {"A": 0, "B": 0}
    with pytest.raises(bc.GameError, match="already been decided"):
        bc.decide_flag(r, 2, flag.id, True)


# ---------- Story Forge ----------


def spark(id="k1", word="goat", *forms):
    return bc.Question(id=id, kind="spark", category="story_chaos", prompt="Twist: a goat steals something.", answer=word, accepted=list(forms))


def test_story_forge_lines_sparks_and_fire():
    r = room("story", players=(("ada", "A"), ("bayo", "B"), ("chidi", "A")), questions=[spark(f"k{i}") for i in range(4)])
    assert r.round.performer_id == 1 and r.round.phase == "open"
    with pytest.raises(bc.GameError, match="ada's line"):
        bc.submit_answer(r, 2, "The goat ran off with the cake.", 1, sec(2))
    with pytest.raises(bc.GameError, match="three words"):
        bc.submit_answer(r, 1, "Goat!", 1, sec(3))
    item = bc.submit_answer(r, 1, "Then the goats ate the wedding cake.", 1, sec(10))
    assert item.verdict == "line" and item.points == 10 and r.round.phase == "vote" and r.story[-1].used_spark
    with pytest.raises(bc.GameError, match="other team"):
        bc.fire(r, 3, 1)  # Chidi is on Ada's team
    bc.fire(r, 2, 1)
    with pytest.raises(bc.GameError, match="already fired"):
        bc.fire(r, 2, 1)
    assert r.scores == {"A": 13, "B": 0} and r.story[-1].fires == 1
    bc.advance(r, r.round.closes_at + timedelta(seconds=1))
    assert r.round.phase == "reveal"
    bc.advance(r, r.round.reveal_until)
    assert r.round.performer_id == 2  # Bayo writes next
    assert bc.submit_answer(r, 2, "Nobody noticed anything strange that night.", 2, r.round.opened_at + timedelta(seconds=5)).points == 0  # no spark word


def test_copying_an_earlier_line_is_flagged():
    r = room("story", questions=[spark(f"k{i}") for i in range(4)])
    bc.submit_answer(r, 1, "The goat walked into the wedding hall.", 1, sec(5))
    bc.advance(r, r.round.closes_at + timedelta(seconds=1))
    bc.advance(r, r.round.reveal_until)
    item = bc.submit_answer(r, 2, "The goat walked into the wedding hall!", 2, r.round.opened_at + timedelta(seconds=5))
    assert item.flag_id and r.scores["B"] == 0 and r.flag(item.flag_id).held == {"B": 10}
    bc.decide_flag(r, 1, item.flag_id, True)  # the host lets it stand
    assert r.scores["B"] == 10


# ---------- the fair-play detector ----------


def test_fair_play_signs_and_suspicion():
    opened, at = sec(0), sec(8)
    clean = fairplay.Signals(typing_ms=2500)
    assert fairplay.answer_signs(clean, "Kilimanjaro", True, opened, at) == []
    away_paste = fairplay.Signals(away_ms=12_000, pasted=True)
    signs = fairplay.answer_signs(away_paste, "Kilimanjaro", True, opened, at)
    assert fairplay.suspicion(signs) >= fairplay.FLAG_AT and len(signs) == 2
    assert fairplay.answer_signs(away_paste, "Kilimanjaro", False, opened, at) == []  # wrong answers gain nothing
    one = fairplay.answer_signs(fairplay.Signals(pasted=True), "Kilimanjaro", True, opened, at)
    assert 0 < fairplay.suspicion(one) < fairplay.FLAG_AT  # one sign alone is not enough
    robot = fairplay.answer_signs(fairplay.Signals(typing_ms=200), "Mount Kilimanjaro", True, opened, sec(0.5))
    assert fairplay.suspicion(robot) >= fairplay.FLAG_AT  # 17 characters in 0.2 s, half a second after the question
    voice = fairplay.answer_signs(fairplay.Signals(voice=True), "Kilimanjaro", True, opened, sec(0.5))
    assert voice == []  # speaking fast is fine
    assert fairplay.hum_signs(["essence"], ["mm", "hmm"]) == []
    assert fairplay.hum_signs(["lonely", "at", "the", "top"], ["lonely", "at", "the", "top"])[0].weight == 0.9


def test_a_flagged_answer_waits_for_the_host():
    r = room("quickfire")
    item = bc.submit_answer(r, 2, "answer0", 1, sec(6), fairplay.Signals(away_ms=11_000, pasted=True))
    flag = r.flag(item.flag_id)
    assert flag and flag.player == "bayo" and r.scores == {"A": 0, "B": 0} and flag.held["B"] >= 10
    with pytest.raises(bc.GameError, match="host decides"):
        bc.decide_flag(r, 2, flag.id, True)  # nobody judges their own flag
    bc.decide_flag(r, 1, flag.id, True)
    assert r.scores["B"] == flag.held["B"] and r.player(2).points == flag.held["B"]


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
    hint = client.app.state.transcriber.prompts[-1]  # speech-to-text was told the words to expect...
    assert hint.startswith("Quiz answers:") and client.app.state.transcriber.text in hint and hint.count(",") >= 5  # ...among decoys
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


@needs_db
async def test_party_screen_sees_the_room_without_its_secrets(client):
    ada, bayo = await signup(client, "ada"), await signup(client, "bayo")
    room = await bc_room(client, ada, mode="hum", categories=["hum_classics"])
    code, key = room["code"], room["screen_key"]
    assert key and (await client.post(f"/brain-clash/rooms/{code}/join", headers=bayo, json={})).json()["screen_key"] is None
    assert (await client.get(f"/brain-clash/rooms/{code}/screen?key=wrong")).status_code == 403
    assert (await client.get(f"/brain-clash/rooms/{code}/screen")).status_code == 422
    await client.post(f"/brain-clash/rooms/{code}/start", headers=ada)
    title = await cheat_answer(client, code)
    # The screen may ask "time's up?", but only the server's clock moves the round on.
    assert (await client.post(f"/brain-clash/rooms/{code}/screen/advance?key=wrong")).status_code == 403
    assert (await client.post(f"/brain-clash/rooms/{code}/screen/advance?key={key}")).status_code == 409
    screen = (await client.get(f"/brain-clash/rooms/{code}/screen?key={key}")).json()
    assert screen["round"]["phase"] == "hum" and title not in json.dumps(screen["round"])  # the song stays secret
    assert screen["you"] == 0 and screen["screen_key"] is None and len(screen["players"]) == 2
    client.app.state.transcriber.text = "hmm mm"
    hum = {"file": ("hum.wav", tone_wav(300, seconds=2), "audio/wav")}
    assert (await client.post(f"/brain-clash/rooms/{code}/hum", headers=ada, data={"round": "1"}, files=hum)).status_code == 200
    played = await client.get(f"/brain-clash/rooms/{code}/screen/hum?key={key}")
    assert played.status_code == 200 and played.headers["content-type"] == "audio/wav"  # the hum on the big speaker
    assert (await client.get(f"/brain-clash/rooms/{code}/screen/hum?key=wrong")).status_code == 403


@needs_db
def test_party_screen_gets_live_updates_with_its_key():
    app = make_app()
    with TestClient(app) as c:
        token = c.post("/auth/guest", json={"name": "Host"}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        room = c.post("/brain-clash/rooms", headers=h, json={}).json()
        code = room["code"]
        with pytest.raises(Exception):
            with c.websocket_connect(f"/ws?bc={code}&screen=wrong") as ws:
                ws.receive_json()
        with c.websocket_connect(f"/ws?bc={code}&screen={room['screen_key']}") as ws:
            c.post(f"/brain-clash/rooms/{code}/react", headers=h, json={"emoji": "🔥"})
            assert ws.receive_json()["type"] == "reaction"
            c.post(f"/brain-clash/rooms/{code}/leave", headers=h)
            assert ws.receive_json()["type"] == "brain_clash"
        c.delete("/me", headers=h)


@needs_db
async def test_beat_drop_over_the_api(client):
    ada, bayo = await signup(client, "ada"), await signup(client, "bayo")
    assert (await client.post("/brain-clash/rooms", headers=ada, json={"settings": {"mode": "hum", "categories": ["everyday"]}})).status_code == 422
    code = (await bc_room(client, ada, mode="hum", categories=["hum_classics"]))["code"]
    assert (await client.patch(f"/brain-clash/rooms/{code}/settings", headers=ada, json={"mode": "battle"})).status_code == 409  # stays Beat Drop
    await client.post(f"/brain-clash/rooms/{code}/join", headers=bayo, json={})
    room = (await client.post(f"/brain-clash/rooms/{code}/start", headers=ada)).json()
    title = await cheat_answer(client, code)
    assert room["game"] == "beat-drop" and room["round"]["phase"] == "hum" and title in room["round"]["question"]["prompt"]  # the hummer sees it
    seen = (await client.get(f"/brain-clash/rooms/{code}", headers=bayo)).json()
    assert title not in json.dumps(seen["round"]) and "hummer" in seen["round"]["question"]["prompt"]  # the guesser doesn't
    hum = {"file": ("hum.wav", tone_wav(300, seconds=2), "audio/wav")}
    assert (await client.post(f"/brain-clash/rooms/{code}/hum", headers=bayo, data={"round": "1"}, files=hum)).status_code == 409
    client.app.state.transcriber.text = "hmm mm"
    res = await client.post(f"/brain-clash/rooms/{code}/hum", headers=ada, data={"round": "1"}, files=hum)
    assert res.status_code == 200, res.text
    assert res.json()["round"]["phase"] == "open" and res.json()["round"]["turn_team"] == "B" and not res.json()["flags"]
    clip = await client.get(f"/brain-clash/rooms/{code}/hum", headers=bayo)
    assert clip.status_code == 200 and clip.headers["content-type"] == "audio/wav"
    res = (await send(client, bayo, code, 1, said=f"{title}")).json()
    assert res["feedback"]["verdict"] == "correct" and res["room"]["scores"]["A"] == 5  # the hummer's bonus
    cats = (await client.get("/brain-clash/categories?game=beat-drop")).json()
    assert {c["id"] for c in cats} == set(bc.HUM_CATEGORIES) and all(c["counts"]["hum"] >= 8 for c in cats)


@needs_db
async def test_fair_play_over_the_api(client):
    ada, bayo = await signup(client, "ada"), await signup(client, "bayo")
    code = (await bc_room(client, ada, mode="quickfire", categories=["everyday"]))["code"]
    await client.post(f"/brain-clash/rooms/{code}/join", headers=bayo, json={})
    await client.post(f"/brain-clash/rooms/{code}/start", headers=ada)
    right = await cheat_answer(client, code)
    data = {"round": "1", "answer_id": uuid.uuid4().hex, "text": right, "away_ms": "15000", "pasted": "true"}
    res = (await client.post(f"/brain-clash/rooms/{code}/answer", headers=bayo, data=data)).json()
    flag = res["room"]["flags"][0]
    assert res["feedback"]["flag_id"] == flag["id"] and flag["status"] == "pending" and res["room"]["scores"]["B"] == 0
    assert any("Left the game" in x for x in flag["reasons"]) and not flag["you_decide"]
    host_view = (await client.get(f"/brain-clash/rooms/{code}", headers=ada)).json()
    assert host_view["flags"][0]["you_decide"]
    assert (await client.post(f"/brain-clash/rooms/{code}/flags/{flag['id']}", headers=bayo, json={"allow": True})).status_code == 403
    done = (await client.post(f"/brain-clash/rooms/{code}/flags/{flag['id']}", headers=ada, json={"allow": False})).json()
    assert done["flags"][0]["status"] == "voided" and done["scores"]["B"] == 0
    assert (await client.post(f"/brain-clash/rooms/{code}/react", headers=bayo, json={"emoji": "🔥"})).status_code == 204
    await client.post(f"/brain-clash/rooms/{code}/end", headers=ada)
    async with client.app.state.sessionmaker() as s:
        rows = (await s.exec(text("SELECT flags FROM bc_results WHERE room_code = :c").bindparams(c=code))).all()
    assert rows[0][0][0]["status"] == "voided"


@needs_db
async def test_public_stats_are_real_counts(client):
    before = (await client.get("/stats")).json()
    assert set(before) == {"online", "players", "matches", "turns"} and all(v >= 0 for v in before.values())
    await signup(client, "statsy")
    after = (await client.get("/stats")).json()
    assert after["players"] == before["players"] + 1


@needs_db
async def test_recent_results_are_public_and_have_no_player_names(client):
    ada, bayo = await signup(client, "ada"), await signup(client, "bayo")
    code = (await bc_room(client, ada, mode="quickfire", categories=["everyday"]))["code"]
    await client.post(f"/brain-clash/rooms/{code}/join", headers=bayo, json={})
    await client.post(f"/brain-clash/rooms/{code}/start", headers=ada)
    await send(client, ada, code, 1, said=await cheat_answer(client, code))
    await client.post(f"/brain-clash/rooms/{code}/end", headers=ada)
    latest = (await client.get("/results")).json()[0]  # no sign-in needed
    assert latest["game"] == "brain-clash" and latest["winner"] == "A" and latest["score_a"] >= 10
    assert "players" not in latest and "ada" not in json.dumps(latest)

"""Brain Clash: two teams, one battle, one champion.

A team quiz game. Everything that decides points lives here, on the server: the browser
only sends what a player said (as text, or a recording the server turns into text).

Modes
-----
- battle:      Brain Battle. Teams take turns: only the team whose turn it is may answer
               (up to MAX_TEAM_ATTEMPTS tries). If they miss, the other team gets a short
               steal, for half points.
- quickfire:   both teams race on short questions. First correct answer wins the round,
               plus a speed bonus for answering early. One try per player.
- namefast:    Name It Fast. "Name five African countries": each team builds its own list
               against the clock. Every valid item scores; saying one again scores nothing.
               One recording can name several items ("Ghana, Kenya and Togo").
- association: Word Association. A word appears; each team scores once for a related word
               from the accepted list. One try per player.

The clock is the server's. Rounds close when the server says so: when someone has won the
round, or when a client reports the time is up and the server checks its own clock (the
same pattern as Who's Talking?, so there's no background job). A round then shows its
answer for REVEAL_SECONDS before the next one.

If the game ends level, one tie-breaker round is played, open to both teams. Still level
after that: a draw.
"""

from __future__ import annotations

import random
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from .store import Store

Mode = Literal["battle", "namefast", "quickfire", "association"]
TeamId = Literal["A", "B"]
Status = Literal["lobby", "playing", "finished"]
Phase = Literal["open", "steal", "reveal"]
Verdict = Literal["correct", "wrong", "duplicate", "item", "steal"]

CATEGORIES = {
    "african_general": "African General Knowledge",
    "nigerian_general": "Nigerian General Knowledge",
    "african_music": "African Music",
    "nigerian_entertainment": "Nigerian Entertainment",
    "african_history": "African History and Culture",
    "current_affairs": "Current Affairs",
    "african_football": "African Football",
    "animals_nature": "Animals and Nature",
    "african_food": "African Food",
    "languages": "Languages and Vocabulary",
    "pidgin": "Nigerian Pidgin",
    "african_movies": "African Movies",
    "riddles": "Riddles and Brain Teasers",
    "word_challenges": "Word Challenges",
    "everyday": "Everyday Knowledge",
    "funny": "Funny Challenges",
}
KIND_FOR_MODE = {"battle": "question", "quickfire": "question", "namefast": "list", "association": "association"}
DEFAULT_SECONDS = {"battle": 30, "quickfire": 12, "namefast": 45, "association": 15}
DEFAULT_TEAM_NAMES = {"A": "Team Nova", "B": "Team Pulse"}

MAX_TEAM_ATTEMPTS = 3  # Brain Battle: tries per team per question
STEAL_SECONDS = 10
REVEAL_SECONDS = 6
GRACE_SECONDS = 0.75  # an answer sent just before the buzzer still counts, despite the network
MAX_PLAYERS = 20
FEED_SIZE = 30
ROOMS_INDEX = "bc:rooms"

CODE_WORDS = ("NOVA", "PULSE", "COMET", "ORBIT", "NEON", "PIXEL", "TURBO", "BLAZE", "STORM", "FLASH", "QUEST", "SPARK", "ECHO", "LUNAR", "VOLT", "PRISM")


def now() -> datetime:
    return datetime.now(timezone.utc)


class GameError(Exception):
    """A move the rules don't allow. `status` is the HTTP status the router should answer with."""

    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


# ---------- the question bank ----------


class Question(BaseModel):
    id: str
    kind: Literal["question", "list", "association"]
    category: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    prompt: str
    answer: str  # what's shown at the reveal
    accepted: list[str] = []  # other ways of saying the answer
    items: list[list[str]] = []  # list / association: each valid item, with its other spellings
    target: int | None = None  # list: how many items to name
    points: int | None = None  # overrides the scoring rules for this question
    explanation: str | None = None
    source: str | None = None
    as_of: str | None = None  # current affairs: when the fact was last checked


class Scoring(BaseModel):
    """The scoring rules. Defaults match the game's design; a room can change them."""

    correct: int = Field(default=10, ge=0, le=100)
    hard: int = Field(default=20, ge=0, le=100)
    list_item: int = Field(default=5, ge=0, le=100)
    speed_max: int = Field(default=5, ge=0, le=50)


class RoomSettings(BaseModel):
    mode: Mode = "battle"
    categories: list[str] = []  # empty = every category
    rounds: int = Field(default=10, ge=1, le=30)
    seconds: int | None = Field(default=None, ge=5, le=120)  # None = the mode's default
    win_score: int | None = Field(default=None, ge=10, le=1000)  # first team to reach it wins
    speed_bonus: bool = True
    steals: bool = True  # Brain Battle: the other team may steal a missed question
    team_names: dict[TeamId, str] = Field(default_factory=lambda: dict(DEFAULT_TEAM_NAMES))
    scoring: Scoring = Field(default_factory=Scoring)

    def round_seconds(self) -> int:
        return self.seconds or DEFAULT_SECONDS[self.mode]


# ---------- answer checking ----------

FILLERS = (
    "i think it is", "i think its", "i think", "the answer is", "my answer is", "answer is", "it is", "its", "is it", "i guess",
    "maybe", "um", "umm", "uh", "erm", "er", "hmm", "ok", "okay", "so", "well", "please", "abeg",
)
ARTICLES = ("the", "a", "an")
UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                                   "sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
SCALES = {"hundred": 100, "thousand": 1000}


def numbers_to_digits(tokens: list[str]) -> list[str]:
    """'one hundred and forty four' -> '144', 'fifty four' -> '54'. Other words are left alone."""
    out: list[str] = []
    total = current = 0
    in_number = False

    def flush() -> None:
        nonlocal total, current, in_number
        if in_number:
            out.append(str(total + current))
        total = current = 0
        in_number = False

    for i, t in enumerate(tokens):
        if t in UNITS:
            current += UNITS[t]
            in_number = True
        elif t in TENS:
            current += TENS[t]
            in_number = True
        elif t in SCALES and in_number:
            if SCALES[t] == 100:
                current *= 100
            else:
                total, current = (total + current) * SCALES[t], 0
        elif t == "and" and in_number and i + 1 < len(tokens) and (tokens[i + 1] in UNITS or tokens[i + 1] in TENS):
            continue  # "one hundred AND forty"
        else:
            flush()
            out.append(t)
    flush()
    return out


def tokens(text: str) -> list[str]:
    """Lower case, no accents or punctuation, numbers as digits, fillers and articles dropped from the start.

    'Um, I think it's the Côte d'Ivoire!' -> ['cote', 'divoire']
    """
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("&", " and ").replace("'", "").replace("’", "")
    words = re.findall(r"[a-z0-9]+", text)
    # Strip "um, I think it's" and a trailing "please", but never the whole answer ("Please" is an answer too).
    changed = True
    while changed:
        changed = False
        for f in FILLERS:
            fw = f.split()
            if words[: len(fw)] == fw and len(words) > len(fw):
                words = words[len(fw) :]
                changed = True
                break
        if len(words) > 1 and words[-1] in ("please", "abeg"):
            words, changed = words[:-1], True
    while len(words) > 1 and words[0] in ARTICLES:
        words = words[1:]
    return numbers_to_digits(words)


def same_token(a: str, b: str) -> bool:
    """Exact for short words and numbers; longer words may be off by a plural or a small slip ('kilimanjiro')."""
    if a == b:
        return True
    if a.isdigit() or b.isdigit() or len(a) < 5 or len(b) < 4:
        return False
    # 0.85 lets "kilimanjiro" through but not "niger" for "nigeria".
    return a.rstrip("s") == b.rstrip("s") or SequenceMatcher(None, a, b).ratio() >= 0.85


def same_answer(said: list[str], want: list[str]) -> bool:
    if not said or not want:
        return False
    if len(said) == len(want) and all(same_token(s, w) for s, w in zip(said, want)):
        return True
    # Run-together or split words ("bulldozer" / "bull dozer", "jollof rice" said fast).
    joined_s, joined_w = "".join(said), "".join(want)
    return len(joined_w) >= 6 and SequenceMatcher(None, joined_s, joined_w).ratio() >= 0.88


def answer_forms(q: Question) -> list[list[str]]:
    return [t for t in (tokens(a) for a in [q.answer, *q.accepted]) if t]


def judge_answer(q: Question, said: str) -> bool:
    """A single-answer question (or a word association): does what they said match an accepted answer?"""
    heard = tokens(said)
    forms = answer_forms(q) if q.kind == "question" else [t for item in q.items for t in (tokens(a) for a in item) if t]
    return any(same_answer(heard, form) for form in forms)


def find_items(q: Question, said: str) -> list[int]:
    """Name It Fast: which of the question's items does the answer name? (Several can be named at once.)

    Each word counts once, for the longest and most exact item it can be: "DR Congo" is DR Congo, not
    also the Republic of the Congo, and "Nigeria" isn't also Niger.
    """
    heard = tokens(said)
    hits = []  # (words, exact words, start, item)
    for i, item in enumerate(q.items):
        for alt in item:
            want = tokens(alt)
            n = len(want)
            for j in range(len(heard) - n + 1) if n else ():
                if all(same_token(h, w) for h, w in zip(heard[j : j + n], want)):
                    hits.append((n, sum(h == w for h, w in zip(heard[j : j + n], want)), j, i))
    used: set[int] = set()
    found: list[tuple[int, int]] = []  # (position, item)
    for n, _, j, i in sorted(hits, key=lambda h: (-h[0], -h[1], h[2])):
        span = set(range(j, j + n))
        if span & used or i in (item for _, item in found):
            continue
        used |= span
        found.append((j, i))
    return [i for _, i in sorted(found)]


# ---------- the room ----------


class Player(BaseModel):
    user_id: int
    name: str
    team: TeamId
    points: int = 0  # this player's contribution to the team score
    correct: int = 0


class FeedItem(BaseModel):
    round: int
    team: TeamId
    player: str
    user_id: int
    said: str
    verdict: Verdict
    points: int = 0
    items: list[str] = []  # Name It Fast: what was found


class Round(BaseModel):
    number: int  # 1-based
    question: Question
    phase: Phase = "open"
    opened_at: datetime
    closes_at: datetime
    turn_team: TeamId | None = None  # Brain Battle: who may answer now (None: both teams)
    attempts: dict[str, int] = {}  # team -> tries this phase (Brain Battle)
    tried: list[int] = []  # one-try modes: who has answered
    found: dict[str, list[int]] = {"A": [], "B": []}  # Name It Fast: item indexes per team
    scored: dict[str, int] = {}  # team -> points this round
    winner_team: TeamId | None = None
    reveal_until: datetime | None = None
    tiebreak: bool = False


class RoundSummary(BaseModel):
    number: int
    prompt: str
    answer: str
    scored: dict[str, int]
    tiebreak: bool = False


class BrainClashRoom(BaseModel):
    code: str
    host_id: int
    status: Status = "lobby"
    game_no: int = 0
    settings: RoomSettings = Field(default_factory=RoomSettings)
    players: list[Player] = []
    scores: dict[str, int] = {"A": 0, "B": 0}
    plan: list[Question] = []  # this game's questions; the last one is kept back for a tie-breaker
    round_index: int = 0  # index into plan of the current round
    round: Round | None = None
    feed: list[FeedItem] = []
    history: list[RoundSummary] = []
    winner: Literal["A", "B", "draw"] | None = None
    finish_reason: str | None = None
    notice: str | None = None  # e.g. "Only 6 questions match those categories"
    created_at: datetime
    updated_at: datetime

    def player(self, user_id: int) -> Player | None:
        return next((p for p in self.players if p.user_id == user_id), None)

    def team(self, team: TeamId) -> list[Player]:
        return [p for p in self.players if p.team == team]

    def rounds_total(self) -> int:
        return max(0, len(self.plan) - 1)  # the reserve tie-breaker isn't a regular round


def other(team: TeamId) -> TeamId:
    return "B" if team == "A" else "A"


def new_code() -> str:
    return f"{secrets.choice(CODE_WORDS)}-{secrets.randbelow(90) + 10}"


def pick_team(room: BrainClashRoom) -> TeamId:
    """New players go to the smaller team (A on a tie)."""
    return "A" if len(room.team("A")) <= len(room.team("B")) else "B"


def choose_questions(pool: list[Question], rounds: int, rng: random.Random | None = None) -> list[Question]:
    """rounds questions plus one in reserve for a tie-breaker, spread across categories."""
    rng = rng or random.SystemRandom()
    by_cat: dict[str, list[Question]] = {}
    for q in pool:
        by_cat.setdefault(q.category, []).append(q)
    for qs in by_cat.values():
        rng.shuffle(qs)
    picked: list[Question] = []
    cats = list(by_cat)
    rng.shuffle(cats)
    while len(picked) < rounds + 1 and any(by_cat.values()):
        for c in cats:  # round-robin, so one big category doesn't take over
            if by_cat[c] and len(picked) < rounds + 1:
                picked.append(by_cat[c].pop())
    return picked


def start_game(room: BrainClashRoom, pool: list[Question], at: datetime | None = None) -> None:
    if not room.team("A") or not room.team("B"):
        raise GameError("Both teams need at least one player.")
    plan = choose_questions(pool, room.settings.rounds)
    if not plan:
        raise GameError("There are no questions for that mode and those categories yet. Pick more categories.")
    if len(plan) == 1:
        plan = plan * 2  # one question: play it, and reuse it only if a tie-breaker is needed
    room.notice = (
        f"Only {len(plan) - 1} questions match those categories, so this game has {len(plan) - 1} rounds."
        if len(plan) - 1 < room.settings.rounds
        else None
    )
    room.plan = plan
    room.status, room.game_no = "playing", room.game_no + 1
    room.scores = {"A": 0, "B": 0}
    for p in room.players:
        p.points = p.correct = 0
    room.feed, room.history, room.winner, room.finish_reason = [], [], None, None
    room.round_index = 0
    open_round(room, at or now())


def open_round(room: BrainClashRoom, at: datetime, tiebreak: bool = False) -> None:
    number = room.round_index + 1
    s = room.settings
    turn: TeamId | None = None
    if s.mode == "battle" and not tiebreak:
        turn = "A" if number % 2 else "B"
    room.round = Round(
        number=number,
        question=room.plan[room.round_index],
        opened_at=at,
        closes_at=at + timedelta(seconds=s.round_seconds()),
        turn_team=turn,
        found={"A": [], "B": []},
        tiebreak=tiebreak,
    )


def question_points(room: BrainClashRoom, q: Question) -> int:
    rules = room.settings.scoring
    return q.points if q.points is not None else rules.hard if q.difficulty == "hard" else rules.correct


def eligible(room: BrainClashRoom, player: Player) -> None:
    """Raise GameError if this player can't answer right now."""
    r = room.round
    if room.status != "playing" or r is None:
        raise GameError("The game isn't running.")
    if r.phase == "reveal":
        raise GameError("This round is over. The next question is coming.")
    mode = room.settings.mode
    if mode == "battle" and r.turn_team and player.team != r.turn_team:
        raise GameError(f"It's {room.settings.team_names[r.turn_team]}'s turn.", 403)
    if mode == "battle" and r.attempts.get(player.team, 0) >= MAX_TEAM_ATTEMPTS:
        raise GameError("Your team has used all its tries on this question.")
    if mode in ("quickfire", "association") or (mode == "battle" and r.tiebreak):
        if player.user_id in r.tried:
            raise GameError("You've had your go on this one.")
    if mode == "association" and player.team in r.scored:
        raise GameError("Your team has already scored on this word.")
    if mode == "namefast" and len(r.found[player.team]) >= list_target(r.question):
        raise GameError("Your team has named enough. Wait for the others!")


def list_target(q: Question) -> int:
    return q.target or 5


def submit_answer(room: BrainClashRoom, user_id: int, said: str, round_number: int, received: datetime) -> FeedItem:
    """Score one answer. `received` is when the request arrived (before any speech-to-text), so slow
    transcription never costs a player the round. Raises GameError for anything the rules don't allow."""
    player = room.player(user_id)
    if player is None:
        raise GameError("Join this room first.", 403)
    r = room.round
    if r is None or r.number != round_number:
        raise GameError("That question has already gone. Answer the one on screen.")
    if received > r.closes_at + timedelta(seconds=GRACE_SECONDS):
        raise GameError("Time's up on that question.")
    eligible(room, player)
    said = said.strip()[:200]
    if not said:
        raise GameError("We didn't catch an answer. Say it again, or type it.", 422)

    q, mode, team = r.question, room.settings.mode, player.team
    item = FeedItem(round=r.number, team=team, player=player.name, user_id=user_id, said=said, verdict="wrong")
    close = False

    if mode == "namefast":
        found = [i for i in find_items(q, said) if i not in r.found[team]]
        room_left = list_target(q) - len(r.found[team])
        found = found[:room_left]
        if found:
            r.found[team].extend(found)
            item.verdict = "item"
            item.items = [q.items[i][0] for i in found]
            item.points = room.settings.scoring.list_item * len(found)
        elif find_items(q, said):
            item.verdict = "duplicate"  # all already on the team's list
        close = all(len(r.found[t]) >= list_target(q) for t in ("A", "B"))
    else:
        if mode in ("quickfire", "association") or (mode == "battle" and r.tiebreak):
            r.tried.append(user_id)
        if mode == "battle":
            r.attempts[team] = r.attempts.get(team, 0) + 1
        if judge_answer(q, said):
            if mode == "association":
                item.points = room.settings.scoring.correct
                close = all(t in r.scored or t == team for t in ("A", "B"))
            else:
                item.points = question_points(room, q)
                if r.phase == "steal":
                    item.points = round(item.points / 2)
                    item.verdict = "steal"
                if mode == "quickfire" and room.settings.speed_bonus:
                    total = (r.closes_at - r.opened_at).total_seconds()
                    left = max(0.0, (r.closes_at - received).total_seconds())
                    item.points += round(room.settings.scoring.speed_max * left / total)
                r.winner_team = team
                close = True
            if item.verdict == "wrong":
                item.verdict = "correct"
        elif mode == "battle" and r.attempts[team] >= MAX_TEAM_ATTEMPTS:
            close = not _start_steal(room, received)
        elif mode == "quickfire" and all(p.user_id in r.tried for p in room.players):
            close = True  # everyone has had a go
        elif mode == "association" and all(p.user_id in r.tried for p in room.players if p.team not in r.scored):
            close = True

    if item.points:
        room.scores[team] += item.points
        r.scored[team] = r.scored.get(team, 0) + item.points
        player.points += item.points
        player.correct += 1
    room.feed = [*room.feed, item][-FEED_SIZE:]
    if close:
        close_round(room, received)
    return item


def _start_steal(room: BrainClashRoom, at: datetime) -> bool:
    """Brain Battle: the turn team missed. Hand the question to the other team, if steals are on."""
    r = room.round
    if not room.settings.steals or r.phase != "open" or r.turn_team is None:
        return False
    r.phase = "steal"
    r.turn_team = other(r.turn_team)
    r.closes_at = at + timedelta(seconds=STEAL_SECONDS)
    return True


def close_round(room: BrainClashRoom, at: datetime) -> None:
    r = room.round
    r.phase = "reveal"
    r.reveal_until = at + timedelta(seconds=REVEAL_SECONDS)
    room.history.append(RoundSummary(number=r.number, prompt=r.question.prompt, answer=r.question.answer, scored=dict(r.scored), tiebreak=r.tiebreak))


def advance(room: BrainClashRoom, at: datetime, by_host: bool = False) -> None:
    """Move the game on when its clock says so (or, between rounds, when the host says so)."""
    r = room.round
    if room.status != "playing" or r is None:
        raise GameError("The game isn't running.")
    if r.phase in ("open", "steal"):
        if at <= r.closes_at + timedelta(seconds=GRACE_SECONDS):
            raise GameError("Not yet!")
        if r.phase == "open" and room.settings.mode == "battle" and r.winner_team is None and _start_steal(room, at):
            return
        close_round(room, at)
        return
    if at < r.reveal_until and not by_host:
        raise GameError("Not yet!")
    _next_round(room, at)


def _next_round(room: BrainClashRoom, at: datetime) -> None:
    r = room.round
    s = room.settings
    reached = s.win_score is not None and max(room.scores.values()) >= s.win_score
    last = room.round_index + 1 >= room.rounds_total()
    tied = room.scores["A"] == room.scores["B"]
    if r.tiebreak or ((reached or last) and not tied):
        finish(room, "Win score reached" if reached and not r.tiebreak else "Tie-breaker" if r.tiebreak else "All rounds played")
        return
    if (reached or last) and tied:
        room.round_index = len(room.plan) - 1  # the reserve question
        open_round(room, at, tiebreak=True)
        return
    room.round_index += 1
    open_round(room, at)


def finish(room: BrainClashRoom, reason: str) -> None:
    room.status = "finished"
    room.finish_reason = reason
    a, b = room.scores["A"], room.scores["B"]
    room.winner = "A" if a > b else "B" if b > a else "draw"
    if room.round and room.round.phase != "reveal":
        close_round(room, now())


def remove_player(room: BrainClashRoom, user_id: int) -> None:
    room.players = [p for p in room.players if p.user_id != user_id]
    if room.host_id == user_id and room.players:
        room.host_id = room.players[0].user_id  # the next person in becomes host
    if room.status == "playing" and (not room.team("A") or not room.team("B")):
        empty = "A" if not room.team("A") else "B"
        finish(room, f"{room.settings.team_names[empty]} has no players left")


# ---------- storage (Redis, like Who's Talking? rooms) ----------


class BrainClashStore:
    def __init__(self, store: Store, ttl_hours: float) -> None:
        self.store = store
        self.ttl = int(ttl_hours * 3600)

    def lock(self, code: str):
        return self.store.lock(f"bc:{code.upper()}", timeout=30)

    async def get(self, code: str) -> BrainClashRoom | None:
        raw = await self.store.get(f"bc:room:{code.upper()}")
        return BrainClashRoom.model_validate_json(raw) if raw else None

    async def save(self, room: BrainClashRoom) -> None:
        room.updated_at = now()
        await self.store.put(f"bc:room:{room.code}", room.model_dump_json(), self.ttl)
        await self.store.set_add(ROOMS_INDEX, room.code)
        await self.store.publish(f"bc:{room.code}", "changed")

    async def delete(self, code: str) -> None:
        await self.store.delete(f"bc:room:{code}")
        await self.store.set_remove(ROOMS_INDEX, code)
        await self.store.publish(f"bc:{code}", "changed")

    async def create(self, host: Player, settings: RoomSettings) -> BrainClashRoom:
        stamp = now()
        for _ in range(20):
            code = new_code()
            if await self.get(code) is None:
                break
        room = BrainClashRoom(code=code, host_id=host.user_id, settings=settings, players=[host], created_at=stamp, updated_at=stamp)
        await self.save(room)
        return room

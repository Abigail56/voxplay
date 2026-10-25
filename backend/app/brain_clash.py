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

The same room engine also runs two more VOXPLAY games, as their own modes:

- hum:         Beat Drop. Each round one player (the hummer, taking turns) secretly sees a song
               title and hums it; their clip plays on every screen and the hummer's teammates try
               to name the song (then the other team may steal). A right guess also earns the hummer
               a bonus. Whisper listens to the hum: saying the title instead is flagged (see fairplay.py).
- story:       Story Forge. The teams build one story together, a line each, taking turns. Every
               line must use the round's spark word; then the other team has a few seconds to
               fire 🔥 at a line they love. Points for the spark and for every fire.

A team that wins three rounds in a row is on fire: +STREAK_BONUS each round until the streak breaks.

The clock is the server's. Rounds close when the server says so: when someone has won the
round, or when a client reports the time is up and the server checks its own clock (the
same pattern as Who's Talking?, so there's no background job). A round then shows its
answer for REVEAL_SECONDS before the next one.

If the game ends level, one tie-breaker round is played, open to both teams. Still level
after that: a draw.
"""

from __future__ import annotations

import hmac
import random
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from . import fairplay
from .store import Store

Mode = Literal["battle", "namefast", "quickfire", "association", "hum", "story", "bomb"]
TeamId = Literal["A", "B"]
Status = Literal["lobby", "playing", "finished"]
# hum: Beat Drop's hummer is recording. vote: Story Forge's fire votes on the new line.
Phase = Literal["hum", "open", "steal", "vote", "reveal"]
Verdict = Literal["correct", "wrong", "duplicate", "item", "steal", "line", "streak", "boom"]

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
HUM_CATEGORIES = {
    "hum_afrobeats": "Afrobeats Hits",
    "hum_amapiano": "Amapiano and South African Hits",
    "hum_classics": "Naija Classics",
}
STORY_CATEGORIES = {
    "story_lagos": "Lagos Life",
    "story_legends": "Myths and Legends",
    "story_chaos": "Comedy Chaos",
}
BOMB_CATEGORIES = {
    "bomb_easy": "Easy Letters",
    "bomb_tricky": "Tricky Letters",
    "bomb_nightmare": "Nightmare Letters",
}
# Story Forge: the game writes the first line, so nobody faces a blank page.
STORY_OPENERS = {
    "story_lagos": [
        "It was 6am in Lagos, and the danfo was already full of surprises.",
        "Nobody on our street expected the new neighbour to arrive with a parrot that spoke Yoruba.",
        "The power came back on at midnight, and with it a strange voice on the radio.",
    ],
    "story_legends": [
        "Long ago, when animals still talked, the tortoise called a meeting under the baobab.",
        "The night the drums fell silent, the village knew something ancient had woken up.",
        "At the edge of the forest lived a girl who could hear the river's secrets.",
    ],
    "story_chaos": [
        "The wedding was going perfectly, until the goat walked in.",
        "Aunty Bisi said it would be a quiet family dinner. She was very, very wrong.",
        "Everyone in the group chat agreed: last Saturday was the most chaotic day of our lives.",
    ],
}

# Which game each mode belongs to, and the categories that game offers.
GAME_FOR_MODE = {"battle": "brain-clash", "quickfire": "brain-clash", "namefast": "brain-clash", "association": "brain-clash", "hum": "beat-drop", "story": "story-forge", "bomb": "word-bomb"}
GAME_CATEGORIES = {"brain-clash": CATEGORIES, "beat-drop": HUM_CATEGORIES, "story-forge": STORY_CATEGORIES, "word-bomb": BOMB_CATEGORIES}
ALL_CATEGORIES = {**CATEGORIES, **HUM_CATEGORIES, **STORY_CATEGORIES, **BOMB_CATEGORIES}
KIND_FOR_MODE = {"battle": "question", "quickfire": "question", "namefast": "list", "association": "association", "hum": "song", "story": "spark", "bomb": "chunk"}
# Every game runs on a 20-second clock by default: fast enough to keep the room shouting. The host can change it.
ROUND_SECONDS = 20
DEFAULT_SECONDS = {mode: ROUND_SECONDS for mode in KIND_FOR_MODE}
# Word Bomb: the fuse is the round's seconds give or take this share, and nobody knows exactly when it blows.
FUSE_SPREAD = 0.4
DEFAULT_TEAM_NAMES = {"A": "Team Nova", "B": "Team Pulse"}

MAX_TEAM_ATTEMPTS = 3  # Brain Battle: tries per team per question
STEAL_SECONDS = 10
REVEAL_SECONDS = 6
HUM_SECONDS = 20  # Beat Drop: time to record the hum
VOTE_SECONDS = 12  # Story Forge: time to fire at the new line
STORY_REVEAL_SECONDS = 4
STREAK_AT = 3  # rounds in a row to be "on fire"
STREAK_BONUS = 5
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
    """One challenge in the bank. Beat Drop songs: `prompt` is what the hummer sees, `answer` the title,
    `items` the artists (["Wizkid", "Tems"]). Story Forge sparks: `answer` is the word every line must
    use, `accepted` its other forms, `prompt` the twist for that round. Word Bomb chunks: `prompt` and
    `answer` are the letters ("ANG"), `items` example words shown at the reveal."""

    id: str
    kind: Literal["question", "list", "association", "song", "spark", "chunk"]
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
    hum_bonus: int = Field(default=5, ge=0, le=50)  # Beat Drop: the hummer's team, when the song is guessed
    spark: int = Field(default=10, ge=0, le=100)  # Story Forge: a line that uses the spark word
    fire: int = Field(default=3, ge=0, le=50)  # Story Forge: each 🔥 from the other team
    bomb_word: int = Field(default=5, ge=0, le=50)  # Word Bomb: each word that passes the bomb on
    blast: int = Field(default=15, ge=0, le=100)  # Word Bomb: the team NOT holding the bomb when it blows


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
    "i believe it is", "i believe its", "i believe", "im sure it is", "im sure its", "im sure", "i am sure", "i know",
    "it should be", "should be", "it must be", "must be",
    "maybe", "um", "umm", "uh", "erm", "er", "hmm", "ok", "okay", "so", "well", "please", "abeg", "and",
    "oh", "ah", "eh", "ehn", "ehen", "oya", "omo", "chai", "haba", "my guy",
    # Nigerian Pidgin: "na Abuja" / "e be Abuja" / "I tink na Abuja" = "it's Abuja"
    "the answer na", "answer na", "i tink na", "i think na", "i tink", "na im be", "na him be", "e fit be", "e be", "na",
)
# Said after the answer: "Abuja o", "Abuja sha", "na Abuja be di answer".
TRAILERS = (
    "be di answer", "be the answer", "na di answer", "na the answer", "is the answer", "na im", "na him",
    "o", "oh", "sha", "abi", "jare", "now", "nau", "na", "ehn", "please", "abeg",
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
    # Strip "um, I think it's" / "na" and a trailing "please" / "o", but never the whole answer ("Please" is an
    # answer too). Answers go through the same steps, so an answer that starts or ends with one still matches.
    changed = True
    while changed:
        changed = False
        for f in FILLERS:
            fw = f.split()
            if words[: len(fw)] == fw and len(words) > len(fw):
                words = words[len(fw) :]
                changed = True
                break
        for f in TRAILERS:
            fw = f.split()
            if words[-len(fw) :] == fw and len(words) > len(fw):
                words = words[: -len(fw)]
                changed = True
                break
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
    if len(joined_w) >= 6 and SequenceMatcher(None, joined_s, joined_w).ratio() >= 0.88:
        return True
    # Said twice: "Abuja, Abuja!" (but "Last Last" is matched whole above).
    half = len(said) // 2
    return len(said) % 2 == 0 and said[:half] == said[half:] and same_answer(said[:half], want)


def answer_forms(q: Question) -> list[list[str]]:
    return [t for t in (tokens(a) for a in [q.answer, *q.accepted]) if t]


def song_title_heard(q: Question, heard: list[str]) -> list[str]:
    """Beat Drop: 'Essence by Wizkid', 'Wizkid Essence', 'essence wizkid and tems' all mean 'Essence'."""
    if "by" in heard[1:]:
        heard = heard[: heard.index("by", 1)]
    artists = {w for name in q.items for alt in name for w in tokens(alt)}
    while len(heard) > 1 and heard[0] in artists:
        heard = heard[1:]
    while len(heard) > 1 and heard[-1] in artists | {"and", "ft", "feat", "featuring"}:
        heard = heard[:-1]
    return heard


def judge_answer(q: Question, said: str) -> bool:
    """A single-answer question, a song or a word association: does what they said match an accepted answer?"""
    heard = tokens(said)
    if q.kind == "song":
        heard = song_title_heard(q, heard)
    forms = answer_forms(q) if q.kind in ("question", "song") else [t for item in q.items for t in (tokens(a) for a in item) if t]
    return any(same_answer(heard, form) for form in forms)


def uses_spark(q: Question, line: str) -> bool:
    """Story Forge: does the line use the spark word (or one of its forms) somewhere?"""
    heard = tokens(line)
    for form in answer_forms(q):
        n = len(form)
        if any(all(same_token(h, w) for h, w in zip(heard[j : j + n], form)) for j in range(len(heard) - n + 1)):
            return True
    return False


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


def vocabulary_hint(q: Question, pool: list[Question], rng: random.Random | None = None) -> str:
    """Words speech-to-text should expect for this round, so names it doesn't know ("Wizkid", "Abuja",
    "egusi") come out spelled right. The right answer is shuffled in among the answers to other questions
    in the same category, so the hint never points at it. (Tested with a robot voice: right answers heard
    went from 8/16 to 14/16, and no wrong answer was turned into a right one.)"""
    rng = rng or random.SystemRandom()
    if q.kind in ("question", "song"):
        words = [x.answer for x in pool if x.kind == q.kind and x.category == q.category]
        if q.answer not in words:
            words.append(q.answer)
    else:
        words = [item[0] for item in q.items]
    rng.shuffle(words)
    hint, used = "Quiz answers:", 0
    for w in words:
        if used + len(w) > 500:  # Whisper's prompt is limited (about 220 tokens)
            break
        hint += f" {w},"
        used += len(w) + 2
    return hint.rstrip(",") + "."


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
    flag_id: str | None = None  # held for the host to review (see Flag)
    note: str | None = None  # Word Bomb: why a word didn't count ("“bango” isn't in our dictionary.")


class Flag(BaseModel):
    """An answer, hum or line the fair-play detector thinks may be cheating. Its points wait here until
    the host allows (they're added) or voids it (they're dropped)."""

    id: str
    round: int
    user_id: int
    player: str
    team: TeamId
    kind: Literal["answer", "hum", "line"]
    said: str
    reasons: list[str]
    suspicion: float
    held: dict[str, int] = {}  # team -> points waiting
    held_players: dict[str, int] = {}  # user id -> points waiting
    status: Literal["pending", "allowed", "voided"] = "pending"


class StoryLine(BaseModel):
    round: int
    team: TeamId
    player: str
    user_id: int
    line: str
    spark: str
    used_spark: bool
    fires: int = 0


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
    performer_id: int | None = None  # Beat Drop's hummer, Story Forge's writer
    has_clip: bool = False  # Beat Drop: the hum is ready to play
    line: str | None = None  # Story Forge: this round's line
    fired: list[int] = []  # Story Forge: who has fired at the line
    flag_id: str | None = None  # a hum or line under review: this round's points wait in that flag


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
    streaks: dict[str, int] = {"A": 0, "B": 0}  # rounds won in a row
    flags: list[Flag] = []
    story: list[StoryLine] = []  # Story Forge: the story so far
    opener: str | None = None  # Story Forge: the game's first line
    used_words: list[str] = []  # Word Bomb: each word counts once a game
    bomb_turns: dict[str, int] = {"A": 0, "B": 0}  # Word Bomb: how often each team has held the bomb (for its rotation)
    finish_reason: str | None = None
    notice: str | None = None  # e.g. "Only 6 questions match those categories"
    # The party screen (a TV or laptop everyone watches) opens the room with this instead of signing in.
    # Only the host is shown it, so nobody can guess their way onto another room's screen.
    screen_key: str = Field(default_factory=lambda: secrets.token_urlsafe(12))
    created_at: datetime
    updated_at: datetime

    def screen_key_ok(self, key: str) -> bool:
        return bool(key) and hmac.compare_digest(key.encode(), self.screen_key.encode())

    def player(self, user_id: int) -> Player | None:
        return next((p for p in self.players if p.user_id == user_id), None)

    def team(self, team: TeamId) -> list[Player]:
        return [p for p in self.players if p.team == team]

    def rounds_total(self) -> int:
        return max(0, len(self.plan) - 1)  # the reserve tie-breaker isn't a regular round

    def flag(self, flag_id: str | None) -> Flag | None:
        return next((f for f in self.flags if f.id == flag_id), None)

    def performer(self) -> Player | None:
        return self.player(self.round.performer_id) if self.round and self.round.performer_id else None


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
    room.streaks, room.flags, room.story = {"A": 0, "B": 0}, [], []
    room.used_words, room.bomb_turns = [], {"A": 0, "B": 0}
    if room.settings.mode == "story":
        room.opener = random.SystemRandom().choice(STORY_OPENERS.get(plan[0].category) or STORY_OPENERS["story_chaos"])
    room.round_index = 0
    open_round(room, at or now())


def performer_for(room: BrainClashRoom, number: int) -> Player:
    """Beat Drop and Story Forge: the teams take turns, and within a team everyone gets a go in join order."""
    team: TeamId = "A" if number % 2 else "B"
    members = room.team(team)
    return members[((number - 1) // 2) % len(members)]


def next_bomber(room: BrainClashRoom, team: TeamId) -> Player:
    """Word Bomb: the next player on this team to get the bomb (everyone gets a go, in join order)."""
    members = room.team(team)
    turn = room.bomb_turns.get(team, 0)
    room.bomb_turns[team] = turn + 1
    return members[turn % len(members)]


def open_round(room: BrainClashRoom, at: datetime, tiebreak: bool = False, rng: random.Random | None = None) -> None:
    number = room.round_index + 1
    s = room.settings
    turn: TeamId | None = None
    if s.mode == "battle" and not tiebreak:
        turn = "A" if number % 2 else "B"
    performer = performer_for(room, number) if s.mode in ("hum", "story") else None
    seconds: float = HUM_SECONDS if s.mode == "hum" else s.round_seconds()
    if s.mode == "bomb":
        performer = next_bomber(room, "A" if number % 2 else "B")  # the teams take turns to start with the bomb
        seconds *= (rng or random.SystemRandom()).uniform(1 - FUSE_SPREAD, 1 + FUSE_SPREAD)
    room.round = Round(
        number=number,
        question=room.plan[room.round_index],
        phase="hum" if s.mode == "hum" else "open",
        opened_at=at,
        closes_at=at + timedelta(seconds=seconds),
        turn_team=performer.team if performer else turn,
        found={"A": [], "B": []},
        tiebreak=tiebreak,
        performer_id=performer.user_id if performer else None,
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
    if mode == "hum":
        if r.phase == "hum":
            raise GameError("Wait for the hum!")
        if player.user_id == r.performer_id:
            raise GameError("You're the hummer. No guessing your own song!")
    if mode == "story":
        if r.phase != "open":
            raise GameError("The line is in. Fire at it if you love it!")
        if player.user_id != r.performer_id:
            raise GameError(f"It's {room.performer().name}'s line.", 403)
        return
    if mode == "bomb":
        if player.user_id != r.performer_id:
            raise GameError(f"{room.performer().name} has the bomb!", 403)
        return
    if mode == "hum" and r.turn_team and player.team != r.turn_team:
        raise GameError(f"It's {room.settings.team_names[r.turn_team]}'s turn to guess.", 403)
    if mode == "hum" and r.attempts.get(player.team, 0) >= MAX_TEAM_ATTEMPTS:
        raise GameError("Your team has used all its guesses on this song.")
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


def book(room: BrainClashRoom, team: TeamId, player: Player | None, points: int, flag: Flag | None) -> None:
    """Add points to a team (and player), or hold them in a flag that's waiting for review."""
    if not points:
        return
    if flag is not None and flag.status == "pending":
        flag.held[team] = flag.held.get(team, 0) + points
        if player:
            flag.held_players[str(player.user_id)] = flag.held_players.get(str(player.user_id), 0) + points
        return
    room.scores[team] += points
    if player:
        player.points += points


def raise_flag(room: BrainClashRoom, player: Player, kind: str, said: str, signs: list[fairplay.Sign]) -> Flag | None:
    """Open a flag when the detector's suspicion reaches fairplay.FLAG_AT."""
    level = fairplay.suspicion(signs)
    if level < fairplay.FLAG_AT:
        return None
    flag = Flag(
        id=secrets.token_hex(4),
        round=room.round.number,
        user_id=player.user_id,
        player=player.name,
        team=player.team,
        kind=kind,
        said=said[:200],
        reasons=[s.reason for s in signs],
        suspicion=level,
    )
    room.flags.append(flag)
    return flag


def submit_answer(
    room: BrainClashRoom,
    user_id: int,
    said: str,
    round_number: int,
    received: datetime,
    signals: fairplay.Signals | None = None,
) -> FeedItem:
    """Score one answer. `received` is when the request arrived (before any speech-to-text), so slow
    transcription never costs a player the round. Raises GameError for anything the rules don't allow.
    `signals` (what the browser saw) feed the fair-play detector; a suspicious right answer's points
    are held for the host."""
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
    signals = signals or fairplay.Signals()
    item = FeedItem(round=r.number, team=team, player=player.name, user_id=user_id, said=said, verdict="wrong")
    if mode == "story":
        return _submit_line(room, player, said, received, signals)
    if mode == "bomb":
        return _submit_word(room, player, said, received, signals)
    close = False
    round_flag = room.flag(r.flag_id)  # Beat Drop: a hum under review holds the whole round's points

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
        if mode in ("battle", "hum"):
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
        elif mode in ("battle", "hum") and r.attempts[team] >= MAX_TEAM_ATTEMPTS:
            close = not _start_steal(room, received)
        elif mode == "quickfire" and all(p.user_id in r.tried for p in room.players):
            close = True  # everyone has had a go
        elif mode == "association" and all(p.user_id in r.tried for p in room.players if p.team not in r.scored):
            close = True

    if item.points:
        rival = next((f.player for f in reversed(room.feed) if f.round == r.number and f.team != team and f.said.lower() == said.lower() and len(said) >= 5), None)
        flag = round_flag or raise_flag(room, player, "answer", said, fairplay.answer_signs(signals, said, True, r.opened_at, received, rival))
        if flag is not None:
            item.flag_id = flag.id
        book(room, team, player, item.points, flag)
        r.scored[team] = r.scored.get(team, 0) + item.points
        player.correct += 1
        if mode == "hum" and item.verdict == "correct" and room.performer():
            hummer = room.performer()  # a hum good enough to guess earns its team a bonus
            book(room, hummer.team, hummer, room.settings.scoring.hum_bonus, round_flag)
            r.scored[hummer.team] = r.scored.get(hummer.team, 0) + room.settings.scoring.hum_bonus
    room.feed = [*room.feed, item][-FEED_SIZE:]
    if close:
        close_round(room, received)
    return item


def submit_hum(room: BrainClashRoom, user_id: int, round_number: int, heard: str, at: datetime) -> Flag | None:
    """Beat Drop: the hummer's clip is in (the router keeps the audio). Open the guessing.
    `heard` is what Whisper made of the hum; the title said out loud is flagged."""
    r = room.round
    if room.status != "playing" or r is None or r.number != round_number:
        raise GameError("That round has already gone.")
    if r.phase != "hum":
        raise GameError("The hum is already in.")
    if user_id != r.performer_id:
        raise GameError("It's not your turn to hum.", 403)
    hummer = room.player(user_id)
    title = [w for form in answer_forms(r.question) for w in form]
    flag = raise_flag(room, hummer, "hum", heard or "(humming)", fairplay.hum_signs(title, tokens(heard)))
    r.flag_id = flag.id if flag else None
    r.has_clip = True
    r.phase = "open"
    r.opened_at = at
    r.closes_at = at + timedelta(seconds=room.settings.round_seconds())
    # The hummer's teammates guess first. A hummer with no teammates hands the guessing to the other team.
    if not [p for p in room.team(hummer.team) if p.user_id != user_id]:
        r.turn_team = other(hummer.team)
    return flag


def _submit_line(room: BrainClashRoom, player: Player, line: str, at: datetime, signals: fairplay.Signals) -> FeedItem:
    """Story Forge: the writer's line goes into the story; then the other team may fire at it."""
    r = room.round
    words = line.split()
    if len(words) < 3:
        raise GameError("Give us a whole line: at least three words.", 422)
    line = " ".join(words[:40])
    q = r.question
    used = uses_spark(q, line)
    item = FeedItem(round=r.number, team=player.team, player=player.name, user_id=player.user_id, said=line, verdict="line")
    flag = raise_flag(room, player, "line", line, fairplay.line_signs(line, [s.line for s in room.story], signals))
    r.flag_id = flag.id if flag else None
    if used:
        item.points = room.settings.scoring.spark
        book(room, player.team, player, item.points, flag)
        r.scored[player.team] = item.points
        player.correct += 1
    item.flag_id = r.flag_id
    room.story.append(StoryLine(round=r.number, team=player.team, player=player.name, user_id=player.user_id, line=line, spark=q.answer, used_spark=used))
    r.line = line
    r.phase = "vote"
    r.closes_at = at + timedelta(seconds=VOTE_SECONDS)
    room.feed = [*room.feed, item][-FEED_SIZE:]
    return item


def _submit_word(room: BrainClashRoom, player: Player, said: str, at: datetime, signals: fairplay.Signals) -> FeedItem:
    """Word Bomb: a real word with the letters scores and passes the bomb to the other team. A miss keeps
    it in your hands. The answering player is told why a word didn't count; the room only sees that it missed,
    so nothing typed in anger reaches the party screen."""
    from . import words  # the dictionary loads on first use, not at import

    r = room.round
    result = words.check(said, r.question.answer, room.used_words)
    item = FeedItem(round=r.number, team=player.team, player=player.name, user_id=player.user_id, said=said,
                    verdict=result.verdict, note=result.note)
    if result.word:
        item.said = result.word
        item.points = room.settings.scoring.bomb_word
        room.used_words.append(result.word)
        flag = raise_flag(room, player, "answer", said, fairplay.answer_signs(signals, said, True, r.opened_at, at, None))
        item.flag_id = flag.id if flag else None
        book(room, player.team, player, item.points, flag)
        r.scored[player.team] = r.scored.get(player.team, 0) + item.points
        player.correct += 1
        holder = next_bomber(room, other(player.team))
        r.performer_id, r.turn_team = holder.user_id, holder.team
        room.feed = [*room.feed, item][-FEED_SIZE:]
    else:
        room.feed = [*room.feed, item.model_copy(update={"said": "…", "note": None})][-FEED_SIZE:]
    return item


def _explode(room: BrainClashRoom, at: datetime) -> None:
    """Word Bomb: the fuse ran out. Whoever holds the bomb loses the round; the other team takes the blast bonus."""
    r = room.round
    holder = room.performer()
    if holder is None:
        return
    winner = other(holder.team)
    pts = room.settings.scoring.blast
    book(room, winner, None, pts, None)
    r.scored[winner] = r.scored.get(winner, 0) + pts
    r.winner_team = winner
    boom = FeedItem(round=r.number, team=holder.team, player=holder.name, user_id=holder.user_id, said="💥", verdict="boom")
    room.feed = [*room.feed, boom][-FEED_SIZE:]


def fire(room: BrainClashRoom, user_id: int, round_number: int) -> None:
    """Story Forge: someone on the other team loves the line. Each fire scores for the writer's team."""
    r = room.round
    voter = room.player(user_id)
    if voter is None:
        raise GameError("Join this room first.", 403)
    if room.status != "playing" or r is None or r.number != round_number or r.phase != "vote":
        raise GameError("There's no line to fire at right now.")
    writer = room.performer()
    if voter.team == writer.team:
        raise GameError("Only the other team can fire. No hyping your own team!", 403)
    if user_id in r.fired:
        raise GameError("You've already fired at this line.")
    r.fired.append(user_id)
    pts = room.settings.scoring.fire
    book(room, writer.team, writer, pts, room.flag(r.flag_id))
    r.scored[writer.team] = r.scored.get(writer.team, 0) + pts
    room.story[-1].fires += 1


def decide_flag(room: BrainClashRoom, user_id: int, flag_id: str, allow: bool) -> Flag:
    """The host (or, when the host is the one flagged, anyone on the other team) allows or voids a flag."""
    flag = room.flag(flag_id)
    if flag is None:
        raise GameError("No such flag.", 404)
    if flag.status != "pending":
        raise GameError("That one has already been decided.")
    judge = room.player(user_id)
    host_flagged = flag.user_id == room.host_id
    if judge is None or (host_flagged and judge.team == flag.team) or (not host_flagged and user_id != room.host_id):
        raise GameError("The host decides flags (the other team does when the host is flagged).", 403)
    flag.status = "allowed" if allow else "voided"
    if allow:
        for team, pts in flag.held.items():
            room.scores[team] += pts
        for uid, pts in flag.held_players.items():
            p = room.player(int(uid))
            if p:
                p.points += pts
    if room.status == "finished":
        a, b = room.scores["A"], room.scores["B"]
        room.winner = "A" if a > b else "B" if b > a else "draw"
    return flag


def _start_steal(room: BrainClashRoom, at: datetime) -> bool:
    """Brain Battle: the turn team missed. Hand the question to the other team, if steals are on."""
    r = room.round
    if not room.settings.steals or r.phase != "open" or r.turn_team is None:
        return False
    if room.settings.mode == "hum" and not [p for p in room.team(other(r.turn_team)) if p.user_id != r.performer_id]:
        return False  # nobody on the other side can guess
    r.phase = "steal"
    r.turn_team = other(r.turn_team)
    r.closes_at = at + timedelta(seconds=STEAL_SECONDS)
    return True


def close_round(room: BrainClashRoom, at: datetime) -> None:
    r = room.round
    r.phase = "reveal"
    r.reveal_until = at + timedelta(seconds=STORY_REVEAL_SECONDS if room.settings.mode == "story" else REVEAL_SECONDS)
    if room.settings.mode != "story":
        _streaks(room)
    room.history.append(RoundSummary(number=r.number, prompt=r.question.prompt, answer=r.question.answer, scored=dict(r.scored), tiebreak=r.tiebreak))


def _streaks(room: BrainClashRoom) -> None:
    """Three rounds won in a row and a team is on fire: +STREAK_BONUS for every round it keeps winning."""
    r = room.round
    for team in ("A", "B"):
        # Word Bomb: both teams score words in a round; the round goes to the team that wasn't left holding it.
        won = r.winner_team == team if room.settings.mode == "bomb" else r.scored.get(team)
        if won:
            room.streaks[team] = room.streaks.get(team, 0) + 1
            if room.streaks[team] >= STREAK_AT:
                book(room, team, None, STREAK_BONUS, room.flag(r.flag_id))
                r.scored[team] += STREAK_BONUS
                name = room.settings.team_names[team]
                room.feed = [*room.feed, FeedItem(round=r.number, team=team, player=name, user_id=0, said=f"{room.streaks[team]} in a row!", verdict="streak", points=STREAK_BONUS)][-FEED_SIZE:]
        else:
            room.streaks[team] = 0


def advance(room: BrainClashRoom, at: datetime, by_host: bool = False) -> None:
    """Move the game on when its clock says so (or, between rounds, when the host says so)."""
    r = room.round
    if room.status != "playing" or r is None:
        raise GameError("The game isn't running.")
    if r.phase in ("hum", "open", "steal", "vote"):
        if at <= r.closes_at + timedelta(seconds=GRACE_SECONDS):
            raise GameError("Not yet!")
        if r.phase == "open" and room.settings.mode in ("battle", "hum") and r.winner_team is None and _start_steal(room, at):
            return
        if room.settings.mode == "bomb":
            _explode(room, at)
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
    no_tiebreak = s.mode in ("hum", "story")  # their rounds belong to one player: a level game is a draw
    if r.tiebreak or ((reached or last) and (not tied or no_tiebreak)):
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
    leaving = room.player(user_id)
    room.players = [p for p in room.players if p.user_id != user_id]
    r = room.round
    if room.status == "playing" and room.settings.mode == "bomb" and r and r.performer_id == user_id and leaving and room.team(leaving.team):
        holder = next_bomber(room, leaving.team)  # you can't run off with the bomb: a teammate catches it
        r.performer_id = holder.user_id
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

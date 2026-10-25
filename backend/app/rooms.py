"""Voice game rooms: who's in, whose turn it is, and the score of each turn.

A room lives in the shared store (Redis) as JSON, so every API instance sees
the same game, and it disappears ROOM_TTL_HOURS after its last change. Every
change is published on the room's channel (and the dashboard's), and the
WebSocket endpoint passes it on to the players' browsers.

The server works out every score itself from the voice check. The browser only
sends the recording, so nobody can send themselves 1,000 points.

Game types
----------
- yourself:    the AI must recognise you.
- impersonate: sound like another player; +50 if you fool the AI. With "humans vs
               AI" on, the other players rate each impression (1-5 stars) before
               the AI's verdict is revealed, and the stars score too.
- disguise:    the opposite of yourself: say the line so the AI does NOT know it's
               you. +25 if it pins it on another player.
- guess:       "Guess Who". A secretly chosen player speaks, everyone else hears
               the clip and votes on who it was. Right guesses +50; the speaker
               gets +25 for everyone they fooled. The AI guesses too, for fun.
- telephone:   broken telephone. The first player in a chain speaks in any voice
               they like; each next player hears the clip before theirs and copies
               that voice. Points = how close the copy is; the chain shows how far
               the voice drifted from where it started.

Options (any type): speed rounds (20 seconds a turn, a bonus for being quick, a
turn that runs out of time scores 0), twists (a silly style for every turn, worth
x1.5 in Be yourself), a final round worth double, and the end-of-game replay
(each turn's clip is kept for an hour so the best bits can be played back).
"""

from __future__ import annotations

import random
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel

from .schemas import LivenessOut
from .store import Store

Mode = Literal["yourself", "impersonate", "disguise", "guess", "telephone"]
Status = Literal["lobby", "playing", "finished"]
Phase = Literal["speak", "vote", "rate"]  # vote: Guess Who; rate: humans vs AI

IMPERSONATION_BONUS = 50
FRAMED_BONUS = 25  # disguise: the AI thinks you're another player
GUESS_RIGHT = 50  # for each player who names the speaker
GUESS_FOOLED = 25  # for the speaker, per player who got it wrong
CHAIN_START_POINTS = 20  # telephone: for setting the voice everyone else copies
POINTS_PER_STAR = 10  # humans vs AI: the average rating x 10 (up to 50)
TWIST_MULTIPLIER = 1.5  # Be yourself with a twist: a silly voice is harder to recognise
SPEED_SECONDS = 20  # per turn in a speed round
VOTE_SECONDS = 30  # to vote in Guess Who
RATE_SECONDS = 25  # to rate an impression
GRACE_SECONDS = 5  # uploads take a moment: don't skip a turn that's just arriving
MAX_PLAYERS = 12
ROOMS_INDEX = "rooms"  # set of room codes that may still exist
REACTIONS = ("😂", "🔥", "👏", "😮", "🤔", "😱", "💯", "🎉")

# Only styles that keep the words clear enough for the live check.
TWISTS = (
    "🤫 Whisper it",
    "🐭 In a squeaky voice",
    "🐻 In a deep, deep voice",
    "🎵 Sing it",
    "🏴‍☠️ Like a pirate",
    "📺 Like a news reader",
    "🤖 Like a robot",
    "🐢 In slow motion",
    "⚽ Like a football commentator",
    "🎩 Very, very posh",
    "🤧 With a terrible cold",
    "🤭 Trying not to laugh",
)

# Short words that are easy to say and spell, for codes like "TIGER-42".
CODE_WORDS = (
    "apple", "river", "tiger", "mango", "rocket", "candle", "dragon", "castle",
    "banana", "planet", "forest", "button", "island", "silver", "orange", "pencil",
)


def now() -> datetime:
    return datetime.now(timezone.utc)


class RoomPlayer(BaseModel):
    user_id: int
    username: str
    speaker_id: int
    country: str | None = None
    points: int = 0
    turns: int = 0


class Turn(BaseModel):
    player_id: int  # user ids
    # Who they must sound like: themselves in yourself/disguise/guess, another player in
    # impersonate, the player before them in telephone.
    target_id: int
    twist: str | None = None  # one of TWISTS
    double: bool = False  # the final round counts double
    chain_start: bool = False  # telephone: the first voice of a chain


class TurnResult(BaseModel):
    turn_number: int  # 1-based
    player_id: int
    player: str
    target: str
    points: int
    message: str  # what the announcer says
    liveness: LivenessOut | None = None
    speed_bonus: int = 0
    twist: str | None = None
    double: bool = False
    # How much the clip sounded like each player in the room (0-100), best first.
    sounded_like: dict[str, int] = {}
    score: float | None = None  # the voice score behind the points (None: no voice check)
    has_clip: bool = False  # can be played back in the replay
    # Guess Who
    votes: dict[str, str] = {}  # voter -> who they named
    ai_guess: str | None = None
    points_by_player: dict[str, int] = {}  # everyone who scored this turn
    # Humans vs AI
    stars: dict[str, int] = {}  # rater -> 1..5
    ai_points: int | None = None
    crowd_points: int = 0
    # Telephone: how much this clip still sounds like the chain's first voice (0-100)
    chain_from: str | None = None
    drift: int | None = None


class Highlight(BaseModel):
    """One of the end-of-game awards, e.g. 'Worst impression', with the clip to replay."""

    emoji: str
    title: str
    player: str
    detail: str
    turn_number: int
    has_clip: bool = False


class Pending(BaseModel):
    """A recorded turn waiting for the vote (Guess Who) or the ratings (humans vs AI)."""

    points: int = 0  # what the AI gave it
    message: str = ""
    liveness: LivenessOut | None = None
    score: float | None = None
    bonus: int = 0  # speed bonus, from when the recording arrived
    sounded_like: dict[str, int] = {}
    ai_guess: str | None = None


class Room(BaseModel):
    code: str
    host_id: int
    mode: Mode = "yourself"
    rounds: int = 2
    speed: bool = False
    twists: bool = False
    crowd: bool = False  # impersonate: humans vs AI ratings
    double_final: bool = False
    replay: bool = True  # keep each turn's clip for an hour for the replay
    status: Status = "lobby"
    game_no: int = 0  # +1 for every start (rematches are new games)
    players: list[RoomPlayer] = []
    plan: list[Turn] = []
    turn_index: int = 0
    turn_started_at: datetime | None = None
    last_result: TurnResult | None = None
    history: list[TurnResult] = []  # this game's turns so far
    highlights: list[Highlight] = []  # worked out when the game finishes
    # Between the recording and the reveal (Guess Who votes, humans-vs-AI ratings)
    phase: Phase = "speak"
    votes: dict[int, int] = {}  # voter id -> suspect id (vote) or stars (rate)
    vote_deadline: datetime | None = None
    # The clip players may listen to right now: Guess Who's mystery clip, the impression
    # being rated, or (telephone) the voice to copy. In the store, never in the room.
    clip_key: str | None = None
    clip_type: str = "audio/webm"
    pending: Pending | None = None
    # Telephone: the voiceprints of the chain's first voice and of its latest copy.
    chain_origin: list[float] | None = None
    chain_last: list[float] | None = None
    created_at: datetime
    updated_at: datetime

    def player(self, user_id: int) -> RoomPlayer | None:
        return next((p for p in self.players if p.user_id == user_id), None)

    def active_turn(self) -> Turn | None:
        return self.plan[self.turn_index] if self.status == "playing" and self.turn_index < len(self.plan) else None

    def turn_deadline(self) -> datetime | None:
        """When the current turn runs out (speed rounds, Guess Who voting, rating)."""
        if self.status != "playing":
            return None
        if self.phase in ("vote", "rate"):
            return self.vote_deadline
        if self.speed and self.turn_started_at:
            return self.turn_started_at + timedelta(seconds=SPEED_SECONDS)
        return None


def new_code() -> str:
    """Easy to read out loud, e.g. 'TIGER-42'."""
    return f"{secrets.choice(CODE_WORDS).upper()}-{secrets.randbelow(90) + 10}"


def min_players(mode: Mode) -> int:
    return 3 if mode in ("guess", "telephone") else 2


def plan_turns(
    players: list[RoomPlayer],
    mode: Mode,
    rounds: int,
    rng: random.Random | None = None,
    *,
    twists: bool = False,
    double_final: bool = False,
) -> list[Turn]:
    """Everyone takes one turn per round. Impersonators get a random other player.

    In Guess Who the order is shuffled every round, so nobody can work out who's next.
    In telephone each round is one chain, started by a different player each time.
    """
    rng = rng or random.Random()
    plan = []
    for r in range(rounds):
        order = list(players)
        if mode == "guess":
            rng.shuffle(order)
        if mode == "telephone":
            shift = r % len(order)
            order = order[shift:] + order[:shift]
        for i, p in enumerate(order):
            if mode == "impersonate":
                target = rng.choice([o for o in players if o.user_id != p.user_id])
            elif mode == "telephone" and i > 0:
                target = order[i - 1]
            else:
                target = p
            plan.append(
                Turn(
                    player_id=p.user_id,
                    target_id=target.user_id,
                    twist=rng.choice(TWISTS) if twists else None,
                    double=double_final and rounds > 1 and r == rounds - 1,
                    chain_start=mode == "telephone" and i == 0,
                )
            )
    return plan


def start_game(room: Room) -> None:
    for p in room.players:
        p.points, p.turns = 0, 0
    room.plan = plan_turns(room.players, room.mode, room.rounds, twists=room.twists, double_final=room.double_final)
    room.turn_index, room.last_result, room.status = 0, None, "playing"
    room.history, room.highlights = [], []
    room.chain_origin = room.chain_last = None
    room.game_no += 1
    reset_turn(room)


def reset_turn(room: Room, keep_clip: bool = False) -> None:
    room.turn_started_at = now()
    room.phase, room.votes, room.vote_deadline, room.pending = "speak", {}, None, None
    if not keep_clip:
        room.clip_key = None


def speed_bonus(room: Room, points: int, at: datetime | None = None) -> int:
    """Up to +20 for answering fast in a speed round (only for turns that scored)."""
    if not room.speed or points <= 0 or room.turn_started_at is None:
        return 0
    used = ((at or now()) - room.turn_started_at).total_seconds()
    return max(0, round(SPEED_SECONDS - used))


def pct(score: float) -> int:
    return max(0, round(score * 100))


def score_yourself(player: str, player_speaker_id: int, recognised_id: int | None, recognised: str, score: float) -> tuple[int, str]:
    """'Be yourself': points = how sure the AI is it's you (0-100), only if it picked you."""
    points = pct(score)
    if recognised_id == player_speaker_id:
        comment = "Unmistakably you!" if score >= 0.7 else "Definitely you." if score >= 0.55 else "Just about you."
        return points, f"That's {player}! {points} points. {comment}"
    if recognised_id is not None:
        return 0, f"The machine thinks that was {recognised}! No points for {player}."
    return 0, f"The machine doesn't recognise that voice. No points for {player}."


def score_impersonation(player: str, target: str, score: float, fooled: bool) -> tuple[int, str]:
    """'Impersonate': points = how much you sound like the target, +50 if you fool the AI."""
    points = pct(score)
    if fooled:
        total = points + IMPERSONATION_BONUS
        return total, f"Wow! {player} fooled the machine as {target}! {total} points."
    return points, f"{player} sounds {points}% like {target}. {points} points."


def score_disguise(player: str, own_score: float, framed: str | None) -> tuple[int, str]:
    """'Disguise': points = how much you DON'T sound like yourself, +25 if the AI blames someone else."""
    you = pct(own_score)
    points = max(0, 100 - you)
    if framed:
        total = points + FRAMED_BONUS
        return total, f"Sneaky! The machine thinks that was {framed}, not {player}. {total} points."
    comment = "Nobody would know!" if you < 25 else "Not bad." if you < 50 else "We can still hear you in there."
    return points, f"{player} sounds {you}% like {player}. {points} points. {comment}"


def score_copy(player: str, copied: str, score: float) -> tuple[int, str]:
    """Telephone: points = how close the copy is to the voice before it."""
    points = pct(score)
    return points, f"{player} copied {copied}'s voice {points}%. {points} points."


def failed_liveness(player: str) -> tuple[int, str]:
    return 0, f"{player}, the live check failed. Say the line on screen. No points."


def multiply(room: Room, turn: Turn, points: int, message: str) -> tuple[int, str]:
    """Twist (Be yourself only) and final-round multipliers, applied to a turn's own points."""
    if points <= 0:
        return points, message
    if turn.twist and room.mode == "yourself":
        points = round(points * TWIST_MULTIPLIER)
        message += f" Twist bonus: x{TWIST_MULTIPLIER:g}, so {points}!"
    if turn.double:
        points *= 2
        message += f" Final round, double points: {points}!"
    return points, message


def chain_origin_name(room: Room) -> str | None:
    """Telephone: who started the chain the current turn belongs to."""
    start = next((room.plan[i] for i in range(room.turn_index, -1, -1) if room.plan[i].chain_start), None)
    first = room.player(start.player_id) if start else None
    return first.username if first else None


def _finish_turn(room: Room, result: TurnResult) -> None:
    room.last_result = result
    room.history.append(result)
    room.turn_index += 1
    if room.turn_index >= len(room.plan):
        room.status = "finished"
        room.highlights = highlights(room)
    # Telephone: the next player copies this chain's latest voice, unless a new chain starts.
    nxt = room.active_turn()
    reset_turn(room, keep_clip=room.mode == "telephone" and nxt is not None and not nxt.chain_start)


def apply_turn(
    room: Room,
    points: int,
    message: str,
    liveness: LivenessOut | None,
    bonus: int = 0,
    *,
    score: float | None = None,
    sounded_like: dict[str, int] | None = None,
    has_clip: bool = False,
    stars: dict[str, int] | None = None,
    crowd_points: int = 0,
    ai_points: int | None = None,
    drift: int | None = None,
) -> None:
    """Book the current turn's result and move on (finishing the game after the last turn)."""
    turn = room.active_turn()
    assert turn is not None
    player, target = room.player(turn.player_id), room.player(turn.target_id)
    points, message = multiply(room, turn, points, message)
    total = points + bonus
    player.points += total
    player.turns += 1
    if bonus:
        message += f" Plus {bonus} for speed!"
    origin = chain_origin_name(room) if room.mode == "telephone" else None
    _finish_turn(
        room,
        TurnResult(
            turn_number=room.turn_index + 1,
            player_id=player.user_id,
            player=player.username,
            target=target.username if target else player.username,
            points=total,
            message=message,
            liveness=liveness,
            speed_bonus=bonus,
            twist=turn.twist,
            double=turn.double,
            sounded_like=sounded_like or {},
            score=score,
            has_clip=has_clip,
            points_by_player={player.username: total} if total else {},
            stars=stars or {},
            crowd_points=crowd_points,
            ai_points=ai_points,
            chain_from=origin,
            drift=drift,
        ),
    )


def open_voting(room: Room, clip_key: str, clip_type: str, pending: Pending) -> None:
    """Guess Who: the secret speaker has recorded; everyone else has VOTE_SECONDS to vote."""
    room.phase = "vote"
    room.clip_key, room.clip_type, room.pending = clip_key, clip_type, pending
    room.vote_deadline = now() + timedelta(seconds=VOTE_SECONDS)
    room.votes = {}


def open_rating(room: Room, clip_key: str, clip_type: str, pending: Pending) -> None:
    """Humans vs AI: the impression is in; the others rate it before the AI's verdict is shown."""
    room.phase = "rate"
    room.clip_key, room.clip_type, room.pending = clip_key, clip_type, pending
    room.vote_deadline = now() + timedelta(seconds=RATE_SECONDS)
    room.votes = {}


def voters(room: Room) -> list[RoomPlayer]:
    turn = room.active_turn()
    return [p for p in room.players if turn and p.user_id != turn.player_id]


def everyone_voted(room: Room) -> bool:
    return all(p.user_id in room.votes for p in voters(room))


def reveal(room: Room, has_clip: bool = False) -> dict[int, int]:
    """Guess Who: show who it was and give out the points. Returns points per user id."""
    turn = room.active_turn()
    assert turn is not None
    pending = room.pending or Pending()
    speaker = room.player(turn.player_id)
    names = {p.user_id: p.username for p in room.players}
    right = [p for p in voters(room) if room.votes.get(p.user_id) == speaker.user_id]
    fooled = len(voters(room)) - len(right)
    points = {p.user_id: GUESS_RIGHT for p in right}
    points[speaker.user_id] = GUESS_FOOLED * fooled
    if turn.double:
        points = {uid: pts * 2 for uid, pts in points.items()}
    for uid, pts in points.items():
        room.player(uid).points += pts
    speaker.turns += 1

    if right:
        guessed = f"{', '.join(p.username for p in right)} guessed right"
    else:
        guessed = "Nobody guessed it"
    ai = f" The AI guessed {pending.ai_guess}." if pending.ai_guess else ""
    double = " Final round, double points!" if turn.double and any(points.values()) else ""
    message = f"It was {speaker.username}! {guessed}. {speaker.username} fooled {fooled}.{ai}{double}"
    _finish_turn(
        room,
        TurnResult(
            turn_number=room.turn_index + 1,
            player_id=speaker.user_id,
            player=speaker.username,
            target=speaker.username,
            points=points[speaker.user_id],
            message=message,
            liveness=pending.liveness,
            twist=turn.twist,
            double=turn.double,
            sounded_like=pending.sounded_like,
            score=pending.score,
            has_clip=has_clip,
            votes={names[v]: names.get(s, "?") for v, s in room.votes.items() if v in names},
            ai_guess=pending.ai_guess,
            points_by_player={names[uid]: pts for uid, pts in points.items() if pts},
        ),
    )
    return points


def crowd_verdict(room: Room, has_clip: bool = False) -> int:
    """Humans vs AI: add the stars to the AI's points and reveal both. Returns the impersonator's total."""
    pending = room.pending or Pending()
    names = {p.user_id: p.username for p in room.players}
    stars = {names[v]: s for v, s in room.votes.items() if v in names}
    avg = sum(stars.values()) / len(stars) if stars else 0.0
    crowd = round(avg * POINTS_PER_STAR)
    machine = pct(pending.score or 0.0)
    if stars:
        message = f"{pending.message} You lot gave it {avg:.1f} stars: +{crowd}."
        if avg >= 4 and machine < 30:
            message += " The humans loved it. The machine did not!"
        elif avg <= 2 and pending.points > IMPERSONATION_BONUS:
            message += " The machine was fooled, but you weren't!"
    else:
        message = f"{pending.message} Nobody rated it."
    apply_turn(
        room,
        pending.points + crowd,
        message,
        pending.liveness,
        pending.bonus,
        score=pending.score,
        sounded_like=pending.sounded_like,
        has_clip=has_clip,
        stars=stars,
        crowd_points=crowd,
        ai_points=pending.points,
    )
    return room.last_result.points


def highlights(room: Room) -> list[Highlight]:
    """The end-of-game awards, from this game's turns. Turns without a voice check don't count."""
    scored = [r for r in room.history if r.score is not None and (r.liveness is None or r.liveness.passed)]
    out: list[Highlight] = []

    def award(emoji: str, title: str, r: TurnResult | None, detail: str) -> None:
        if r is not None:
            out.append(Highlight(emoji=emoji, title=title, player=r.player, detail=detail, turn_number=r.turn_number, has_clip=r.has_clip))

    best = max(scored, key=lambda r: r.score, default=None)
    worst = min(scored, key=lambda r: r.score, default=None)
    if room.mode == "disguise":
        best, worst = worst, best  # the less like yourself, the better
    if worst is best:
        worst = None  # a single scored turn only gets the good award
    if room.mode == "yourself":
        award("💯", "Most you", best, f"{pct(best.score)}% themselves" if best else "")
        award("🫥", "Identity crisis", worst, f"only {pct(worst.score)}% themselves" if worst else "")
    elif room.mode == "impersonate":
        award("🎭", "Best impression", best, f"{pct(best.score)}% like {best.target}" if best else "")
        award("🙈", "Worst impression", worst, f"{pct(worst.score)}% like {worst.target}" if worst else "")
        rated = [r for r in scored if r.stars]
        fave = max(rated, key=lambda r: sum(r.stars.values()) / len(r.stars), default=None)
        if fave:
            award("⭐", "Crowd favourite", fave, f"{sum(fave.stars.values()) / len(fave.stars):.1f} stars")
        split = max(rated, key=lambda r: abs(sum(r.stars.values()) / len(r.stars) / 5 - r.score), default=None)
        if split and split is not fave:
            avg = sum(split.stars.values()) / len(split.stars)
            award("🤖", "Humans vs machine", split, f"{avg:.1f} stars, but the machine said {pct(split.score)}%")
    elif room.mode == "disguise":
        award("🥸", "Best disguise", best, f"only {pct(best.score)}% themselves" if best else "")
        award("🙃", "Who are you kidding", worst, f"still {pct(worst.score)}% themselves" if worst else "")
    elif room.mode == "guess":
        sneaky = max((r for r in room.history if r.votes), key=lambda r: sum(s != r.player for s in r.votes.values()), default=None)
        if sneaky:
            fooled = sum(s != sneaky.player for s in sneaky.votes.values())
            award("🕵️", "Best poker face", sneaky, f"fooled {fooled} of {len(sneaky.votes)}")
    elif room.mode == "telephone":
        copies = [r for r in scored if r.drift is not None]
        copy = max(copies, key=lambda r: r.score, default=None)
        award("📞", "Perfect copy", copy, f"{pct(copy.score)}% like {copy.target}" if copy else "")
        lost = min(copies, key=lambda r: r.drift, default=None)
        if lost and lost is not copy:
            award("🌀", "Lost in the line", lost, f"only {lost.drift}% like {lost.chain_from}")
    fastest = max(room.history, key=lambda r: r.speed_bonus, default=None)
    if fastest and fastest.speed_bonus > 0:
        award("⚡", "Quickest draw", fastest, f"+{fastest.speed_bonus} for speed")
    return out


def timed_out(room: Room, at: datetime | None = None) -> bool:
    deadline = room.turn_deadline()
    return deadline is not None and (at or now()) > deadline + timedelta(seconds=GRACE_SECONDS)


def remove_player(room: Room, user_id: int) -> None:
    """Someone left: drop their future turns, and any turn where they were the target."""
    current = room.active_turn()
    room.players = [p for p in room.players if p.user_id != user_id]
    room.votes = {v: s for v, s in room.votes.items() if v != user_id}
    if room.status == "playing":
        done, todo = room.plan[: room.turn_index], room.plan[room.turn_index :]
        if room.mode == "telephone":
            todo = relink_chain(todo, user_id)
        else:
            todo = [t for t in todo if user_id not in (t.player_id, t.target_id)]
        room.plan = done + todo
        if current and user_id in (current.player_id, current.target_id):
            reset_turn(room, keep_clip=room.mode == "telephone")  # the next turn starts now
        if len(room.players) < min_players(room.mode) or room.turn_index >= len(room.plan):  # Guess Who with 2 is a free 50
            room.status = "finished"
            room.highlights = highlights(room)
    if room.host_id == user_id and room.players:
        room.host_id = room.players[0].user_id  # the next person in becomes host


def relink_chain(todo: list[Turn], user_id: int) -> list[Turn]:
    """Telephone without the leaver: whoever was going to copy them copies their voice's source instead
    (and starts the chain, if the leaver was going to)."""
    out, gap = [], None  # gap: the leaver's turn that was just dropped
    for t in todo:
        if t.player_id == user_id:
            gap = t
            continue
        if gap is not None and t.target_id == user_id:
            t.chain_start = gap.chain_start
            t.target_id = t.player_id if gap.chain_start else gap.target_id
        gap = None
        out.append(t)
    return out


def winners(room: Room) -> list[RoomPlayer]:
    if not room.players:
        return []
    top = max(p.points for p in room.players)
    return [p for p in room.players if p.points == top]


def ranks(room: Room) -> dict[int, int]:
    """1 = best; players with equal points share a place."""
    ordered = sorted(room.players, key=lambda p: p.points, reverse=True)
    out, last, place = {}, None, 0
    for i, p in enumerate(ordered, 1):
        if p.points != last:
            place, last = i, p.points
        out[p.user_id] = place
    return out


class RoomStore:
    """Rooms as JSON in the shared store, plus an index of codes for the dashboard."""

    def __init__(self, store: Store, ttl_hours: float) -> None:
        self.store = store
        self.ttl = int(ttl_hours * 3600)

    def lock(self, code: str):
        return self.store.lock(f"room:{code.upper()}", timeout=30)

    async def get(self, code: str) -> Room | None:
        raw = await self.store.get(f"room:{code.upper()}")
        return Room.model_validate_json(raw) if raw else None

    async def save(self, room: Room) -> None:
        room.updated_at = now()
        await self.store.put(f"room:{room.code}", room.model_dump_json(), self.ttl)
        await self.store.set_add(ROOMS_INDEX, room.code)
        # Tell everyone watching this room, and every dashboard.
        await self.store.publish(f"room:{room.code}", "changed")
        await self.store.publish("dashboard", "changed")

    async def delete(self, code: str) -> None:
        await self.store.delete(f"room:{code}")
        await self.store.set_remove(ROOMS_INDEX, code)
        await self.store.publish(f"room:{code}", "changed")
        await self.store.publish("dashboard", "changed")

    async def all(self) -> list[Room]:
        rooms = []
        for code in await self.store.set_members(ROOMS_INDEX):
            room = await self.get(code)
            if room is None:
                await self.store.set_remove(ROOMS_INDEX, code)  # expired
            else:
                rooms.append(room)
        return sorted(rooms, key=lambda r: r.updated_at, reverse=True)

    async def room_of(self, user_id: int) -> Room | None:
        """The lobby or game this user is in right now (one at a time)."""
        return next((r for r in await self.all() if r.status != "finished" and r.player(user_id)), None)

    async def leave(self, code: str, user_id: int) -> Room | None:
        code = code.upper()
        async with self.lock(code):
            room = await self.get(code)
            if room is None or room.player(user_id) is None:
                return room
            remove_player(room, user_id)
            if room.players:
                await self.save(room)
            else:
                await self.delete(room.code)  # the last one out closes the room
                return None
            return room

    async def leave_everywhere(self, user_id: int) -> None:
        for room in await self.all():
            if room.player(user_id):
                await self.leave(room.code, user_id)

    async def create(self, host: RoomPlayer, **options) -> Room:
        stamp = now()
        for _ in range(20):  # find a free code
            code = new_code()
            if await self.get(code) is None:
                break
        room = Room(code=code, host_id=host.user_id, players=[host], created_at=stamp, updated_at=stamp, **options)
        await self.save(room)
        return room

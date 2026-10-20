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
- impersonate: sound like another player; +50 if you fool the AI.
- guess:       "Guess Who". A secretly chosen player speaks, everyone else hears
               the clip and votes on who it was. Right guesses +50; the speaker
               gets +25 for everyone they fooled. The AI guesses too, for fun.

Speed rounds (any type): 20 seconds per turn, a bonus for being quick, and a
turn that runs out of time scores 0.
"""

from __future__ import annotations

import random
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel

from .schemas import LivenessOut
from .store import Store

Mode = Literal["yourself", "impersonate", "guess"]
Status = Literal["lobby", "playing", "finished"]
Phase = Literal["speak", "vote"]

IMPERSONATION_BONUS = 50
GUESS_RIGHT = 50  # for each player who names the speaker
GUESS_FOOLED = 25  # for the speaker, per player who got it wrong
SPEED_SECONDS = 20  # per turn in a speed round
VOTE_SECONDS = 30  # to vote in Guess Who
GRACE_SECONDS = 5  # uploads take a moment: don't skip a turn that's just arriving
MAX_PLAYERS = 12
ROOMS_INDEX = "rooms"  # set of room codes that may still exist
REACTIONS = ("😂", "🔥", "👏", "😮", "🤔", "😱", "💯", "🎉")

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
    target_id: int  # who they must sound like (themselves in "yourself" and "guess")


class TurnResult(BaseModel):
    turn_number: int  # 1-based
    player_id: int
    player: str
    target: str
    points: int
    message: str  # what the announcer says
    liveness: LivenessOut | None = None
    speed_bonus: int = 0
    # Guess Who
    votes: dict[str, str] = {}  # voter -> who they named
    ai_guess: str | None = None
    points_by_player: dict[str, int] = {}  # everyone who scored this turn


class Room(BaseModel):
    code: str
    host_id: int
    mode: Mode = "yourself"
    rounds: int = 2
    speed: bool = False
    status: Status = "lobby"
    game_no: int = 0  # +1 for every start (rematches are new games)
    players: list[RoomPlayer] = []
    plan: list[Turn] = []
    turn_index: int = 0
    turn_started_at: datetime | None = None
    last_result: TurnResult | None = None
    # Guess Who, between the recording and the reveal
    phase: Phase = "speak"
    votes: dict[int, int] = {}  # voter id -> suspect id
    vote_deadline: datetime | None = None
    clip_key: str | None = None  # the secret speaker's clip, in the store until the reveal
    clip_type: str = "audio/webm"
    ai_guess: str | None = None
    pending_liveness: LivenessOut | None = None
    created_at: datetime
    updated_at: datetime

    def player(self, user_id: int) -> RoomPlayer | None:
        return next((p for p in self.players if p.user_id == user_id), None)

    def active_turn(self) -> Turn | None:
        return self.plan[self.turn_index] if self.status == "playing" and self.turn_index < len(self.plan) else None

    def turn_deadline(self) -> datetime | None:
        """When the current turn runs out (speed rounds, and Guess Who voting)."""
        if self.status != "playing":
            return None
        if self.mode == "guess" and self.phase == "vote":
            return self.vote_deadline
        if self.speed and self.turn_started_at:
            return self.turn_started_at + timedelta(seconds=SPEED_SECONDS)
        return None


def new_code() -> str:
    """Easy to read out loud, e.g. 'TIGER-42'."""
    return f"{secrets.choice(CODE_WORDS).upper()}-{secrets.randbelow(90) + 10}"


def plan_turns(players: list[RoomPlayer], mode: Mode, rounds: int, rng: random.Random | None = None) -> list[Turn]:
    """Everyone takes one turn per round. Impersonators get a random other player.

    In Guess Who the order is shuffled every round, so nobody can work out who's next.
    """
    rng = rng or random.Random()
    plan = []
    for _ in range(rounds):
        order = list(players)
        if mode == "guess":
            rng.shuffle(order)
        for p in order:
            if mode == "impersonate":
                target = rng.choice([o for o in players if o.user_id != p.user_id])
            else:
                target = p
            plan.append(Turn(player_id=p.user_id, target_id=target.user_id))
    return plan


def start_game(room: Room) -> None:
    for p in room.players:
        p.points, p.turns = 0, 0
    room.plan = plan_turns(room.players, room.mode, room.rounds)
    room.turn_index, room.last_result, room.status = 0, None, "playing"
    room.game_no += 1
    reset_turn(room)


def reset_turn(room: Room) -> None:
    room.turn_started_at = now()
    room.phase, room.votes, room.vote_deadline = "speak", {}, None
    room.clip_key, room.ai_guess, room.pending_liveness = None, None, None


def speed_bonus(room: Room, points: int, at: datetime | None = None) -> int:
    """Up to +20 for answering fast in a speed round (only for turns that scored)."""
    if not room.speed or points <= 0 or room.turn_started_at is None:
        return 0
    used = ((at or now()) - room.turn_started_at).total_seconds()
    return max(0, round(SPEED_SECONDS - used))


def score_yourself(player: str, player_speaker_id: int, recognised_id: int | None, recognised: str, score: float) -> tuple[int, str]:
    """'Be yourself': points = how sure the AI is it's you (0-100), only if it picked you."""
    pct = max(0, round(score * 100))
    if recognised_id == player_speaker_id:
        comment = "Unmistakably you!" if score >= 0.7 else "Definitely you." if score >= 0.55 else "Just about you."
        return pct, f"That's {player}! {pct} points. {comment}"
    if recognised_id is not None:
        return 0, f"The machine thinks that was {recognised}! No points for {player}."
    return 0, f"The machine doesn't recognise that voice. No points for {player}."


def score_impersonation(player: str, target: str, score: float, fooled: bool) -> tuple[int, str]:
    """'Impersonate': points = how much you sound like the target, +50 if you fool the AI."""
    pct = max(0, round(score * 100))
    if fooled:
        total = pct + IMPERSONATION_BONUS
        return total, f"Wow! {player} fooled the machine as {target}! {total} points."
    return pct, f"{player} sounds {pct}% like {target}. {pct} points."


def failed_liveness(player: str) -> tuple[int, str]:
    return 0, f"{player}, the live check failed. Say the numbers on screen. No points."


def _finish_turn(room: Room, result: TurnResult) -> None:
    room.last_result = result
    room.turn_index += 1
    if room.turn_index >= len(room.plan):
        room.status = "finished"
    reset_turn(room)


def apply_turn(room: Room, points: int, message: str, liveness: LivenessOut | None, bonus: int = 0) -> None:
    """Book the current turn's result and move on (finishing the game after the last turn)."""
    turn = room.active_turn()
    assert turn is not None
    player, target = room.player(turn.player_id), room.player(turn.target_id)
    total = points + bonus
    player.points += total
    player.turns += 1
    if bonus:
        message += f" Plus {bonus} for speed!"
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
            points_by_player={player.username: total} if total else {},
        ),
    )


def open_voting(room: Room, clip_key: str, clip_type: str, ai_guess: str | None, liveness: LivenessOut | None) -> None:
    """Guess Who: the secret speaker has recorded; everyone else has VOTE_SECONDS to vote."""
    room.phase = "vote"
    room.clip_key, room.clip_type, room.ai_guess, room.pending_liveness = clip_key, clip_type, ai_guess, liveness
    room.vote_deadline = now() + timedelta(seconds=VOTE_SECONDS)
    room.votes = {}


def voters(room: Room) -> list[RoomPlayer]:
    turn = room.active_turn()
    return [p for p in room.players if turn and p.user_id != turn.player_id]


def everyone_voted(room: Room) -> bool:
    return all(p.user_id in room.votes for p in voters(room))


def reveal(room: Room) -> dict[int, int]:
    """Guess Who: show who it was and give out the points. Returns points per user id."""
    turn = room.active_turn()
    assert turn is not None
    speaker = room.player(turn.player_id)
    names = {p.user_id: p.username for p in room.players}
    right = [p for p in voters(room) if room.votes.get(p.user_id) == speaker.user_id]
    fooled = len(voters(room)) - len(right)
    points = {p.user_id: GUESS_RIGHT for p in right}
    points[speaker.user_id] = GUESS_FOOLED * fooled
    for uid, pts in points.items():
        room.player(uid).points += pts
    speaker.turns += 1

    if right:
        guessed = f"{', '.join(p.username for p in right)} guessed right"
    else:
        guessed = "Nobody guessed it"
    ai = f" The AI guessed {room.ai_guess}." if room.ai_guess else ""
    message = f"It was {speaker.username}! {guessed}. {speaker.username} fooled {fooled}.{ai}"
    _finish_turn(
        room,
        TurnResult(
            turn_number=room.turn_index + 1,
            player_id=speaker.user_id,
            player=speaker.username,
            target=speaker.username,
            points=points[speaker.user_id],
            message=message,
            liveness=room.pending_liveness,
            votes={names[v]: names.get(s, "?") for v, s in room.votes.items() if v in names},
            ai_guess=room.ai_guess,
            points_by_player={names[uid]: pts for uid, pts in points.items() if pts},
        ),
    )
    return points


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
        todo = [t for t in todo if user_id not in (t.player_id, t.target_id)]
        room.plan = done + todo
        if current and user_id in (current.player_id, current.target_id):
            reset_turn(room)  # the next turn starts now
        if len(room.players) < 2 or room.turn_index >= len(room.plan):
            room.status = "finished"
    if room.host_id == user_id and room.players:
        room.host_id = room.players[0].user_id  # the next person in becomes host


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

    async def create(self, host: RoomPlayer, mode: Mode, rounds: int, speed: bool = False) -> Room:
        stamp = now()
        for _ in range(20):  # find a free code
            code = new_code()
            if await self.get(code) is None:
                break
        room = Room(
            code=code, host_id=host.user_id, mode=mode, rounds=rounds, speed=speed, players=[host], created_at=stamp, updated_at=stamp
        )
        await self.save(room)
        return room

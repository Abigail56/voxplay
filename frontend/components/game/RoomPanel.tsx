"use client";

import { useEffect, useRef, useState } from "react";

import { api, type Clip, type GameMode, type Me, type Room, type TurnResult } from "@/lib/api";
import { announce, sfx } from "@/lib/game";
import { useChallenge } from "@/lib/useChallenge";

import { ClipInput } from "../ClipInput";
import { LivenessBadge } from "../LivenessBadge";
import { Phrase } from "../Phrase";
import { Avatar } from "./Avatar";
import { Invite } from "./Invite";
import { ModePicker } from "./ModePicker";
import { ResultCard } from "./ResultCard";

export type Reaction = { id: number; emoji: string; from: string };

const EMOJIS = ["😂", "🔥", "👏", "😮", "🤔", "😱", "💯", "🎉"];
const MODE_NAMES: Record<GameMode, string> = { yourself: "Be yourself", impersonate: "Impersonate", guess: "Guess Who" };

type Props = { room: Room; me: Me; sound: boolean; reactions: Reaction[]; onRoom: (room: Room | null) => void };

export function RoomPanel({ room, me, sound, reactions, onRoom }: Props) {
  const [error, setError] = useState<string | null>(null);
  const isHost = room.host_id === me.id;
  const name = (id: number) => room.players.find((p) => p.user_id === id)?.username ?? "?";
  const turn = room.current_turn;
  const guess = room.mode === "guess";
  const myTurn = guess ? room.you_speak : turn?.player_id === me.id;
  const minPlayers = guess ? 3 : 2;

  // Every device announces each result as it arrives, and plays a sound when it's your turn.
  const lastAnnounced = useRef<number | null>(room.last_result?.turn_number ?? null);
  useEffect(() => {
    const r = room.last_result;
    if (!r || r.turn_number === lastAnnounced.current) return;
    lastAnnounced.current = r.turn_number;
    sfx(Object.keys(r.points_by_player).length ? "score" : "zero", sound);
    announce(r.message, sound);
  }, [room.last_result, sound]);
  useEffect(() => {
    if (myTurn && room.phase === "speak") sfx("turn", sound);
  }, [myTurn, room.turn_index, room.phase, sound]);
  const wasFinished = useRef(room.status === "finished");
  useEffect(() => {
    if (room.status === "finished" && !wasFinished.current) {
      sfx("win", sound);
      setTimeout(() => announce(winnerLine(room), sound), 2500); // after the last result is read out
    }
    wasFinished.current = room.status === "finished";
  }, [room, sound]);

  async function act(action: () => Promise<Room | null>) {
    setError(null);
    try {
      onRoom(await action());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const board = [...room.players].sort((a, b) => b.points - a.points);

  return (
    <section className="card room">
      <Floaters reactions={reactions} />
      <div className="room-head">
        <div>
          <span className="hint">Game code</span>
          <div className="code big-code">{room.code}</div>
        </div>
        <div className="badges-row">
          <span className="badge">{MODE_NAMES[room.mode]}</span>
          {room.speed && <span className="badge speed">Speed round</span>}
          <span className={`badge ${room.status}`}>
            {room.status === "lobby" ? "Waiting room" : room.status === "playing" ? `Turn ${room.turn_index + 1} of ${room.turns_total}` : "Game over"}
          </span>
        </div>
      </div>

      {room.status === "lobby" && (
        <>
          <p className="tagline">
            Invite friends: they open the link (or type <strong className="code">{room.code}</strong>) and play from their
            own phones.
          </p>
          <Invite code={room.code} />
          <ul className="seats">
            {room.players.map((p) => (
              <li key={p.user_id}>
                <Avatar name={p.username} size={48} />
                <span>
                  {p.username}
                  {p.user_id === room.host_id && <span className="hint"> (host)</span>}
                </span>
              </li>
            ))}
            {Array.from({ length: Math.max(0, minPlayers - room.players.length) }, (_, i) => (
              <li key={`empty${i}`} className="empty">
                <span className="avatar empty-seat">?</span>
                <span className="hint">waiting…</span>
              </li>
            ))}
          </ul>
          {isHost ? (
            <HostControls room={room} onChange={(mode, rounds, speed) => act(() => api.changeRoom(room.code, mode, rounds, speed))} />
          ) : (
            <p className="hint">
              {MODE_NAMES[room.mode]} · {room.rounds} round{room.rounds === 1 ? "" : "s"}
              {room.speed && " · speed round"}. Waiting for {name(room.host_id)} to start…
            </p>
          )}
          {isHost && (
            <button className="btn primary big" disabled={room.players.length < minPlayers} onClick={() => act(() => api.startRoom(room.code))}>
              {room.players.length >= minPlayers
                ? `Start game (${room.players.length} players)`
                : guess
                  ? "Guess Who needs 3 players…"
                  : "Waiting for players…"}
            </button>
          )}
        </>
      )}

      {room.status !== "lobby" && (
        <ul className="scoreboard">
          {board.map((p, i) => (
            <li key={p.user_id} className={`${!guess && turn?.player_id === p.user_id ? "up" : ""} ${p.user_id === me.id ? "me" : ""}`}>
              <span className="rank">{i + 1}</span>
              <Avatar name={p.username} size={32} />
              <span className="who">
                {p.username}
                {guess && room.phase === "vote" && room.voted.includes(p.user_id) && <span className="hint"> · voted ✓</span>}
              </span>
              <strong className="pts">{p.points}</strong>
            </li>
          ))}
        </ul>
      )}

      {/* Stable wrappers: each keyed child is the only child of its own slot. */}
      <div className="slot">
        {room.last_result && room.status !== "lobby" && <ResultBox key={room.last_result.turn_number} result={room.last_result} />}
      </div>

      <div className="slot">
        {room.status === "playing" && room.deadline && <Countdown key={`${room.turn_index}-${room.phase}`} room={room} />}
      </div>

      <div className="slot">
        {room.status === "playing" && myTurn && room.phase === "speak" && (
          <MyTurn
            key={room.turn_index}
            room={room}
            prompt={
              guess
                ? "You've been picked to speak in secret. Read the numbers, and disguise your voice if you like."
                : turn && turn.target_id !== me.id
                  ? `Your turn. Do your best ${name(turn.target_id)}.`
                  : "Your turn."
            }
            onRoom={onRoom}
          />
        )}
      </div>

      {room.status === "playing" && !myTurn && room.phase === "speak" && (
        <div className="waiting-turn">
          {guess ? (
            <>
              <span className="avatar empty-seat">?</span>
              <p>
                Someone has been picked to speak in secret<span className="dots">…</span>
              </p>
            </>
          ) : (
            turn && (
              <>
                <Avatar name={name(turn.player_id)} size={44} />
                <p>
                  <strong>{name(turn.player_id)}</strong> is up
                  {room.mode === "impersonate" && (
                    <>
                      , trying to sound like <strong>{name(turn.target_id)}</strong>
                    </>
                  )}
                  <span className="dots" aria-hidden>
                    …
                  </span>
                </p>
              </>
            )
          )}
        </div>
      )}

      <div className="slot">
        {room.status === "playing" && guess && room.phase === "vote" && !room.you_speak && <Vote key={room.turn_index} room={room} me={me} onRoom={onRoom} />}
      </div>
      {room.status === "playing" && guess && room.phase === "vote" && room.you_speak && (
        <div className="waiting-turn">
          <span className="avatar empty-seat">?</span>
          <p>The others are trying to work out it was you. Keep a straight face.</p>
        </div>
      )}

      {room.status === "finished" && (
        <div className="winner">
          <div className="confetti" aria-hidden>
            {Array.from({ length: 24 }, (_, i) => (
              <span key={i} style={{ left: `${(i * 41) % 100}%`, animationDelay: `${(i % 8) * 0.12}s`, background: `var(--series-${(i % 8) + 1})` }} />
            ))}
          </div>
          <p className="winner-line">{winnerLine(room)}</p>
          <ResultCard room={room} me={me} />
          {isHost && (
            <button className="btn primary big" onClick={() => act(() => api.startRoom(room.code))}>
              Rematch
            </button>
          )}
        </div>
      )}

      {room.status !== "lobby" && (
        <div className="react-bar" aria-label="Send a reaction">
          {EMOJIS.map((e) => (
            <button key={e} type="button" onClick={() => api.react(room.code, e).catch(() => {})} aria-label={`React ${e}`}>
              {e}
            </button>
          ))}
        </div>
      )}

      {error && <p className="error">{error}</p>}
      <button className="link" onClick={() => act(() => api.leaveRoom(room.code).then(() => null))}>
        {room.status === "finished" ? "Back to the lobby" : "Leave game"}
      </button>
    </section>
  );
}

function ResultBox({ result }: { result: TurnResult }) {
  const votes = Object.entries(result.votes);
  const scored = Object.keys(result.points_by_player).length > 0;
  return (
    <div className={`result pop ${scored ? "match" : "unknown"}`}>
      <div className="points">
        {votes.length ? "Votes are in" : `+${result.points}`}
        {result.speed_bonus > 0 && <span className="speed-tag">+{result.speed_bonus} for speed</span>}
      </div>
      <p className="announce">{result.message}</p>
      {votes.length > 0 && (
        <ul className="votes">
          {votes.map(([voter, suspect]) => (
            <li key={voter} className={suspect === result.player ? "right" : "wrong"}>
              {voter} → {suspect} {suspect === result.player ? "✓" : "✗"}
              {result.points_by_player[voter] ? <strong> +{result.points_by_player[voter]}</strong> : null}
            </li>
          ))}
          <li className="ai">
            The game guessed {result.ai_guess ?? "nobody"} {result.ai_guess === result.player ? "✓" : "✗"}
          </li>
        </ul>
      )}
      {result.liveness && <LivenessBadge liveness={result.liveness} />}
    </div>
  );
}

function HostControls({ room, onChange }: { room: Room; onChange: (mode: GameMode, rounds: number, speed: boolean) => void }) {
  return (
    <>
    <ModePicker value={room.mode} onChange={(m) => onChange(m, room.rounds, room.speed)} />
    <div className="create">
      <label className="field">
        Rounds
        <select value={room.rounds} onChange={(e) => onChange(room.mode, Number(e.target.value), room.speed)}>
          {[1, 2, 3, 5].map((n) => (
            <option key={n}>{n}</option>
          ))}
        </select>
      </label>
      <label className="consent">
        <input type="checkbox" checked={room.speed} onChange={(e) => onChange(room.mode, room.rounds, e.target.checked)} />
        Speed round (20 seconds a turn, extra points for being quick)
      </label>
    </div>
    </>
  );
}

/** Seconds left on the turn. When it runs out, this screen asks the server to move on (the server checks the clock). */
function Countdown({ room }: { room: Room }) {
  const end = new Date(room.deadline!).getTime();
  const [left, setLeft] = useState(() => Math.max(0, Math.ceil((end - Date.now()) / 1000)));
  useEffect(() => {
    const id = setInterval(() => setLeft(Math.max(0, Math.ceil((end - Date.now()) / 1000))), 250);
    return () => clearInterval(id);
  }, [end]);
  useEffect(() => {
    if (left > 0) return;
    // A few seconds' grace for an upload that's on its way, then nudge the server.
    const id = setTimeout(() => api.advance(room.code).catch(() => {}), 6000);
    return () => clearTimeout(id);
  }, [left, room.code]);
  const total = room.phase === "vote" ? 30 : 20;
  return (
    <div className={`countdown ${left <= 5 ? "urgent" : ""}`}>
      <div className="countdown-fill" style={{ width: `${Math.min(100, (left / total) * 100)}%` }} />
      <span>{left > 0 ? `⏱ ${left}s` : "⏱ Time's up!"}</span>
    </div>
  );
}

/** Your turn: a fresh phrase, the mic, and off it goes to the server for scoring. */
function MyTurn({ room, prompt, onRoom }: { room: Room; prompt: string; onRoom: (room: Room) => void }) {
  const phrase = useChallenge();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(clip: Clip) {
    if (!phrase.challenge) return;
    setBusy(true);
    setError(null);
    try {
      onRoom(await api.takeTurn(room.code, clip, phrase.challenge.challenge_id));
    } catch (e) {
      setError((e as Error).message);
      phrase.renew(); // the phrase was used up; try again with a new one
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="my-turn">
      <p className="your-turn">{prompt}</p>
      <Phrase state={phrase} />
      <ClipInput onClip={send} disabled={busy || !phrase.challenge || phrase.expired} allowUpload={false} />
      {busy && <p className="hint">Listening…</p>}
      {(error || phrase.error) && <p className="error">{error ?? phrase.error}</p>}
    </div>
  );
}

/** Guess Who: listen to the mystery clip and name the speaker. */
function Vote({ room, me, onRoom }: { room: Room; me: Me; onRoom: (room: Room) => void }) {
  const [audio, setAudio] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let url: string | null = null;
    api
      .clip(room.code)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setAudio(url);
      })
      .catch((e) => setError((e as Error).message));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [room.code]);

  async function vote(id: number) {
    setError(null);
    try {
      onRoom(await api.vote(room.code, id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="my-turn vote">
      <p className="your-turn">Who said it?</p>
      {audio ? <audio src={audio} controls autoPlay className="preview" /> : <p className="hint">Loading the clip…</p>}
      <div className="suspects">
        {room.players
          .filter((p) => p.user_id !== me.id)
          .map((p) => (
            <button key={p.user_id} className={`suspect ${room.my_vote === p.user_id ? "on" : ""}`} onClick={() => vote(p.user_id)}>
              <Avatar name={p.username} size={40} />
              {p.username}
              {room.my_vote === p.user_id && " ✓"}
            </button>
          ))}
      </div>
      <p className="hint">
        {room.voted.length} of {room.players.length - 1} voted. You can change your mind until everyone has voted.
      </p>
      {error && <p className="error">{error}</p>}
    </div>
  );
}

/** Emoji reactions floating up across the room card. */
function Floaters({ reactions }: { reactions: Reaction[] }) {
  return (
    <div className="floaters" aria-hidden>
      {reactions.map((r) => (
        <span key={r.id} className="floater" style={{ left: `${10 + ((r.id * 37) % 80)}%` }}>
          {r.emoji}
          <small>{r.from}</small>
        </span>
      ))}
    </div>
  );
}

function winnerLine(room: Room): string {
  const winners = room.players.filter((p) => room.winner_ids.includes(p.user_id));
  if (winners.length === 0) return "Game over!";
  const top = winners[0].points;
  return winners.length > 1
    ? `It's a tie between ${winners.map((w) => w.username).join(" and ")}, with ${top} points each!`
    : `${winners[0].username} wins with ${top} points!`;
}

"use client";

import { useEffect, useRef, useState } from "react";

import { api, type Clip, type Highlight, type Me, type Room, type TurnResult } from "@/lib/api";
import { announce, sfx } from "@/lib/game";
import { useChallenge } from "@/lib/useChallenge";

import { ClipInput } from "../ClipInput";
import { LivenessBadge } from "../LivenessBadge";
import { Phrase } from "../Phrase";
import { Avatar } from "./Avatar";
import { GameOptions, optionsOf } from "./GameOptions";
import { Invite } from "./Invite";
import { modeName } from "./ModePicker";
import { PlayButton } from "./PlayButton";
import { ResultCard } from "./ResultCard";

export type Reaction = { id: number; emoji: string; from: string };

const EMOJIS = ["😂", "🔥", "👏", "😮", "🤔", "😱", "💯", "🎉"];

type Props = { room: Room; me: Me; sound: boolean; reactions: Reaction[]; onRoom: (room: Room | null) => void };

export function RoomPanel({ room, me, sound, reactions, onRoom }: Props) {
  const [error, setError] = useState<string | null>(null);
  const isHost = room.host_id === me.id;
  const name = (id: number) => room.players.find((p) => p.user_id === id)?.username ?? "?";
  const turn = room.current_turn;
  const guess = room.mode === "guess";
  const myTurn = guess ? room.you_speak : turn?.player_id === me.id;
  const minPlayers = guess || room.mode === "telephone" ? 3 : 2;
  const judging = room.phase === "vote" || room.phase === "rate";

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
          <span className="badge">{modeName(room.mode)}</span>
          {room.speed && <span className="badge speed">Speed round</span>}
          {room.twists && <span className="badge">Twists</span>}
          {room.crowd && room.mode === "impersonate" && <span className="badge">Humans vs AI</span>}
          {room.status === "playing" && turn?.double && <span className="badge hot">Double points</span>}
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
            <GameOptions value={optionsOf(room)} onChange={(o) => act(() => api.changeRoom(room.code, o))} />
          ) : (
            <p className="hint">
              {modeName(room.mode)} · {room.rounds} round{room.rounds === 1 ? "" : "s"}
              {room.speed && " · speed round"}
              {room.twists && " · twists"}
              {room.double_final && " · double final"}. Waiting for {name(room.host_id)} to start…
            </p>
          )}
          <p className="hint">
            {room.replay
              ? "🔁 Replay is on: each turn's recording is kept for an hour so you can play back the best bits, then deleted."
              : ["guess", "telephone"].includes(room.mode) || room.crowd
                ? "Your recording is played to the other players during your turn, then deleted."
                : "Recordings are deleted as soon as they're scored."}
          </p>
          {isHost && (
            <button className="btn primary big" disabled={room.players.length < minPlayers} onClick={() => act(() => api.startRoom(room.code))}>
              {room.players.length >= minPlayers
                ? `Start game (${room.players.length} players)`
                : minPlayers === 3
                  ? `${modeName(room.mode)} needs 3 players…`
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
                {judging && room.voted.includes(p.user_id) && <span className="hint"> · {room.phase === "vote" ? "voted" : "rated"} ✓</span>}
              </span>
              <strong className="pts">{p.points}</strong>
            </li>
          ))}
        </ul>
      )}

      {/* Stable wrappers: each keyed child is the only child of its own slot. */}
      <div className="slot">
        {room.last_result && room.status !== "lobby" && <ResultBox key={room.last_result.turn_number} room={room} result={room.last_result} />}
      </div>

      <div className="slot">
        {room.status === "playing" && room.deadline && <Countdown key={`${room.turn_index}-${room.phase}`} room={room} />}
      </div>

      <div className="slot">
        {room.status === "playing" && myTurn && room.phase === "speak" && turn !== null && (
          <MyTurn key={room.turn_index} room={room} prompt={prompt(room, name)} listen={room.mode === "telephone" && !turn.chain_start} onRoom={onRoom} />
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
                  <strong>{name(turn.player_id)}</strong> {waiting(room, name)}
                  {turn.twist && <span className="twist">{turn.twist}</span>}
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
      <div className="slot">
        {room.status === "playing" && room.phase === "rate" && !myTurn && <Rate key={room.turn_index} room={room} name={name} onRoom={onRoom} />}
      </div>
      {room.status === "playing" && judging && myTurn && (
        <div className="waiting-turn">
          <span className="avatar empty-seat">?</span>
          <p>
            {room.phase === "vote"
              ? "The others are trying to work out it was you. Keep a straight face."
              : "The others are rating your impression. The machine's verdict comes after."}
          </p>
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
          {room.highlights.length > 0 && <Highlights room={room} />}
          <ResultCard room={room} me={me} />
          {room.replay && room.history.some((r) => r.has_clip) && <FullReplay room={room} />}
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

/** What the player whose turn it is should do. */
function prompt(room: Room, name: (id: number) => string): string {
  const turn = room.current_turn!;
  switch (room.mode) {
    case "guess":
      return "You've been picked to speak in secret. Read the line, and disguise your voice if you like.";
    case "impersonate":
      return `Your turn. Do your best ${name(turn.target_id)}.`;
    case "disguise":
      return "Your turn. Disguise your voice: don't let the game know it's you.";
    case "telephone":
      return turn.chain_start
        ? "You start the chain. Say the line in any voice you like: everyone after you has to copy it."
        : `Copy ${name(turn.target_id)}'s voice. Listen first, then say your line just like that.`;
    default:
      return "Your turn. Say it in your own voice.";
  }
}

/** What everyone else sees while someone takes their turn ("Bayo is up, trying to sound like Ada"). */
function waiting(room: Room, name: (id: number) => string): string {
  const turn = room.current_turn!;
  switch (room.mode) {
    case "impersonate":
      return `is up, trying to sound like ${name(turn.target_id)}`;
    case "disguise":
      return "is up, hiding their voice";
    case "telephone":
      return turn.chain_start ? "is starting a new chain" : `is copying ${name(turn.target_id)}'s voice`;
    default:
      return "is up";
  }
}

function ResultBox({ room, result }: { room: Room; result: TurnResult }) {
  const votes = Object.entries(result.votes);
  const stars = Object.entries(result.stars);
  const scored = Object.keys(result.points_by_player).length > 0;
  const avg = stars.length ? stars.reduce((s, [, n]) => s + n, 0) / stars.length : 0;
  return (
    <div className={`result pop ${scored ? "match" : "unknown"}`}>
      <div className="points">
        {votes.length ? "Votes are in" : `+${result.points}`}
        {result.speed_bonus > 0 && <span className="speed-tag">+{result.speed_bonus} for speed</span>}
        {result.double && <span className="speed-tag">x2 final round</span>}
      </div>
      <p className="announce">{result.message}</p>
      {result.twist && <p className="hint">Twist: {result.twist}</p>}
      {stars.length > 0 && (
        <div className="verdicts">
          <div>
            <span className="hint">The machine</span>
            <strong>{result.ai_points ?? 0}</strong>
          </div>
          <div>
            <span className="hint">You lot</span>
            <strong>
              {"★".repeat(Math.round(avg))}
              <span className="dim-stars">{"★".repeat(5 - Math.round(avg))}</span> {avg.toFixed(1)}
            </strong>
          </div>
        </div>
      )}
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
      <SoundedLike result={result} />
      {result.drift !== null && result.chain_from && result.chain_from !== result.target && (
        <p className="hint">
          Drift: the voice now sounds {result.drift}% like {result.chain_from}, who started the chain.
        </p>
      )}
      <div className="row">
        {result.liveness && <LivenessBadge liveness={result.liveness} />}
        {result.has_clip && <ReplayButton code={room.code} turn={result.turn_number} label="▶ Hear it" />}
      </div>
    </div>
  );
}

/** "Sounded like: ada 82%, bayo 31%…": how the machine heard the clip. */
function SoundedLike({ result }: { result: TurnResult }) {
  const rows = Object.entries(result.sounded_like).slice(0, 4);
  if (rows.length < 2) return null;
  return (
    <div className="sounded">
      <span className="hint">To the machine it sounded like</span>
      <ul>
        {rows.map(([who, p]) => (
          <li key={who}>
            <span className="who">{who}</span>
            <span className="track">
              <span className={`fill ${who === result.player ? "self" : ""}`} style={{ width: `${p}%` }} />
            </span>
            <span className="num">{p}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Plays one turn's clip from the replay. */
function ReplayButton({ code, turn, label }: { code: string; turn: number; label?: string }) {
  return <PlayButton load={() => api.replay(code, turn)} label={label} />;
}

function Highlights({ room }: { room: Room }) {
  return (
    <ul className="highlights">
      {room.highlights.map((h: Highlight) => (
        <li key={h.title}>
          <span className="hl-emoji" aria-hidden>
            {h.emoji}
          </span>
          <span>
            <strong>{h.title}</strong>
            <span className="hint">
              {" "}
              {h.player}
              {h.detail && ` · ${h.detail}`}
            </span>
          </span>
          {h.has_clip && <ReplayButton code={room.code} turn={h.turn_number} />}
        </li>
      ))}
    </ul>
  );
}

function FullReplay({ room }: { room: Room }) {
  return (
    <details className="full-replay">
      <summary>Replay every turn</summary>
      <ol>
        {room.history.map((r) => (
          <li key={r.turn_number}>
            <span>
              <strong>{r.player}</strong>
              <span className="hint">
                {room.mode === "impersonate" && ` as ${r.target}`}
                {r.twist && ` · ${r.twist}`} · {r.points} pts
              </span>
            </span>
            {r.has_clip ? <ReplayButton code={room.code} turn={r.turn_number} /> : <span className="hint">no clip</span>}
          </li>
        ))}
      </ol>
    </details>
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
  const total = room.deadline_seconds ?? 20;
  return (
    <div className={`countdown ${left <= 5 ? "urgent" : ""}`}>
      <div className="countdown-fill" style={{ width: `${Math.min(100, (left / total) * 100)}%` }} />
      <span>{left > 0 ? `⏱ ${left}s` : "⏱ Time's up!"}</span>
    </div>
  );
}

/** The clip everyone's listening to right now (Guess Who, a rating, or the voice to copy). */
function useClip(code: string) {
  const [audio, setAudio] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    api
      .clip(code)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setAudio(url);
      })
      .catch((e) => setError((e as Error).message));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [code]);
  return { audio, error };
}

/** Your turn: a fresh line, the mic, and off it goes to the server for scoring. */
function MyTurn({ room, prompt, listen, onRoom }: { room: Room; prompt: string; listen: boolean; onRoom: (room: Room) => void }) {
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
      phrase.renew(); // the line was used up; try again with a new one
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="my-turn">
      <p className="your-turn">{prompt}</p>
      {listen && <CopyThis code={room.code} />}
      <Phrase state={phrase} twist={room.current_turn?.twist} />
      <ClipInput onClip={send} disabled={busy || !phrase.challenge || phrase.expired} allowUpload={false} />
      {busy && <p className="hint">Listening…</p>}
      {(error || phrase.error) && <p className="error">{error ?? phrase.error}</p>}
    </div>
  );
}

/** Telephone: the voice to copy. */
function CopyThis({ code }: { code: string }) {
  const { audio, error } = useClip(code);
  if (error) return <p className="hint">Couldn&apos;t load the voice to copy. Do your best from memory!</p>;
  return audio ? <audio src={audio} controls autoPlay className="preview" /> : <p className="hint">Loading the voice to copy…</p>;
}

/** Guess Who: listen to the mystery clip and name the speaker. */
function Vote({ room, me, onRoom }: { room: Room; me: Me; onRoom: (room: Room) => void }) {
  const { audio, error: clipError } = useClip(room.code);
  const [error, setError] = useState<string | null>(null);

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
      {(error || clipError) && <p className="error">{error ?? clipError}</p>}
    </div>
  );
}

/** Humans vs AI: listen to the impression and rate it, before the machine's verdict is revealed. */
function Rate({ room, name, onRoom }: { room: Room; name: (id: number) => string; onRoom: (room: Room) => void }) {
  const { audio, error: clipError } = useClip(room.code);
  const [error, setError] = useState<string | null>(null);
  const turn = room.current_turn!;

  async function rate(stars: number) {
    setError(null);
    try {
      onRoom(await api.rate(room.code, stars));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="my-turn vote">
      <p className="your-turn">
        How good was {name(turn.player_id)}&apos;s {name(turn.target_id)}?
      </p>
      {audio ? <audio src={audio} controls autoPlay className="preview" /> : <p className="hint">Loading the impression…</p>}
      <div className="stars" role="radiogroup" aria-label="Your rating">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={room.my_vote === n}
            aria-label={`${n} star${n > 1 ? "s" : ""}`}
            className={room.my_vote !== null && n <= room.my_vote ? "on" : ""}
            onClick={() => rate(n)}
          >
            ★
          </button>
        ))}
      </div>
      <p className="hint">
        {room.voted.length} of {room.players.length - 1} rated. Then the machine has its say.
      </p>
      {(error || clipError) && <p className="error">{error ?? clipError}</p>}
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

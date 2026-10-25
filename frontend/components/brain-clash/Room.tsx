"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  api,
  SignedOutError,
  type BcFeed,
  type BcFlag,
  type BcGame,
  type BcPlayer,
  type BcRoom,
  type BcSettings,
  type BcSignals,
  type BcTeam,
  type Clip,
} from "@/lib/api";
import { BC_MODES, modeName, ROOM_GAMES } from "@/lib/brainClash";
import { announce, loadSoundSetting, sfx } from "@/lib/game";
import { useLive } from "@/lib/useLive";
import { useAuthStore } from "@/store/useAuthStore";

import { ART, artSrc } from "@/lib/art";

import { Art } from "../art/Scenes";
import { Loader } from "../brand/Loader";
import { ClipInput } from "../ClipInput";
import { Avatar } from "../game/Avatar";

const TEAMS: BcTeam[] = ["A", "B"];
const EMOJIS = ["😂", "🔥", "👏", "😮", "😱", "💯", "🎉"];
type Reaction = { id: number; emoji: string; from: string };

/** /brain-clash/CODE (and /beat-drop/CODE, /story-forge/CODE): the lobby, the match and the victory screen of one room. */
export function BrainClashRoomPage({ code, game = "brain-clash" }: { code: string; game?: BcGame }) {
  const { token, me, ready, restore, signOut } = useAuthStore();
  const [room, setRoom] = useState<BcRoom | null>(null);
  const [missing, setMissing] = useState<string | null>(null);
  const [offset, setOffset] = useState(0); // server clock minus this device's clock, in ms
  const [sound, setSound] = useState(true);
  const [reactions, setReactions] = useState<Reaction[]>([]);
  const g = ROOM_GAMES[room?.game ?? game];

  useEffect(() => {
    restore();
    setSound(loadSoundSetting());
  }, [restore]);

  const show = useCallback((r: BcRoom) => {
    setOffset(Date.parse(r.server_time) - Date.now());
    setRoom(r);
  }, []);

  const load = useCallback(async () => {
    try {
      show(await api.bc.room(code));
      setMissing(null);
    } catch (e) {
      if (e instanceof SignedOutError) return signOut();
      setMissing((e as Error).message);
    }
  }, [code, show, signOut]);

  useEffect(() => {
    if (token) load();
  }, [token, load]);
  const onReaction = useCallback((emoji: string, from: string) => {
    const id = Date.now() + Math.random();
    setReactions((rs) => [...rs.slice(-12), { id, emoji, from }]);
    setTimeout(() => setReactions((rs) => rs.filter((r) => r.id !== id)), 2600);
  }, []);
  useLive(token, null, { onBrainClash: load, onReaction, onSignedOut: signOut }, token ? code : null);

  if (!ready) return <Loader label="Entering the room…" art="searching" />;
  if (!me) {
    return (
      <section className="state-page">
        <p className="eyebrow">
          {g.title} · room {code}
        </p>
        <h1>You&apos;re invited!</h1>
        <p className="tagline">Make a VOXPLAY player (or sign in) and you&apos;ll come straight back to this room. No voice setup needed.</p>
        <Link href={`/sign-in?next=${encodeURIComponent(`${g.path}/${code}`)}`} className="btn primary big">
          Sign in to join
        </Link>
      </section>
    );
  }
  if (missing) {
    return (
      <section className="state-page">
        {artSrc(ART["state-empty-room"].file) && <Art slot="state-empty-room" className="state-art" />}
        <p className="eyebrow">{g.title}</p>
        <h1>Room not found</h1>
        <p className="tagline">{missing} Rooms close a few hours after the last game.</p>
        <Link href={g.path} className="btn primary big">
          Open a new room
        </Link>
      </section>
    );
  }
  if (!room) return <Loader label="Entering the room…" art="searching" />;

  const mine = room.players.find((p) => p.user_id === me.id) ?? null;
  return (
    <div className={`bc-room status-${room.status} game-${room.game}`}>
      <div className="bc-backdrop" aria-hidden>
        <Art slot={room.status === "finished" ? "victory" : room.game === "brain-clash" ? "lobby" : g.art} className="art-fill" />
      </div>
      <Floaters reactions={reactions} />
      {!mine && room.status === "lobby" && <JoinPanel room={room} name={me.username} onRoom={show} />}
      {!mine && room.status !== "lobby" && <p className="notice">You&apos;re watching. This match started before you arrived; join the next one!</p>}
      {room.status === "lobby" && <Lobby room={room} me={me.id} onRoom={show} />}
      {room.status === "playing" && <Match room={room} me={mine} offset={offset} sound={sound} onRoom={show} />}
      {room.status === "finished" && <Victory room={room} me={me.id} sound={sound} onRoom={show} />}
      {mine && room.status !== "lobby" && <ReactBar code={room.code} />}
    </div>
  );
}

function ReactBar({ code }: { code: string }) {
  return (
    <div className="react-bar" aria-label="Send a reaction">
      {EMOJIS.map((e) => (
        <button key={e} type="button" onClick={() => api.bc.react(code, e).catch(() => {})} aria-label={`React ${e}`}>
          {e}
        </button>
      ))}
    </div>
  );
}

/** Emoji reactions floating up across the screen. */
function Floaters({ reactions }: { reactions: Reaction[] }) {
  return (
    <div className="floaters bc-floaters" aria-hidden>
      {reactions.map((r) => (
        <span key={r.id} className="floater" style={{ left: `${10 + ((Math.round(r.id) * 37) % 80)}%` }}>
          {r.emoji}
          <small>{r.from}</small>
        </span>
      ))}
    </div>
  );
}

function useAct(onRoom: (r: BcRoom) => void) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const act = async (action: () => Promise<BcRoom | void>) => {
    setError(null);
    setBusy(true);
    try {
      const r = await action();
      if (r) onRoom(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return { act, error, busy };
}

function teamName(room: BcRoom, t: BcTeam) {
  return room.settings.team_names[t];
}

// ---------- joining and the lobby ----------

function JoinPanel({ room, name, onRoom }: { room: BcRoom; name: string; onRoom: (r: BcRoom) => void }) {
  const [display, setDisplay] = useState(name);
  const { act, error, busy } = useAct(onRoom);
  return (
    <section className="card bc-join">
      <h2>Join room {room.code}</h2>
      <label className="field">
        Your name in this room
        <input value={display} onChange={(e) => setDisplay(e.target.value)} maxLength={20} />
      </label>
      <div className="row">
        {TEAMS.map((t) => (
          <button key={t} className={`btn big team-btn team-${t}`} disabled={busy} onClick={() => act(() => api.bc.join(room.code, display.trim(), t))}>
            Join {teamName(room, t)}
          </button>
        ))}
        <button className="btn big" disabled={busy} onClick={() => act(() => api.bc.join(room.code, display.trim()))}>
          Put me anywhere
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  );
}

function Lobby({ room, me, onRoom }: { room: BcRoom; me: number; onRoom: (r: BcRoom) => void }) {
  const isHost = room.host_id === me;
  const mine = room.players.find((p) => p.user_id === me);
  const { act, error, busy } = useAct(onRoom);
  const ready = TEAMS.every((t) => room.players.some((p) => p.team === t));
  return (
    <>
      <section className="card bc-lobby-head">
        <div>
          <p className="eyebrow">
            {room.game === "brain-clash" ? `Brain Clash · ${modeName(room.settings.mode)}` : ROOM_GAMES[room.game].title}
          </p>
          <span className="hint">Room code</span>
          <div className="code big-code">{room.code}</div>
        </div>
        <RoomInvite code={room.code} game={room.game} />
      </section>

      <div className="bc-teams">
        {TEAMS.map((t) => (
          <section key={t} className={`card bc-team team-${t}`} aria-label={teamName(room, t)}>
            <h2>{teamName(room, t)}</h2>
            <ul className="bc-roster">
              {room.players
                .filter((p) => p.team === t)
                .map((p) => (
                  <PlayerRow key={p.user_id} room={room} p={p} me={me}>
                    {isHost && p.user_id !== me && (
                      <button className="btn small ghost" disabled={busy} onClick={() => act(() => api.bc.team(room.code, p.user_id, t === "A" ? "B" : "A"))}>
                        Move {t === "A" ? "→" : "←"}
                      </button>
                    )}
                  </PlayerRow>
                ))}
              {!room.players.some((p) => p.team === t) && <li className="hint">Nobody yet. Every team needs at least one player.</li>}
            </ul>
            {mine && mine.team !== t && (
              <button className="btn small" disabled={busy} onClick={() => act(() => api.bc.team(room.code, me, t))}>
                Switch to {teamName(room, t)}
              </button>
            )}
          </section>
        ))}
      </div>

      {isHost ? (
        <section className="card">
          <h2>Match settings</h2>
          <SettingsForm room={room} disabled={busy} onChange={(s) => act(() => api.bc.settings(room.code, s))} />
          <div className="row">
            <button className="btn primary big" disabled={busy || !ready} onClick={() => act(() => api.bc.start(room.code))}>
              {ready ? ROOM_GAMES[room.game].startLabel : "Both teams need a player"}
            </button>
            <button className="btn" disabled={busy || room.players.length < 2} onClick={() => act(() => api.bc.shuffle(room.code))}>
              Shuffle teams
            </button>
          </div>
        </section>
      ) : (
        <section className="card">
          {artSrc(ART["state-waiting"].file) && <Art slot="state-waiting" className="state-art" />}
          <p className="tagline">
            {modeName(room.settings.mode)} · {room.settings.rounds} rounds
            {room.settings.win_score ? ` · first to ${room.settings.win_score}` : ""}
          </p>
          <p className="hint">Waiting for {room.players.find((p) => p.user_id === room.host_id)?.name ?? "the host"} to start…</p>
        </section>
      )}
      {error && <p className="error">{error}</p>}
      <LeaveLink code={room.code} game={room.game} />
    </>
  );
}

function PlayerRow({ room, p, me, children }: { room: BcRoom; p: BcPlayer; me: number; children?: React.ReactNode }) {
  return (
    <li>
      <Avatar name={p.name} size={36} online={p.online} />
      <span className="who">
        {p.name}
        {p.user_id === me && <span className="hint"> (you)</span>}
        {p.user_id === room.host_id && <span className="host-tag">host</span>}
      </span>
      {children}
    </li>
  );
}

function SettingsForm({ room, disabled, onChange }: { room: BcRoom; disabled: boolean; onChange: (s: BcSettings) => void }) {
  const s = room.settings;
  const [cats, setCats] = useState<{ id: string; name: string; count: number }[]>([]);
  const [names, setNames] = useState(s.team_names);
  useEffect(() => {
    api.bc
      .categories(room.game)
      .then((cs) => setCats(cs.map((c) => ({ id: c.id, name: c.name, count: c.counts[s.mode] ?? 0 }))))
      .catch(() => {});
  }, [s.mode, room.game]);
  useEffect(() => setNames(s.team_names), [s.team_names]);
  const set = (patch: Partial<BcSettings>) => onChange({ ...s, ...patch });
  const toggle = (id: string) => set({ categories: s.categories.includes(id) ? s.categories.filter((c) => c !== id) : [...s.categories, id] });
  return (
    <div className="bc-settings">
      {room.game === "brain-clash" && (
        <div className="bc-modes" role="radiogroup" aria-label="Game mode">
          {BC_MODES.map((m) => (
            <button key={m.id} type="button" role="radio" aria-checked={s.mode === m.id} className={`mode ${s.mode === m.id ? "on" : ""}`} disabled={disabled} onClick={() => set({ mode: m.id, categories: [] })}>
              <span className="mode-tick" aria-hidden />
              <span className="mode-name">
                {m.icon} {m.name}
              </span>
              <span className="mode-blurb">{m.blurb}</span>
            </button>
          ))}
        </div>
      )}
      <fieldset className="chip-set">
        <legend>
          Categories <span className="hint">{s.categories.length ? `${s.categories.length} picked` : "all of them"}</span>
        </legend>
        {cats
          .filter((c) => c.count > 0)
          .map((c) => (
            <label key={c.id} className={`chip-toggle ${s.categories.includes(c.id) ? "on" : ""}`}>
              <input type="checkbox" checked={s.categories.includes(c.id)} disabled={disabled} onChange={() => toggle(c.id)} />
              {c.name} <span className="hint">{c.count}</span>
            </label>
          ))}
      </fieldset>
      <div className="bc-setting-row">
        <label className="field">
          Rounds
          <select value={s.rounds} disabled={disabled} onChange={(e) => set({ rounds: Number(e.target.value) })}>
            {[3, 5, 8, 10, 15, 20, 30].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Timer
          <select value={s.seconds ?? ""} disabled={disabled} onChange={(e) => set({ seconds: e.target.value ? Number(e.target.value) : null })}>
            <option value="">Mode default</option>
            {[10, 15, 20, 30, 45, 60, 90].map((n) => (
              <option key={n} value={n}>
                {n} seconds
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Winning score
          <select value={s.win_score ?? ""} disabled={disabled} onChange={(e) => set({ win_score: e.target.value ? Number(e.target.value) : null })}>
            <option value="">Play every round</option>
            {[50, 100, 150, 200, 300].map((n) => (
              <option key={n} value={n}>
                First to {n}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="bc-setting-row">
        {s.mode === "quickfire" && (
          <label className="switch">
            <input type="checkbox" checked={s.speed_bonus} disabled={disabled} onChange={(e) => set({ speed_bonus: e.target.checked })} />
            <span>
              <strong>⚡ Speed bonus</strong> <span className="hint">up to +{s.scoring.speed_max} for a fast answer</span>
            </span>
          </label>
        )}
        {(s.mode === "battle" || s.mode === "hum") && (
          <label className="switch">
            <input type="checkbox" checked={s.steals} disabled={disabled} onChange={(e) => set({ steals: e.target.checked })} />
            <span>
              <strong>🥷 Steals</strong> <span className="hint">a missed question passes to the other team for half points</span>
            </span>
          </label>
        )}
      </div>
      <div className="bc-setting-row">
        {TEAMS.map((t) => (
          <label key={t} className="field">
            Team {t} name
            <input
              value={names[t]}
              maxLength={24}
              disabled={disabled}
              onChange={(e) => setNames({ ...names, [t]: e.target.value })}
              onBlur={() => names[t].trim() && names[t] !== s.team_names[t] && set({ team_names: { ...s.team_names, [t]: names[t].trim() } })}
            />
          </label>
        ))}
      </div>
    </div>
  );
}

function RoomInvite({ code, game }: { code: string; game: BcGame }) {
  const g = ROOM_GAMES[game];
  const [link, setLink] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [canShare, setCanShare] = useState(false);
  useEffect(() => {
    setLink(`${window.location.origin}${g.path}/${encodeURIComponent(code)}`);
    setCanShare(typeof navigator.share === "function");
  }, [code, g.path]);
  const message = `Join my ${g.title} room on VOXPLAY! Code ${code}: ${link}`;
  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setNote("Link copied");
    } catch {
      setNote("Your browser blocked copying. Share the code instead.");
    }
    setTimeout(() => setNote(null), 2500);
  }
  return (
    <div className="invite">
      <div className="row">
        {canShare && (
          <button className="btn small primary" onClick={() => navigator.share({ title: `${g.title} · VOXPLAY`, text: message, url: link }).catch(() => {})}>
            Share invite
          </button>
        )}
        <a className="btn small whatsapp" href={`https://wa.me/?text=${encodeURIComponent(message)}`} target="_blank" rel="noreferrer">
          WhatsApp
        </a>
        <button className="btn small" onClick={copy}>
          Copy link
        </button>
      </div>
      {note && (
        <p className="hint" role="status">
          {note}
        </p>
      )}
    </div>
  );
}

function LeaveLink({ code, game }: { code: string; game: BcGame }) {
  return (
    <button
      className="link"
      onClick={() =>
        api.bc
          .leave(code)
          .catch(() => {})
          .finally(() => (window.location.href = ROOM_GAMES[game].path))
      }
    >
      Leave room
    </button>
  );
}

// ---------- the match ----------

/** Seconds until an ISO time on the server's clock, ticking. */
function useSecondsLeft(iso: string | null, offset: number) {
  const target = iso ? Date.parse(iso) : 0;
  const calc = () => (iso ? Math.max(0, (target - (Date.now() + offset)) / 1000) : 0);
  const [left, setLeft] = useState(calc);
  useEffect(() => {
    setLeft(calc());
    const id = setInterval(() => setLeft(calc()), 200);
    return () => clearInterval(id);
  }, [iso, offset]); // calc only reads these two
  return left;
}

function performerName(room: BcRoom) {
  return room.players.find((p) => p.user_id === room.round?.performer_id)?.name ?? "Someone";
}

function canAnswer(room: BcRoom, me: BcPlayer | null): string | null {
  const r = room.round;
  if (!me) return "You're watching this match.";
  if (!r || r.phase === "reveal") return "Round over.";
  const mode = room.settings.mode;
  if (mode === "hum") {
    if (r.phase === "hum") return `🎧 ${performerName(room)} is getting ready to hum…`;
    if (r.performer_id === me.user_id) return "🎵 Your hum is playing. No hints now!";
    if (r.turn_team && r.turn_team !== me.team) return `${teamName(room, r.turn_team)} is guessing. Listen closely: you might get to steal it!`;
    if ((r.attempts[me.team] ?? 0) >= 3) return "Your team has used its 3 guesses.";
    return null;
  }
  if (mode === "battle" && r.turn_team && r.turn_team !== me.team) return `${teamName(room, r.turn_team)} is answering. Get ready for your turn!`;
  if (mode === "battle" && (r.attempts[me.team] ?? 0) >= 3) return "Your team has used its 3 tries.";
  if ((mode === "quickfire" || mode === "association" || (mode === "battle" && r.tiebreak)) && r.you_tried) return "You've had your go on this one.";
  if (mode === "association" && r.scored[me.team] !== undefined) return "Your team scored on this word!";
  if (mode === "namefast" && r.question.target && r.found_count[me.team] >= r.question.target) return "Your team has named enough!";
  return null;
}

function Match({ room, me, offset, sound, onRoom }: { room: BcRoom; me: BcPlayer | null; offset: number; sound: boolean; onRoom: (r: BcRoom) => void }) {
  const r = room.round!;
  const isHost = me?.user_id === room.host_id;
  const deadline = r.phase === "reveal" ? r.reveal_until : r.closes_at;
  const left = useSecondsLeft(deadline, offset);
  const story = room.settings.mode === "story";
  const total =
    r.phase === "reveal" ? (story ? 4 : 6) : r.phase === "steal" ? 10 : r.phase === "hum" ? 20 : r.phase === "vote" ? 12 : (Date.parse(r.closes_at) - Date.parse(r.opened_at)) / 1000;
  const [feedback, setFeedback] = useState<BcFeed | null>(null);
  const { act, error } = useAct(onRoom);
  const away = useAwayTime(`${r.number}-${r.phase === "steal" ? "open" : r.phase}`);

  // The last five seconds tick.
  const lastTick = useRef(0);
  useEffect(() => {
    const s = Math.ceil(left);
    if (r.phase !== "reveal" && s <= 5 && s > 0 && s !== lastTick.current) {
      lastTick.current = s;
      sfx("tick", sound);
    }
  }, [left, r.phase, sound]);

  // When the clock runs out, ask the server to move on (it checks its own clock). A little jitter
  // so every phone in the room doesn't call at the same instant.
  const asked = useRef<string | null>(null);
  useEffect(() => {
    const key = `${r.number}-${r.phase}`;
    if (left > 0 || asked.current === key) return;
    asked.current = key;
    const id = setTimeout(() => api.bc.advance(room.code).then(onRoom).catch(() => {}), (r.phase === "reveal" ? 300 : 900) + Math.random() * 500);
    return () => clearTimeout(id);
  }, [left, r.number, r.phase, room.code, onRoom]);

  // Sounds and the spoken announcer: a new question, and each reveal.
  const lastPhase = useRef<string>("");
  useEffect(() => {
    const key = `${r.number}-${r.phase}`;
    if (lastPhase.current === key) return;
    lastPhase.current = key;
    if (r.phase === "open" || r.phase === "hum") sfx("turn", sound);
    if (r.phase === "steal") announce(`Steal! ${teamName(room, r.turn_team!)} can take it.`, sound);
    if (r.phase === "vote" && r.line) announce(r.line, sound);
    if (r.phase === "reveal") {
      const scored = Object.keys(r.scored);
      sfx(scored.length ? "score" : "zero", sound);
      announce(r.reveal ? `The answer: ${r.reveal.answer}` : "", sound);
    }
  }, [r.number, r.phase, r.scored, r.reveal, r.turn_team, room, sound]);
  useEffect(() => setFeedback(null), [r.number]);

  // A new flag makes a sound for everyone: the detector caught something.
  const flagsSeen = useRef(room.flags.length);
  useEffect(() => {
    if (room.flags.length > flagsSeen.current) sfx("flag", sound);
    flagsSeen.current = room.flags.length;
  }, [room.flags.length, sound]);

  const blocked = canAnswer(room, me);
  const performer = r.performer_id === me?.user_id;
  return (
    <>
      <RoundIntro room={room} offset={offset} sound={sound} />
      <ScoreBar room={room} />
      {room.notice && r.number === 1 && <p className="notice">{room.notice}</p>}
      <FlagPanel room={room} onRoom={onRoom} />
      {story && <StoryScroll room={room} />}
      <section className={`card bc-question phase-${r.phase} ${r.turn_team ? `turn-${r.turn_team}` : ""}`} aria-live="polite">
        <div className="bc-q-meta">
          <span className="eyebrow">{r.tiebreak ? "Tie-breaker!" : `Round ${r.number} of ${room.rounds_total}`}</span>
          <span className="hint">
            {r.question.category_name} · {r.question.difficulty} · {r.question.kind === "list" ? `${r.question.points} per answer` : `${r.question.points} pts`}
          </span>
        </div>
        {r.turn_team && r.phase !== "reveal" && (
          <p className={`turn-banner team-${r.turn_team}`}>
            {r.phase === "steal"
              ? `🥷 Steal! ${teamName(room, r.turn_team)} for half points`
              : r.phase === "hum"
                ? `🎤 ${performerName(room)} hums for ${teamName(room, r.turn_team)}`
                : story
                  ? `✍️ ${performerName(room)} writes for ${teamName(room, r.turn_team)}`
                  : `${teamName(room, r.turn_team)}'s turn`}
          </p>
        )}
        <h2 className="bc-prompt">
          {room.settings.mode === "association" ? (
            <>
              <span className="hint">Say a word that goes with</span> <span className="assoc-word">{r.question.prompt}</span>
            </>
          ) : story ? (
            <>
              <span className="hint">Spark word</span> <span className="assoc-word">{r.question.spark}</span>
              <span className="bc-twist">{r.question.prompt}</span>
            </>
          ) : room.settings.mode === "hum" && performer && r.phase !== "reveal" ? (
            <>
              <span className="hint">🤫 Your secret song: hum it, don&apos;t say it!</span> <span className="assoc-word">{r.question.prompt}</span>
            </>
          ) : (
            r.question.prompt
          )}
        </h2>
        <div className={`bc-timer ${left <= 5 && r.phase !== "reveal" ? "urgent" : ""}`} role="timer" aria-label={`${Math.ceil(left)} seconds left`}>
          <div className="bc-timer-fill" style={{ width: `${Math.min(100, (left / Math.max(1, total)) * 100)}%` }} />
          <span>{r.phase === "reveal" ? `Next round in ${Math.ceil(left)}s` : left > 0 ? `${Math.ceil(left)}` : "Time!"}</span>
        </div>

        {r.question.kind === "list" && r.phase !== "reveal" && me && (
          <div className="found">
            <span className="hint">
              Your list: {r.found_count[me.team]} of {r.question.target} · {teamName(room, me.team === "A" ? "B" : "A")}: {r.found_count[me.team === "A" ? "B" : "A"]}
            </span>
            <ul className="chips">
              {r.found[me.team].map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
        )}

        {r.phase === "reveal" && <HypeBurst key={`hype-${r.number}`} room={room} me={me} />}
        {room.settings.mode === "hum" && r.has_clip && r.phase !== "hum" && <HumPlayer key={`hum-${r.number}`} code={room.code} round={r.number} />}
        {r.phase === "reveal" ? (
          <Reveal room={room} />
        ) : room.settings.mode === "hum" && r.phase === "hum" && performer ? (
          <HumBox key={r.number} room={room} onRoom={onRoom} />
        ) : story && r.phase === "vote" ? (
          <FireBox room={room} me={me} onRoom={onRoom} sound={sound} />
        ) : story && !performer ? (
          <p className="waiting-turn">{me ? `✍️ ${performerName(room)} is writing the next line…` : "You're watching this match."}</p>
        ) : blocked && !story ? (
          <p className="waiting-turn">{blocked}</p>
        ) : (
          <AnswerBox
            key={r.number}
            room={room}
            away={away}
            onAnswered={(fb, rm) => {
              setFeedback(fb);
              onRoom(rm);
              sfx(fb.flag_id ? "flag" : fb.points ? "score" : "zero", sound);
            }}
          />
        )}
        {feedback && <FeedbackPop fb={feedback} />}
        {isHost && r.phase === "reveal" && (
          <button className="btn primary" onClick={() => act(() => api.bc.advance(room.code))}>
            Next round now
          </button>
        )}
      </section>
      <Feed room={room} />
      {error && <p className="error">{error}</p>}
      {isHost && (
        <button className="link" onClick={() => window.confirm("End the match now? The team ahead wins.") && act(() => api.bc.end(room.code))}>
          End match
        </button>
      )}
      <LeaveLink code={room.code} game={room.game} />
    </>
  );
}

/** The match intro (a VS splash with both team names) when round 1 opens, then a quick "ROUND n"
 *  flash for every new round. It never blocks the screen: taps go straight through. */
function RoundIntro({ room, offset, sound }: { room: BcRoom; offset: number; sound: boolean }) {
  const r = room.round!;
  const [show, setShow] = useState<"vs" | "round" | null>(null);
  const seen = useRef<string>("");
  useEffect(() => {
    const key = `${room.game_no}-${r.number}`;
    if (seen.current === key) return;
    seen.current = key;
    // Only when the round has just started: a player who reloads mid-round doesn't get the splash again.
    if (Date.now() + offset - Date.parse(r.opened_at) > 4000 && r.phase !== "hum") return;
    const kind = r.number === 1 && !r.tiebreak ? "vs" : "round";
    setShow(kind);
    if (kind === "vs") announce(`${teamName(room, "A")} versus ${teamName(room, "B")}. Go!`, sound);
  }, [room, r.number, r.opened_at, r.phase, r.tiebreak, offset, sound]);
  // Its own effect, so a room update arriving mid-splash can't cancel the timer that hides it.
  useEffect(() => {
    if (!show) return;
    const id = setTimeout(() => setShow(null), show === "vs" ? 2300 : 1100);
    return () => clearTimeout(id);
  }, [show]);
  if (!show) return null;
  if (show === "round")
    return (
      <div className="round-flash" aria-hidden>
        <span>{r.tiebreak ? "TIE-BREAKER" : `ROUND ${r.number}`}</span>
      </div>
    );
  return (
    <div className="match-intro" aria-hidden>
      <Art slot="brainClash" className="art-fill" />
      <div className="match-intro-names">
        <span className="side a">{teamName(room, "A")}</span>
        <span className="vs-big">VS</span>
        <span className="side b">{teamName(room, "B")}</span>
      </div>
      <span className="match-intro-go">Round 1 · GO!</span>
    </div>
  );
}

/** The moment after a round: a big burst for the team that scored (with confetti for your team). */
function HypeBurst({ room, me }: { room: BcRoom; me: BcPlayer | null }) {
  const r = room.round!;
  const scorers = Object.keys(r.scored) as BcTeam[];
  const mine = me && scorers.includes(me.team);
  const fire = scorers.find((t) => room.streaks[t] >= 3);
  const stole = room.feed.some((f) => f.round === r.number && f.verdict === "steal");
  const text = !scorers.length
    ? "MISSED IT!"
    : fire
      ? "ON FIRE! 🔥"
      : stole
        ? "STOLEN! 🥷"
        : mine
          ? "YES! ⚡"
          : `${teamName(room, scorers[0]).toUpperCase()} SCORES!`;
  return (
    <div className={`hype-burst ${scorers.length ? "hit" : "miss"} ${fire ? "fire" : ""}`} aria-hidden>
      <span>{text}</span>
      {mine && (
        <div className="confetti">
          {Array.from({ length: 18 }, (_, i) => (
            <span key={i} style={{ left: `${(i * 53) % 100}%`, animationDelay: `${(i % 6) * 0.08}s`, background: ["#f472b6", "#38bdf8", "#fde047", "#a78bfa"][i % 4] }} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Fair play: how long this screen was hidden (another tab or app) since `key` (the round) changed. */
function useAwayTime(key: string) {
  const away = useRef(0);
  const hiddenAt = useRef<number | null>(null);
  useEffect(() => {
    away.current = 0;
    hiddenAt.current = document.hidden ? Date.now() : null;
    const onChange = () => {
      if (document.hidden) hiddenAt.current = Date.now();
      else if (hiddenAt.current !== null) {
        away.current += Date.now() - hiddenAt.current;
        hiddenAt.current = null;
      }
    };
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, [key]);
  return () => away.current + (hiddenAt.current !== null ? Date.now() - hiddenAt.current : 0);
}

/** Beat Drop: the hummer records their hum. */
function HumBox({ room, onRoom }: { room: BcRoom; onRoom: (r: BcRoom) => void }) {
  const { act, error, busy } = useAct(onRoom);
  return (
    <div className="bc-answer bc-hum">
      <p className="hint">Press record, hum the tune (or la-la-la it), then stop. Up to 15 seconds. Words get you flagged!</p>
      <ClipInput onClip={(clip) => act(() => api.bc.hum(room.code, room.round!.number, clip))} disabled={busy} allowUpload={false} label="🎤 Record your hum" />
      {busy && <p className="hint">Sending your hum… the AI is listening.</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

/** Beat Drop: the hum, playing on every screen. */
function HumPlayer({ code, round }: { code: string; round: number }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let made: string | null = null;
    api.bc
      .humClip(code)
      .then((blob) => setUrl((made = URL.createObjectURL(blob))))
      .catch(() => {});
    return () => {
      if (made) URL.revokeObjectURL(made);
    };
  }, [code, round]);
  if (!url) return <p className="hint">Loading the hum…</p>;
  return (
    <div className="bc-hum-player">
      <span className="eq" aria-hidden>
        <i />
        <i />
        <i />
        <i />
        <i />
      </span>
      <audio src={url} controls autoPlay aria-label="The hum" />
    </div>
  );
}

/** Story Forge: the story so far, on every screen. */
function StoryScroll({ room }: { room: BcRoom }) {
  return (
    <section className="card bc-story" aria-label="The story so far">
      <p className="eyebrow">The story so far</p>
      <div className="bc-story-text">
        {room.opener && <p className="opener">{room.opener}</p>}
        {room.story.map((s) => (
          <p key={s.round} className={`team-${s.team}`}>
            {s.line}{" "}
            <span className="hint">
              — {s.player}
              {s.used_spark ? " ⚡" : ""}
              {s.fires ? ` ${"🔥".repeat(Math.min(s.fires, 5))}` : ""}
            </span>
          </p>
        ))}
      </div>
    </section>
  );
}

/** Story Forge: the other team fires at the line they love. */
function FireBox({ room, me, onRoom, sound }: { room: BcRoom; me: BcPlayer | null; onRoom: (r: BcRoom) => void; sound: boolean }) {
  const r = room.round!;
  const { act, error, busy } = useAct(onRoom);
  const writer = room.players.find((p) => p.user_id === r.performer_id);
  const canFire = me && writer && me.team !== writer.team && !r.you_fired;
  return (
    <div className="bc-fire pop">
      <p className="bc-line">&ldquo;{r.line}&rdquo;</p>
      <p className="hint">
        {writer?.name} · {r.scored[writer?.team ?? "A"] ? `+${r.scored[writer?.team ?? "A"]} so far` : "no spark word: 0 points"} · {r.fires} 🔥
      </p>
      {canFire ? (
        <button
          className="btn primary big fire-btn"
          disabled={busy}
          onClick={() => {
            sfx("fire", sound);
            act(() => api.bc.fire(room.code, r.number));
          }}
        >
          🔥 Fire! (+{room.settings.scoring.fire})
        </button>
      ) : (
        <p className="hint">{r.you_fired ? "You fired! 🔥" : "The other team is deciding whether to fire…"}</p>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

/** Fair play: what the detector flagged, why, and (for the host) Allow / Void. */
function FlagPanel({ room, onRoom }: { room: BcRoom; onRoom: (r: BcRoom) => void }) {
  const { act, error, busy } = useAct(onRoom);
  const pending = room.flags.filter((f) => f.status === "pending");
  if (!pending.length) return null;
  return (
    <section className="card bc-flags" aria-live="polite">
      <p className="eyebrow">🤖 Fair-play AI · needs a decision</p>
      {pending.map((f) => (
        <FlagItem key={f.id} flag={f} room={room} busy={busy} onDecide={(allow) => act(() => api.bc.decide(room.code, f.id, allow))} />
      ))}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

function FlagItem({ flag, room, busy, onDecide }: { flag: BcFlag; room: BcRoom; busy: boolean; onDecide: (allow: boolean) => void }) {
  const what = flag.kind === "hum" ? "hum" : flag.kind === "line" ? "line" : "answer";
  return (
    <div className={`bc-flag team-${flag.team}`}>
      <p>
        <strong>{flag.player}</strong>&apos;s {what} looks suspicious <span className="hint">({Math.round(flag.suspicion * 100)}% sure)</span>
        {flag.held > 0 && <span className="hint"> · {flag.held} points on hold</span>}
      </p>
      <ul>
        {flag.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      {flag.you_decide ? (
        <div className="row">
          <button className="btn small" disabled={busy} onClick={() => onDecide(true)}>
            ✅ Allow it
          </button>
          <button className="btn small danger" disabled={busy} onClick={() => onDecide(false)}>
            🚫 Void it
          </button>
        </div>
      ) : (
        <p className="hint">
          Waiting for {flag.user_id === room.host_id ? `${teamName(room, flag.team === "A" ? "B" : "A")} (the host is the one flagged)` : "the host"} to decide.
        </p>
      )}
    </div>
  );
}

function ScoreBar({ room }: { room: BcRoom }) {
  return (
    <div className="bc-scorebar">
      {TEAMS.map((t) => (
        <div key={t} className={`bc-score team-${t} ${room.round?.turn_team === t ? "active" : ""}`}>
          <span className="bc-team-name">
            {teamName(room, t)}
            {room.streaks[t] >= 3 && <span className="streak-badge"> 🔥×{room.streaks[t]}</span>}
          </span>
          {/* Keyed on the score, so it replays the bump animation each time it changes. */}
          <strong key={room.scores[t]} className="bc-points">
            {room.scores[t]}
          </strong>
          <span className="hint">{room.players.filter((p) => p.team === t).map((p) => p.name).join(", ")}</span>
        </div>
      ))}
      <span className="bc-vs" aria-hidden>
        VS
      </span>
    </div>
  );
}

function AnswerBox({ room, away, onAnswered }: { room: BcRoom; away: () => number; onAnswered: (fb: BcFeed, room: BcRoom) => void }) {
  const r = room.round!;
  const story = room.settings.mode === "story";
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Fair play: was this answer pasted, and how long did the typing take?
  const pasted = useRef(false);
  const firstKey = useRef<number | null>(null);

  async function send(answer: { text: string } | { clip: Clip }) {
    setBusy(true);
    setError(null);
    const signals: BcSignals = {
      away_ms: away(),
      pasted: "text" in answer && pasted.current,
      typing_ms: "text" in answer && firstKey.current !== null ? Date.now() - firstKey.current : null,
    };
    try {
      const res = await api.bc.answer(room.code, r.number, answer, signals);
      onAnswered(res.feedback, res.room);
      setText("");
      pasted.current = false;
      firstKey.current = null;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bc-answer">
      {story && <p className="hint">Use the spark word &ldquo;{r.question.spark}&rdquo; in your line for +{r.question.points}. {r.question.prompt}</p>}
      <ClipInput onClip={(clip) => send({ clip })} disabled={busy} allowUpload={false} label={story ? "🎙 Say your line" : "🎙 Speak your answer"} />
      <form
        className="join"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) send({ text: text.trim() });
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={() => (firstKey.current ??= Date.now())}
          onPaste={() => (pasted.current = true)}
          placeholder={story ? "…or type your line" : r.question.kind === "list" ? "Type answers, e.g. Ghana, Kenya" : "…or type your answer"}
          aria-label={story ? "Your line" : "Your answer"}
          maxLength={story ? 300 : 200}
          autoComplete="off"
          disabled={busy}
        />
        <button className="btn primary" disabled={busy || !text.trim()}>
          Send
        </button>
      </form>
      {busy && <p className="hint">Checking…</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

function FeedbackPop({ fb }: { fb: BcFeed }) {
  const good = fb.points > 0 && !fb.flag_id;
  const text = fb.flag_id
    ? fb.points
      ? `Right, but the fair-play AI flagged it: ${fb.points} points on hold until it's decided.`
      : "The fair-play AI flagged this one for review."
    : fb.verdict === "line"
      ? fb.points
        ? `Spark used! +${fb.points}`
        : "In the story! (No spark word, no points.)"
      : fb.verdict === "item"
      ? `+${fb.points}: ${fb.items.join(", ")}`
      : fb.verdict === "duplicate"
        ? "Already on your list. No extra points."
        : fb.verdict === "steal"
          ? `Stolen! +${fb.points}`
          : good
            ? `Correct! +${fb.points}`
            : "Not quite.";
  return (
    <div className={`bc-feedback ${fb.flag_id ? "flagged" : good ? "good" : "bad"}`} role="status">
      <strong>{text}</strong>
      <span className="hint">We heard: &ldquo;{fb.said}&rdquo;</span>
    </div>
  );
}

function Reveal({ room }: { room: BcRoom }) {
  const r = room.round!;
  const scored = Object.entries(r.scored);
  return (
    <div className="bc-reveal pop">
      <span className="hint">
        {r.question.kind === "list" ? "Some answers that counted" : r.question.kind === "song" ? "The song was" : r.question.kind === "spark" ? "The spark word" : "The answer"}
      </span>
      <p className="bc-answer-text">{r.reveal?.answer}</p>
      {r.question.kind === "spark" && r.line && <p className="bc-line">&ldquo;{r.line}&rdquo;</p>}
      {r.reveal?.explanation && <p className="hint">{r.reveal.explanation}</p>}
      {r.reveal && r.reveal.more.length > 0 && r.question.kind !== "question" && <p className="hint">Also good: {r.reveal.more.join(", ")}</p>}
      {r.reveal?.as_of && (
        <p className="hint">
          Correct as of {r.reveal.as_of}
          {r.reveal.source ? ` (${r.reveal.source})` : ""}
        </p>
      )}
      <p className="tagline">
        {scored.length ? scored.map(([t, p]) => `${teamName(room, t as BcTeam)} +${p}`).join(" · ") : "No points this round."}
      </p>
    </div>
  );
}

function Feed({ room }: { room: BcRoom }) {
  const items = room.feed.filter((f) => f.round === room.round?.number).slice(-6).reverse();
  if (!items.length) return null;
  const icon = { correct: "✅", steal: "🥷", item: "✅", duplicate: "🔁", wrong: "❌", line: "✍️", streak: "🔥" };
  return (
    <section className="card bc-feed" aria-label="Answers this round">
      <ul>
        {items.map((f, i) => (
          <li key={`${f.user_id}-${i}-${f.said}`} className={`team-${f.team}`}>
            <span aria-hidden>{icon[f.verdict]}</span>
            <strong>{f.player}</strong>
            <span className="said">{f.verdict === "streak" ? f.said : <>&ldquo;{f.said}&rdquo;</>}</span>
            {f.flag_id && <span className="flag-tag">⚠ review</span>}
            {f.points > 0 && <span className="pts">+{f.points}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------- the end ----------

function Victory({ room, me, sound, onRoom }: { room: BcRoom; me: number; sound: boolean; onRoom: (r: BcRoom) => void }) {
  const isHost = room.host_id === me;
  const { act, error, busy } = useAct(onRoom);
  const draw = room.winner === "draw";
  const champ = draw ? null : (room.winner as BcTeam);
  const myTeam = room.players.find((p) => p.user_id === me)?.team;
  const lost = !!champ && !!myTeam && myTeam !== champ;
  const mvp = [...room.players].sort((a, b) => b.points - a.points)[0];
  const said = useRef(false);
  useEffect(() => {
    if (said.current) return;
    said.current = true;
    sfx("win", sound);
    announce(draw ? "It's a draw!" : `${teamName(room, champ!)} are the champions!`, sound);
  }, [draw, champ, room, sound]);
  const wholeStory = [room.opener, ...room.story.map((s) => s.line)].filter(Boolean).join(" ");

  return (
    <section className={`card bc-victory ${champ ? `team-${champ}` : ""}`}>
      <div className="confetti" aria-hidden>
        {Array.from({ length: 28 }, (_, i) => (
          <span key={i} style={{ left: `${(i * 37) % 100}%`, animationDelay: `${(i % 7) * 0.15}s`, background: ["#f472b6", "#38bdf8", "#fbbf24", "#a78bfa"][i % 4] }} />
        ))}
      </div>
      <div className="bc-victory-art">
        <Art slot={lost ? "defeat" : "victory"} className="art-fill" />
      </div>
      <p className="eyebrow">{lost ? "So close. Run it back?" : room.finish_reason}</p>
      <h1 className="bc-champion">{draw ? "It's a draw!" : `${teamName(room, champ!)} wins!`}</h1>
      <div className="bc-final">
        {TEAMS.map((t) => (
          <div key={t} className={`bc-score team-${t} ${champ === t ? "active" : ""}`}>
            <span className="bc-team-name">{teamName(room, t)}</span>
            <strong className="bc-points">{room.scores[t]}</strong>
          </div>
        ))}
      </div>
      {mvp && mvp.points > 0 && (
        <p className="tagline">
          ⭐ Star player: <strong>{mvp.name}</strong> with {mvp.points} points ({mvp.correct} right)
        </p>
      )}
      <FlagPanel room={room} onRoom={onRoom} />
      {room.game === "story-forge" && room.story.length > 0 && (
        <div className="bc-story bc-legend">
          <p className="eyebrow">📜 Your legend</p>
          <div className="bc-story-text">
            {room.opener && <p className="opener">{room.opener}</p>}
            {room.story.map((s) => (
              <p key={s.round} className={`team-${s.team}`}>
                {s.line}
              </p>
            ))}
          </div>
          <button className="btn" onClick={() => announce(wholeStory, true)}>
            🔊 Read it aloud
          </button>
        </div>
      )}
      <details className="full-replay">
        <summary>Every round</summary>
        <ol>
          {room.history.map((h) => (
            <li key={h.number}>
              <span>
                <strong>{h.tiebreak ? "Tie-breaker" : `R${h.number}`}</strong> <span className="hint">{h.prompt}</span>
              </span>
              <span className="hint">
                {h.answer}
                {Object.entries(h.scored).map(([t, p]) => ` · ${teamName(room, t as BcTeam)} +${p}`)}
              </span>
            </li>
          ))}
        </ol>
      </details>
      <div className="row">
        {isHost ? (
          <button className="btn primary big" disabled={busy} onClick={() => act(() => api.bc.start(room.code))}>
            Play again
          </button>
        ) : (
          <span className="hint">The host can start a rematch with the same teams.</span>
        )}
        <Link href="/games" className="btn big">
          Return to games
        </Link>
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  );
}

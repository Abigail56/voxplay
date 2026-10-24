"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, SignedOutError, type BcFeed, type BcPlayer, type BcRoom, type BcSettings, type BcTeam, type Clip } from "@/lib/api";
import { BC_MODES, modeName } from "@/lib/brainClash";
import { announce, loadSoundSetting, sfx } from "@/lib/game";
import { useLive } from "@/lib/useLive";
import { useAuthStore } from "@/store/useAuthStore";

import { Art } from "../art/Scenes";
import { Loader } from "../brand/Loader";
import { ClipInput } from "../ClipInput";
import { Avatar } from "../game/Avatar";

const TEAMS: BcTeam[] = ["A", "B"];

/** /brain-clash/CODE: the lobby, the match and the victory screen of one room. */
export function BrainClashRoomPage({ code }: { code: string }) {
  const { token, me, ready, restore, signOut } = useAuthStore();
  const [room, setRoom] = useState<BcRoom | null>(null);
  const [missing, setMissing] = useState<string | null>(null);
  const [offset, setOffset] = useState(0); // server clock minus this device's clock, in ms
  const [sound, setSound] = useState(true);

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
  useLive(token, null, { onBrainClash: load, onSignedOut: signOut }, token ? code : null);

  if (!ready) return <Loader label="Entering the arena…" />;
  if (!me) {
    return (
      <section className="state-page">
        <p className="eyebrow">Brain Clash · room {code}</p>
        <h1>You&apos;re invited to the arena</h1>
        <p className="tagline">Make a VOXPLAY player (or sign in) and you&apos;ll come straight back to this room. No voice setup needed.</p>
        <Link href={`/sign-in?next=${encodeURIComponent(`/brain-clash/${code}`)}`} className="btn primary big">
          Sign in to join
        </Link>
      </section>
    );
  }
  if (missing) {
    return (
      <section className="state-page">
        <p className="eyebrow">Brain Clash</p>
        <h1>Room not found</h1>
        <p className="tagline">{missing} Rooms close a few hours after the last game.</p>
        <Link href="/brain-clash" className="btn primary big">
          Open a new room
        </Link>
      </section>
    );
  }
  if (!room) return <Loader label="Entering the arena…" />;

  const mine = room.players.find((p) => p.user_id === me.id) ?? null;
  return (
    <div className={`bc-room status-${room.status}`}>
      <div className="bc-backdrop" aria-hidden>
        <Art slot={room.status === "finished" ? "victory" : "lobby"} className="art-fill" />
      </div>
      {!mine && room.status === "lobby" && <JoinPanel room={room} name={me.username} onRoom={show} />}
      {!mine && room.status !== "lobby" && <p className="notice">You&apos;re watching. This match started before you arrived; join the next one!</p>}
      {room.status === "lobby" && <Lobby room={room} me={me.id} onRoom={show} />}
      {room.status === "playing" && <Match room={room} me={mine} offset={offset} sound={sound} onRoom={show} />}
      {room.status === "finished" && <Victory room={room} me={me.id} sound={sound} onRoom={show} />}
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
          <p className="eyebrow">Brain Clash · {modeName(room.settings.mode)}</p>
          <span className="hint">Room code</span>
          <div className="code big-code">{room.code}</div>
        </div>
        <RoomInvite code={room.code} />
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
              {ready ? "Start the clash" : "Both teams need a player"}
            </button>
            <button className="btn" disabled={busy || room.players.length < 2} onClick={() => act(() => api.bc.shuffle(room.code))}>
              Shuffle teams
            </button>
          </div>
        </section>
      ) : (
        <section className="card">
          <p className="tagline">
            {modeName(room.settings.mode)} · {room.settings.rounds} rounds
            {room.settings.win_score ? ` · first to ${room.settings.win_score}` : ""}
          </p>
          <p className="hint">Waiting for {room.players.find((p) => p.user_id === room.host_id)?.name ?? "the host"} to start the clash…</p>
        </section>
      )}
      {error && <p className="error">{error}</p>}
      <LeaveLink code={room.code} />
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
    api.bc.categories().then((cs) => setCats(cs.map((c) => ({ id: c.id, name: c.name, count: c.counts[s.mode] })))).catch(() => {});
  }, [s.mode]);
  useEffect(() => setNames(s.team_names), [s.team_names]);
  const set = (patch: Partial<BcSettings>) => onChange({ ...s, ...patch });
  const toggle = (id: string) => set({ categories: s.categories.includes(id) ? s.categories.filter((c) => c !== id) : [...s.categories, id] });
  return (
    <div className="bc-settings">
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
        {s.mode === "battle" && (
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

function RoomInvite({ code }: { code: string }) {
  const [link, setLink] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [canShare, setCanShare] = useState(false);
  useEffect(() => {
    setLink(`${window.location.origin}/brain-clash/${encodeURIComponent(code)}`);
    setCanShare(typeof navigator.share === "function");
  }, [code]);
  const message = `Join my Brain Clash room on VOXPLAY! Code ${code}: ${link}`;
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
          <button className="btn small primary" onClick={() => navigator.share({ title: "Brain Clash · VOXPLAY", text: message, url: link }).catch(() => {})}>
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

function LeaveLink({ code }: { code: string }) {
  return (
    <button
      className="link"
      onClick={() =>
        api.bc
          .leave(code)
          .catch(() => {})
          .finally(() => (window.location.href = "/brain-clash"))
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

function canAnswer(room: BcRoom, me: BcPlayer | null): string | null {
  const r = room.round;
  if (!me) return "You're watching this match.";
  if (!r || r.phase === "reveal") return "Round over.";
  const mode = room.settings.mode;
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
  const total = r.phase === "reveal" ? 6 : r.phase === "steal" ? 10 : (Date.parse(r.closes_at) - Date.parse(r.opened_at)) / 1000;
  const [feedback, setFeedback] = useState<BcFeed | null>(null);
  const { act, error } = useAct(onRoom);

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
    if (r.phase === "open") sfx("turn", sound);
    if (r.phase === "steal") announce(`Steal! ${teamName(room, r.turn_team!)} can take it.`, sound);
    if (r.phase === "reveal") {
      const scored = Object.keys(r.scored);
      sfx(scored.length ? "score" : "zero", sound);
      announce(r.reveal ? `The answer: ${r.reveal.answer}` : "", sound);
    }
  }, [r.number, r.phase, r.scored, r.reveal, r.turn_team, room, sound]);
  useEffect(() => setFeedback(null), [r.number]);

  const blocked = canAnswer(room, me);
  return (
    <>
      <ScoreBar room={room} />
      {room.notice && r.number === 1 && <p className="notice">{room.notice}</p>}
      <section className={`card bc-question phase-${r.phase} ${r.turn_team ? `turn-${r.turn_team}` : ""}`} aria-live="polite">
        <div className="bc-q-meta">
          <span className="eyebrow">{r.tiebreak ? "Tie-breaker!" : `Round ${r.number} of ${room.rounds_total}`}</span>
          <span className="hint">
            {r.question.category_name} · {r.question.difficulty} · {r.question.kind === "list" ? `${r.question.points} per answer` : `${r.question.points} pts`}
          </span>
        </div>
        {r.turn_team && r.phase !== "reveal" && (
          <p className={`turn-banner team-${r.turn_team}`}>
            {r.phase === "steal" ? `🥷 Steal! ${teamName(room, r.turn_team)} for half points` : `${teamName(room, r.turn_team)}'s turn`}
          </p>
        )}
        <h2 className="bc-prompt">
          {room.settings.mode === "association" ? (
            <>
              <span className="hint">Say a word that goes with</span> <span className="assoc-word">{r.question.prompt}</span>
            </>
          ) : (
            r.question.prompt
          )}
        </h2>
        <div className={`bc-timer ${left <= 5 && r.phase !== "reveal" ? "urgent" : ""}`} role="timer" aria-label={`${Math.ceil(left)} seconds left`}>
          <div className="bc-timer-fill" style={{ width: `${Math.min(100, (left / Math.max(1, total)) * 100)}%` }} />
          <span>{r.phase === "reveal" ? `Next question in ${Math.ceil(left)}s` : left > 0 ? `${Math.ceil(left)}` : "Time!"}</span>
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

        {r.phase === "reveal" ? (
          <Reveal room={room} />
        ) : blocked ? (
          <p className="waiting-turn">{blocked}</p>
        ) : (
          <AnswerBox
            key={r.number}
            room={room}
            onAnswered={(fb, rm) => {
              setFeedback(fb);
              onRoom(rm);
              sfx(fb.points ? "score" : "zero", sound);
            }}
          />
        )}
        {feedback && <FeedbackPop fb={feedback} />}
        {isHost && r.phase === "reveal" && (
          <button className="btn primary" onClick={() => act(() => api.bc.advance(room.code))}>
            Next question now
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
      <LeaveLink code={room.code} />
    </>
  );
}

function ScoreBar({ room }: { room: BcRoom }) {
  return (
    <div className="bc-scorebar">
      {TEAMS.map((t) => (
        <div key={t} className={`bc-score team-${t} ${room.round?.turn_team === t ? "active" : ""}`}>
          <span className="bc-team-name">{teamName(room, t)}</span>
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

function AnswerBox({ room, onAnswered }: { room: BcRoom; onAnswered: (fb: BcFeed, room: BcRoom) => void }) {
  const r = room.round!;
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(answer: { text: string } | { clip: Clip }) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.bc.answer(room.code, r.number, answer);
      onAnswered(res.feedback, res.room);
      setText("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bc-answer">
      <ClipInput onClip={(clip) => send({ clip })} disabled={busy} allowUpload={false} label="🎙 Speak your answer" />
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
          placeholder={r.question.kind === "list" ? "Type answers, e.g. Ghana, Kenya" : "…or type your answer"}
          aria-label="Your answer"
          maxLength={200}
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
  const good = fb.points > 0;
  const text =
    fb.verdict === "item"
      ? `+${fb.points}: ${fb.items.join(", ")}`
      : fb.verdict === "duplicate"
        ? "Already on your list. No extra points."
        : fb.verdict === "steal"
          ? `Stolen! +${fb.points}`
          : good
            ? `Correct! +${fb.points}`
            : "Not quite.";
  return (
    <div className={`bc-feedback ${good ? "good" : "bad"}`} role="status">
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
      <span className="hint">{r.question.kind === "list" ? "Some answers that counted" : "The answer"}</span>
      <p className="bc-answer-text">{r.reveal?.answer}</p>
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
  const icon = { correct: "✅", steal: "🥷", item: "✅", duplicate: "🔁", wrong: "❌" };
  return (
    <section className="card bc-feed" aria-label="Answers this round">
      <ul>
        {items.map((f, i) => (
          <li key={`${f.user_id}-${i}-${f.said}`} className={`team-${f.team}`}>
            <span aria-hidden>{icon[f.verdict]}</span>
            <strong>{f.player}</strong>
            <span className="said">&ldquo;{f.said}&rdquo;</span>
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
  const mvp = [...room.players].sort((a, b) => b.points - a.points)[0];
  const said = useRef(false);
  useEffect(() => {
    if (said.current) return;
    said.current = true;
    sfx("win", sound);
    announce(draw ? "It's a draw!" : `${teamName(room, champ!)} are the champions!`, sound);
  }, [draw, champ, room, sound]);

  return (
    <section className={`card bc-victory ${champ ? `team-${champ}` : ""}`}>
      <div className="confetti" aria-hidden>
        {Array.from({ length: 28 }, (_, i) => (
          <span key={i} style={{ left: `${(i * 37) % 100}%`, animationDelay: `${(i % 7) * 0.15}s`, background: ["#f472b6", "#38bdf8", "#fbbf24", "#a78bfa"][i % 4] }} />
        ))}
      </div>
      <div className="bc-victory-art">
        <Art slot="victory" className="art-fill" />
      </div>
      <p className="eyebrow">{room.finish_reason}</p>
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

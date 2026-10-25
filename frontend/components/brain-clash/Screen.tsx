"use client";

import qrcode from "qrcode-generator";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, type BcFeed, type BcGame, type BcRoom, type BcTeam } from "@/lib/api";
import { modeName, ROOM_GAMES } from "@/lib/brainClash";
import { announce, sfx } from "@/lib/game";
import { useLive } from "@/lib/useLive";

import { Logo } from "../brand/Logo";

const TEAMS: BcTeam[] = ["A", "B"];
type Reaction = { id: number; emoji: string; from: string };

const teamName = (room: BcRoom, t: BcTeam) => room.settings.team_names[t];

/** A QR code as crisp SVG squares, so a phone can scan the TV from across the room. */
function QR({ text, label }: { text: string; label: string }) {
  const cells = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    const n = qr.getModuleCount();
    const on: [number, number][] = [];
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) if (qr.isDark(y, x)) on.push([x, y]);
    return { n, on };
  }, [text]);
  return (
    <svg className="ps-qr" viewBox={`-2 -2 ${cells.n + 4} ${cells.n + 4}`} role="img" aria-label={label}>
      <rect x={-2} y={-2} width={cells.n + 4} height={cells.n + 4} fill="#fff" rx={1.5} />
      {cells.on.map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width={1.02} height={1.02} fill="#0a0819" />
      ))}
    </svg>
  );
}

/** Seconds until an ISO time on the server's clock, ticking. */
function useSecondsLeft(iso: string | null, offset: number) {
  const calc = useCallback(() => (iso ? Math.max(0, (Date.parse(iso) - (Date.now() + offset)) / 1000) : 0), [iso, offset]);
  const [left, setLeft] = useState(calc);
  useEffect(() => {
    setLeft(calc());
    const id = setInterval(() => setLeft(calc()), 200);
    return () => clearInterval(id);
  }, [calc]);
  return left;
}

function feedText(f: BcFeed): string {
  switch (f.verdict) {
    case "correct":
      return `got it! +${f.points}`;
    case "steal":
      return `STOLE IT! +${f.points}`;
    case "item":
      return `+${f.points}: ${f.items.join(", ")}`;
    case "duplicate":
      return "repeated an answer";
    case "line":
      return f.points ? `added a line ⚡ +${f.points}` : "added a line";
    case "streak":
      return `is ON FIRE 🔥 +${f.points}`;
    default:
      return "missed";
  }
}

/** /brain-clash/CODE/screen?key=…: the room on a TV or laptop everyone can see. Players answer on their phones. */
export function PartyScreen({ code, game }: { code: string; game: BcGame }) {
  const [key, setKey] = useState<string | null>(null);
  const [room, setRoom] = useState<BcRoom | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [sound, setSound] = useState(false); // browsers only allow sound after a tap
  const [reactions, setReactions] = useState<Reaction[]>([]);
  const [origin, setOrigin] = useState("");
  const g = ROOM_GAMES[room?.game ?? game];

  useEffect(() => {
    setKey(new URLSearchParams(window.location.search).get("key"));
    setOrigin(window.location.origin);
  }, []);

  const load = useCallback(async () => {
    if (!key) return;
    try {
      const r = await api.bc.screen(code, key);
      setOffset(Date.parse(r.server_time) - Date.now());
      setRoom(r);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [code, key]);

  useEffect(() => {
    load();
  }, [load]);
  const onReaction = useCallback((emoji: string, from: string) => {
    const id = Date.now() + Math.random();
    setReactions((rs) => [...rs.slice(-16), { id, emoji, from }]);
    setTimeout(() => setReactions((rs) => rs.filter((r) => r.id !== id)), 3000);
  }, []);
  useLive(null, null, { onBrainClash: load, onReaction }, key ? code : null, key);

  // At the buzzer the screen asks "time's up?" too, so the match moves on even if every phone is locked.
  // The server checks its own clock; a phone that asked first just means there's nothing left to do.
  const closes = room?.status === "playing" ? (room.round?.phase === "reveal" ? room.round.reveal_until : room.round?.closes_at) : null;
  useEffect(() => {
    if (!closes || !key) return;
    // The server keeps answers sent just before the buzzer for 0.75 s (GRACE_SECONDS), so ask after that.
    const ms = Date.parse(closes) - (Date.now() + offset) + 1100;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const ask = (again: boolean) =>
      api.bc
        .screenAdvance(code, key)
        .then((r) => {
          setOffset(Date.parse(r.server_time) - Date.now());
          setRoom(r);
        })
        .catch(() => {
          if (again) retry = setTimeout(() => ask(false), 1000);
          else load();
        });
    const id = setTimeout(() => ask(true), Math.max(300, ms));
    return () => {
      clearTimeout(id);
      clearTimeout(retry);
    };
  }, [closes, offset, load, code, key]);

  async function startShow() {
    setSound(true);
    sfx("join", true);
    await document.documentElement.requestFullscreen?.().catch(() => {});
  }

  if (key === null && origin) return <ScreenMessage title="This party-screen link is missing its key" text="Open it again from the host's lobby." />;
  if (error) return <ScreenMessage title="Can't open the party screen" text={error} />;
  if (!room) return <ScreenMessage title="Opening the party screen…" text={`${g.title} · room ${code}`} />;

  const joinUrl = `${origin}${g.path}/${encodeURIComponent(room.code)}`;
  return (
    <div className={`party-screen status-${room.status} game-${room.game}`}>
      <header className="ps-top">
        <Logo size={34} />
        <span className="ps-title">
          {room.game === "brain-clash" ? `Brain Clash · ${modeName(room.settings.mode)}` : g.title}
        </span>
        <span className="ps-code">
          Room <strong>{room.code}</strong>
        </span>
      </header>

      {room.status === "lobby" && <ScreenLobby room={room} joinUrl={joinUrl} />}
      {room.status === "playing" && <ScreenMatch room={room} offset={offset} sound={sound} screenKey={key!} />}
      {room.status === "finished" && <ScreenVictory room={room} joinUrl={joinUrl} sound={sound} />}

      <div className="floaters ps-floaters" aria-hidden>
        {reactions.map((r) => (
          <span key={r.id} className="floater" style={{ left: `${8 + ((Math.round(r.id) * 37) % 84)}%` }}>
            {r.emoji}
            <small>{r.from}</small>
          </span>
        ))}
      </div>
      {!sound && (
        <button className="ps-start" onClick={startShow}>
          🔊 Tap to start the show <small>(sound and full screen)</small>
        </button>
      )}
    </div>
  );
}

function ScreenMessage({ title, text }: { title: string; text: string }) {
  return (
    <div className="party-screen ps-message">
      <Logo size={48} />
      <h1>{title}</h1>
      <p>{text}</p>
    </div>
  );
}

function ScreenLobby({ room, joinUrl }: { room: BcRoom; joinUrl: string }) {
  const host = room.players.find((p) => p.user_id === room.host_id)?.name ?? "the host";
  return (
    <section className="ps-lobby">
      <section className="ps-join">
        <h1>Scan to join</h1>
        {joinUrl && <QR text={joinUrl} label={`QR code for ${joinUrl}`} />}
        <p className="ps-url">{joinUrl.replace(/^https?:\/\//, "")}</p>
        <p className="ps-big-code">{room.code}</p>
      </section>
      <section className="ps-teams">
        {TEAMS.map((t) => {
          const players = room.players.filter((p) => p.team === t);
          return (
            <div key={t} className={`ps-team team-${t}`}>
              <h2>{teamName(room, t)}</h2>
              <ul>
                {players.map((p) => (
                  <li key={p.user_id} className="seat-in">
                    {p.name}
                    {p.user_id === room.host_id && <small> host</small>}
                  </li>
                ))}
                {!players.length && <li className="ps-empty">Waiting for players…</li>}
              </ul>
            </div>
          );
        })}
        <p className="ps-waiting">
          {room.settings.rounds} rounds · {room.settings.seconds || 20}s a question · waiting for {host} to start
        </p>
      </section>
    </section>
  );
}

function Scores({ room }: { room: BcRoom }) {
  const r = room.round;
  return (
    <div className="ps-scores">
      {TEAMS.map((t) => (
        <div key={t} className={`ps-score team-${t} ${r?.turn_team === t && r.phase !== "reveal" ? "on-turn" : ""}`}>
          <span className="ps-team-name">{teamName(room, t)}</span>
          <strong>{room.scores[t]}</strong>
          {room.streaks[t] >= 3 && <span className="ps-streak">🔥 {room.streaks[t]} in a row</span>}
        </div>
      ))}
    </div>
  );
}

function ScreenMatch({ room, offset, sound, screenKey }: { room: BcRoom; offset: number; sound: boolean; screenKey: string }) {
  const r = room.round!;
  const reveal = r.phase === "reveal";
  const left = useSecondsLeft(reveal ? r.reveal_until : r.closes_at, offset);
  const total = Math.max(1, (Date.parse(r.closes_at) - Date.parse(r.opened_at)) / 1000);
  const performer = room.players.find((p) => p.user_id === r.performer_id)?.name;
  const lastPhase = useRef("");
  useEffect(() => {
    const now = `${r.number}:${r.phase}`;
    if (now === lastPhase.current) return;
    lastPhase.current = now;
    if (reveal) sfx(Object.keys(r.scored).length ? "score" : "zero", sound);
    else if (r.phase === "steal") announce(`Steal! ${teamName(room, r.turn_team ?? "A")}, it's yours.`, sound);
    else sfx("turn", sound);
  }, [r.number, r.phase, r.scored, r.turn_team, reveal, room, sound]);
  useEffect(() => {
    if (!reveal && left > 0 && left <= 5 && Math.abs(left - Math.round(left)) < 0.11) sfx("tick", sound);
  }, [left, reveal, sound]);

  const status = reveal
    ? r.winner_team
      ? `${teamName(room, r.winner_team)} took the round`
      : "Nobody got it"
    : r.phase === "steal"
      ? `STEAL! ${teamName(room, r.turn_team ?? "A")} can snatch it`
      : r.phase === "hum"
        ? `🎵 ${performer ?? "The hummer"} is recording a hum…`
        : r.phase === "vote"
          ? "🔥 Fire at the line you love!"
          : r.turn_team && room.settings.mode !== "quickfire" && room.settings.mode !== "namefast" && room.settings.mode !== "association"
            ? `${teamName(room, r.turn_team)}'s turn`
            : "Both teams: answer on your phones!";

  return (
    <section className="ps-match">
      <Scores room={room} />
      <section className={`ps-question ${reveal ? "revealed" : ""}`} key={`${r.number}-${r.phase === "reveal"}`}>
        <p className="ps-round">
          {r.tiebreak ? "Tie-breaker" : `Round ${r.number} of ${room.rounds_total}`} · {r.question.category_name}
          {r.question.kind === "list" && r.question.target ? ` · name ${r.question.target}` : ""} · {r.question.points} pts
        </p>
        {room.game === "story-forge" ? (
          <StoryOnScreen room={room} />
        ) : (
          <h1 className="ps-prompt">{r.question.prompt}</h1>
        )}
        {r.question.kind === "spark" && r.question.spark && <p className="ps-spark">⚡ Spark word: {r.question.spark}</p>}
        {r.question.kind === "list" && (
          <p className="ps-found">
            {TEAMS.map((t) => `${teamName(room, t)} ${r.found_count[t]}`).join("   ·   ")}
          </p>
        )}
        {r.has_clip && !reveal && r.phase !== "hum" && <ScreenHum code={room.code} round={r.number} screenKey={screenKey} sound={sound} />}
        {reveal && r.reveal && (
          <div className="ps-reveal pop">
            <span>{r.question.kind === "song" ? "The song was" : r.question.kind === "list" ? "Answers that counted" : "The answer"}</span>
            <strong>{r.question.kind === "list" ? [...r.found.A, ...r.found.B, ...r.reveal.more].slice(0, 10).join(", ") : r.reveal.answer}</strong>
            {r.reveal.explanation && <p>{r.reveal.explanation}</p>}
          </div>
        )}
      </section>
      <p className={`ps-status ${r.phase}`}>{status}</p>
      {!reveal && (
        <div className="ps-timer" aria-label={`${Math.ceil(left)} seconds left`}>
          <div className="ps-timer-fill" style={{ width: `${Math.min(100, (left / total) * 100)}%` }} />
          <span>{Math.ceil(left)}</span>
        </div>
      )}
      <ul className="ps-feed">
        {room.feed
          .filter((f) => f.round === r.number && f.said !== "…")
          .slice(-4)
          .map((f, i) => (
            <li key={i} className={`team-${f.team} ${f.points > 0 ? "good" : ""}`}>
              <strong>{f.player}</strong> {feedText(f)}
            </li>
          ))}
      </ul>
    </section>
  );
}

function StoryOnScreen({ room }: { room: BcRoom }) {
  const r = room.round!;
  const lines = [...(room.opener ? [{ key: "opener", text: room.opener, team: null as BcTeam | null }] : []),
    ...room.story.map((s) => ({ key: String(s.round), text: s.line, team: s.team as BcTeam | null }))].slice(-4);
  return (
    <div className="ps-story">
      {lines.map((l) => (
        <p key={l.key} className={l.team ? `team-${l.team}` : "opener"}>
          {l.text}
        </p>
      ))}
      {r.phase === "vote" && r.line && <p className="ps-new-line pop">“{r.line}” {"🔥".repeat(Math.min(r.fires, 8))}</p>}
    </div>
  );
}

/** Beat Drop: the hum on the big speaker. */
function ScreenHum({ code, round, screenKey, sound }: { code: string; round: number; screenKey: string; sound: boolean }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let made: string | null = null;
    api.bc
      .screenHum(code, screenKey)
      .then((blob) => setUrl((made = URL.createObjectURL(blob))))
      .catch(() => {});
    return () => {
      if (made) URL.revokeObjectURL(made);
    };
  }, [code, round, screenKey]);
  if (!url) return null;
  return (
    <div className="ps-hum">
      <span className="eq" aria-hidden>
        <i />
        <i />
        <i />
        <i />
        <i />
      </span>
      <audio src={url} controls autoPlay={sound} aria-label="The hum" />
    </div>
  );
}

function ScreenVictory({ room, joinUrl, sound }: { room: BcRoom; joinUrl: string; sound: boolean }) {
  const champ = room.winner === "draw" ? null : (room.winner as BcTeam | null);
  const star = [...room.players].sort((a, b) => b.points - a.points)[0];
  const said = useRef(false);
  useEffect(() => {
    if (said.current) return;
    said.current = true;
    sfx("win", sound);
    announce(champ ? `${teamName(room, champ)} are the champions!` : "It's a draw!", sound);
  }, [champ, room, sound]);
  return (
    <section className={`ps-victory ${champ ? `team-${champ}` : ""}`}>
      <div className="confetti" aria-hidden>
        {Array.from({ length: 40 }, (_, i) => (
          <span key={i} style={{ left: `${(i * 37) % 100}%`, animationDelay: `${(i % 8) * 0.18}s`, background: ["#f472b6", "#38bdf8", "#fbbf24", "#a78bfa"][i % 4] }} />
        ))}
      </div>
      <p className="ps-round">{room.finish_reason}</p>
      <h1 className="ps-champion">{champ ? `${teamName(room, champ)} wins!` : "It's a draw!"}</h1>
      <Scores room={room} />
      {star && star.points > 0 && (
        <p className="ps-star">
          ⭐ Star player: <strong>{star.name}</strong> · {star.points} pts
        </p>
      )}
      <div className="ps-again">
        {joinUrl && <QR text={joinUrl} label="QR code to join the rematch" />}
        <p>Rematch? Scan to join, then the host taps Play again.</p>
      </div>
    </section>
  );
}

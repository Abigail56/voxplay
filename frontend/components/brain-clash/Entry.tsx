"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, type BcCategory, type BcGame, type BcMode } from "@/lib/api";
import { BC_MODES, ROOM_GAMES } from "@/lib/brainClash";
import { useAuthStore } from "@/store/useAuthStore";

import { ArtTile } from "../art/ArtTile";
import { Art, CategoryArt } from "../art/Scenes";

/** /brain-clash, /beat-drop and /story-forge: what the game is, and the way in (create a room, or join one with a code). */
export function GameEntry({ game }: { game: BcGame }) {
  const g = ROOM_GAMES[game];
  const router = useRouter();
  const { me, ready, restore } = useAuthStore();
  const [cats, setCats] = useState<BcCategory[]>([]);
  const [mode, setMode] = useState<BcMode>(g.mode);
  const [picked, setPicked] = useState<string[]>([]);
  const [rounds, setRounds] = useState(game === "brain-clash" ? 10 : 6);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    restore();
    api.bc.categories(game).then(setCats).catch(() => setCats([]));
  }, [restore, game]);

  const available = cats.filter((c) => (c.counts[mode] ?? 0) > 0);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const categories = picked.filter((id) => available.some((c) => c.id === id));
      const room = await api.bc.create({ mode, rounds, categories }, name.trim() || undefined);
      router.push(`${g.path}/${room.code}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className={`landing game-${game}`}>
      <section className="bc-banner">
        <Art slot={g.art} className="art-fill" />
        <div className="bc-banner-copy">
          <p className="eyebrow">{g.eyebrow}</p>
          <h1 className="page-title">{g.title}</h1>
          <p className="game-tagline">{g.tagline}</p>
          <p className="lede">{g.lede}</p>
          <div className="row">
            <a href="#create" className="btn primary big">
              Create room
            </a>
            <a href="#join" className="btn big">
              Join room
            </a>
          </div>
        </div>
      </section>

      <div className="bc-entry-grid">
        <section className="card" id="create" aria-labelledby="create-title">
          <h2 id="create-title">Create a room</h2>
          {!ready ? (
            <p className="hint">Checking who you are…</p>
          ) : !me ? (
            <>
              <p className="hint">You need a VOXPLAY player to host or join (a name and a password, no voice setup).</p>
              <Link href={`/sign-in?next=${g.path}`} className="btn primary">
                Sign in to play
              </Link>
            </>
          ) : (
            <>
              {game === "brain-clash" && (
                <div className="bc-modes" role="radiogroup" aria-label="Game mode">
                  {BC_MODES.map((m) => (
                    <button key={m.id} type="button" role="radio" aria-checked={mode === m.id} className={`mode ${mode === m.id ? "on" : ""}`} onClick={() => setMode(m.id)}>
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
                  Categories <span className="hint">{picked.length ? `${picked.length} picked` : "all of them"}</span>
                </legend>
                {available.map((c) => (
                  <label key={c.id} className={`chip-toggle ${picked.includes(c.id) ? "on" : ""}`}>
                    <input type="checkbox" checked={picked.includes(c.id)} onChange={() => toggle(c.id)} />
                    {c.name}
                  </label>
                ))}
              </fieldset>
              <div className="row">
                <label className="field">
                  Rounds
                  <select value={rounds} onChange={(e) => setRounds(Number(e.target.value))}>
                    {(game === "brain-clash" ? [5, 10, 15, 20] : [4, 6, 8, 10, 12]).map((n) => (
                      <option key={n}>{n}</option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Your name in the room
                  <input value={name} onChange={(e) => setName(e.target.value)} placeholder={me.username} maxLength={20} />
                </label>
              </div>
              <p className="hint">You can change all of this, set the timer, a winning score and team names in the room.</p>
              <button className="btn primary big" onClick={create} disabled={busy}>
                {busy ? "Opening the room…" : "Create room"}
              </button>
              {error && <p className="error">{error}</p>}
            </>
          )}
        </section>

        <section className="card" id="join" aria-labelledby="join-title">
          <h2 id="join-title">Join a room</h2>
          <p className="hint">Got a code from a friend, like NOVA-42? Type it here, or just open the link they sent.</p>
          <form
            className="join"
            onSubmit={(e) => {
              e.preventDefault();
              if (code.trim().length >= 4) router.push(`${g.path}/${encodeURIComponent(code.trim().toUpperCase())}`);
            }}
          >
            <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="Room code" aria-label="Room code" maxLength={20} />
            <button className="btn primary" disabled={code.trim().length < 4}>
              Join
            </button>
          </form>
          <h3>Multiplayer</h3>
          <ul className="bc-facts">
            <li>Everyone plays on their own phone, laptop or tablet.</li>
            <li>Two teams, 2 to 20 players. The host picks the teams or shuffles them.</li>
            <li>Everything arrives on every screen at the same moment.</li>
            <li>Lost your connection? Open the link again: your team and points are kept.</li>
            <li>🤖 A fair-play AI watches for cheating; the host has the final say.</li>
          </ul>
        </section>
      </div>

      <section className="landing-section" aria-labelledby="how-bc">
        <div className="section-title">
          <p className="eyebrow">How to play</p>
          <h2 id="how-bc">{g.howTitle}</h2>
        </div>
        <div className="art-tile-grid">
          {g.how.map((m) => (
            <ArtTile key={m.name} slot={m.art} title={m.name} icon={m.icon}>
              <ul className="bc-rules">
                {m.rules.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </ArtTile>
          ))}
        </div>
        {game === "brain-clash" && (
          <p className="hint">
            Answer by voice (press the mic, say it, press stop) or type it. The server turns speech into words, checks
            them against the accepted answers (small slips and different spellings are fine) and keeps the score. Level
            at the end? One tie-breaker question decides it, or it&apos;s a draw. Win three rounds in a row and your team
            is on fire: +5 every round the streak lasts.
          </p>
        )}
      </section>

      <section className="landing-section" aria-labelledby="cats-bc">
        <div className="section-title">
          <p className="eyebrow">Categories</p>
          <h2 id="cats-bc">{g.catsTitle}</h2>
        </div>
        <ul className="art-tile-grid small">
          {cats.map((c) => (
            <li key={c.id}>
              <ArtTile media={<CategoryArt id={c.id} className="art-fill" />} title={c.name} size="small">
                <span className="hint">{Object.values(c.counts).reduce((a, b) => a + (b ?? 0), 0)} challenges</span>
              </ArtTile>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

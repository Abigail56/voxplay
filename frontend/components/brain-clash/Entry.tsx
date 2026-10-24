"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, type BcCategory, type BcMode } from "@/lib/api";
import { BC_MODES } from "@/lib/brainClash";
import { useAuthStore } from "@/store/useAuthStore";

import { Art } from "../art/Scenes";

/** /brain-clash: what the game is, and the way in (create a room, or join one with a code). */
export function BrainClashEntry() {
  const router = useRouter();
  const { me, ready, restore } = useAuthStore();
  const [cats, setCats] = useState<BcCategory[]>([]);
  const [mode, setMode] = useState<BcMode>("battle");
  const [picked, setPicked] = useState<string[]>([]);
  const [rounds, setRounds] = useState(10);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    restore();
    api.bc.categories().then(setCats).catch(() => setCats([]));
  }, [restore]);

  const available = cats.filter((c) => c.counts[mode] > 0);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const categories = picked.filter((id) => available.some((c) => c.id === id));
      const room = await api.bc.create({ mode, rounds, categories }, name.trim() || undefined);
      router.push(`/brain-clash/${room.code}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="landing">
      <section className="bc-banner">
        <Art slot="brainClash" className="art-fill" />
        <div className="bc-banner-copy">
          <p className="eyebrow">A VOXPLAY team quiz</p>
          <h1 className="page-title">Brain Clash</h1>
          <p className="game-tagline">Two teams. One battle. One champion.</p>
          <p className="lede">
            Split into two teams and battle through questions on African and Nigerian knowledge, music, football, food,
            Pidgin, riddles and more. Shout your answer into your phone or type it. The server keeps score.
          </p>
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
              <Link href="/sign-in?next=/brain-clash" className="btn primary">
                Sign in to play
              </Link>
            </>
          ) : (
            <>
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
                    {[5, 10, 15, 20].map((n) => (
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
                {busy ? "Opening the arena…" : "Create room"}
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
              if (code.trim().length >= 4) router.push(`/brain-clash/${encodeURIComponent(code.trim().toUpperCase())}`);
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
            <li>Questions, timers and scores arrive on every screen at the same moment.</li>
            <li>Lost your connection? Open the link again: your team and points are kept.</li>
          </ul>
        </section>
      </div>

      <section className="landing-section" aria-labelledby="how-bc">
        <div className="section-title">
          <p className="eyebrow">How to play</p>
          <h2 id="how-bc">Four ways to clash</h2>
        </div>
        <div className="feature-grid">
          {BC_MODES.map((m) => (
            <div key={m.id} className="feature">
              <span className="feature-icon" aria-hidden>
                {m.icon}
              </span>
              <h3>{m.name}</h3>
              <ul className="bc-rules">
                {m.rules.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="hint">
          Answer by voice (press the mic, say it, press stop) or type it. The server turns speech into words, checks
          them against the accepted answers (small slips and different spellings are fine) and keeps the score. Level
          at the end? One tie-breaker question decides it, or it&apos;s a draw.
        </p>
      </section>

      <section className="landing-section" aria-labelledby="cats-bc">
        <div className="section-title">
          <p className="eyebrow">Categories</p>
          <h2 id="cats-bc">Sixteen ways to win</h2>
        </div>
        <ul className="cat-grid">
          {cats.map((c) => (
            <li key={c.id}>
              <strong>{c.name}</strong>
              <span className="hint">{Object.values(c.counts).reduce((a, b) => a + b, 0)} challenges</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

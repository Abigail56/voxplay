"use client";

import { useState } from "react";

import { api, type Dashboard, type GameMode, type Room } from "@/lib/api";

import { MODES, ModePicker } from "./ModePicker";

/** Not in a game yet: start one, join one with a code, or pick an open game. */
export function Lobby({ dashboard, onEnter }: { dashboard: Dashboard | null; onEnter: (room: Room) => void }) {
  const [code, setCode] = useState("");
  const [mode, setMode] = useState<GameMode>("yourself");
  const [rounds, setRounds] = useState(2);
  const [speed, setSpeed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const open = dashboard?.rooms.filter((r) => r.status === "lobby") ?? [];
  const playing = dashboard?.rooms.filter((r) => r.status === "playing") ?? [];

  async function run(action: () => Promise<Room>) {
    setBusy(true);
    setError(null);
    try {
      onEnter(await action());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card lobby">
      <h2>Play</h2>

      <form
        className="join"
        onSubmit={(e) => {
          e.preventDefault();
          run(() => api.joinRoom(code.trim()));
        }}
      >
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="Game code, like TIGER-42"
          aria-label="Game code"
          maxLength={20}
        />
        <button className="btn primary" disabled={busy || code.trim().length < 4}>
          Join
        </button>
      </form>

      <div className="or">or start your own</div>
      <ModePicker value={mode} onChange={setMode} disabled={busy} />
      <div className="create">
        <label className="field">
          Rounds
          <select value={rounds} onChange={(e) => setRounds(Number(e.target.value))}>
            {[1, 2, 3, 5].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label className="consent">
          <input type="checkbox" checked={speed} onChange={(e) => setSpeed(e.target.checked)} />Speed round
        </label>
        <button className="btn primary big" disabled={busy} onClick={() => run(() => api.createRoom(mode, rounds, speed))}>
          Create game
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      {open.length > 0 && (
        <>
          <h3>Open games</h3>
          <ul className="room-list">
            {open.map((r) => (
              <li key={r.code}>
                <div>
                  <strong className="code">{r.code}</strong>
                  <span className="hint">
                    {" "}
                    · {r.host}&apos;s game · {MODES.find((m) => m.id === r.mode)?.name} ·{" "}
                    {r.players.length} waiting
                  </span>
                </div>
                <button className="btn small primary" disabled={busy} onClick={() => run(() => api.joinRoom(r.code))}>
                  Join
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {playing.length > 0 && (
        <p className="hint">
          Playing now:{" "}
          {playing.map((r) => `${r.players.join(", ")} (turn ${r.turn + 1}/${r.turns_total})`).join(" · ")}
        </p>
      )}
    </section>
  );
}

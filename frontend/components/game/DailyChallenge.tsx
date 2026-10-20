"use client";

import { useCallback, useEffect, useState } from "react";

import { api, type Clip, type DailyState } from "@/lib/api";
import { flag } from "@/lib/countries";
import { announce, sfx } from "@/lib/game";

import { ClipInput } from "../ClipInput";

function hms(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

/** Today's tongue-twister: 3 tries, best counts, streaks, and today's leaderboard. */
export function DailyChallenge({ sound, refreshKey, onPlayed }: { sound: boolean; refreshKey: number; onPlayed: () => void }) {
  const [state, setState] = useState<DailyState | null>(null);
  // Kept apart from `state`: background refreshes (any player's turn) mustn't wipe your result.
  const [last, setLast] = useState<DailyState["last_attempt"]>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.daily().then(setState).catch((e) => setError((e as Error).message));
  }, []);
  useEffect(load, [load, refreshKey]);

  async function attempt(clip: Clip) {
    setBusy(true);
    setError(null);
    try {
      const s = await api.tryDaily(clip);
      setState(s);
      setLast(s.last_attempt);
      const score = s.last_attempt?.score ?? 0;
      sfx(score > 0 ? "score" : "zero", sound);
      announce(s.last_attempt?.message ?? "", sound);
      onPlayed();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!state) return <section className="card daily">{error ? <p className="error">{error}</p> : <p className="hint">Loading today&apos;s challenge…</p>}</section>;

  return (
    <section className="card daily">
      <div className="section-head">
        <h2>Daily challenge</h2>
        {state.streak > 0 && <span className="streak">{state.streak}-day streak</span>}
      </div>
      <p className="hint">Today&apos;s tongue-twister, the same for everyone. Say it in your own voice!</p>
      <blockquote className="read-line daily-phrase">&ldquo;{state.phrase}&rdquo;</blockquote>

      {state.attempts_left > 0 ? (
        <>
          <ClipInput onClip={attempt} disabled={busy} allowUpload={false} />
          <p className="hint">
            {state.attempts_left} {state.attempts_left === 1 ? "try" : "tries"} left today · your best counts
            {state.best !== null && (
              <>
                {" "}
                · best so far <strong>{state.best}</strong>
              </>
            )}
          </p>
        </>
      ) : (
        <p className="tagline">
          Done for today: best <strong>{state.best}</strong>. New phrase in {hms(state.ends_in_seconds)}.
        </p>
      )}
      {busy && <p className="hint">Listening…</p>}
      {last && (
        <div className={`result pop ${last.score > 0 ? "match" : "unknown"}`}>
          <div className="points">{last.score}</div>
          <p className="announce">{last.message}</p>
          <p className="hint">Heard: &ldquo;{last.heard || "nothing"}&rdquo;</p>
        </div>
      )}
      {error && <p className="error">{error}</p>}

      {state.leaderboard.length > 0 && (
        <ol className="mini-board">
          {state.leaderboard.slice(0, 5).map((e, i) => (
            <li key={e.username}>
              <span>
                <span className="rank">{i + 1}</span> {flag(e.country)} {e.username}
              </span>
              <strong>{e.score}</strong>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

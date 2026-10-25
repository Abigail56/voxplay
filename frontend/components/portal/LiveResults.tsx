"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type MatchResult } from "@/lib/api";
import { ROOM_GAMES } from "@/lib/brainClash";

const ICON = { "brain-clash": "⚔️", "beat-drop": "🎵", "story-forge": "✍️", "word-bomb": "💣" } as const;

function ago(iso: string, now: number) {
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

/** The latest finished matches from the server, refreshed every 10 seconds. Real results only. */
export function LiveResults() {
  const [results, setResults] = useState<MatchResult[] | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const load = () =>
      api
        .results()
        .then((r) => {
          setResults(r);
          setNow(Date.now());
        })
        .catch(() => {});
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);
  if (results === null) return null;
  if (!results.length)
    return (
      <p className="hint">
        No matches finished yet. <Link href="/brain-clash">Start the first one</Link> and it shows up here live.
      </p>
    );
  return (
    <ul className="live-results" aria-live="polite">
      {results.map((r) => {
        const g = ROOM_GAMES[r.game];
        return (
          <li key={r.id} className={`result-card winner-${r.winner}`}>
            <span className="result-game">
              <span aria-hidden>{ICON[r.game]}</span> {g.title}
            </span>
            <span className="result-score">
              <span className={`team a ${r.winner === "A" ? "won" : ""}`}>{r.team_a}</span>
              <strong>
                {r.score_a} – {r.score_b}
              </strong>
              <span className={`team b ${r.winner === "B" ? "won" : ""}`}>{r.team_b}</span>
            </span>
            <span className="hint">
              {r.winner === "draw" ? "Draw" : `${r.winner === "A" ? r.team_a : r.team_b} won`} · {r.rounds} rounds · {ago(r.finished_at, now)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

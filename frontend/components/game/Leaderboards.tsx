"use client";

import { useEffect, useState } from "react";

import { api, type Leaderboards as Boards } from "@/lib/api";
import { countryName, flag } from "@/lib/countries";

import { Avatar } from "./Avatar";

function dhm(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
}

/** This week: country vs country, and the Weekly Cup (Top 8 + last week's champion). */
export function Leaderboards({ refreshKey }: { refreshKey: number }) {
  const [boards, setBoards] = useState<Boards | null>(null);

  useEffect(() => {
    api.leaderboards().then(setBoards).catch(() => {});
  }, [refreshKey]);

  if (!boards) return null;
  const top = boards.countries[0]?.points || 1;

  return (
    <div className="grid">
      <section className="card">
        <h2>Country vs country</h2>
        <p className="hint">Every point scored this week counts for your country. Resets on Monday.</p>
        {boards.countries.length === 0 ? (
          <p className="hint">No points yet this week. Play a game to get your country on the board.</p>
        ) : (
          <ul className="country-board">
            {boards.countries.map((c, i) => (
              <li key={c.country}>
                <span className="country-name">
                  {flag(c.country)} {countryName(c.country)}
                  <span className="hint"> · {c.players} player{c.players === 1 ? "" : "s"}</span>
                </span>
                <span className="bar" style={{ width: `${(c.points / top) * 100}%` }} />
                <strong className="num">{c.points}</strong>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <div className="section-head">
          <h2>Weekly Cup</h2>
          <span className="hint">ends in {dhm(boards.week_ends_in_seconds)}</span>
        </div>
        <p className="hint">Top 8 this week, counting games and the daily challenge. Whoever's on top on Monday wins the cup.</p>
        {boards.last_week_champion && (
          <p className="champion">
            Last week&apos;s champion: <strong>{boards.last_week_champion.username}</strong> {flag(boards.last_week_champion.country)} with{" "}
            {boards.last_week_champion.points} points
          </p>
        )}
        {boards.weekly_top.length === 0 ? (
          <p className="hint">Nobody has scored this week yet.</p>
        ) : (
          <ol className="cup">
            {boards.weekly_top.map((e, i) => (
              <li key={e.username} className={i < 3 ? `podium p${i + 1}` : ""}>
                <span className="place">{i + 1}</span>
                <Avatar name={e.username} size={28} />
                <span className="who">
                  {e.username} {flag(e.country)}
                  {e.wins > 0 && <span className="hint"> · {e.wins} win{e.wins === 1 ? "" : "s"}</span>}
                </span>
                <strong className="num">{e.points}</strong>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

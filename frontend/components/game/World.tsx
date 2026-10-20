"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";

import type { Dashboard } from "@/lib/api";
import { countryName, flag } from "@/lib/countries";
import { level } from "@/lib/game";

import { Avatar } from "./Avatar";
import type { Place } from "./PlayersMapLeaflet";

const PlayersMapLeaflet = dynamic(() => import("./PlayersMapLeaflet"), {
  ssr: false,
  loading: () => <div className="play-map placeholder hint">Loading map…</div>,
});

function toPlaces(d: Dashboard): Place[] {
  const places = new Map<string, Place>();
  for (const p of d.players) {
    if (p.lat === null || p.lon === null) continue;
    const key = `${p.lat},${p.lon}`;
    const label = `${flag(p.country)} ${p.place ?? ""}${p.country ? `, ${countryName(p.country)}` : ""}`;
    const place = places.get(key) ?? { key, label, lat: p.lat, lon: p.lon, online: false, players: [] };
    place.players.push({ name: p.username, online: p.online, points: p.total_points, room: p.room_code });
    place.online ||= p.online;
    places.set(key, place);
  }
  return [...places.values()];
}

function ago(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

/** Everyone who plays: the map, the all-time leaderboard and the live feed. */
export function World({ dashboard }: { dashboard: Dashboard }) {
  const places = useMemo(() => toPlaces(dashboard), [dashboard]);
  const ranked = useMemo(
    () => [...dashboard.players].filter((p) => p.has_voice).sort((a, b) => b.total_points - a.total_points),
    [dashboard],
  );

  return (
    <>
      <section className="card">
        <div className="section-head">
          <h2>Where people are playing</h2>
          <span className="online-count">
            <span className="presence on" /> {dashboard.online} online
          </span>
        </div>
        <p className="hint">
          Each pin is roughly where a player lives. Red pins have someone online right now.
        </p>
        <PlayersMapLeaflet places={places} />
      </section>

      <div className="grid">
        <section className="card">
          <h2>All-time leaderboard</h2>
          {ranked.length === 0 ? (
            <p className="hint">No players yet.</p>
          ) : (
            <table className="leaders">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Player</th>
                  <th>Now</th>
                  <th className="num">Points</th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((p, i) => (
                  <tr key={p.user_id} className={p.user_id === dashboard.me ? "current" : ""}>
                    <td className="rank">{i + 1}</td>
                    <td>
                      <span className="who-cell">
                        <Avatar name={p.username} size={28} online={p.online} />
                        <span>
                          {p.username}
                          <span className="hint"> · Lv {level(p.total_points).level}</span>
                          <span className="hint">
                            {" "}
                            · {flag(p.country)} {p.place ?? (p.country ? countryName(p.country) : "")}
                          </span>
                        </span>
                      </span>
                    </td>
                    <td className="hint">
                      {p.room_code ? (p.room_status === "playing" ? `playing ${p.room_code}` : `in ${p.room_code}`) : p.online ? "online" : "offline"}
                    </td>
                    <td className="num">
                      <strong>{p.total_points}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="card">
          <h2>Latest turns</h2>
          {dashboard.recent_plays.length === 0 ? (
            <p className="hint">No turns played yet.</p>
          ) : (
            <ul className="feed">
              {dashboard.recent_plays.map((p, i) => (
                <li key={i}>
                  <Avatar name={p.username} size={28} />
                  <span>
                    <strong>{p.username}</strong> scored <strong>{p.points}</strong>
                    {p.mode === "impersonate" ? " impersonating" : ""}
                    {p.room_code && <span className="hint"> in {p.room_code}</span>}
                  </span>
                  <span className="hint">{ago(p.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}

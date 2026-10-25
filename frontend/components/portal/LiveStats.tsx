"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

/** Real numbers from the server (players online now, players, matches played), refreshed every 30 s.
 *  Nothing is shown until they arrive, so the page never displays made-up activity. */
export function LiveStats() {
  const [s, setS] = useState<Awaited<ReturnType<typeof api.stats>> | null>(null);
  useEffect(() => {
    const load = () => api.stats().then(setS).catch(() => {});
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);
  if (!s) return null;
  return (
    <ul className="live-stats" aria-label="VOXPLAY right now">
      <li>
        <span className="live-dot" aria-hidden /> <strong>{s.online}</strong> online now
      </li>
      <li>
        <strong>{s.players}</strong> players
      </li>
      <li>
        <strong>{s.matches}</strong> team matches played
      </li>
    </ul>
  );
}

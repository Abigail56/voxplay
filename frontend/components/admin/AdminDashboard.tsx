"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api, SignedOutError, type AdminOverview, type AdminPlay, type AdminPlayer, type AdminRoom } from "@/lib/api";
import { countryName } from "@/lib/countries";
import { useLive } from "@/lib/useLive";
import { useAuthStore } from "@/store/useAuthStore";

import type { Place } from "../game/PlayersMapLeaflet";

const PlayersMapLeaflet = dynamic(() => import("../game/PlayersMapLeaflet"), {
  ssr: false,
  loading: () => <div className="play-map placeholder adm-muted">Loading map…</div>,
});

type Data = { overview: AdminOverview; players: AdminPlayer[]; rooms: AdminRoom[]; plays: AdminPlay[] };
type Tab = "overview" | "players" | "games" | "turns";
const TABS: Tab[] = ["overview", "players", "games", "turns"];
const MODE: Record<string, string> = {
  yourself: "Be yourself",
  impersonate: "Impersonate",
  disguise: "Disguise",
  guess: "Guess Who",
  guess_vote: "Guess Who (vote)",
  telephone: "Broken telephone",
  solo_guess: "Solo: guess the voice",
  solo_impersonate: "Solo: impersonate",
  solo_disguise: "Solo: disguise",
};

function when(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function Pill({ tone, children }: { tone: "ok" | "warn" | "bad" | "info" | "neutral"; children: React.ReactNode }) {
  return <span className={`adm-pill ${tone}`}>{children}</span>;
}

/** The admin console: overview, players, games and turns, in tabs. */
export function AdminDashboard() {
  const { token, me, ready, signOut } = useAuthStore();
  const [data, setData] = useState<Data | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [failedOnly, setFailedOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [playerFilter, setPlayerFilter] = useState<"all" | "online" | "flagged">("all");
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  // Open the tab named in the address (#players), and keep it there when switching.
  useEffect(() => {
    const fromHash = window.location.hash.slice(1) as Tab;
    if (TABS.includes(fromHash)) setTab(fromHash);
  }, []);
  function show(t: Tab) {
    setTab(t);
    window.history.replaceState(null, "", `#${t}`);
  }

  const load = useCallback(async () => {
    try {
      const [overview, players, rooms, plays] = await Promise.all([
        api.admin.overview(),
        api.admin.players(),
        api.admin.rooms(),
        api.admin.plays(failedOnly),
      ]);
      setData({ overview, players, rooms, plays });
      setUpdatedAt(new Date());
      setError(null);
    } catch (e) {
      if (e instanceof SignedOutError) return signOut();
      setError((e as Error).message);
    }
  }, [failedOnly, signOut]);

  useEffect(() => {
    if (me?.is_admin) load();
  }, [me?.is_admin, load]);
  useEffect(() => {
    if (!me?.is_admin) return;
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [me?.is_admin, load]);
  // Every change to players, games or turns is announced on the dashboard channel.
  useLive(me?.is_admin ? token : null, null, { onDashboard: load, onSignedOut: signOut });

  const places = useMemo<Place[]>(() => {
    const map = new Map<string, Place>();
    for (const p of data?.players ?? []) {
      if (!p.share_location || p.lat === null || p.lon === null) continue;
      const key = `${p.lat},${p.lon}`;
      const label = `${p.place ?? ""}${p.country ? `, ${countryName(p.country)}` : ""}`;
      const place = map.get(key) ?? { key, label, lat: p.lat, lon: p.lon, online: false, players: [] };
      place.players.push({ name: p.username, online: p.online, points: p.total_points, room: p.room_code });
      place.online ||= p.online;
      map.set(key, place);
    }
    return [...map.values()];
  }, [data]);

  const shownPlayers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data?.players ?? []).filter((p) => {
      if (playerFilter === "online" && !p.online) return false;
      if (playerFilter === "flagged" && !p.cheat_attempts) return false;
      return !q || p.username.includes(q) || (p.place ?? "").toLowerCase().includes(q) || countryName(p.country ?? "").toLowerCase().includes(q);
    });
  }, [data, search, playerFilter]);

  const byCountry = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of data?.players ?? []) if (p.country) counts.set(p.country, (counts.get(p.country) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [data]);

  async function act(action: () => Promise<unknown>, confirmText: string) {
    if (!confirm(confirmText)) return;
    try {
      await action();
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!ready) return <div className="adm"><p className="adm-muted">Loading…</p></div>;
  if (!me || !me.is_admin) {
    return (
      <div className="adm">
        <div className="adm-panel adm-gate">
          <h1>Admin console</h1>
          <p className="adm-muted">
            {me
              ? "Your account doesn't have admin access. Admins are listed in ADMIN_USERNAMES on the server."
              : "Sign in on the game page with an admin account, then come back here."}
          </p>
          <Link href="/" className="adm-btn">
            Go to the game
          </Link>
        </div>
      </div>
    );
  }
  if (!data) return <div className="adm"><p className="adm-muted">{error ?? "Loading…"}</p></div>;

  const o = data.overview;
  const kpis: { label: string; value: number; note?: string; tone?: "warn" }[] = [
    { label: "Players", value: o.players, note: `${o.with_voice} with voice` },
    { label: "Online now", value: o.online },
    { label: "Countries", value: o.countries },
    { label: "Live games", value: o.games_live, note: `${o.games_total} in last 6 h` },
    { label: "Turns today", value: o.turns_today, note: `${o.turns_total} all time` },
    { label: "Failed live checks", value: o.cheat_attempts, tone: o.cheat_attempts ? "warn" : undefined },
    { label: "Points scored", value: o.points_total },
    { label: "Lab voices", value: o.lab_speakers, note: "not players" },
  ];
  const counts: Record<Tab, number | null> = { overview: null, players: data.players.length, games: data.rooms.length, turns: null };

  return (
    <div className="adm">
      <header className="adm-bar">
        <div className="adm-title">
          <span className="adm-product">Who&apos;s Talking?</span>
          <span className="adm-sep">/</span>
          <h1>Admin console</h1>
        </div>
        <div className="adm-bar-right">
          <span className="adm-live" title="Updates automatically">
            <span className="dot-live" /> Live{updatedAt && ` · ${updatedAt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`}
          </span>
          <span className="adm-muted">{me.username}</span>
          <Link href="/" className="adm-btn ghost">
            Back to game
          </Link>
        </div>
      </header>

      <nav className="adm-tabs" role="tablist" aria-label="Sections">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => show(t)}>
            {t[0].toUpperCase() + t.slice(1)}
            {counts[t] !== null && <span className="adm-count">{counts[t]}</span>}
          </button>
        ))}
      </nav>

      {error && <p className="adm-error">{error}</p>}

      {tab === "overview" && (
        <div className="adm-stack">
          <div className="adm-kpis">
            {kpis.map((k) => (
              <div key={k.label} className={`adm-kpi ${k.tone ?? ""}`}>
                <span className="adm-label">{k.label}</span>
                <strong>{k.value.toLocaleString()}</strong>
                {k.note && <span className="adm-muted">{k.note}</span>}
              </div>
            ))}
          </div>

          <section className="adm-panel">
            <div className="adm-panel-head">
              <h2>Players by country</h2>
            </div>
            {byCountry.length === 0 ? (
              <p className="adm-muted">No players yet.</p>
            ) : (
              <ul className="adm-bars">
                {byCountry.slice(0, 8).map(([code, n]) => (
                  <li key={code}>
                    <span className="adm-bar-label">
                      <span className="mono adm-cc">{code}</span> {countryName(code)}
                    </span>
                    <span className="adm-bar-track">
                      <span className="adm-bar-fill" style={{ width: `${(n / byCountry[0][1]) * 100}%` }} />
                    </span>
                    <span className="num">{n}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="adm-panel">
            <div className="adm-panel-head">
              <h2>Player locations</h2>
              <span className="adm-muted">Only players who share their location.</span>
            </div>
            <PlayersMapLeaflet places={places} />
          </section>
        </div>
      )}

      {tab === "players" && (
        <section className="adm-panel">
          <div className="adm-toolbar">
            <input className="adm-input" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name, place or country" aria-label="Search players" />
            <div className="adm-seg" role="group" aria-label="Filter players">
              {(["all", "online", "flagged"] as const).map((f) => (
                <button key={f} className={playerFilter === f ? "on" : ""} onClick={() => setPlayerFilter(f)}>
                  {f === "all" ? "All" : f === "online" ? "Online" : "Failed checks"}
                </button>
              ))}
            </div>
            <span className="adm-muted">
              {shownPlayers.length} of {data.players.length}
            </span>
          </div>
          <div className="adm-scroll">
            <table className="adm-table">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Location</th>
                  <th>Status</th>
                  <th className="num">Points</th>
                  <th className="num">Turns</th>
                  <th className="num">Failed checks</th>
                  <th>Joined</th>
                  <th>Last seen</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {shownPlayers.map((p) => (
                  <tr key={p.user_id}>
                    <td>
                      <span className="adm-name">{p.username}</span>
                      {p.is_admin && <Pill tone="neutral">Admin</Pill>}
                      {!p.has_voice && <Pill tone="warn">No voice</Pill>}
                    </td>
                    <td>
                      {p.country && <span className="mono adm-cc">{p.country}</span>} {p.place ?? "—"}
                      {!p.share_location && <span className="adm-muted"> · hidden</span>}
                    </td>
                    <td>
                      {p.room_code ? <Pill tone="ok">In {p.room_code}</Pill> : p.online ? <Pill tone="ok">Online</Pill> : <Pill tone="neutral">Offline</Pill>}
                    </td>
                    <td className="num">{p.total_points.toLocaleString()}</td>
                    <td className="num">{p.turns}</td>
                    <td className="num">{p.cheat_attempts ? <Pill tone="bad">{p.cheat_attempts}</Pill> : 0}</td>
                    <td className="adm-muted nowrap">{when(p.created_at)}</td>
                    <td className="adm-muted nowrap">{when(p.last_seen_at)}</td>
                    <td className="actions">
                      {p.user_id !== me.id && (
                        <button
                          className="adm-link danger"
                          onClick={() => act(() => api.admin.deletePlayer(p.user_id), `Delete ${p.username}? Their account, voice, turns and location are removed for good.`)}
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {shownPlayers.length === 0 && (
                  <tr>
                    <td colSpan={9} className="adm-muted">
                      No players match.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "games" && (
        <section className="adm-panel">
          <div className="adm-panel-head">
            <h2>Games</h2>
            <span className="adm-muted">Kept for 6 hours after the last move.</span>
          </div>
          {data.rooms.length === 0 ? (
            <p className="adm-muted">No games in the last 6 hours.</p>
          ) : (
            <div className="adm-scroll">
              <table className="adm-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Mode</th>
                    <th>Status</th>
                    <th>Host</th>
                    <th>Players</th>
                    <th className="num">Progress</th>
                    <th>Created</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {data.rooms.map((r) => (
                    <tr key={r.code}>
                      <td className="mono">{r.code}</td>
                      <td>{MODE[r.mode] ?? r.mode}</td>
                      <td>
                        {r.status === "playing" ? <Pill tone="ok">Playing</Pill> : r.status === "lobby" ? <Pill tone="info">Waiting</Pill> : <Pill tone="neutral">Finished</Pill>}
                      </td>
                      <td>{r.host}</td>
                      <td className="adm-wrap">{r.players.join(", ")}</td>
                      <td className="num">
                        {r.turn}/{r.turns_total || "—"}
                      </td>
                      <td className="adm-muted nowrap">{when(r.created_at)}</td>
                      <td className="actions">
                        {r.status !== "finished" && (
                          <button className="adm-link danger" onClick={() => act(() => api.admin.endRoom(r.code), `End game ${r.code} now? Scores so far are kept.`)}>
                            End game
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === "turns" && (
        <section className="adm-panel">
          <div className="adm-toolbar">
            <div className="adm-seg" role="group" aria-label="Filter turns">
              <button className={!failedOnly ? "on" : ""} onClick={() => setFailedOnly(false)}>
                All turns
              </button>
              <button className={failedOnly ? "on" : ""} onClick={() => setFailedOnly(true)}>
                Failed live checks
              </button>
            </div>
            <span className="adm-muted">Latest 200</span>
          </div>
          <TurnsTable plays={data.plays} empty={failedOnly ? "No failed live checks." : "No turns played yet."} />
        </section>
      )}

    </div>
  );
}

function TurnsTable({ plays, empty }: { plays: AdminPlay[]; empty: string }) {
  if (plays.length === 0) return <p className="adm-muted">{empty}</p>;
  return (
    <div className="adm-scroll">
      <table className="adm-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Player</th>
            <th>Game</th>
            <th>Mode</th>
            <th>Live check</th>
            <th className="num">Points</th>
          </tr>
        </thead>
        <tbody>
          {plays.map((p) => (
            <tr key={p.id}>
              <td className="adm-muted nowrap">{when(p.created_at)}</td>
              <td>{p.username}</td>
              <td className="mono">{p.room_code ?? "—"}</td>
              <td>{MODE[p.mode] ?? p.mode}</td>
              <td>{p.live_passed === false ? <Pill tone="bad">Failed</Pill> : p.live_passed ? <Pill tone="ok">Passed</Pill> : <span className="adm-muted">—</span>}</td>
              <td className="num">{p.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

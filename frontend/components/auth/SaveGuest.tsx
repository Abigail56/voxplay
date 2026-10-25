"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";

import { LocationPicker, type Where } from "../game/LocationPicker";

/** A guest picks a player name and password, and keeps their points, wins and history. */
export function SaveGuest({ onDone }: { onDone?: () => void }) {
  const { me, setMe } = useAuthStore();
  const [username, setUsername] = useState(() =>
    (me?.nickname ?? "").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 20),
  );
  const [password, setPassword] = useState("");
  const [where, setWhere] = useState<Where>({ country: "", place: "", found: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const place = where.found ? { country: where.country, place: where.place } : {};
      setMe(await api.claim({ username, password, ...place }));
      onDone?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card auth" onSubmit={submit}>
      <p className="tagline">
        Save your player to keep your points and wins, sign in on any device, and play Who&apos;s Talking?.
      </p>
      <label className="field">
        Player name
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="e.g. ada_99"
          autoComplete="username"
          maxLength={20}
          required
        />
        <span className="hint">3–20 letters, numbers or _</span>
      </label>
      <label className="field">
        Password
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" minLength={8} required />
        <span className="hint">At least 8 characters</span>
      </label>
      <fieldset className="where">
        <legend>Where are you playing from? (optional, puts you on the map)</legend>
        <LocationPicker value={where} onChange={setWhere} />
      </fieldset>
      <button className="btn primary big" disabled={busy || (!!where.place && !where.found)}>
        {busy ? "…" : "Save my player"}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

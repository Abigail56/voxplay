"use client";

import { useState } from "react";

import { useAuthStore } from "@/store/useAuthStore";

import { LocationPicker, type Where } from "../game/LocationPicker";

/** Make a player or sign in. Used by the sign-in page and the Who's Talking? title screen. */
export function AuthForm({ onDone }: { onDone?: () => void }) {
  const signIn = useAuthStore((s) => s.signIn);
  const [mode, setMode] = useState<"signup" | "login">("signup");
  const [where, setWhere] = useState<Where>({ country: "", place: "", found: null });
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(mode, username, password, { country: where.country, place: where.place });
      onDone?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card auth" onSubmit={submit}>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={mode === "signup"} className={mode === "signup" ? "on" : ""} onClick={() => setMode("signup")}>
          New player
        </button>
        <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "on" : ""} onClick={() => setMode("login")}>
          I have an account
        </button>
      </div>
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
        {mode === "signup" && <span className="hint">3–20 letters, numbers or _</span>}
      </label>
      <label className="field">
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          minLength={mode === "signup" ? 8 : undefined}
          required
        />
        {mode === "signup" && <span className="hint">At least 8 characters</span>}
      </label>
      {mode === "signup" && (
        <fieldset className="where">
          <legend>Where are you playing from?</legend>
          <LocationPicker value={where} onChange={setWhere} />
        </fieldset>
      )}
      <button className="btn primary big" disabled={busy || (mode === "signup" && !where.found)}>
        {busy ? "…" : mode === "signup" ? "Create player" : "Sign in"}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

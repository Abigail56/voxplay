"use client";

import { useState } from "react";

import { useAuthStore } from "@/store/useAuthStore";

import { LocationPicker, type Where } from "./LocationPicker";

/** The title screen: what the game is, plus sign up / sign in. */
export function Welcome({ invite }: { invite: string | null }) {
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
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="welcome">
      <section className="hero">
        {invite && (
          <p className="invite-banner">
            You&apos;ve been invited to game <strong className="code">{invite}</strong>. Make a player (or sign in) and
            you&apos;ll go straight in.
          </p>
        )}
        <p className="kicker">
          <span className="on-air" aria-hidden /> A party game for voices
        </p>
        <h1>
          Who&apos;s <em>Talking?</em>
        </h1>
        <p className="tagline">
          Everyone records their voice, then you take turns reading numbers out loud while the game works out who&apos;s
          speaking. It&apos;s usually right. Your job is to make it wrong.
        </p>
        <ol className="how">
          <li>
            <strong>Record three short clips</strong> so the game learns your voice.
          </li>
          <li>
            <strong>Share a game code</strong> with friends. Everyone plays on their own phone.
          </li>
          <li>
            <strong>On your turn</strong>, read the numbers on screen. Sound like yourself, do an impression of
            someone, or hide in Guess Who while everyone votes.
          </li>
          <li>
            <strong>Every point counts</strong> towards the weekly cup and your country&apos;s total.
          </li>
        </ol>
      </section>

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
    </div>
  );
}

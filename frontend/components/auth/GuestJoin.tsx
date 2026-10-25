"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuthStore } from "@/store/useAuthStore";

/** "Type your name, play now": a guest player, no password. Used wherever a game needs a player. */
export function GuestJoin({ next, cta = "Play now" }: { next: string; cta?: string }) {
  const playAsGuest = useAuthStore((s) => s.playAsGuest);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await playAsGuest(name.trim());
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form className="guest-join" onSubmit={submit}>
      <label className="field">
        Your name
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Ada"
          autoComplete="nickname"
          minLength={2}
          maxLength={20}
          required
          autoFocus
        />
      </label>
      <button className="btn primary big" disabled={busy || name.trim().length < 2}>
        {busy ? "…" : cta}
      </button>
      {error && <p className="error">{error}</p>}
      <p className="hint">
        No password needed. Already have a player?{" "}
        <Link href={`/sign-in?next=${encodeURIComponent(next)}`}>Sign in</Link>
      </p>
    </form>
  );
}

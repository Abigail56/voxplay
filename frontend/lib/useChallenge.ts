"use client";

import { useCallback, useEffect, useState } from "react";

import { api, type Challenge } from "./api";

/** A fresh "say these digits" phrase from the server, with a live countdown.
 *  Call `renew()` after every attempt: each phrase works only once. */
export function useChallenge() {
  const [challenge, setChallenge] = useState<(Challenge & { expiresAt: number }) | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const renew = useCallback(async () => {
    try {
      const c = await api.challenge();
      setChallenge({ ...c, expiresAt: Date.now() + c.expires_in_seconds * 1000 });
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    renew();
  }, [renew]);

  // Count down so people know to hurry; an expired phrase is refused by the server anyway.
  useEffect(() => {
    if (!challenge) return;
    const tick = () => setSecondsLeft(Math.max(0, Math.round((challenge.expiresAt - Date.now()) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [challenge]);

  return { challenge, secondsLeft, expired: challenge !== null && secondsLeft === 0, error, renew };
}

"use client";

import { useEffect, useRef, useState } from "react";

/** Fetches a recording when pressed and plays it (press again to stop). */
export function PlayButton({ load, label = "▶" }: { load: () => Promise<Blob>; label?: string }) {
  const [state, setState] = useState<"idle" | "loading" | "playing" | "gone">("idle");
  const player = useRef<HTMLAudioElement | null>(null);
  useEffect(() => () => player.current?.pause(), []);

  async function play() {
    if (state === "playing") return player.current?.pause();
    setState("loading");
    try {
      const url = URL.createObjectURL(await load());
      const a = new Audio(url);
      player.current = a;
      a.onended = a.onpause = () => {
        setState("idle");
        URL.revokeObjectURL(url);
      };
      await a.play();
      setState("playing");
    } catch {
      setState("gone");
    }
  }

  return (
    <button type="button" className="btn small ghost" onClick={play} disabled={state === "loading" || state === "gone"}>
      {state === "playing" ? "■ Stop" : state === "gone" ? "Not available" : state === "loading" ? "…" : label}
    </button>
  );
}

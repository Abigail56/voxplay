"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { duckMusic, musicWanted, onMusicChange, setMood, setMusic, startMusic, stopMusic } from "@/lib/music";

// The game pages (and their rooms) get the battle theme; everywhere else the calm one.
const BATTLE_PAGES = ["/games", "/brain-clash", "/beat-drop", "/story-forge", "/whos-talking"];

/** The music on/off switch in the navigation bar. Music starts on the first tap anywhere (if it's on). */
export function MusicToggle() {
  const [on, setOn] = useState(true);
  const path = usePathname();
  useEffect(() => setMood(BATTLE_PAGES.some((p) => path.startsWith(p)) ? "battle" : "calm"), [path]);

  useEffect(() => {
    setOn(musicWanted());
    const off = onMusicChange(setOn);
    const begin = () => musicWanted() && startMusic();
    window.addEventListener("pointerdown", begin, { once: true });
    window.addEventListener("keydown", begin, { once: true });
    // No music playing in a hidden tab.
    const onVisible = () => (document.hidden ? stopMusic() : musicWanted() && startMusic());
    document.addEventListener("visibilitychange", onVisible);
    // Any <audio> on the page (a hum, a voice clip, a replay) makes the music step aside while it plays.
    // Media events don't bubble, so listen in the capture phase.
    const playing = new Set<EventTarget>();
    const onMedia = (e: Event) => {
      if (!(e.target instanceof HTMLMediaElement)) return;
      if (e.type === "play") playing.add(e.target);
      else playing.delete(e.target);
      duckMusic(playing.size > 0);
    };
    for (const type of ["play", "pause", "ended", "emptied"]) document.addEventListener(type, onMedia, true);
    return () => {
      for (const type of ["play", "pause", "ended", "emptied"]) document.removeEventListener(type, onMedia, true);
      off();
      window.removeEventListener("pointerdown", begin);
      window.removeEventListener("keydown", begin);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  return (
    <button
      type="button"
      className={`music-toggle ${on ? "on" : ""}`}
      aria-pressed={on}
      aria-label={on ? "Mute the music" : "Play the music"}
      title={on ? "Mute the music" : "Play the music"}
      onClick={() => setMusic(!on)}
    >
      <span className="eq-mini" aria-hidden>
        <i />
        <i />
        <i />
      </span>
      <span>{on ? "Music on" : "Music off"}</span>
    </button>
  );
}

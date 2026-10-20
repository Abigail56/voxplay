"use client";

import type { GameMode } from "@/lib/api";

export const MODES: { id: GameMode; name: string; blurb: string; players: string }[] = [
  { id: "yourself", name: "Be yourself", blurb: "Read the numbers in your normal voice. The surer the game is that it's you, the more you score.", players: "2 or more" },
  { id: "impersonate", name: "Impersonate", blurb: "Do your best impression of another player. Fool the game and take 50 points.", players: "2 or more" },
  { id: "guess", name: "Guess Who", blurb: "One player is picked in secret to speak. Everyone else listens and votes on who it was.", players: "3 or more" },
];

/** The three game types side by side, so every mode is visible at a glance. */
export function ModePicker({ value, onChange, disabled }: { value: GameMode; onChange: (m: GameMode) => void; disabled?: boolean }) {
  return (
    <div className="modes" role="radiogroup" aria-label="Game type">
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          role="radio"
          aria-checked={value === m.id}
          className={`mode ${value === m.id ? "on" : ""}`}
          onClick={() => onChange(m.id)}
          disabled={disabled}
        >
          <span className="mode-tick" aria-hidden />
          <span className="mode-name">{m.name}</span>
          <span className="mode-blurb">{m.blurb}</span>
          <span className="mode-players">{m.players}</span>
        </button>
      ))}
    </div>
  );
}

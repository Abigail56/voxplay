"use client";

import type { RoomOptions } from "@/lib/api";

import { ModePicker } from "./ModePicker";

export const DEFAULT_OPTIONS: RoomOptions = {
  mode: "yourself",
  rounds: 2,
  speed: false,
  twists: false,
  crowd: false,
  double_final: false,
  replay: true,
};

const SWITCHES: { key: keyof RoomOptions; label: string; hint: string; only?: RoomOptions["mode"] }[] = [
  { key: "speed", label: "⚡ Speed round", hint: "20 seconds a turn, extra points for being quick" },
  { key: "twists", label: "🌀 Twists", hint: "a silly style every turn: whisper it, sing it, like a pirate…" },
  { key: "crowd", label: "⭐ Humans vs AI", hint: "everyone rates each impression before the machine's verdict", only: "impersonate" },
  { key: "double_final", label: "🔥 Double final", hint: "the last round counts double" },
  { key: "replay", label: "🔁 Replay", hint: "keep the clips for an hour, so you can play back the best bits" },
];

/** Game type, rounds and the optional extras, for a new game or the waiting room. */
export function GameOptions({ value, onChange, disabled }: { value: RoomOptions; onChange: (o: RoomOptions) => void; disabled?: boolean }) {
  const set = (patch: Partial<RoomOptions>) => onChange({ ...value, ...patch });
  return (
    <>
      <ModePicker value={value.mode} onChange={(mode) => set({ mode })} disabled={disabled} />
      <div className="options">
        <label className="field">
          Rounds
          <select value={value.rounds} onChange={(e) => set({ rounds: Number(e.target.value) })} disabled={disabled}>
            {[1, 2, 3, 5].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        {SWITCHES.filter((s) => !s.only || s.only === value.mode).map((s) => (
          <label key={s.key} className="switch">
            <input type="checkbox" checked={Boolean(value[s.key])} onChange={(e) => set({ [s.key]: e.target.checked })} disabled={disabled} />
            <span>
              <strong>{s.label}</strong> <span className="hint">{s.hint}</span>
            </span>
          </label>
        ))}
      </div>
    </>
  );
}

/** The room's options, as sent to the server. */
export function optionsOf(room: RoomOptions): RoomOptions {
  const { mode, rounds, speed, twists, crowd, double_final, replay } = room;
  return { mode, rounds, speed, twists, crowd, double_final, replay };
}

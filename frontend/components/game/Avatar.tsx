import { avatarSlot } from "@/lib/game";

/** A round avatar with the player's initial, in a colour that's always the same for that name. */
export function Avatar({ name, size = 36, online }: { name: string; size?: number; online?: boolean }) {
  return (
    <span
      className="avatar"
      style={{ width: size, height: size, fontSize: size * 0.45, background: `var(--series-${avatarSlot(name)})` }}
      aria-hidden
    >
      {name.slice(0, 1).toUpperCase()}
      {online !== undefined && <span className={`presence ${online ? "on" : ""}`} />}
    </span>
  );
}

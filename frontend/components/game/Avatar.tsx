import { AVATARS, artSrc } from "@/lib/art";
import { avatarSlot } from "@/lib/game";

/** A round avatar: a player portrait (picked by name, so it's always the same for that player) once the
 *  portraits exist, otherwise the player's initial in a colour that's always the same for that name. */
export function Avatar({ name, size = 36, online }: { name: string; size?: number; online?: boolean }) {
  const portraits = AVATARS.filter((a) => artSrc(a));
  const portrait = portraits.length ? portraits[(avatarSlot(name) * 7 + name.length) % portraits.length] : null;
  return (
    <span
      className={`avatar ${portrait ? "has-portrait" : ""}`}
      style={{ width: size, height: size, fontSize: size * 0.45, background: portrait ? undefined : `var(--series-${avatarSlot(name)})` }}
      aria-hidden
    >
      {portrait ? <img src={portrait} alt="" width={size} height={size} loading="lazy" decoding="async" /> : name.slice(0, 1).toUpperCase()}
      {online !== undefined && <span className={`presence ${online ? "on" : ""}`} />}
    </span>
  );
}

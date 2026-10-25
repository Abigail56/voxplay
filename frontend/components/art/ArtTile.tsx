import { ART, artSrc, type ArtSlot } from "@/lib/art";

import { Art } from "./Scenes";

/** A card led by artwork: the picture with a fade behind its title (labels are always real text, never
 *  part of the image), then whatever the card says. Used for game modes and categories. */
export function ArtTile({
  slot,
  media,
  title,
  eyebrow,
  icon,
  children,
  size = "big",
}: {
  slot?: ArtSlot;
  media?: React.ReactNode; // a picture of its own instead of an artwork slot
  title: string;
  eyebrow?: string;
  icon?: string;
  children?: React.ReactNode;
  size?: "big" | "small";
}) {
  const label = (
    <div className="art-tile-label">
      {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      <h3>
        {icon && (
          <span aria-hidden className="art-tile-icon">
            {icon}
          </span>
        )}
        {title}
      </h3>
    </div>
  );
  // Big tiles lay the title over the bottom of a drawn scene; small ones, and big ones with a painting
  // (which often has the name painted in), put it underneath, so the picture stays whole.
  const painted = size === "big" && !media && !!slot && !!artSrc(ART[slot].file);
  const over = size === "big" && !painted;
  return (
    <article className={`art-tile ${size}${painted ? " painted" : ""}`}>
      <div className="art-tile-media">
        {media ?? (slot && <Art slot={slot} className="art-fill" />)}
        {over && label}
      </div>
      {(!over || children) && (
        <div className="art-tile-body">
          {!over && label}
          {children}
        </div>
      )}
    </article>
  );
}

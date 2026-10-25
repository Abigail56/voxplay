import type { ArtSlot } from "@/lib/art";

import { Art } from "./Scenes";

/** A card led by artwork: the picture with a fade behind its title (labels are always real text, never
 *  part of the image), then whatever the card says. Used for game modes and categories. */
export function ArtTile({ slot, title, eyebrow, icon, children, size = "big" }: { slot: ArtSlot; title: string; eyebrow?: string; icon?: string; children?: React.ReactNode; size?: "big" | "small" }) {
  return (
    <article className={`art-tile ${size}`}>
      <div className="art-tile-media">
        <Art slot={slot} className="art-fill" />
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
      </div>
      {children && <div className="art-tile-body">{children}</div>}
    </article>
  );
}

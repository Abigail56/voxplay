import { CREW, artSrc } from "@/lib/art";

import { Nova, Pulse } from "../art/Characters";

/** The recurring VOXPLAY cast. A member shows their portrait once its file exists; Nova and Pulse have a
 *  drawn bust until then, and the others appear when their portraits arrive. */
export function Crew() {
  const shown = CREW.filter((c) => artSrc(c.portrait) || c.id === "nova" || c.id === "pulse");
  return (
    <div className="crew">
      {shown.map((c) => {
        const portrait = artSrc(c.portrait);
        const Bust = c.id === "nova" ? Nova : Pulse;
        return (
          <article key={c.id} className="crew-card" style={{ "--c1": c.colors[0], "--c2": c.colors[1] } as React.CSSProperties}>
            <div className="crew-portrait">
              {portrait ? (
                <img src={portrait} alt={`${c.name}, ${c.role}`} loading="lazy" decoding="async" />
              ) : (
                <svg viewBox="70 20 260 260" role="img" aria-label={`${c.name}, ${c.role}`}>
                  <Bust id={`crew-${c.id}`} />
                </svg>
              )}
            </div>
            <div className="crew-copy">
              <h3>{c.name}</h3>
              <span className="eyebrow">{c.role}</span>
              <p className="hint">{c.bio}</p>
            </div>
          </article>
        );
      })}
    </div>
  );
}

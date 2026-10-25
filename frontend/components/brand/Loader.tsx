import { Art } from "../art/Scenes";
import { ART, artSrc, type StateArt } from "@/lib/art";

import { LogoMark } from "./Logo";

/** The full-area loading state: the VOXPLAY mark breathing (or a waiting-state illustration, once its
 *  image exists), with what's happening underneath. */
export function Loader({ label = "Loading…", art }: { label?: string; art?: StateArt }) {
  const picture = art && artSrc(ART[`state-${art}`].file);
  return (
    <div className="loader" role="status" aria-live="polite">
      {picture ? <Art slot={`state-${art}`} className="loader-art" /> : <LogoMark size={56} />}
      <span className="hint">{label}</span>
    </div>
  );
}

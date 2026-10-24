import { LogoMark } from "./Logo";

/** The full-area loading state: the VOXPLAY mark breathing, with what's happening underneath. */
export function Loader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="loader" role="status" aria-live="polite">
      <LogoMark size={56} />
      <span className="hint">{label}</span>
    </div>
  );
}

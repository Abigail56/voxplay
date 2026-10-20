import type { Liveness } from "@/lib/api";

/** "✓ Live check passed · heard “4, 7, 2…”" under a result. */
export function LivenessBadge({ liveness }: { liveness: Liveness }) {
  return (
    <p className={`liveness ${liveness.passed ? "ok" : "bad"}`}>
      <strong>{liveness.passed ? "✓ Live check passed" : "✗ Live check failed"}</strong>
      <span className="hint">
        {" "}
        · heard &ldquo;{liveness.heard || "nothing"}&rdquo; ({Math.round(liveness.match * 100)}% of the phrase)
      </span>
    </p>
  );
}

"use client";

import Link from "next/link";

/** Shown when a page crashes. "Try again" re-renders it without a full reload. */
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <section className="state-page">
      <p className="kicker">Glitch in the system</p>
      <h1>Something broke</h1>
      <p className="tagline">That&apos;s on us, not you. Try again, and if it keeps happening, head back to the start.</p>
      <div className="row">
        <button className="btn primary big" onClick={reset}>
          Try again
        </button>
        <Link href="/" className="btn big">
          Back to VOXPLAY
        </Link>
      </div>
    </section>
  );
}

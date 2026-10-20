"use client";

import type { useChallenge } from "@/lib/useChallenge";

const DIGIT: Record<string, number> = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9 };

/** The digits to read out, with the countdown (or a "new phrase" button once expired). */
export function Phrase({ state }: { state: ReturnType<typeof useChallenge> }) {
  const { challenge, secondsLeft, expired, renew } = state;
  if (!challenge) return null;
  return (
    <div className={`challenge ${expired ? "expired" : ""}`}>
      <span className="hint">Say:</span>
      <span className="digits" aria-label={challenge.phrase}>
        {challenge.phrase.split(" ").map((w, i) => (
          <span key={i}>{DIGIT[w] ?? w}</span>
        ))}
      </span>
      <span className="hint">
        {expired ? (
          <button type="button" className="link plain" onClick={renew}>
            Expired. Get a new phrase
          </button>
        ) : (
          `${secondsLeft}s left`
        )}
      </span>
    </div>
  );
}

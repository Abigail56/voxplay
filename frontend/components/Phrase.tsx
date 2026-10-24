"use client";

import type { useChallenge } from "@/lib/useChallenge";

const DIGIT: Record<string, number> = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9 };

/** What to say (a silly line, or digits), with the countdown (or a "new phrase" button once expired). */
export function Phrase({ state, twist }: { state: ReturnType<typeof useChallenge>; twist?: string | null }) {
  const { challenge, secondsLeft, expired, renew } = state;
  if (!challenge) return null;
  const words = challenge.phrase.split(" ");
  const digits = words.every((w) => w in DIGIT);
  return (
    <div className={`challenge ${expired ? "expired" : ""}`}>
      <span className="hint">Say:</span>
      {digits ? (
        <span className="digits" aria-label={challenge.phrase}>
          {words.map((w, i) => (
            <span key={i}>{DIGIT[w]}</span>
          ))}
        </span>
      ) : (
        <span className="line">&ldquo;{challenge.phrase.charAt(0).toUpperCase() + challenge.phrase.slice(1)}&rdquo;</span>
      )}
      {twist && <span className="twist">{twist}</span>}
      <span className="hint">
        {expired ? (
          <button type="button" className="link plain" onClick={renew}>
            Expired. Get a new line
          </button>
        ) : (
          `${secondsLeft}s left`
        )}
      </span>
    </div>
  );
}

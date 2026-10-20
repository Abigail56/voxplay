"use client";

import { useEffect, useState } from "react";

import { api, type Clip, type IdentifyResult } from "@/lib/api";
import { announce, loadSoundSetting, sfx } from "@/lib/game";
import { useChallenge } from "@/lib/useChallenge";

import { ClipInput } from "./ClipInput";
import { LivenessBadge } from "./LivenessBadge";
import { Phrase } from "./Phrase";
import { Avatar } from "./game/Avatar";

const DRUMROLL = ["Listening…", "Comparing voices…", "And the voice belongs to…"];

/** Record anyone reading the digits; the AI reveals which player it thinks it is. */
export function MysteryVoice() {
  const phrase = useChallenge();
  const [result, setResult] = useState<IdentifyResult | null>(null);
  const [stage, setStage] = useState<number | null>(null); // drumroll step while waiting
  const [error, setError] = useState<string | null>(null);

  // A little suspense: step through the drumroll while the AI works.
  useEffect(() => {
    if (stage === null || stage >= DRUMROLL.length - 1) return;
    const id = setTimeout(() => setStage((s) => (s === null ? s : s + 1)), 900);
    return () => clearTimeout(id);
  }, [stage]);

  async function identify(clip: Clip) {
    if (!phrase.challenge) return;
    setResult(null);
    setError(null);
    setStage(0);
    try {
      const [r] = await Promise.all([api.identify(clip, phrase.challenge.challenge_id), new Promise((ok) => setTimeout(ok, 2400))]);
      setResult(r);
      const sound = loadSoundSetting(); // the game's sound on/off switch
      sfx(r.is_match ? "score" : "zero", sound);
      announce(r.is_match ? `It's ${r.label}!` : "That's not a voice I know.", sound);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStage(null);
      phrase.renew(); // every phrase works once
    }
  }

  return (
    <section className="card mystery">
      <h2>Mystery voice</h2>
      <p className="hint">
        Hand the phone to someone, have them read the numbers, and see if the game can tell who it is. Works for anyone who has
        recorded their voice.
      </p>

      <Phrase state={phrase} />
      <ClipInput onClip={identify} disabled={stage !== null || !phrase.challenge || phrase.expired} allowUpload={false} />
      {stage !== null && <p className="drumroll">{DRUMROLL[stage]}</p>}
      {error && <p className="error">{error}</p>}

      {result && (
        <div className={`reveal ${result.is_match ? "match" : "unknown"}`}>
          {result.is_match ? (
            <>
              <Avatar name={result.label} size={72} />
              <div className="reveal-name">It&apos;s {result.label}!</div>
              <div className="hint">{Math.round(result.score * 100)}% sure</div>
            </>
          ) : (
            <>
              <span className="avatar empty-seat">?</span>
              <div className="reveal-name">Not a voice I know</div>
              <div className="hint">
                {result.liveness?.passed === false ? "The numbers weren't read out." : "That voice doesn't match any player."}
              </div>
            </>
          )}
          {result.liveness && <LivenessBadge liveness={result.liveness} />}
          {result.candidates.length > 1 && result.is_match && (
            <p className="hint">
              Runner-up: {result.candidates[1].name} ({Math.round(result.candidates[1].score * 100)}%)
            </p>
          )}
        </div>
      )}
    </section>
  );
}

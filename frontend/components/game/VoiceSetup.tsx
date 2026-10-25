"use client";

import { useEffect, useState } from "react";

import { api, type Clip, type TakeCheck } from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";

import { ClipInput } from "../ClipInput";

// Three of these are picked at random for every recording, so nobody reads the same lines every time.
// The voice model doesn't care what's said, only how it sounds: each takes 5-10 seconds at a natural pace.
const POOL = [
  "The quick brown fox jumps over the lazy dog, and then it takes a long nap in the sun.",
  "I'd like a big bowl of jollof rice, some fried plantain, and a cold drink, please.",
  "My favourite place to be on a weekend is somewhere quiet, with good music and good friends.",
  "Every morning the danfo conductor shouts the same three stops, and somehow everybody understands him.",
  "If I could travel anywhere tomorrow, I would pack a small bag and fly somewhere warm by the sea.",
  "My grandmother tells the best stories, especially the ones about the clever tortoise and the proud lion.",
  "When the power comes back on at night, the whole street cheers like we just won the World Cup.",
  "I always say I'll only watch one episode, and then suddenly it's two o'clock in the morning.",
  "The best part of any party is when the music changes and everybody rushes to the dance floor.",
  "Last weekend we cooked pepper soup for the whole family, and there was nothing left by evening.",
  "Rain on a tin roof is the best sound in the world when you're warm and dry inside.",
  "My phone battery always dies at the worst moment, usually when I need a map the most.",
  "Football on Saturday, church on Sunday, and on Monday everybody is tired at work again.",
  "A good friend is someone who laughs at your jokes, even when they aren't very funny.",
  "The market was so busy today that it took me an hour to buy tomatoes and onions.",
  "I learned to ride a bicycle when I was seven, and I fell off at least twenty times.",
  "On a clear night away from the city, you can see thousands of stars across the sky.",
  "Our neighbour's rooster starts crowing at four in the morning, long before the sun comes up.",
  "If you want to learn something well, try teaching it to someone else for a day.",
  "The traffic this evening was terrible, so I listened to my favourite songs all the way home.",
];

function pickThree(): string[] {
  const pool = [...POOL];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, 3);
}

type Take = { clip: Clip; check: TakeCheck | null; error: string | null };

/** Record your voice: what the game compares you against. 3 takes, each checked for quality straight away. */
export function VoiceSetup({ onDone, again = false }: { onDone?: () => void; again?: boolean }) {
  const setMe = useAuthStore((s) => s.setMe);
  // Chosen after the page loads (not while rendering), so the server and the browser draw the same thing first.
  const [lines, setLines] = useState<string[]>(() => POOL.slice(0, 3));
  useEffect(() => setLines(pickThree()), []);
  const [takes, setTakes] = useState<Take[]>([]);
  const [checking, setChecking] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const good = takes.filter((t) => t.check?.ok);
  const step = Math.min(takes.length, lines.length - 1);

  async function add(clip: Clip) {
    setChecking(true);
    try {
      const check = await api.checkTake(clip);
      setTakes((ts) => [...ts, { clip, check, error: null }]);
    } catch (e) {
      setTakes((ts) => [...ts, { clip, check: null, error: (e as Error).message }]);
    } finally {
      setChecking(false);
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      setMe(await api.enrollMyVoice(consent, good.map((t) => t.clip)));
      onDone?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card voice-setup">
      <h2>{again ? "Re-record your voice" : "Record your voice"}</h2>
      <p className="hint">
        Read 3 lines in your normal voice, somewhere quiet, with the phone about a hand&apos;s width from your mouth. Each
        take is checked straight away, so only clean recordings are kept.
      </p>

      <div className="steps" aria-label={`${good.length} of 3 good takes`}>
        {lines.map((_, i) => (
          <span key={i} className={`step ${i < good.length ? "done" : i === good.length ? "now" : ""}`}>
            {i < good.length ? "✓" : i + 1}
          </span>
        ))}
      </div>

      {good.length < lines.length && (
        <>
          <blockquote className="read-line">&ldquo;{lines[Math.min(good.length, step)]}&rdquo;</blockquote>
          <ClipInput onClip={add} disabled={busy || checking} allowUpload={false} />
        </>
      )}
      {checking && <p className="hint">Checking the recording…</p>}

      {takes.length > 0 && (
        <ul className="clips takes">
          {takes.map((t, i) => (
            <li key={t.clip.id} className={t.check?.ok ? "good" : "bad"}>
              <span className="take-status">
                Take {i + 1}: {t.check?.ok ? "✓ good" : "✗ redo this one"}
              </span>
              <audio src={t.clip.url} controls />
              <button type="button" className="link" onClick={() => setTakes((ts) => ts.filter((x) => x !== t))}>
                remove
              </button>
              {!t.check?.ok && <span className="take-problem">{t.error ?? t.check?.problems[0]}</span>}
              {t.check?.ok && (
                <span className="hint">
                  {t.check.speech_seconds.toFixed(1)}s of speech · {t.check.snr_db >= 40 ? "very clean" : t.check.snr_db >= 25 ? "clean" : "OK"} sound
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <label className="consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        I agree to my voiceprint (192 numbers, not the recording) being stored for this game. I can delete it any
        time by deleting my player.
      </label>
      <button className="btn primary big" disabled={!consent || good.length < 3 || busy} onClick={save}>
        {busy ? "Learning your voice…" : good.length < 3 ? `Record ${3 - good.length} more good take${good.length === 2 ? "" : "s"}` : "Save my voice"}
      </button>
      {error && <p className="error">{error}</p>}
      <p className="hint">It gets better at knowing you as you play: clear turns are added automatically.</p>
    </section>
  );
}

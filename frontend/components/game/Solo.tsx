"use client";

import { useCallback, useEffect, useState } from "react";

import { api, type Clip, type SoloGuess, type SoloInfo, type SoloRound, type SoloTurn, type SoloVoice } from "@/lib/api";
import { announce, sfx } from "@/lib/game";
import { useChallenge } from "@/lib/useChallenge";

import { ClipInput } from "../ClipInput";
import { LivenessBadge } from "../LivenessBadge";
import { Phrase } from "../Phrase";
import { PlayButton } from "./PlayButton";

type Tab = "guess" | "impersonate" | "disguise";

const TABS: { id: Tab; name: string; blurb: string }[] = [
  { id: "guess", name: "Guess the voice", blurb: "Hear how each reader sounds, then a mystery clip. Who is it? The machine guesses too." },
  { id: "impersonate", name: "Impersonate", blurb: "Pick a reader, listen, and do your best impression. Fool the machine for 50 more." },
  { id: "disguise", name: "Disguise", blurb: "Say the line so the machine can't tell it's you. Practice for the real thing." },
];

/** No one to play with? The built-in voices (public audiobook readers) are always around. */
export function Solo({ sound, onPlayed }: { sound: boolean; onPlayed: () => void }) {
  const [info, setInfo] = useState<SoloInfo | null>(null);
  const [tab, setTab] = useState<Tab>("guess");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.solo().then(setInfo).catch((e) => setError((e as Error).message));
  }, []);
  useEffect(load, [load]);

  function played(points: number, message: string) {
    sfx(points > 0 ? "score" : "zero", sound);
    announce(message, sound);
    load();
    onPlayed();
  }

  if (error) return null; // solo is a bonus: the game works without it
  if (!info || info.voices.length < 2) return null;

  return (
    <section className="card solo">
      <div className="section-head">
        <h2>Play solo</h2>
        {info.rounds > 0 && (
          <span className="hint">
            {info.rounds} played · {info.right} voices picked out · {info.points} pts
          </span>
        )}
      </div>
      <p className="hint">No one around? Play against {info.voices.length} built-in voices: real people reading audiobooks (from{" "}
        <a href="https://www.openslr.org/12" target="_blank" rel="noreferrer">
          LibriSpeech
        </a>
        , CC BY 4.0).</p>
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
            {t.name}
          </button>
        ))}
      </div>
      <p className="hint">{TABS.find((t) => t.id === tab)!.blurb}</p>
      {tab === "guess" && <GuessTheVoice onPlayed={played} />}
      {tab === "impersonate" && <SoloSpeak key="impersonate" mode="impersonate" voices={info.voices} onPlayed={played} />}
      {tab === "disguise" && <SoloSpeak key="disguise" mode="disguise" voices={info.voices} onPlayed={played} />}
    </section>
  );
}

function GuessTheVoice({ onPlayed }: { onPlayed: (points: number, message: string) => void }) {
  const [round, setRound] = useState<SoloRound | null>(null);
  const [mystery, setMystery] = useState<string | null>(null);
  const [result, setResult] = useState<SoloGuess | null>(null);
  const [pick, setPick] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function next() {
    setBusy(true);
    setError(null);
    setResult(null);
    setPick(null);
    try {
      const r = await api.soloNewGuess();
      setRound(r);
      setMystery(URL.createObjectURL(await api.soloGuessClip(r.round_id)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => () => void (mystery && URL.revokeObjectURL(mystery)), [mystery]);

  async function guess(v: SoloVoice) {
    if (!round || result) return;
    setBusy(true);
    setPick(v.speaker_id);
    try {
      const g = await api.soloGuess(round.round_id, v.speaker_id);
      setResult(g);
      onPlayed(g.points, g.message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!round) {
    return (
      <button className="btn primary" onClick={next} disabled={busy}>
        Start a round
      </button>
    );
  }
  return (
    <div className="solo-round">
      <div className="mystery">
        <strong>Mystery voice</strong>
        {mystery && <audio src={mystery} controls className="preview" />}
      </div>
      <ul className="solo-voices">
        {round.options.map((v) => {
          const state = result ? (v.speaker_id === result.answer.speaker_id ? "right" : v.speaker_id === pick ? "wrong" : "") : "";
          return (
            <li key={v.speaker_id} className={state}>
              <span className="who">{v.name}</span>
              <PlayButton load={() => api.soloIntro(v.speaker_id)} label="▶ Hear them" />
              <button className="btn small primary" onClick={() => guess(v)} disabled={busy || result !== null}>
                It&apos;s them
              </button>
              {result?.ai_guess?.speaker_id === v.speaker_id && <span className="hint">🤖 machine&apos;s pick</span>}
            </li>
          );
        })}
      </ul>
      {result && (
        <div className={`result pop ${result.right ? "match" : "unknown"}`}>
          <div className="points">+{result.points}</div>
          <p className="announce">{result.message}</p>
          <button className="btn primary" onClick={next} disabled={busy}>
            Next round
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

function SoloSpeak({ mode, voices, onPlayed }: { mode: "impersonate" | "disguise"; voices: SoloVoice[]; onPlayed: (points: number, message: string) => void }) {
  const phrase = useChallenge();
  const [target, setTarget] = useState<SoloVoice>(voices[0]);
  const [result, setResult] = useState<SoloTurn | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(clip: Clip) {
    if (!phrase.challenge) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.soloTurn(mode, clip, phrase.challenge.challenge_id, mode === "impersonate" ? target.speaker_id : undefined);
      setResult(r);
      onPlayed(r.points, r.message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      phrase.renew();
    }
  }

  return (
    <div className="solo-round">
      {mode === "impersonate" && (
        <div className="row">
          <label className="field">
            Sound like
            <select value={target.speaker_id} onChange={(e) => setTarget(voices.find((v) => v.speaker_id === Number(e.target.value))!)}>
              {voices.map((v) => (
                <option key={v.speaker_id} value={v.speaker_id}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
          <PlayButton key={target.speaker_id} load={() => api.soloIntro(target.speaker_id)} label={`▶ Hear ${target.name}`} />
        </div>
      )}
      <Phrase state={phrase} />
      <ClipInput onClip={send} disabled={busy || !phrase.challenge || phrase.expired} allowUpload={false} />
      {busy && <p className="hint">Listening…</p>}
      {result && (
        <div className={`result pop ${result.points > 0 ? "match" : "unknown"}`}>
          <div className="points">+{result.points}</div>
          <p className="announce">{result.message}</p>
          {Object.keys(result.sounded_like).length > 0 && (
            <p className="hint">
              Closest voices: {Object.entries(result.sounded_like).map(([who, p]) => `${who} ${p}%`).join(" · ")}
            </p>
          )}
          {result.liveness && <LivenessBadge liveness={result.liveness} />}
        </div>
      )}
      {(error || phrase.error) && <p className="error">{error ?? phrase.error}</p>}
    </div>
  );
}

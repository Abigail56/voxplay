"use client";

import { useState } from "react";

import { api, type Clip, type IdentifyResult } from "@/lib/api";

import { ClipInput } from "./ClipInput";

export function IdentifyPanel() {
  const [clip, setClip] = useState<Clip | null>(null);
  const [result, setResult] = useState<IdentifyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function identify(c: Clip) {
    setClip(c);
    setResult(null);
    setError(null);
    setBusy(true);
    try {
      setResult(await api.identify(c));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>2. Who is speaking?</h2>
      <p className="hint">Record or upload a clip; it is identified automatically.</p>

      <ClipInput onClip={identify} disabled={busy} />
      {clip && <audio src={clip.url} controls className="preview" />}
      {busy && <p className="hint">Analysing voice…</p>}
      {error && <p className="error">{error}</p>}

      {result && (
        <div className={`result ${result.is_match ? "match" : "unknown"}`}>
          <div className="label">{result.is_match ? result.label : "Unknown speaker"}</div>
          <ScoreBar score={result.score} threshold={result.threshold} />
          <p className="hint">{result.reason}</p>
          {result.candidates.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Similarity</th>
                </tr>
              </thead>
              <tbody>
                {result.candidates.map((c) => (
                  <tr key={c.speaker_id}>
                    <td>{c.name}</td>
                    <td>{c.score.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}

function ScoreBar({ score, threshold }: { score: number; threshold: number }) {
  const pct = (v: number) => `${Math.max(0, Math.min(1, v)) * 100}%`;
  return (
    <div className="scorebar" title={`score ${score.toFixed(3)} / threshold ${threshold}`}>
      <div className="fill" style={{ width: pct(score) }} />
      <div className="threshold" style={{ left: pct(threshold) }} />
      <span className="value">
        confidence {score.toFixed(3)} · threshold {threshold.toFixed(2)}
      </span>
    </div>
  );
}

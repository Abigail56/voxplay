"use client";

import { useEffect, useState } from "react";

import { api, type Accuracy } from "@/lib/api";

const pct = (v: number) => `${(v * 100).toFixed(v > 0 && v < 0.1 ? 1 : 0)}%`;

/** How well the AI tells real players apart, from real turns, and the threshold that works best. */
export function AccuracyPanel({ refreshKey }: { refreshKey: number }) {
  const [acc, setAcc] = useState<Accuracy | null>(null);
  const [manual, setManual] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.admin.accuracy().then(setAcc).catch((e) => setError((e as Error).message));
  }, [refreshKey]);

  async function apply(threshold: number) {
    if (!confirm(`Use ${threshold.toFixed(2)} as the match threshold from now on?`)) return;
    try {
      setAcc(await api.admin.setThreshold(threshold));
      setManual("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!acc) return <section className="adm-panel">{error ? <p className="adm-error">{error}</p> : <p className="adm-muted">Loading…</p>}</section>;
  const rec = acc.recommended;
  const same = rec !== null && Math.abs(rec.threshold - acc.current.threshold) < 0.005;
  const kpis: { label: string; value: string; note: string; tone?: "warn" }[] = [
    { label: "Turns measured", value: String(acc.genuine_count), note: `${acc.impostor_count} with a comparison` },
    { label: "Correctly identified", value: pct(acc.current.recognition), note: `at threshold ${acc.current.threshold.toFixed(2)}` },
    { label: "Misidentified", value: pct(acc.current.wrong), note: "wrong player named", tone: acc.current.wrong > 0 ? "warn" : undefined },
    {
      label: "Stranger acceptance",
      value: pct(acc.current.far),
      note: `target ≤ ${pct(acc.target_far)}`,
      tone: acc.current.far > acc.target_far ? "warn" : undefined,
    },
    { label: "Not recognised", value: pct(acc.current.frr), note: "false rejects" },
    { label: "Learned clips", value: String(acc.learned_samples), note: "in voiceprints" },
  ];

  return (
    <div className="adm-stack">
      <div className="adm-kpis three">
        {kpis.map((k) => (
          <div key={k.label} className={`adm-kpi ${k.tone ?? ""}`}>
            <span className="adm-label">{k.label}</span>
            <strong>{k.value}</strong>
            <span className="adm-muted">{k.note}</span>
          </div>
        ))}
      </div>

      <section className="adm-panel">
        <div className="adm-panel-head">
          <h2>Score distribution</h2>
          <span className="adm-muted">Real turns that passed the live check</span>
        </div>
        <p className="adm-muted adm-prose">
          Genuine: similarity to the speaker&apos;s own voiceprint. Impostor: similarity to the closest other player. A good
          threshold sits between the two groups. Stranger acceptance estimates how often an unenrolled voice would be
          matched to a player.
        </p>
        <Histogram acc={acc} />
      </section>

      <section className="adm-panel">
        <div className="adm-panel-head">
          <h2>Match threshold</h2>
          <span className="adm-muted">Current: {acc.current.threshold.toFixed(2)}</span>
        </div>
        {acc.enough_data && rec ? (
          same ? (
            <p className="adm-notice ok">The current threshold is the recommended one for this data.</p>
          ) : (
            <div className="adm-notice">
              <p>
                Recommended: <strong>{rec.threshold.toFixed(2)}</strong>. At that setting {pct(rec.recognition)} of turns are
                correctly identified, {pct(rec.frr)} are not recognised, and stranger acceptance is {pct(rec.far)}.
              </p>
              <button className="adm-btn primary" onClick={() => apply(rec.threshold)}>
                Apply {rec.threshold.toFixed(2)}
              </button>
            </div>
          )
        ) : (
          <p className="adm-notice">
            A recommendation needs {acc.min_samples} measured turns of each kind ({acc.genuine_count}/{acc.min_samples} genuine,{" "}
            {acc.impostor_count}/{acc.min_samples} impostor). Until then the threshold stays at {acc.current.threshold.toFixed(2)},
            chosen on recorded test voices.
          </p>
        )}
        <form
          className="adm-toolbar"
          onSubmit={(e) => {
            e.preventDefault();
            const v = Number(manual);
            if (v >= 0.2 && v <= 0.8) apply(v);
            else setError("Enter a threshold between 0.20 and 0.80.");
          }}
        >
          <label className="adm-field">
            Set manually
            <input className="adm-input narrow" value={manual} onChange={(e) => setManual(e.target.value)} placeholder={acc.current.threshold.toFixed(2)} inputMode="decimal" />
          </label>
          <button className="adm-btn" disabled={!manual}>
            Apply
          </button>
          <span className="adm-muted">Higher is stricter: fewer misidentifications, more players not recognised.</span>
        </form>
        {error && <p className="adm-error">{error}</p>}
      </section>
    </div>
  );
}

const W = 640;
const H = 200;
const PAD = { left: 34, right: 10, top: 12, bottom: 28 };

/** Genuine vs impostor scores, side by side per bin, with the current threshold marked. */
function Histogram({ acc }: { acc: Accuracy }) {
  const [hover, setHover] = useState<number | null>(null);
  const bins = acc.histogram;
  if (acc.genuine_count === 0) return <p className="adm-muted">No turns measured yet. The chart fills in as people play.</p>;
  const max = Math.max(1, ...bins.flatMap(([, g, i]) => [g, i]));
  const lo = bins[0][0];
  const hi = bins[bins.length - 1][0] + 0.05;
  const x = (v: number) => PAD.left + ((v - lo) / (hi - lo)) * (W - PAD.left - PAD.right);
  const y = (n: number) => H - PAD.bottom - (n / max) * (H - PAD.top - PAD.bottom);
  const bw = (x(lo + 0.05) - x(lo)) / 2 - 2; // two bars per bin, 2px surface gap
  const t = acc.current.threshold;

  return (
    <figure className="histogram">
      <div className="legend">
        <span>
          <i style={{ background: "var(--series-1)" }} /> Genuine
        </span>
        <span>
          <i style={{ background: "var(--series-2)" }} /> Impostor
        </span>
        <span>
          <i className="line" /> Threshold {t.toFixed(2)}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Similarity scores of real turns: genuine vs impostor" onPointerLeave={() => setHover(null)}>
        <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} className="axis-line" />
        {[0, 0.25, 0.5, 0.75].map((v) => (
          <text key={v} x={x(v)} y={H - 8} textAnchor="middle" className="axis-text">
            {v.toFixed(2)}
          </text>
        ))}
        <text x={4} y={PAD.top + 8} className="axis-text">
          {max}
        </text>
        {bins.map(([start, g, i], k) => (
          <g key={k} onPointerEnter={() => setHover(k)}>
            <rect x={x(start)} y={PAD.top} width={bw * 2 + 4} height={H - PAD.top - PAD.bottom} fill="transparent" />
            {g > 0 && <rect x={x(start) + 1} y={y(g)} width={bw} height={y(0) - y(g)} rx={2} fill="var(--series-1)" opacity={hover === k ? 1 : 0.85} />}
            {i > 0 && <rect x={x(start) + bw + 3} y={y(i)} width={bw} height={y(0) - y(i)} rx={2} fill="var(--series-2)" opacity={hover === k ? 1 : 0.85} />}
          </g>
        ))}
        <line x1={x(t)} x2={x(t)} y1={PAD.top - 6} y2={y(0)} className="threshold-line" />
      </svg>
      {hover !== null && (
        <figcaption className="hist-readout">
          <strong>
            {bins[hover][0].toFixed(2)}–{(bins[hover][0] + 0.05).toFixed(2)}
          </strong>{" "}
          · genuine <strong>{bins[hover][1]}</strong> · impostor <strong>{bins[hover][2]}</strong>
        </figcaption>
      )}
      <details>
        <summary className="adm-muted">Show as table</summary>
        <table className="adm-table">
          <thead>
            <tr>
              <th>Similarity</th>
              <th className="num">Genuine</th>
              <th className="num">Impostor</th>
            </tr>
          </thead>
          <tbody>
            {bins
              .filter(([, g, i]) => g || i)
              .map(([start, g, i]) => (
                <tr key={start}>
                  <td>
                    {start.toFixed(2)}–{(start + 0.05).toFixed(2)}
                  </td>
                  <td className="num">{g}</td>
                  <td className="num">{i}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

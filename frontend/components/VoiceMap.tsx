"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type MapSpeaker, type VoiceMap as VoiceMapData } from "@/lib/api";

const W = 420;
const H = 300;
const PAD = 36;

// Map coordinates are in [-1, 1]; screen y grows downwards.
const sx = (x: number) => PAD + ((x + 1) / 2) * (W - 2 * PAD);
const sy = (y: number) => H - PAD - ((y + 1) / 2) * (H - 2 * PAD);

export function VoiceMap() {
  const [data, setData] = useState<VoiceMapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState<MapSpeaker | null>(null);

  useEffect(() => {
    api
      .voiceMap()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError((e as Error).message));
  }, []);

  const byId = useMemo(() => new Map(data?.speakers.map((s) => [s.speaker_id, s]) ?? []), [data]);
  const twin = focus?.twin ? byId.get(focus.twin.speaker_id) : undefined;

  return (
    <section className="card">
      <h2>Voice twins</h2>
      <p className="hint">
        Every player&apos;s voice as a dot: voices that sound alike sit close together. Hover or tab to a name to find
        their voice twin.
      </p>
      {error && <p className="error">{error}</p>}
      {data && data.speakers.length === 0 && <p className="hint">Once players record their voices, they show up here.</p>}

      {data && data.speakers.length > 0 && (
        <>
          <div className="map-wrap">
            <svg viewBox={`0 0 ${W} ${H}`} className="voice-map" role="img" aria-label="Map of enrolled voices">
              <rect x={PAD / 2} y={PAD / 2} width={W - PAD} height={H - PAD} rx={8} className="map-frame" />

              {data.samples.map((d, i) => (
                <circle
                  key={i}
                  cx={sx(d.x)}
                  cy={sy(d.y)}
                  r={3}
                  className={`map-sample ${focus ? (d.speaker_id === focus.speaker_id ? "on" : "off") : ""}`}
                />
              ))}

              {focus && twin && (
                <line x1={sx(focus.x)} y1={sy(focus.y)} x2={sx(twin.x)} y2={sy(twin.y)} className="twin-line" />
              )}

              {data.speakers.map((s) => {
                const cx = sx(s.x);
                const cy = sy(s.y);
                const labelLeft = s.x > 0.55; // keep labels inside the frame
                const dim = focus && focus !== s && focus.twin?.speaker_id !== s.speaker_id;
                return (
                  <g
                    key={s.speaker_id}
                    className={`map-point ${dim ? "dim" : ""} ${focus === s ? "active" : ""}`}
                    tabIndex={0}
                    role="button"
                    aria-label={describe(s)}
                    onPointerEnter={() => setFocus(s)}
                    onPointerLeave={() => setFocus(null)}
                    onFocus={() => setFocus(s)}
                    onBlur={() => setFocus(null)}
                  >
                    <circle cx={cx} cy={cy} r={14} className="hit" />
                    <circle cx={cx} cy={cy} r={6} className={`map-dot ${s.is_sample ? "builtin" : ""}`} />
                    <text x={labelLeft ? cx - 10 : cx + 10} y={cy + 4} textAnchor={labelLeft ? "end" : "start"}>
                      {s.name}
                    </text>
                  </g>
                );
              })}
            </svg>

          </div>

          {/* A fixed readout instead of a floating tooltip, so it never hides the twin it points to. */}
          <p className="map-readout" role="status">
            {focus ? (
              <>
                <strong>{focus.name}</strong>
                {focus.twin ? (
                  <>
                    {" "}
                    sounds most like <strong>{focus.twin.name}</strong>{" "}
                    <span className="hint">(similarity {focus.twin.score.toFixed(2)})</span>
                  </>
                ) : (
                  <span className="hint"> · no one else enrolled yet</span>
                )}
                {focus.consistency !== null && (
                  <span className="hint"> · own clips agree {Math.round(focus.consistency * 100)}%</span>
                )}
              </>
            ) : (
              <span className="hint">Hover or tab to a voice.</span>
            )}
          </p>

          <table>
            <thead>
              <tr>
                <th>Voice</th>
                <th>Sounds most like</th>
                <th className="num">Similarity</th>
                <th className="num">Own clips agree</th>
              </tr>
            </thead>
            <tbody>
              {data.speakers.map((s) => (
                <tr key={s.speaker_id}>
                  <td>
                    {s.name}
                    {s.is_sample && <span className="hint"> · built-in</span>}
                  </td>
                  <td>{s.twin?.name ?? "–"}</td>
                  <td className="num">{s.twin ? s.twin.score.toFixed(2) : "–"}</td>
                  <td className="num">{s.consistency !== null ? `${Math.round(s.consistency * 100)}%` : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">
            The map squeezes 192 numbers into 2, so distances are rough. &ldquo;Sounds most like&rdquo; uses all 192
            and is exact. Two different people usually score below 0.3.
          </p>
        </>
      )}
    </section>
  );
}

function describe(s: MapSpeaker): string {
  const twin = s.twin ? `, sounds most like ${s.twin.name} (${s.twin.score.toFixed(2)})` : "";
  return `${s.name}${twin}`;
}

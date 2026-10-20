"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type MapSpeaker, type VoiceMap } from "@/lib/api";

const W = 420;
const H = 300;
const PAD = 36;

// Map coordinates are in [-1, 1]; screen y grows downwards.
const sx = (x: number) => PAD + ((x + 1) / 2) * (W - 2 * PAD);
const sy = (y: number) => H - PAD - ((y + 1) / 2) * (H - 2 * PAD);

/** Who sounds like whom: every player's voice on a map, and your own voice twin. */
export function VoiceTwins({ refreshKey }: { refreshKey: number }) {
  const [data, setData] = useState<VoiceMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState<MapSpeaker | null>(null);

  // Refetch with the dashboard, so a player who has just recorded shows up.
  useEffect(() => {
    api
      .voiceTwins()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError((e as Error).message));
  }, [refreshKey]);

  const byId = useMemo(() => new Map(data?.speakers.map((s) => [s.speaker_id, s]) ?? []), [data]);
  const me = data?.me != null ? byId.get(data.me) : undefined;
  const twin = focus?.twin ? byId.get(focus.twin.speaker_id) : undefined;

  return (
    <section className="card">
      <h2>Voice twins</h2>
      {me?.twin ? (
        <p>
          Your voice twin is <strong>{me.twin.name}</strong>{" "}
          <span className="hint">(similarity {me.twin.score.toFixed(2)})</span>. Try impersonating them!
        </p>
      ) : (
        <p className="hint">Once another player records their voice, you&apos;ll find out who sounds most like you.</p>
      )}
      <p className="hint">
        Every player&apos;s voice as a dot: voices that sound alike sit close together. Hover or tab to a name to find
        their voice twin.
      </p>
      {error && <p className="error">{error}</p>}

      {data && data.speakers.length > 0 && (
        <>
          <div className="map-wrap">
            <svg viewBox={`0 0 ${W} ${H}`} className="voice-map" role="img" aria-label="Map of players' voices">
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
                const mine = s === me;
                return (
                  <g
                    key={s.speaker_id}
                    className={`map-point ${dim ? "dim" : ""} ${focus === s ? "active" : ""} ${mine ? "me" : ""}`}
                    tabIndex={0}
                    role="button"
                    aria-label={describe(s, mine)}
                    onPointerEnter={() => setFocus(s)}
                    onPointerLeave={() => setFocus(null)}
                    onFocus={() => setFocus(s)}
                    onBlur={() => setFocus(null)}
                  >
                    <circle cx={cx} cy={cy} r={14} className="hit" />
                    <circle cx={cx} cy={cy} r={6} className={`map-dot ${mine ? "me" : ""}`} />
                    <text x={labelLeft ? cx - 10 : cx + 10} y={cy + 4} textAnchor={labelLeft ? "end" : "start"}>
                      {mine ? `${s.name} (you)` : s.name}
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
                  <span className="hint"> · no one else has recorded yet</span>
                )}
                {focus.consistency !== null && (
                  <span className="hint"> · own clips agree {Math.round(focus.consistency * 100)}%</span>
                )}
              </>
            ) : (
              <span className="hint">Hover or tab to a voice.</span>
            )}
          </p>

          <p className="hint">
            The map squeezes 192 numbers into 2, so distances are rough. &ldquo;Sounds most like&rdquo; uses all 192
            and is exact. Two different people usually score below 0.3.
          </p>
        </>
      )}
    </section>
  );
}

function describe(s: MapSpeaker, mine: boolean): string {
  const twin = s.twin ? `, sounds most like ${s.twin.name} (${s.twin.score.toFixed(2)})` : "";
  return `${s.name}${mine ? " (you)" : ""}${twin}`;
}

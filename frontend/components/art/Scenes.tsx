// Original VOXPLAY artwork, drawn as SVG: a few kilobytes each, sharp at any size, no licences needed.
// The look: anime-style silhouettes with neon rim light, against a night sky over a floating Nexus.
// Motion comes from CSS classes (art-float, art-spin, art-pulse), which reduced-motion turns off.

import { ART, type ArtSlot } from "@/lib/art";

type SceneProps = { className?: string };

// Deterministic "random" stars, so the server and the browser draw the same sky.
function stars(count: number, w: number, h: number, seed: number) {
  let s = seed;
  const next = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  return Array.from({ length: count }, () => ({ x: next() * w, y: next() * h * 0.7, r: next() * 1.4 + 0.3, o: next() * 0.6 + 0.3 }));
}

function Sky({ id, w, h, seed = 7 }: { id: string; w: number; h: number; seed?: number }) {
  return (
    <>
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0b0d26" />
          <stop offset="0.55" stopColor="#1b1150" />
          <stop offset="1" stopColor="#080a16" />
        </linearGradient>
      </defs>
      <rect width={w} height={h} fill={`url(#${id}-sky)`} />
      {stars(70, w, h, seed).map((st, i) => (
        <circle key={i} cx={st.x} cy={st.y} r={st.r} fill="#e9e4ff" opacity={st.o} className={i % 9 === 0 ? "art-twinkle" : undefined} />
      ))}
    </>
  );
}

/** A far-off city skyline with a few lit windows. */
function Skyline({ y, w, color = "#12153a", seed = 3 }: { y: number; w: number; color?: string; seed?: number }) {
  let s = seed;
  const next = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  const towers = [];
  for (let x = -10; x < w; ) {
    const tw = 18 + next() * 34;
    const th = 30 + next() * 120;
    towers.push({ x, tw, th });
    x += tw + 2;
  }
  return (
    <g>
      {towers.map((t, i) => (
        <g key={i}>
          <rect x={t.x} y={y - t.th} width={t.tw} height={t.th + 200} fill={color} />
          {i % 3 === 0 && <rect x={t.x + t.tw / 2 - 1} y={y - t.th - 14} width={2} height={14} fill={color} />}
          {Array.from({ length: Math.floor(t.th / 22) }, (_, k) =>
            (i + k) % 4 === 0 ? <rect key={k} x={t.x + 5} y={y - t.th + 8 + k * 22} width={4} height={3} fill={k % 2 ? "#38bdf8" : "#f472b6"} opacity={0.7} /> : null,
          )}
        </g>
      ))}
    </g>
  );
}

/** The Nexus portal: neon rings around a bright core. */
function Portal({ id, cx, cy, r }: { id: string; cx: number; cy: number; r: number }) {
  return (
    <g>
      <defs>
        <radialGradient id={`${id}-core`}>
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="0.25" stopColor="#c4b5fd" stopOpacity="0.8" />
          <stop offset="0.6" stopColor="#7c3aed" stopOpacity="0.35" />
          <stop offset="1" stopColor="#7c3aed" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#38bdf8" />
          <stop offset="0.5" stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
      </defs>
      <circle cx={cx} cy={cy} r={r * 1.9} fill={`url(#${id}-core)`} className="art-pulse" />
      <g className="art-spin" style={{ transformOrigin: `${cx}px ${cy}px` }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={`url(#${id}-ring)`} strokeWidth={5} strokeDasharray={`${r * 1.2} ${r * 0.35}`} />
        <circle cx={cx} cy={cy} r={r * 0.78} fill="none" stroke="#38bdf8" strokeWidth={1.5} strokeDasharray="3 9" opacity={0.8} />
      </g>
      <circle cx={cx} cy={cy} r={r * 1.18} fill="none" stroke={`url(#${id}-ring)`} strokeWidth={1} opacity={0.5} />
    </g>
  );
}

/** A floating hexagonal platform with a neon edge. */
function Platform({ x, y, s, edge = "#38bdf8", className }: { x: number; y: number; s: number; edge?: string; className?: string }) {
  const top = `M${x - s} ${y} L${x - s / 2} ${y - s * 0.28} L${x + s / 2} ${y - s * 0.28} L${x + s} ${y} L${x + s / 2} ${y + s * 0.28} L${x - s / 2} ${y + s * 0.28} Z`;
  return (
    <g className={className}>
      <path d={`M${x - s} ${y} L${x - s} ${y + s * 0.3} L${x - s / 2} ${y + s * 0.58} L${x + s / 2} ${y + s * 0.58} L${x + s} ${y + s * 0.3} L${x + s} ${y} Z`} fill="#0e1130" />
      <path d={top} fill="#1c2050" stroke={edge} strokeWidth={1.5} />
      <path d={`M${x - s / 2} ${y + s * 0.28} L${x - s / 2} ${y + s * 0.58} M${x + s / 2} ${y + s * 0.28} L${x + s / 2} ${y + s * 0.58}`} stroke={edge} strokeOpacity={0.35} />
    </g>
  );
}

/** The hero: seen from behind, coat in the wind, headphones on, looking into the portal. */
function Hero({ id, x, y, scale = 1 }: { id: string; x: number; y: number; scale?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <defs>
        <linearGradient id={`${id}-rim`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#f472b6" />
          <stop offset="0.5" stopColor="#8b5cf6" stopOpacity="0.2" />
          <stop offset="1" stopColor="#38bdf8" />
        </linearGradient>
      </defs>
      {/* coat tails caught by the wind */}
      <path d="M-62 170 C-90 210 -112 250 -128 300 L-86 292 C-74 250 -64 214 -46 188 Z" fill="#0b0d20" stroke={`url(#${id}-rim)`} strokeWidth={1.5} />
      {/* body and coat */}
      <path
        d="M-14 30 L14 30 L20 44 C46 50 62 62 66 92 L74 172 L84 262 L42 254 L30 172 L22 262 L-18 262 L-26 172 L-40 254 L-80 260 L-68 172 L-62 94 C-58 62 -42 50 -20 44 Z"
        fill="#0b0d20"
        stroke={`url(#${id}-rim)`}
        strokeWidth={2}
        strokeLinejoin="round"
      />
      {/* seam and collar light */}
      <path d="M2 46 L2 250" stroke="#8b5cf6" strokeOpacity={0.45} strokeWidth={1.5} />
      <path d="M-20 44 C-8 54 12 54 20 44" fill="none" stroke="#38bdf8" strokeWidth={2} />
      {/* head and spiky, wind-swept hair */}
      <circle cx={0} cy={0} r={27} fill="#0b0d20" />
      <path
        d="M-30 6 C-36 -24 -16 -46 6 -46 C32 -46 46 -26 40 4 L52 18 L36 12 L40 34 L26 18 L22 40 L12 20 L2 42 L-4 18 L-16 36 L-16 16 L-34 28 L-26 12 L-44 14 Z"
        fill="#0d0f26"
        stroke={`url(#${id}-rim)`}
        strokeWidth={1.8}
        strokeLinejoin="round"
      />
      <path d="M-18 -34 C-8 -40 10 -40 22 -32" fill="none" stroke="#c4b5fd" strokeOpacity={0.6} strokeWidth={1.5} />
      {/* headphones */}
      <path d="M-30 -2 C-30 -40 32 -42 34 -4" fill="none" stroke="#38bdf8" strokeWidth={3.5} />
      <rect x={-37} y={-6} width={10} height={20} rx={4} fill="#38bdf8" />
      <rect x={30} y={-8} width={10} height={20} rx={4} fill="#f472b6" />
    </g>
  );
}

/** A bust in profile for the Brain Clash face-off. `ponytail` changes the hair. */
function Rival({ ponytail, color }: { ponytail?: boolean; color: string }) {
  return (
    <g>
      <path d="M-70 160 C-70 110 -40 88 0 84 C40 88 70 110 70 160 Z" fill="#0b0d20" stroke={color} strokeWidth={2} />
      <path d="M-12 62 L12 62 L14 88 L-14 88 Z" fill="#0b0d20" />
      <path d="M-30 20 C-30 -14 -8 -30 14 -28 C38 -26 50 -6 46 18 L52 30 L44 32 L42 50 C40 62 28 70 12 68 C-14 66 -30 48 -30 20 Z" fill="#0b0d20" stroke={color} strokeWidth={2} />
      {ponytail ? (
        <path d="M-30 6 C-38 -30 6 -46 34 -26 C48 -16 50 0 46 10 C30 -6 4 -10 -14 4 C-30 16 -40 40 -56 52 C-70 64 -86 60 -96 72 C-88 44 -60 34 -46 18 Z" fill="#141039" stroke={color} strokeWidth={1.8} />
      ) : (
        <path d="M-34 14 L-48 -6 L-26 -6 L-34 -30 L-10 -18 L-6 -44 L10 -22 L24 -42 L28 -18 L48 -28 L42 -6 L56 4 L36 4 C24 -8 0 -10 -18 0 Z" fill="#141039" stroke={color} strokeWidth={1.8} strokeLinejoin="round" />
      )}
      <path d="M30 22 L40 20" stroke={color} strokeWidth={3} strokeLinecap="round" />
    </g>
  );
}

export function NexusScene({ className }: SceneProps) {
  const W = 800;
  const H = 600;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="A hero in headphones stands on a floating platform, facing a glowing portal above a neon city">
      <Sky id="nx" w={W} h={H} />
      <Portal id="nx" cx={520} cy={230} r={92} />
      <Skyline y={470} w={W} seed={11} color="#121538" />
      <Skyline y={520} w={W} seed={5} color="#0d1030" />
      <Platform x={640} y={150} s={38} edge="#f472b6" className="art-float slow" />
      <Platform x={420} y={400} s={46} edge="#38bdf8" className="art-float" />
      <Platform x={710} y={360} s={28} edge="#8b5cf6" className="art-float slow" />
      {/* light beams from the portal */}
      <path d="M520 230 L300 600 L420 600 Z" fill="#8b5cf6" opacity={0.08} />
      <path d="M520 230 L560 600 L660 600 Z" fill="#38bdf8" opacity={0.06} />
      <Platform x={250} y={560} s={120} edge="#8b5cf6" />
      <Hero id="nx" x={250} y={300} />
    </svg>
  );
}

export function ArenaScene({ className, label = "Two rivals face off across a glowing arena" }: SceneProps & { label?: string }) {
  const W = 800;
  const H = 400;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label={label}>
      <defs>
        <linearGradient id="ar-split" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#3b1a8f" />
          <stop offset="0.48" stopColor="#120f3a" />
          <stop offset="0.52" stopColor="#0d1c3d" />
          <stop offset="1" stopColor="#0c4a6e" />
        </linearGradient>
        <radialGradient id="ar-core">
          <stop offset="0" stopColor="#fff" stopOpacity="0.9" />
          <stop offset="0.4" stopColor="#f472b6" stopOpacity="0.5" />
          <stop offset="1" stopColor="#f472b6" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill="url(#ar-split)" />
      {stars(40, W, H, 21).map((st, i) => (
        <circle key={i} cx={st.x} cy={st.y * 0.7} r={st.r} fill="#fff" opacity={st.o * 0.6} />
      ))}
      {/* arena floor: a perspective grid */}
      <path d="M0 300 L800 300 L800 400 L0 400 Z" fill="#080a16" opacity={0.7} />
      {Array.from({ length: 13 }, (_, i) => (
        <line key={i} x1={400} y1={300} x2={-200 + i * 100} y2={400} stroke="#8b5cf6" strokeOpacity={0.25} />
      ))}
      {[310, 330, 360].map((y) => (
        <line key={y} x1={0} y1={y} x2={W} y2={y} stroke="#38bdf8" strokeOpacity={0.2} />
      ))}
      {/* the clash in the middle */}
      <circle cx={400} cy={170} r={120} fill="url(#ar-core)" className="art-pulse" />
      <path d="M408 70 L366 180 L398 180 L382 270 L438 150 L404 150 L424 70 Z" fill="#fde68a" stroke="#fff" strokeWidth={2} strokeLinejoin="round" />
      <g transform="translate(190 190)">
        <Rival ponytail color="#a78bfa" />
      </g>
      <g transform="translate(610 190) scale(-1 1)">
        <Rival color="#38bdf8" />
      </g>
    </svg>
  );
}

export function VoiceScene({ className }: SceneProps) {
  const W = 800;
  const H = 400;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="A figure with a headset speaks into rings of sound">
      <Sky id="vs" w={W} h={H} seed={31} />
      <Skyline y={360} w={W} seed={8} color="#10133a" />
      {[60, 110, 160, 210].map((r, i) => (
        <circle key={r} cx={470} cy={190} r={r} fill="none" stroke={i % 2 ? "#38bdf8" : "#f472b6"} strokeOpacity={0.55 - i * 0.1} strokeWidth={3} className="art-pulse" />
      ))}
      {Array.from({ length: 21 }, (_, i) => {
        const h = 16 + Math.abs(Math.sin(i * 1.7)) * 70;
        return <rect key={i} x={560 + i * 10} y={190 - h / 2} width={5} height={h} rx={2.5} fill="#a78bfa" opacity={0.8} />;
      })}
      <g transform="translate(330 220)">
        <Rival ponytail color="#f472b6" />
        <path d="M-26 6 C-30 -40 40 -44 46 0" fill="none" stroke="#38bdf8" strokeWidth={4} transform="translate(0 4)" />
        <path d="M44 22 C70 26 82 36 88 44" fill="none" stroke="#38bdf8" strokeWidth={3} />
        <circle cx={90} cy={46} r={5} fill="#38bdf8" />
      </g>
    </svg>
  );
}

export function SoonScene({ className, hue = "#8b5cf6" }: SceneProps & { hue?: string }) {
  const W = 800;
  const H = 400;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="A sealed portal, still charging">
      <Sky id="ss" w={W} h={H} seed={53} />
      <Skyline y={380} w={W} seed={13} color="#10133a" />
      <g opacity={0.6}>
        <Portal id="ss" cx={400} cy={190} r={80} />
      </g>
      <path d="M340 190 L400 130 L460 190 L400 250 Z" fill="none" stroke={hue} strokeWidth={3} />
      <rect x={385} y={180} width={30} height={26} rx={4} fill="#0b0d20" stroke={hue} strokeWidth={2} />
      <path d="M391 180 V170 a9 9 0 0 1 18 0 V180" fill="none" stroke={hue} strokeWidth={2} />
    </svg>
  );
}

export function VictoryScene({ className, color = "#a78bfa" }: SceneProps & { color?: string }) {
  const W = 800;
  const H = 420;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="A trophy blazes with light as the champions celebrate">
      <Sky id="vc" w={W} h={H} seed={77} />
      {Array.from({ length: 16 }, (_, i) => {
        const a = (i / 16) * Math.PI * 2;
        return <path key={i} d={`M400 170 L${400 + Math.cos(a) * 520} ${170 + Math.sin(a) * 520} L${400 + Math.cos(a + 0.12) * 520} ${170 + Math.sin(a + 0.12) * 520} Z`} fill={i % 2 ? color : "#38bdf8"} opacity={0.08} />;
      })}
      <circle cx={400} cy={170} r={110} fill={color} opacity={0.15} className="art-pulse" />
      {/* trophy */}
      <path d="M350 100 L450 100 L444 170 C440 200 420 214 400 214 C380 214 360 200 356 170 Z" fill="#fbbf24" stroke="#fff7d6" strokeWidth={2} />
      <path d="M350 112 C318 112 316 156 356 164 M450 112 C482 112 484 156 444 164" fill="none" stroke="#fbbf24" strokeWidth={8} />
      <rect x={390} y={212} width={20} height={34} fill="#d99a06" />
      <rect x={362} y={244} width={76} height={18} rx={4} fill="#fbbf24" />
      <path d="M400 128 l8 16 18 2 -13 12 4 18 -17 -9 -17 9 4 -18 -13 -12 18 -2 Z" fill="#fff7d6" />
      {/* the champions, arms up */}
      {[220, 580].map((x, i) => (
        <g key={x} transform={`translate(${x} 300)`}>
          <path d="M-40 120 C-40 70 -26 48 0 46 C26 48 40 70 40 120 Z" fill="#0b0d20" stroke={i ? "#38bdf8" : "#f472b6"} strokeWidth={2} />
          <path d="M-30 64 L-54 -6 M30 64 L54 -6" stroke="#0b0d20" strokeWidth={14} strokeLinecap="round" />
          <path d="M-30 64 L-54 -6 M30 64 L54 -6" stroke={i ? "#38bdf8" : "#f472b6"} strokeWidth={2} strokeLinecap="round" fill="none" opacity={0.7} />
          <circle cx={0} cy={22} r={22} fill="#0b0d20" stroke={i ? "#38bdf8" : "#f472b6"} strokeWidth={2} />
        </g>
      ))}
      {Array.from({ length: 24 }, (_, i) => (
        <rect key={i} x={(i * 97) % W} y={(i * 53) % 260} width={8} height={14} rx={2} fill={["#f472b6", "#38bdf8", "#fbbf24", "#a78bfa"][i % 4]} transform={`rotate(${i * 37} ${(i * 97) % W} ${(i * 53) % 260})`} opacity={0.8} />
      ))}
    </svg>
  );
}

const SCENES: Record<ArtSlot, (props: SceneProps) => React.ReactElement> = {
  hero: NexusScene,
  brainClash: ArenaScene,
  whosTalking: VoiceScene,
  comingSoon: SoonScene,
  lobby: (p) => <ArenaScene {...p} label="An empty arena, waiting for players" />,
  victory: VictoryScene,
  empty: SoonScene,
};

/** One artwork slot: the image set in lib/art.ts if there is one, otherwise its SVG scene. */
export function Art({ slot, className }: { slot: ArtSlot; className?: string }) {
  const image = ART[slot];
  if (image) return <img src={image.src} alt={image.alt} className={className} loading="lazy" decoding="async" />;
  const Scene = SCENES[slot];
  return <Scene className={className} />;
}

// Original VOXPLAY artwork, drawn as SVG: a few kilobytes each, sharp at any size, no licences needed.
// The look: an anime key visual. Cel-shaded mascots (components/art/Characters.tsx) in front of sunset
// skies, manga speed lines, sparkles and a glowing portal. Motion comes from CSS classes (art-float,
// art-spin, art-pulse, art-twinkle), which reduced-motion turns off.

import { ART, type ArtSlot } from "@/lib/art";

import { Mystery, Nova, Pulse } from "./Characters";

type SceneProps = { className?: string };

// Deterministic "random" numbers, so the server and the browser draw the same picture.
function rng(seed: number) {
  let s = seed;
  return () => ((s = (s * 9301 + 49297) % 233280) / 233280);
}

/** A point at angle `a` and radius `r` from (cx, cy), rounded: Math.cos can differ in the last digit
 *  between the server and the browser, and the SVG must match exactly. */
function polar(cx: number, cy: number, a: number, r: number) {
  return `${Math.round((cx + Math.cos(a) * r) * 10) / 10} ${Math.round((cy + Math.sin(a) * r) * 10) / 10}`;
}

/** A sky in three colours with stars in its upper part. */
function Sky({ id, w, h, colors, seed = 7 }: { id: string; w: number; h: number; colors: [string, string, string]; seed?: number }) {
  const next = rng(seed);
  return (
    <>
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={colors[0]} />
          <stop offset="0.55" stopColor={colors[1]} />
          <stop offset="1" stopColor={colors[2]} />
        </linearGradient>
      </defs>
      <rect width={w} height={h} fill={`url(#${id}-sky)`} />
      {Array.from({ length: 50 }, (_, i) => (
        <circle key={i} cx={next() * w} cy={next() * h * 0.5} r={next() * 1.3 + 0.3} fill="#fff" opacity={next() * 0.5 + 0.3} className={i % 7 === 0 ? "art-twinkle" : undefined} />
      ))}
    </>
  );
}

/** Manga focus lines bursting out from one point. */
function SpeedLines({ cx, cy, color = "#fff", count = 36, opacity = 0.14, seed = 5 }: { cx: number; cy: number; color?: string; count?: number; opacity?: number; seed?: number }) {
  const next = rng(seed);
  return (
    <g opacity={opacity}>
      {Array.from({ length: count }, (_, i) => {
        const a = (i / count) * Math.PI * 2 + next() * 0.08;
        const spread = 0.012 + next() * 0.02;
        const r0 = 90 + next() * 80;
        const r1 = 1100;
        return (
          <path
            key={i}
            d={`M${polar(cx, cy, a, r0)} L${polar(cx, cy, a - spread, r1)} L${polar(cx, cy, a + spread, r1)} Z`}
            fill={color}
          />
        );
      })}
    </g>
  );
}

/** A four-pointed anime sparkle. */
function Sparkle({ x, y, s, color = "#fff", twinkle }: { x: number; y: number; s: number; color?: string; twinkle?: boolean }) {
  const k = s * 0.22;
  return (
    <path
      d={`M${x} ${y - s} Q${x + k} ${y - k} ${x + s} ${y} Q${x + k} ${y + k} ${x} ${y + s} Q${x - k} ${y + k} ${x - s} ${y} Q${x - k} ${y - k} ${x} ${y - s} Z`}
      fill={color}
      className={twinkle ? "art-twinkle" : undefined}
    />
  );
}

/** Soft anime clouds lit from below. */
function Clouds({ y, w, color, light, seed = 2 }: { y: number; w: number; color: string; light: string; seed?: number }) {
  const next = rng(seed);
  const puffs = [];
  for (let x = -40; x < w + 40; x += 70 + next() * 60) puffs.push({ x, r: 34 + next() * 40, dy: next() * 26 });
  return (
    <g>
      {puffs.map((p, i) => (
        <circle key={`l${i}`} cx={p.x} cy={y + p.dy + 4} r={p.r} fill={light} />
      ))}
      {puffs.map((p, i) => (
        <circle key={`c${i}`} cx={p.x} cy={y + p.dy} r={p.r} fill={color} />
      ))}
      <rect x={0} y={y + 20} width={w} height={400} fill={color} />
    </g>
  );
}

/** A far-off city skyline with a few lit windows. */
function Skyline({ y, w, color, seed = 3 }: { y: number; w: number; color: string; seed?: number }) {
  const next = rng(seed);
  const towers = [];
  for (let x = -10; x < w; ) {
    const tw = 18 + next() * 34;
    const th = 30 + next() * 110;
    towers.push({ x, tw, th });
    x += tw + 2;
  }
  return (
    <g>
      {towers.map((t, i) => (
        <g key={i}>
          <rect x={t.x} y={y - t.th} width={t.tw} height={t.th + 300} fill={color} />
          {Array.from({ length: Math.floor(t.th / 20) }, (_, k) =>
            (i + k) % 3 === 0 ? <rect key={k} x={t.x + 5} y={y - t.th + 8 + k * 20} width={4} height={3} fill={k % 2 ? "#7dd3fc" : "#f9a8d4"} opacity={0.75} /> : null,
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
          <stop offset="0.3" stopColor="#f5d0fe" stopOpacity="0.75" />
          <stop offset="0.65" stopColor="#a855f7" stopOpacity="0.3" />
          <stop offset="1" stopColor="#a855f7" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#38bdf8" />
          <stop offset="0.5" stopColor="#c084fc" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
      </defs>
      <circle cx={cx} cy={cy} r={r * 2} fill={`url(#${id}-core)`} className="art-pulse" />
      <g className="art-spin" style={{ transformOrigin: `${cx}px ${cy}px` }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={`url(#${id}-ring)`} strokeWidth={7} strokeDasharray={`${r * 1.3} ${r * 0.3}`} />
        <circle cx={cx} cy={cy} r={r * 0.8} fill="none" stroke="#e0f2fe" strokeWidth={2} strokeDasharray="4 10" opacity={0.85} />
      </g>
      <circle cx={cx} cy={cy} r={r * 1.2} fill="none" stroke={`url(#${id}-ring)`} strokeWidth={1.5} opacity={0.6} />
    </g>
  );
}

/** A soft light behind a character, so they pop off the background. */
function Aura({ cx, cy, r, color }: { cx: number; cy: number; r: number; color: string }) {
  return <ellipse cx={cx} cy={cy} rx={r} ry={r * 1.1} fill={color} opacity={0.35} filter="url(#soft)" />;
}

function SoftFilter() {
  return (
    <filter id="soft" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="30" />
    </filter>
  );
}

export function NexusScene({ className }: SceneProps) {
  const W = 800;
  const H = 600;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="Nova and Pulse, the VOXPLAY captains, stand before a glowing portal above a neon city at dusk">
      <defs>
        <SoftFilter />
      </defs>
      <Sky id="nx" w={W} h={H} colors={["#1a0b4a", "#7b2c8f", "#f472b6"]} seed={11} />
      <Portal id="nx" cx={560} cy={210} r={110} />
      <SpeedLines cx={560} cy={210} color="#fff" opacity={0.12} count={44} seed={9} />
      <Clouds y={430} w={W} color="#3b1466" light="#f9a8d4" seed={4} />
      <Skyline y={520} w={W} color="#24104a" seed={11} />
      <Aura cx={610} cy={250} r={150} color="#38bdf8" />
      <Aura cx={300} cy={290} r={170} color="#c084fc" />
      <g transform="translate(424 40) scale(0.95)">
        <Pulse id="nx" />
      </g>
      <g transform="translate(84 44) scale(1.1)">
        <Nova id="nx" />
      </g>
      <Sparkle x={120} y={120} s={16} color="#fde68a" twinkle />
      <Sparkle x={730} y={90} s={12} color="#fff" twinkle />
      <Sparkle x={80} y={330} s={9} color="#f9a8d4" />
      <Sparkle x={760} y={300} s={10} color="#a5f3fc" twinkle />
    </svg>
  );
}

/** The two captains face off, split down the middle like a fighting-game "VS" screen. */
export function ArenaScene({ className, label = "Nova and Pulse face off on a split violet and blue VS screen" }: SceneProps & { label?: string }) {
  const W = 800;
  const H = 400;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label={label}>
      <defs>
        <SoftFilter />
        <linearGradient id="ar-a" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4c1d95" />
          <stop offset="1" stopColor="#db2777" />
        </linearGradient>
        <linearGradient id="ar-b" x1="1" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#075985" />
          <stop offset="1" stopColor="#1e3a8a" />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill="url(#ar-a)" />
      <path d={`M470 0 L${W} 0 L${W} ${H} L330 ${H} Z`} fill="url(#ar-b)" />
      <SpeedLines cx={400} cy={200} color="#fff" opacity={0.16} count={40} seed={21} />
      {/* The captains stay inside the middle 560px, so a narrower crop of the scene still shows both. */}
      <Aura cx={264} cy={230} r={110} color="#f0abfc" />
      <Aura cx={536} cy={230} r={110} color="#7dd3fc" />
      <g transform="translate(112 64) scale(0.74)">
        <Nova id="ar" />
      </g>
      <g transform="translate(392 60) scale(0.74)">
        <Pulse id="ar" />
      </g>
      {/* the slash between the two halves */}
      <path d={`M466 -10 L478 -10 L338 ${H + 10} L326 ${H + 10} Z`} fill="#fff" opacity={0.9} />
      <path d="M418 92 L372 196 L404 196 L386 298 L448 168 L412 168 L436 92 Z" fill="#fde047" stroke="#fff" strokeWidth={4} strokeLinejoin="round" />
      <text
        x={400}
        y={232}
        textAnchor="middle"
        fontSize={86}
        fontWeight={900}
        fontStyle="italic"
        fill="#fff"
        stroke="#1e1b4b"
        strokeWidth={6}
        paintOrder="stroke"
        style={{ fontFamily: "var(--font-display), sans-serif" }}
      >
        VS
      </text>
      <Sparkle x={300} y={60} s={12} color="#fde68a" twinkle />
      <Sparkle x={520} y={340} s={10} color="#fff" twinkle />
    </svg>
  );
}

/** Nova sings into her headset mic while sound rings roll out across the sky. */
export function VoiceScene({ className }: SceneProps) {
  const W = 800;
  const H = 400;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="Nova sings into her headset mic as rings of sound roll out across a pink sky">
      <defs>
        <SoftFilter />
      </defs>
      <Sky id="vs" w={W} h={H} colors={["#2e1065", "#a21caf", "#fb7185"]} seed={31} />
      <SpeedLines cx={250} cy={220} color="#fff" opacity={0.1} count={32} seed={3} />
      {[70, 130, 190, 250, 310].map((r, i) => (
        <circle key={r} cx={250} cy={230} r={r} fill="none" stroke={i % 2 ? "#a5f3fc" : "#fde68a"} strokeOpacity={0.7 - i * 0.12} strokeWidth={4} className="art-pulse" />
      ))}
      {Array.from({ length: 22 }, (_, i) => {
        const h = Math.round(18 + Math.abs(Math.sin(i * 1.7)) * 90);
        return <rect key={i} x={500 + i * 13} y={200 - h / 2} width={7} height={h} rx={3.5} fill="#fff" opacity={0.85} />;
      })}
      <text x={640} y={110} fontSize={48} fill="#fde68a" className="art-float">♪</text>
      <text x={720} y={300} fontSize={36} fill="#a5f3fc" className="art-float slow">♫</text>
      <Aura cx={250} cy={250} r={140} color="#fdf4ff" />
      <g transform="translate(90 40) scale(0.8)">
        <Nova id="vs" mood="sing" />
      </g>
      <Sparkle x={470} y={70} s={14} color="#fff" twinkle />
      <Sparkle x={60} y={80} s={10} color="#fde68a" />
    </svg>
  );
}

/** A captain still in the shadows behind a sealed gate. */
export function SoonScene({ className, hue = "#a78bfa" }: SceneProps & { hue?: string }) {
  const W = 800;
  const H = 400;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="A new challenger waits in the shadows">
      <Sky id="ss" w={W} h={H} colors={["#0b0d26", "#1e1b4b", "#312e81"]} seed={53} />
      <SpeedLines cx={400} cy={180} color={hue} opacity={0.12} count={30} seed={17} />
      <g transform="translate(200 40) scale(0.8)">
        <Mystery color={hue} />
      </g>
      <text
        x={560}
        y={210}
        textAnchor="middle"
        fontSize={120}
        fontWeight={900}
        fontStyle="italic"
        fill={hue}
        opacity={0.9}
        style={{ fontFamily: "var(--font-display), sans-serif" }}
        className="art-pulse"
      >
        ?
      </text>
      <Sparkle x={160} y={90} s={10} color={hue} twinkle />
      <Sparkle x={640} y={120} s={12} color="#fff" twinkle />
    </svg>
  );
}

export function VictoryScene({ className, color = "#c084fc" }: SceneProps & { color?: string }) {
  const W = 800;
  const H = 420;
  const next = rng(77);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="Nova and Pulse celebrate beside a blazing trophy">
      <defs>
        <SoftFilter />
      </defs>
      <Sky id="vc" w={W} h={H} colors={["#1e1b4b", "#6d28d9", "#f59e0b"]} seed={77} />
      {Array.from({ length: 18 }, (_, i) => {
        const a = (i / 18) * Math.PI * 2;
        return (
          <path key={i} d={`M400 170 L${polar(400, 170, a, 600)} L${polar(400, 170, a + 0.13, 600)} Z`} fill={i % 2 ? color : "#fde68a"} opacity={0.14} />
        );
      })}
      <circle cx={400} cy={170} r={120} fill="#fde68a" opacity={0.3} filter="url(#soft)" className="art-pulse" />
      <g transform="translate(-10 70) scale(0.72)">
        <Nova id="vc" />
      </g>
      <g transform="translate(522 66) scale(0.72)">
        <Pulse id="vc" />
      </g>
      {/* trophy */}
      <g className="art-float">
        <path d="M350 96 L450 96 L444 168 C440 200 420 214 400 214 C380 214 360 200 356 168 Z" fill="#fbbf24" stroke="#fff7d6" strokeWidth={3} />
        <path d="M362 104 L376 104 L372 180 C368 168 364 150 362 104 Z" fill="#fff7d6" opacity={0.7} />
        <path d="M350 110 C316 110 314 156 356 164 M450 110 C484 110 486 156 444 164" fill="none" stroke="#fbbf24" strokeWidth={9} />
        <rect x={390} y={212} width={20} height={36} fill="#d99a06" />
        <rect x={360} y={246} width={80} height={20} rx={5} fill="#fbbf24" />
        <path d="M400 124 l8 16 18 2 -13 12 4 18 -17 -9 -17 9 4 -18 -13 -12 18 -2 Z" fill="#fff7d6" />
      </g>
      {Array.from({ length: 30 }, (_, i) => {
        const x = next() * W;
        const y = next() * 300;
        return <rect key={i} x={x} y={y} width={8} height={15} rx={2} fill={["#f472b6", "#38bdf8", "#fde047", "#c084fc", "#4ade80"][i % 5]} transform={`rotate(${next() * 360} ${x} ${y})`} opacity={0.9} />;
      })}
      <Sparkle x={300} y={70} s={14} color="#fff" twinkle />
      <Sparkle x={510} y={60} s={10} color="#fff" twinkle />
    </svg>
  );
}

const SCENES: Record<ArtSlot, (props: SceneProps) => React.ReactElement> = {
  hero: NexusScene,
  brainClash: ArenaScene,
  whosTalking: VoiceScene,
  comingSoon: SoonScene,
  lobby: (p) => <ArenaScene {...p} label="Nova and Pulse wait in the arena for the match to start" />,
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

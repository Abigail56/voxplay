// Original VOXPLAY artwork, drawn as SVG: a few kilobytes each, sharp at any size, no licences needed.
// The look: an anime key visual. Cel-shaded mascots (components/art/Characters.tsx) in front of sunset
// skies, manga speed lines, sparkles and a glowing portal. Motion comes from CSS classes (art-float,
// art-spin, art-pulse, art-twinkle), which reduced-motion turns off.

import { ART, artSrc, CATEGORY_LOOK, categoryFile, type ArtSlot } from "@/lib/art";

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
        <g className="art-breathe late">
          <Pulse id="nx" />
        </g>
      </g>
      <g transform="translate(84 44) scale(1.1)">
        <g className="art-breathe">
          <Nova id="nx" />
        </g>
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
        <g className="art-breathe">
          <Nova id="ar" />
        </g>
      </g>
      <g transform="translate(392 60) scale(0.74)">
        <g className="art-breathe late">
          <Pulse id="ar" />
        </g>
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
        <g className="art-breathe">
          <Nova id="vs" mood="sing" />
        </g>
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

/** Beat Drop: Pulse hums in front of a spinning vinyl, with the club's equalizer pumping below. */
export function BeatDropScene({ className }: SceneProps) {
  const W = 800;
  const H = 400;
  const next = rng(61);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="Pulse hums a tune in front of a giant spinning vinyl record in a neon club">
      <defs>
        <SoftFilter />
        <radialGradient id="bd-vinyl">
          <stop offset="0" stopColor="#1f2937" />
          <stop offset="0.7" stopColor="#0b1120" />
          <stop offset="1" stopColor="#020617" />
        </radialGradient>
      </defs>
      <Sky id="bd" w={W} h={H} colors={["#0c0a3e", "#5b21b6", "#db2777"]} seed={61} />
      <SpeedLines cx={400} cy={190} color="#fff" opacity={0.1} count={40} seed={8} />
      {/* the record */}
      <g className="art-spin" style={{ transformOrigin: "400px 190px" }}>
        <circle cx={400} cy={190} r={180} fill="url(#bd-vinyl)" stroke="#a78bfa" strokeWidth={3} />
        {[150, 128, 106, 84].map((r) => (
          <circle key={r} cx={400} cy={190} r={r} fill="none" stroke="#334155" strokeWidth={1.5} />
        ))}
        <circle cx={400} cy={190} r={56} fill="#f472b6" />
        <path d="M360 170 A46 46 0 0 1 430 150" fill="none" stroke="#fde68a" strokeWidth={6} strokeLinecap="round" />
        <circle cx={400} cy={190} r={8} fill="#0b1120" />
      </g>
      <Aura cx={400} cy={240} r={130} color="#22d3ee" />
      {/* the equalizer */}
      {Array.from({ length: 40 }, (_, i) => {
        const h = Math.round(30 + next() * 110);
        return <rect key={i} x={i * 20 + 2} y={H - h} width={14} height={h} rx={3} fill={i % 3 ? "#22d3ee" : "#f472b6"} opacity={0.75} className={i % 4 ? undefined : "art-pulse"} />;
      })}
      <g transform="translate(244 56) scale(0.78)">
        <g className="art-breathe late">
          <Pulse id="bd" />
        </g>
      </g>
      {/* "hmm hmm" bubble and notes */}
      <g className="art-float">
        <path d="M530 70 h110 a16 16 0 0 1 16 16 v34 a16 16 0 0 1 -16 16 h-74 l-22 20 l4 -20 h-18 a16 16 0 0 1 -16 -16 v-34 a16 16 0 0 1 16 -16 Z" fill="#fff" />
        <text x={585} y={112} textAnchor="middle" fontSize={28} fontWeight={900} fontStyle="italic" fill="#1e1b4b" style={{ fontFamily: "var(--font-display), sans-serif" }}>
          hmm ♪
        </text>
      </g>
      <text x={150} y={110} fontSize={56} fill="#fde68a" className="art-float">
        ♪
      </text>
      <text x={210} y={250} fontSize={38} fill="#a5f3fc" className="art-float slow">
        ♫
      </text>
      <text x={660} y={260} fontSize={44} fill="#f9a8d4" className="art-float slow">
        ♬
      </text>
      <Sparkle x={120} y={60} s={12} color="#fff" twinkle />
      <Sparkle x={690} y={190} s={10} color="#fde68a" twinkle />
    </svg>
  );
}

/** Story Forge: Nova and a glowing spellbook under a fantasy moon, words drifting up like sparks. */
export function StoryForgeScene({ className }: SceneProps) {
  const W = 800;
  const H = 400;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="Nova stands beside a floating, glowing storybook under a huge moon">
      <defs>
        <SoftFilter />
        <radialGradient id="sf-moon">
          <stop offset="0" stopColor="#fff7ed" />
          <stop offset="0.7" stopColor="#fde68a" />
          <stop offset="1" stopColor="#f59e0b" />
        </radialGradient>
        <linearGradient id="sf-page" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fffbeb" />
          <stop offset="1" stopColor="#fde68a" />
        </linearGradient>
      </defs>
      <Sky id="sf" w={W} h={H} colors={["#020617", "#1e1b4b", "#7c2d12"]} seed={83} />
      <circle cx={560} cy={120} r={120} fill="#fde68a" opacity={0.25} filter="url(#soft)" />
      <circle cx={560} cy={120} r={78} fill="url(#sf-moon)" />
      <circle cx={530} cy={100} r={12} fill="#f59e0b" opacity={0.25} />
      <circle cx={585} cy={140} r={8} fill="#f59e0b" opacity={0.2} />
      {/* far mountains and a castle */}
      <path d="M0 300 L90 220 L160 270 L250 190 L340 280 L430 230 L520 290 L610 210 L700 270 L800 220 L800 400 L0 400 Z" fill="#1e1b4b" />
      <path d="M600 300 L600 230 L615 230 L615 215 L630 230 L640 200 L650 230 L665 215 L665 230 L680 230 L680 300 Z" fill="#0f0a2e" />
      <path d="M0 330 C140 300 260 340 400 320 C540 300 660 340 800 315 L800 400 L0 400 Z" fill="#0b0820" />
      <Aura cx={290} cy={250} r={130} color="#c084fc" />
      <g transform="translate(130 56) scale(0.76)">
        <g className="art-breathe">
          <Nova id="sf" />
        </g>
      </g>
      {/* the floating book */}
      <g className="art-float">
        <ellipse cx={540} cy={300} rx={90} ry={16} fill="#fde68a" opacity={0.35} filter="url(#soft)" />
        <path d="M460 250 Q500 230 540 248 L540 316 Q500 298 460 318 Z" fill="url(#sf-page)" stroke="#92400e" strokeWidth={2} />
        <path d="M620 250 Q580 230 540 248 L540 316 Q580 298 620 318 Z" fill="url(#sf-page)" stroke="#92400e" strokeWidth={2} />
        <path d="M472 262 Q500 250 528 260 M472 276 Q500 264 528 274 M472 290 Q500 278 528 288 M552 260 Q580 250 608 262 M552 274 Q580 264 608 276" stroke="#b45309" strokeWidth={2} opacity={0.6} fill="none" />
        <path d="M455 318 Q500 300 540 320 Q580 300 625 318 L625 326 Q580 308 540 328 Q500 308 455 326 Z" fill="#7c2d12" />
        {/* the quill */}
        <path d="M600 236 Q640 170 690 150 Q650 196 612 244 Z" fill="#f9a8d4" stroke="#be185d" strokeWidth={2} />
        <path d="M612 244 L598 262" stroke="#1e1b4b" strokeWidth={3} strokeLinecap="round" />
      </g>
      {/* words rising like sparks */}
      {["once", "upon", "a", "danfo", "legend"].map((w, i) => (
        <text
          key={w}
          x={470 - i * 14}
          y={225 - i * 32}
          fontSize={17 + i * 2}
          fontWeight={900}
          fontStyle="italic"
          fill={i % 2 ? "#fde68a" : "#f5d0fe"}
          stroke="#1e1b4b"
          strokeWidth={4}
          paintOrder="stroke"
          opacity={1 - i * 0.1}
          style={{ fontFamily: "var(--font-display), sans-serif" }}
          className="art-float slow"
        >
          {w}
        </text>
      ))}
      <Sparkle x={470} y={220} s={10} color="#fde68a" twinkle />
      <Sparkle x={640} y={300} s={8} color="#fff" twinkle />
      <Sparkle x={90} y={80} s={12} color="#f5d0fe" twinkle />
    </svg>
  );
}

/** The match is lost, not the war: dusk-blue light, both captains steady, a spark of the next fight. */
export function DefeatScene({ className }: SceneProps) {
  const W = 800;
  const H = 420;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} role="img" aria-label="Nova and Pulse, determined, ready for a rematch">
      <defs>
        <SoftFilter />
      </defs>
      <Sky id="df" w={W} h={H} colors={["#020617", "#1e3a8a", "#4c1d95"]} seed={91} />
      <SpeedLines cx={400} cy={210} color="#93c5fd" opacity={0.08} count={30} seed={4} />
      <Skyline y={360} w={W} color="#0b1033" seed={21} />
      <Aura cx={264} cy={240} r={110} color="#818cf8" />
      <Aura cx={536} cy={240} r={110} color="#38bdf8" />
      <g transform="translate(112 74) scale(0.72)">
        <Nova id="df" />
      </g>
      <g transform="translate(392 70) scale(0.72)">
        <Pulse id="df" />
      </g>
      <path d="M408 120 L380 190 L402 190 L390 250 L430 170 L406 170 L420 120 Z" fill="#93c5fd" opacity={0.8} className="art-pulse" />
      <Sparkle x={150} y={80} s={10} color="#bfdbfe" twinkle />
      <Sparkle x={660} y={110} s={8} color="#fff" twinkle />
    </svg>
  );
}

const MODE_LOOK: Record<string, { hue: string; glow: string; icon: string; extras: [string, string] }> = {
  "african-knowledge": { hue: "#7c3aed", glow: "#fbbf24", icon: "🌍", extras: ["📚", "💡"] },
  "music-challenge": { hue: "#db2777", glow: "#22d3ee", icon: "🎵", extras: ["🎤", "🎧"] },
  "culture-challenge": { hue: "#b45309", glow: "#f472b6", icon: "🥁", extras: ["👑", "🎭"] },
  "word-association": { hue: "#0e7490", glow: "#a78bfa", icon: "🔗", extras: ["💬", "🧠"] },
  riddles: { hue: "#4c1d95", glow: "#c084fc", icon: "🧩", extras: ["❓", "🔮"] },
  "quick-fire": { hue: "#be123c", glow: "#fde047", icon: "⚡", extras: ["⏱️", "🔥"] },
  "general-knowledge": { hue: "#1d4ed8", glow: "#67e8f9", icon: "💡", extras: ["📖", "🌐"] },
  "team-battle": { hue: "#6d28d9", glow: "#38bdf8", icon: "⚔️", extras: ["🛡️", "🏆"] },
  "name-it-fast": { hue: "#0f766e", glow: "#fde047", icon: "📝", extras: ["⏱️", "✅"] },
};

/** A tile's stand-in until its painting arrives: a coloured burst, the big symbol of what the tile is
 *  about, and two smaller related ones floating around it. */
function IconScene({ className, id, hue, glow, icon, extras }: SceneProps & { id: string; hue: string; glow: string; icon: string; extras: [string, string] }) {
  const W = 600;
  const H = 400;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} aria-hidden>
      <defs>
        <radialGradient id={`ic-${id}`} cx="0.5" cy="0.45" r="0.75">
          <stop offset="0" stopColor={glow} stopOpacity="0.6" />
          <stop offset="0.42" stopColor={hue} />
          <stop offset="1" stopColor="#0a0819" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#ic-${id})`} />
      <SpeedLines cx={300} cy={185} color="#fff" opacity={0.14} count={32} seed={id.length * 7} />
      <circle cx={300} cy={185} r={92} fill="#fff" opacity={0.1} />
      <circle cx={300} cy={185} r={92} fill="none" stroke={glow} strokeWidth={3} opacity={0.6} strokeDasharray="10 8" className="art-spin" style={{ transformOrigin: "300px 185px" }} />
      <text x={300} y={226} textAnchor="middle" fontSize={120} className="art-float">
        {icon}
      </text>
      <text x={150} y={135} textAnchor="middle" fontSize={54} className="art-float slow" opacity={0.95}>
        {extras[0]}
      </text>
      <text x={460} y={290} textAnchor="middle" fontSize={54} className="art-float slow" opacity={0.95}>
        {extras[1]}
      </text>
      <Sparkle x={110} y={300} s={10} color="#fff" twinkle />
      <Sparkle x={500} y={80} s={12} color={glow} twinkle />
    </svg>
  );
}

export function ModeScene({ className, mode }: SceneProps & { mode: string }) {
  const look = MODE_LOOK[mode] ?? MODE_LOOK["general-knowledge"];
  return <IconScene className={className} id={`m-${mode}`} {...look} />;
}

/** A category's picture: its painting once categories/<id>.webp exists, otherwise its icon scene. */
export function CategoryArt({ id, className }: { id: string; className?: string }) {
  const look = CATEGORY_LOOK[id];
  const src = artSrc(categoryFile(id));
  if (src) return <img src={src} alt={look?.alt ?? ""} className={className} loading="lazy" decoding="async" style={{ objectPosition: "50% 35%" }} />;
  if (!look) return <ModeScene className={className} mode="general-knowledge" />;
  return <IconScene className={className} id={`c-${id}`} hue={look.hue} glow={look.glow} icon={look.icon} extras={look.extras} />;
}

const SCENES: Partial<Record<ArtSlot, (props: SceneProps) => React.ReactElement>> = {
  hero: NexusScene,
  brainClash: ArenaScene,
  whosTalking: VoiceScene,
  beatDrop: BeatDropScene,
  storyForge: StoryForgeScene,
  wordBomb: (p) => <IconScene {...p} id="word-bomb" hue="#c2410c" glow="#fde047" icon="💣" extras={["🔤", "💥"]} />,
  comingSoon: SoonScene,
  lobby: (p) => <ArenaScene {...p} label="Nova and Pulse wait in the arena for the match to start" />,
  victory: VictoryScene,
  defeat: DefeatScene,
  empty: SoonScene,
};

/** One artwork slot: its image when the file exists (lib/art.ts), otherwise its drawn SVG scene.
 *  `priority` loads it straight away (the hero); everything else loads lazily. */
export function Art({ slot, className, priority }: { slot: ArtSlot; className?: string; priority?: boolean }) {
  const meta = ART[slot];
  const src = artSrc(meta.file);
  if (src) {
    const mobile = artSrc(meta.mobile);
    return (
      <picture className={className}>
        {mobile && <source media="(max-width: 640px)" srcSet={mobile} />}
        <img
          src={src}
          alt={meta.alt}
          className="art-img"
          style={{ objectPosition: meta.position }}
          loading={priority ? "eager" : "lazy"}
          fetchPriority={priority ? "high" : "auto"}
          decoding="async"
        />
      </picture>
    );
  }
  if (slot.startsWith("mode-")) return <ModeScene className={className} mode={slot.slice(5)} />;
  const Scene = SCENES[slot] ?? SoonScene;
  return <Scene className={className} />;
}

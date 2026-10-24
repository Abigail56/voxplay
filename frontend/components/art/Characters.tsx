// VOXPLAY's original mascots, the two Brain Clash captains, drawn as cel-shaded anime busts.
// Each one draws into a 400 x 480 box (head at the top, shoulders running off the bottom), so a scene
// places them with a transform. `id` prefixes their gradients so several can share one page.
//
// The shading follows one light from the upper left: a lit skin gradient, a soft shadow cast by the
// fringe, a cooler rim light on the right edge, and line art a shade darker than the skin.

type CharacterProps = { id: string; mood?: "smile" | "sing" };

const NOVA_FACE = "M132 168 C132 118 166 96 200 96 C234 96 268 118 268 168 C268 214 254 250 232 274 C220 288 210 298 200 300 C190 298 180 288 168 274 C146 250 132 214 132 168 Z";
const PULSE_FACE = "M136 170 C136 120 168 100 200 100 C232 100 264 120 264 170 C264 214 256 246 238 268 C224 284 212 292 200 294 C188 292 176 284 162 268 C144 246 136 214 136 170 Z";

/** One big anime eye: white, a ringed gradient iris with streaks, two highlights, lid shadow, lashes. */
function Eye({ id, side, cx, cy, shape, iris, lash, crease, small }: { id: string; side: "L" | "R"; cx: number; cy: number; shape: string; iris: string; lash: string; crease: string; small?: boolean }) {
  const rx = small ? 13 : 15;
  const ry = small ? 16 : 19;
  return (
    <g>
      <clipPath id={`${id}-eye${side}`}>
        <path d={shape} />
      </clipPath>
      <path d={shape} fill="#fdfbff" />
      <g clipPath={`url(#${id}-eye${side})`}>
        <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill={iris} />
        <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="none" stroke="#12061f" strokeWidth={2} opacity={0.7} />
        {[-50, -20, 10, 40, 140, 170, 200, 230].map((a) => {
          // Rounded: Math.cos can differ in the last digit between the server and the browser.
          const at = (k: number) => {
            const r = (a * Math.PI) / 180;
            return `${Math.round((cx + Math.cos(r) * rx * k) * 10) / 10} ${Math.round((cy + Math.sin(r) * ry * k) * 10) / 10}`;
          };
          return <path key={a} d={`M${at(0.45)} L${at(0.85)}`} stroke="#fff" strokeWidth={1} opacity={0.25} />;
        })}
        <ellipse cx={cx} cy={cy + 1} rx={rx * 0.45} ry={ry * 0.52} fill="#10041f" />
        <path d={`M${cx - 30} ${cy - ry - 4} L${cx + 30} ${cy - ry - 4} L${cx + 30} ${cy - ry * 0.35} Q${cx} ${cy - ry * 0.85} ${cx - 30} ${cy - ry * 0.3} Z`} fill="#1a0b2e" opacity={0.4} />
        <circle cx={cx - 6} cy={cy - 8} r={small ? 4 : 5.2} fill="#fff" />
        <circle cx={cx + 6} cy={cy + 8} r={2.2} fill="#fff" opacity={0.9} />
        <ellipse cx={cx} cy={cy + ry * 0.7} rx={rx * 0.7} ry={3} fill="#fff" opacity={0.25} />
      </g>
      <path d={crease} fill="none" stroke="#3b1d10" strokeWidth={1.6} strokeLinecap="round" opacity={0.6} />
      <path d={lash} fill="none" stroke="#14081f" strokeWidth={small ? 5.5 : 6} strokeLinecap="round" />
    </g>
  );
}

/** Nova: violet box braids in a high bun, headphones, gold hoops, a cropped jacket. Team A's captain. */
export function Nova({ id, mood = "smile" }: CharacterProps) {
  const p = (name: string) => `${id}-nova-${name}`;
  const braid = (x0: number, x1: number) =>
    Array.from({ length: 10 }, (_, i) => {
      const y = 196 + i * 25;
      const x = x0 + ((x1 - x0) * i) / 9;
      return (
        <g key={i}>
          <ellipse cx={x} cy={y} rx={17} ry={15} fill={`url(#${p("braid")})`} stroke="#2e1065" strokeWidth={1.6} />
          <path d={`M${x - 10} ${y - 6} Q${x} ${y - 12} ${x + 8} ${y - 4}`} fill="none" stroke="#e9d5ff" strokeWidth={1.6} opacity={0.55} />
        </g>
      );
    });
  return (
    <g>
      <defs>
        <linearGradient id={p("hair")} x1="0" y1="0" x2="0.4" y2="1">
          <stop offset="0" stopColor="#d8c4ff" />
          <stop offset="0.35" stopColor="#9b6bff" />
          <stop offset="0.7" stopColor="#6d28d9" />
          <stop offset="1" stopColor="#3b0f80" />
        </linearGradient>
        <linearGradient id={p("braid")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#4c1d95" />
        </linearGradient>
        <radialGradient id={p("skin")} cx="0.38" cy="0.32" r="0.8">
          <stop offset="0" stopColor="#a8714b" />
          <stop offset="0.55" stopColor="#8a5636" />
          <stop offset="1" stopColor="#6b3c22" />
        </radialGradient>
        <linearGradient id={p("iris")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#24094f" />
          <stop offset="0.5" stopColor="#8b5cf6" />
          <stop offset="0.85" stopColor="#e879f9" />
          <stop offset="1" stopColor="#fbcfe8" />
        </linearGradient>
        <linearGradient id={p("jacket")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2a2470" />
          <stop offset="0.6" stopColor="#1e1b4b" />
          <stop offset="1" stopColor="#151238" />
        </linearGradient>
        <linearGradient id={p("neck")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#5c3520" />
          <stop offset="0.45" stopColor="#7a4a2e" />
          <stop offset="1" stopColor="#85532f" />
        </linearGradient>
        <clipPath id={p("face")}>
          <path d={NOVA_FACE} />
        </clipPath>
      </defs>

      {/* box braids falling behind the shoulders */}
      <g>{braid(132, 122)}</g>
      <g>{braid(268, 278)}</g>

      {/* cropped jacket over a pink top, with folds and a zip */}
      <path d="M70 520 C74 384 110 346 160 334 L240 334 C290 346 326 384 330 520 Z" fill={`url(#${p("jacket")})`} />
      <path d="M168 334 L200 394 L232 334 Z" fill="#f472b6" />
      <path d="M178 334 L200 376 L222 334" fill="none" stroke="#fbcfe8" strokeWidth={2} opacity={0.6} />
      <path d="M160 334 L200 404 L176 520 L140 520 C150 414 150 374 160 334 Z" fill="#3730a3" />
      <path d="M240 334 L200 404 L224 520 L260 520 C250 414 250 374 240 334 Z" fill="#312e81" />
      <path d="M160 334 L200 404 M240 334 L200 404" stroke="#818cf8" strokeWidth={2} opacity={0.7} />
      <g fill="none" stroke="#0f0c2e" strokeWidth={2.5} strokeLinecap="round" opacity={0.55}>
        <path d="M100 430 C112 416 126 412 138 416" />
        <path d="M300 430 C288 416 274 412 262 416" />
        <path d="M92 470 C104 462 118 460 128 464" />
      </g>
      <path d="M112 388 L150 382 M288 388 L250 382" stroke="#38bdf8" strokeWidth={3} strokeLinecap="round" />
      <path d="M200 404 L200 520" stroke="#94a3b8" strokeWidth={2} strokeDasharray="3 3" opacity={0.6} />
      <circle cx={276} cy={414} r={9} fill="#38bdf8" />
      <path d="M272 414 l3 3 6 -7" stroke="#0b0d26" strokeWidth={2} fill="none" />

      {/* neck in shadow under the chin, collarbones */}
      <path d="M178 264 L222 264 L226 336 L174 336 Z" fill={`url(#${p("neck")})`} />
      <path d="M172 336 Q186 344 196 338 M228 336 Q214 344 204 338" fill="none" stroke="#5c3520" strokeWidth={1.8} opacity={0.6} />

      {/* face: lit gradient, side shadow, cast shadow from the fringe, rim light, line art */}
      <path d={NOVA_FACE} fill={`url(#${p("skin")})`} />
      <g clipPath={`url(#${p("face")})`}>
        <path d="M132 168 C132 210 146 248 168 274 C180 288 190 298 200 300 C176 280 156 240 150 190 Z" fill="#5c3320" opacity={0.45} />
        <path d="M126 168 L140 190 L154 152 L166 186 L180 146 L194 182 L210 144 L226 184 L240 150 L252 190 L266 162 L276 190 L276 120 L126 120 Z" fill="#3d1d0e" opacity={0.35} />
        <path d="M262 168 C262 214 250 248 228 274" fill="none" stroke="#f0abfc" strokeWidth={3} opacity={0.4} />
      </g>
      <path d={NOVA_FACE} fill="none" stroke="#3d2014" strokeWidth={2.2} />
      <ellipse cx={156} cy={238} rx={17} ry={8} fill="#f472b6" opacity={0.32} />
      <ellipse cx={244} cy={238} rx={17} ry={8} fill="#f472b6" opacity={0.32} />
      <path d="M150 236 l4 -4 M158 238 l4 -4 M240 236 l4 -4 M248 238 l4 -4" stroke="#fbcfe8" strokeWidth={1.4} opacity={0.6} />

      <Eye
        id={p("e")}
        side="L"
        cx={164}
        cy={204}
        shape="M138 196 Q160 180 186 188 Q186 214 164 222 Q142 216 138 196 Z"
        iris={`url(#${p("iris")})`}
        lash="M134 198 Q156 176 190 186 M134 198 L125 191 M140 190 L131 181"
        crease="M140 184 Q160 170 186 177"
      />
      <Eye
        id={p("e")}
        side="R"
        cx={236}
        cy={204}
        shape="M262 196 Q240 180 214 188 Q214 214 236 222 Q258 216 262 196 Z"
        iris={`url(#${p("iris")})`}
        lash="M266 198 Q244 176 210 186 M266 198 L275 191 M260 190 L269 181"
        crease="M260 184 Q240 170 214 177"
      />
      <path d="M150 221 Q164 227 180 219 M220 219 Q236 227 250 221" fill="none" stroke="#3b1d10" strokeWidth={2} strokeLinecap="round" />
      {/* tapered brows */}
      <path d="M140 170 Q160 154 186 162 Q162 160 142 173 Z M260 170 Q240 154 214 162 Q238 160 258 173 Z" fill="#2e1065" />

      {/* nose: bridge light, tip, nostril */}
      <path d="M199 212 L201 234" stroke="#c98d62" strokeWidth={2.2} strokeLinecap="round" opacity={0.55} />
      <circle cx={203} cy={238} r={3} fill="#c98d62" opacity={0.5} />
      <path d="M193 244 Q197 248 202 246 M206 245 Q208 243 207 241" fill="none" stroke="#4a2613" strokeWidth={2} strokeLinecap="round" />

      {/* mouth */}
      {mood === "sing" ? (
        <>
          <ellipse cx={200} cy={268} rx={15} ry={13} fill="#4a1525" />
          <path d="M187 262 Q200 258 213 262 L211 265 Q200 262 189 265 Z" fill="#fff" />
          <path d="M190 276 Q200 270 210 276 Q206 282 200 282 Q194 282 190 276 Z" fill="#f472b6" />
          <path d="M184 266 Q186 252 200 253 Q214 252 216 266" fill="none" stroke="#8b3a4a" strokeWidth={3} strokeLinecap="round" />
        </>
      ) : (
        <>
          <path d="M180 262 Q190 255 200 259 Q210 255 220 262 Q200 266 180 262 Z" fill="#7a3340" />
          <path d="M182 263 Q200 281 218 263 Q200 269 182 263 Z" fill="#9c4a57" />
          <path d="M182 263 Q200 268 218 263" fill="none" stroke="#3f1520" strokeWidth={2} strokeLinecap="round" />
          <ellipse cx={205} cy={271} rx={5} ry={1.8} fill="#fbcfe8" opacity={0.8} />
        </>
      )}

      {/* fringe in strands, side locks, strand lines, shine */}
      <path
        d="M126 182 C112 104 156 60 204 60 C254 60 292 104 276 184 L264 150 L252 176 L240 138 L226 170 L210 132 L194 168 L180 134 L166 172 L154 140 L140 180 L132 160 Z"
        fill={`url(#${p("hair")})`}
        stroke="#2e1065"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      <path d="M210 132 L204 160 L194 168 Z M240 138 L236 160 L226 170 Z M180 134 L176 158 L166 172 Z M154 140 L150 160 L140 180 Z" fill="#4c1d95" opacity={0.5} />
      <g fill="none" strokeLinecap="round">
        <path d="M150 96 Q168 118 166 160 M176 76 Q190 104 186 150 M214 70 Q216 104 206 140 M246 86 Q252 112 244 146 M266 112 Q272 140 262 168" stroke="#efe7ff" strokeWidth={1.5} opacity={0.55} />
        <path d="M162 84 Q178 112 176 150 M232 74 Q238 104 228 150 M140 120 Q146 146 146 176" stroke="#3b0764" strokeWidth={1.4} opacity={0.5} />
      </g>
      <path d="M124 176 C118 220 126 262 140 290 L150 220 C146 200 146 186 152 170 Z" fill="#6d28d9" stroke="#2e1065" strokeWidth={1.6} />
      <path d="M278 180 C284 222 276 262 262 290 L252 220 C256 200 256 186 248 170 Z" fill="#5b21b6" stroke="#2e1065" strokeWidth={1.6} />
      <path d="M160 92 C176 82 200 80 222 86 C204 90 186 96 172 108 Z" fill="#f5f0ff" opacity={0.85} />
      <path d="M232 96 C242 100 250 106 256 116" fill="none" stroke="#f5f0ff" strokeWidth={3} strokeLinecap="round" opacity={0.6} />

      {/* high bun with a pink band */}
      <circle cx={200} cy={58} r={26} fill={`url(#${p("hair")})`} stroke="#2e1065" strokeWidth={2} />
      <path d="M180 50 C190 38 210 38 220 50 M184 62 C194 54 208 54 216 62" fill="none" stroke="#efe7ff" strokeWidth={2.2} opacity={0.6} />
      <path d="M176 72 L224 72" stroke="#be185d" strokeWidth={8} strokeLinecap="round" />
      <path d="M180 70 L220 70" stroke="#f9a8d4" strokeWidth={2} strokeLinecap="round" />

      {/* gold hoops */}
      <circle cx={130} cy={232} r={10} fill="none" stroke="#fbbf24" strokeWidth={3.5} />
      <circle cx={270} cy={232} r={10} fill="none" stroke="#f59e0b" strokeWidth={3.5} />

      {/* headphones */}
      <path d="M120 176 C110 90 290 90 280 176" fill="none" stroke="#0f172a" strokeWidth={11} />
      <path d="M120 176 C110 90 290 90 280 176" fill="none" stroke="#38bdf8" strokeWidth={3} />
      <path d="M140 116 C170 92 230 92 260 116" fill="none" stroke="#e0f2fe" strokeWidth={1.5} opacity={0.7} />
      <rect x={102} y={164} width={32} height={50} rx={13} fill="#0f172a" stroke="#334155" strokeWidth={2} />
      <rect x={107} y={171} width={8} height={36} rx={4} fill="#f472b6" />
      <rect x={266} y={164} width={32} height={50} rx={13} fill="#0f172a" stroke="#334155" strokeWidth={2} />
      <rect x={285} y={171} width={8} height={36} rx={4} fill="#38bdf8" />
      {mood === "sing" && (
        <>
          <path d="M120 208 C124 250 150 272 176 274" fill="none" stroke="#0f172a" strokeWidth={5} strokeLinecap="round" />
          <rect x={168} y={265} width={18} height={13} rx={6} fill="#38bdf8" stroke="#0c4a6e" strokeWidth={1.5} />
        </>
      )}
    </g>
  );
}

/** Pulse: spiky cyan hair under a pink headband, a lightning hoodie, a plaster on the cheek. Team B's captain. */
export function Pulse({ id }: { id: string }) {
  const p = (name: string) => `${id}-pulse-${name}`;
  return (
    <g>
      <defs>
        <linearGradient id={p("hair")} x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stopColor="#a5f3fc" />
          <stop offset="0.3" stopColor="#22d3ee" />
          <stop offset="0.65" stopColor="#0284c7" />
          <stop offset="1" stopColor="#1e3a8a" />
        </linearGradient>
        <radialGradient id={p("skin")} cx="0.38" cy="0.3" r="0.8">
          <stop offset="0" stopColor="#9a6440" />
          <stop offset="0.55" stopColor="#7a4a2b" />
          <stop offset="1" stopColor="#5c351d" />
        </radialGradient>
        <linearGradient id={p("iris")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#062a40" />
          <stop offset="0.5" stopColor="#0ea5e9" />
          <stop offset="0.85" stopColor="#67e8f9" />
          <stop offset="1" stopColor="#cffafe" />
        </linearGradient>
        <linearGradient id={p("hood")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1e293b" />
          <stop offset="0.6" stopColor="#0f172a" />
          <stop offset="1" stopColor="#0b1120" />
        </linearGradient>
        <linearGradient id={p("neck")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#4e2c18" />
          <stop offset="0.45" stopColor="#6b3f24" />
          <stop offset="1" stopColor="#744528" />
        </linearGradient>
        <clipPath id={p("face")}>
          <path d={PULSE_FACE} />
        </clipPath>
      </defs>

      {/* hoodie with folds, drawstrings and a lightning bolt */}
      <path d="M60 520 C64 404 104 350 160 334 L240 334 C296 350 336 404 340 520 Z" fill={`url(#${p("hood")})`} />
      <path d="M150 334 C150 376 250 376 250 334 L240 334 C232 356 168 356 160 334 Z" fill="#334155" />
      <path d="M156 336 C160 366 240 366 244 336" fill="none" stroke="#64748b" strokeWidth={2} opacity={0.7} />
      <g fill="none" stroke="#020617" strokeWidth={2.5} strokeLinecap="round" opacity={0.7}>
        <path d="M96 440 C110 424 126 420 140 424" />
        <path d="M304 440 C290 424 274 420 260 424" />
        <path d="M86 486 C100 476 116 474 128 478" />
        <path d="M150 470 L250 470" opacity={0.5} />
      </g>
      <path d="M100 410 C108 400 118 396 128 398" fill="none" stroke="#475569" strokeWidth={2} opacity={0.6} />
      <path d="M176 360 L172 420 M224 360 L228 420" stroke="#38bdf8" strokeWidth={3} strokeLinecap="round" />
      <rect x={168} y={420} width={8} height={10} rx={2} fill="#e0f2fe" />
      <rect x={224} y={420} width={8} height={10} rx={2} fill="#e0f2fe" />
      <path d="M206 384 L186 424 L202 424 L194 456 L222 412 L206 412 L216 384 Z" fill="#fde047" stroke="#fef9c3" strokeWidth={1.5} strokeLinejoin="round" />
      <path d="M206 388 L192 418" stroke="#fff" strokeWidth={2} opacity={0.6} strokeLinecap="round" />

      {/* neck and ears */}
      <path d="M178 276 L222 276 L226 340 L174 340 Z" fill={`url(#${p("neck")})`} />
      <ellipse cx={134} cy={210} rx={11} ry={17} fill="#6b3f24" stroke="#3b1f10" strokeWidth={1.8} />
      <path d="M134 200 Q128 210 134 220" fill="none" stroke="#4e2c18" strokeWidth={2} />
      <ellipse cx={266} cy={210} rx={11} ry={17} fill="#7a4a2b" stroke="#3b1f10" strokeWidth={1.8} />
      <path d="M266 200 Q272 210 266 220" fill="none" stroke="#4e2c18" strokeWidth={2} />
      <circle cx={268} cy={224} r={3.5} fill="#e0f2fe" stroke="#38bdf8" strokeWidth={1.5} />

      {/* face: a stronger jaw, lit gradient, side shadow, fringe shadow, rim light, line art */}
      <path d={PULSE_FACE} fill={`url(#${p("skin")})`} />
      <g clipPath={`url(#${p("face")})`}>
        <path d="M136 170 C136 214 144 246 162 268 C176 284 188 292 200 294 C178 274 158 236 154 192 Z" fill="#46260f" opacity={0.45} />
        <path d="M130 160 C170 150 230 150 270 160 L270 120 L130 120 Z" fill="#2b1409" opacity={0.35} />
        <path d="M258 170 C258 214 250 244 232 266" fill="none" stroke="#67e8f9" strokeWidth={3} opacity={0.35} />
      </g>
      <path d={PULSE_FACE} fill="none" stroke="#33190b" strokeWidth={2.2} />

      <Eye
        id={p("e")}
        side="L"
        cx={168}
        cy={206}
        small
        shape="M140 202 Q162 188 188 194 Q186 214 166 220 Q146 216 140 202 Z"
        iris={`url(#${p("iris")})`}
        lash="M136 204 Q158 184 192 192"
        crease="M142 190 Q162 180 188 184"
      />
      <Eye
        id={p("e")}
        side="R"
        cx={232}
        cy={206}
        small
        shape="M260 202 Q238 188 212 194 Q214 214 234 220 Q254 216 260 202 Z"
        iris={`url(#${p("iris")})`}
        lash="M264 204 Q242 184 208 192"
        crease="M258 190 Q238 180 212 184"
      />
      <path d="M150 220 Q166 226 182 219 M218 219 Q234 226 250 220" fill="none" stroke="#33190b" strokeWidth={1.8} strokeLinecap="round" opacity={0.8} />
      {/* thick, determined brows */}
      <path d="M138 180 L186 178 L188 186 L140 186 Z M262 180 L214 178 L212 186 L260 186 Z" fill="#0b1220" />

      {/* nose, a big grin, a plaster on the cheek */}
      <path d="M199 214 L201 232" stroke="#b07a52" strokeWidth={2.2} strokeLinecap="round" opacity={0.55} />
      <circle cx={203} cy={236} r={3} fill="#b07a52" opacity={0.5} />
      <path d="M192 241 Q196 245 202 243 M206 242 Q208 240 207 238" fill="none" stroke="#3b1f10" strokeWidth={2} strokeLinecap="round" />
      <path d="M172 254 Q200 262 230 250 Q222 278 200 280 Q178 278 172 254 Z" fill="#3b0d1a" stroke="#260710" strokeWidth={1.8} strokeLinejoin="round" />
      <path d="M174 256 Q200 263 228 252 L226 260 Q200 268 176 262 Z" fill="#fff" />
      <path d="M186 258 L186 264 M200 259 L200 266 M214 257 L214 263" stroke="#cbd5e1" strokeWidth={1} />
      <path d="M186 274 Q200 282 214 274" fill="none" stroke="#f472b6" strokeWidth={3} strokeLinecap="round" />
      <g transform="rotate(-18 242 238)">
        <rect x={228} y={232} width={30} height={12} rx={4} fill="#fef3c7" stroke="#d6b77a" strokeWidth={1} />
        <path d="M238 236 v4 M243 236 v4 M248 236 v4" stroke="#d6b77a" strokeWidth={1.5} />
      </g>

      {/* spiky hair swept up, with light and shadow facets and strand lines */}
      <path
        d="M128 186 C120 150 126 120 140 102 L110 92 L146 80 L124 46 L168 64 L170 22 L198 58 L222 14 L232 58 L270 30 L262 72 L304 64 L272 100 L298 116 L266 122 C276 140 276 164 270 188 L262 156 L250 168 L246 138 L228 158 L222 130 L204 150 L196 124 L178 150 L172 128 L156 156 L150 134 L138 168 Z"
        fill={`url(#${p("hair")})`}
        stroke="#0c2a5a"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      <path d="M168 64 L186 96 L198 58 Z M222 14 L222 84 L232 58 Z M270 30 L246 90 L262 72 Z M124 46 L156 92 L146 80 Z M304 64 L262 100 L272 100 Z" fill="#ecfeff" opacity={0.6} />
      <path d="M196 124 L200 146 L204 150 Z M222 130 L226 152 L228 158 Z M172 128 L174 146 L178 150 Z M246 138 L248 160 L250 168 Z" fill="#1e3a8a" opacity={0.6} />
      <g fill="none" strokeLinecap="round">
        <path d="M150 110 Q170 96 190 104 M200 88 Q220 80 240 92 M160 130 Q182 120 200 126" stroke="#ecfeff" strokeWidth={1.5} opacity={0.5} />
        <path d="M176 70 L190 110 M226 40 L222 96 M260 50 L244 100" stroke="#0c4a6e" strokeWidth={1.4} opacity={0.45} />
      </g>

      {/* headband with tails in the wind */}
      <path d="M132 150 C168 128 232 128 270 150 L268 164 C232 142 168 142 134 164 Z" fill="#ec4899" stroke="#9d174d" strokeWidth={1.6} />
      <path d="M140 150 C172 134 228 134 262 150" fill="none" stroke="#fbcfe8" strokeWidth={2} opacity={0.7} />
      <path d="M270 152 L306 140 L298 160 L320 168 L284 168 Z" fill="#ec4899" stroke="#9d174d" strokeWidth={1.6} strokeLinejoin="round" />
    </g>
  );
}

/** A captain still in the shadows, for games that are coming soon. */
export function Mystery({ color }: { color: string }) {
  return (
    <g>
      <path d="M70 520 C74 390 112 346 160 334 L240 334 C288 346 326 390 330 520 Z" fill="#0b0d20" stroke={color} strokeWidth={3} />
      <path d="M178 270 L222 270 L226 340 L174 340 Z" fill="#0b0d20" />
      <path d={NOVA_FACE} fill="#0b0d20" stroke={color} strokeWidth={3} />
      <path d="M124 180 C110 100 156 56 204 56 C256 56 294 100 278 184 L262 146 L246 172 L232 132 L214 164 L196 128 L178 166 L162 134 L146 176 Z" fill="#12153a" stroke={color} strokeWidth={3} strokeLinejoin="round" />
      <path d="M150 200 L186 206 M250 200 L214 206" stroke={color} strokeWidth={6} strokeLinecap="round" />
    </g>
  );
}

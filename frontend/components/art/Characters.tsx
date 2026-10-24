// VOXPLAY's original mascots, the two Brain Clash captains, drawn as cel-shaded anime busts.
// Each one draws into a 400 x 480 box (head at the top, shoulders running off the bottom), so a scene
// places them with a transform. `id` prefixes their gradients so several can share one page.

type CharacterProps = { id: string; mood?: "smile" | "sing" };

/** Nova: violet braids in a high bun, headphones, a cropped jacket. Team A's captain. */
export function Nova({ id, mood = "smile" }: CharacterProps) {
  const p = (name: string) => `${id}-nova-${name}`;
  return (
    <g>
      <defs>
        <linearGradient id={p("hair")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#c4a8ff" />
          <stop offset="0.55" stopColor="#7c3aed" />
          <stop offset="1" stopColor="#4c1d95" />
        </linearGradient>
        <linearGradient id={p("iris")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2b0f5c" />
          <stop offset="0.55" stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#f0abfc" />
        </linearGradient>
        <linearGradient id={p("jacket")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1e1b4b" />
          <stop offset="1" stopColor="#312e81" />
        </linearGradient>
        <clipPath id={p("eyeL")}>
          <path d="M138 196 Q160 180 186 188 Q186 214 164 222 Q142 216 138 196 Z" />
        </clipPath>
        <clipPath id={p("eyeR")}>
          <path d="M262 196 Q240 180 214 188 Q214 214 236 222 Q258 216 262 196 Z" />
        </clipPath>
      </defs>

      {/* long braids behind the shoulders */}
      <path d="M120 150 C96 230 96 330 112 440 L150 440 C140 340 138 250 150 180 Z" fill="#4c1d95" />
      <path d="M280 150 C304 230 304 330 288 440 L250 440 C260 340 262 250 250 180 Z" fill="#4c1d95" />
      <path
        d="M108 220 L146 214 M104 260 L142 256 M104 300 L142 298 M106 340 L144 340 M108 380 L146 382 M292 220 L254 214 M296 260 L258 256 M296 300 L258 298 M294 340 L256 340 M292 380 L254 382"
        stroke="#2e1065"
        strokeWidth={2}
        opacity={0.7}
      />

      {/* cropped jacket over a pink top */}
      <path d="M70 520 C74 384 110 346 160 334 L240 334 C290 346 326 384 330 520 Z" fill={`url(#${p("jacket")})`} />
      <path d="M168 334 L200 394 L232 334 Z" fill="#f472b6" />
      <path d="M160 334 L200 404 L176 520 L140 520 C150 414 150 374 160 334 Z" fill="#3730a3" />
      <path d="M240 334 L200 404 L224 520 L260 520 C250 414 250 374 240 334 Z" fill="#3730a3" />
      <path d="M112 388 L150 382 M288 388 L250 382" stroke="#38bdf8" strokeWidth={3} strokeLinecap="round" />
      <circle cx={276} cy={414} r={9} fill="#38bdf8" />
      <path d="M272 414 l3 3 6 -7" stroke="#0b0d26" strokeWidth={2} fill="none" />

      {/* neck */}
      <path d="M178 264 L222 264 L226 336 L174 336 Z" fill="#7a4a2e" />
      <path d="M178 274 C190 290 210 290 222 274 L222 296 C210 306 190 306 178 296 Z" fill="#5c3520" />

      {/* face with a cel-shaded side */}
      <path d="M132 168 C132 118 166 96 200 96 C234 96 268 118 268 168 C268 214 254 250 232 274 C220 288 210 298 200 300 C190 298 180 288 168 274 C146 250 132 214 132 168 Z" fill="#8a5636" />
      <path d="M132 168 C132 210 146 248 168 274 C180 288 190 298 200 300 C176 280 156 240 150 190 Z" fill="#74452a" opacity={0.6} />
      <ellipse cx={156} cy={238} rx={16} ry={8} fill="#f472b6" opacity={0.35} />
      <ellipse cx={244} cy={238} rx={16} ry={8} fill="#f472b6" opacity={0.35} />

      {/* big anime eyes */}
      <path d="M138 196 Q160 180 186 188 Q186 214 164 222 Q142 216 138 196 Z" fill="#fff" />
      <g clipPath={`url(#${p("eyeL")})`}>
        <ellipse cx={164} cy={204} rx={15} ry={19} fill={`url(#${p("iris")})`} />
        <ellipse cx={164} cy={204} rx={7} ry={10} fill="#1a0838" />
        <circle cx={158} cy={196} r={5} fill="#fff" />
        <circle cx={170} cy={212} r={2.2} fill="#fff" />
        <path d="M138 186 L190 186 L190 196 Q164 186 138 198 Z" fill="#2e1065" opacity={0.35} />
      </g>
      <path d="M262 196 Q240 180 214 188 Q214 214 236 222 Q258 216 262 196 Z" fill="#fff" />
      <g clipPath={`url(#${p("eyeR")})`}>
        <ellipse cx={236} cy={204} rx={15} ry={19} fill={`url(#${p("iris")})`} />
        <ellipse cx={236} cy={204} rx={7} ry={10} fill="#1a0838" />
        <circle cx={230} cy={196} r={5} fill="#fff" />
        <circle cx={242} cy={212} r={2.2} fill="#fff" />
        <path d="M262 186 L210 186 L210 196 Q236 186 262 198 Z" fill="#2e1065" opacity={0.35} />
      </g>
      <g fill="none" stroke="#1a0b2e" strokeLinecap="round">
        <path d="M134 198 Q156 176 190 186" strokeWidth={6} />
        <path d="M134 198 L126 192 M140 190 L132 182" strokeWidth={3.5} />
        <path d="M266 198 Q244 176 210 186" strokeWidth={6} />
        <path d="M266 198 L274 192 M260 190 L268 182" strokeWidth={3.5} />
      </g>
      <path d="M150 220 Q164 226 180 218 M220 218 Q236 226 250 220" fill="none" stroke="#4a2613" strokeWidth={2} strokeLinecap="round" />
      <path d="M142 168 Q160 158 182 164 M258 168 Q240 158 218 164" fill="none" stroke="#3b1a63" strokeWidth={4} strokeLinecap="round" />

      {/* nose and mouth */}
      <path d="M202 236 Q206 244 198 246" fill="none" stroke="#5c3520" strokeWidth={2.5} strokeLinecap="round" />
      {mood === "sing" ? (
        <>
          <ellipse cx={200} cy={268} rx={15} ry={13} fill="#5a1f2e" />
          <path d="M190 276 Q200 270 210 276 Q206 282 200 282 Q194 282 190 276 Z" fill="#f472b6" />
        </>
      ) : (
        <>
          <path d="M180 262 Q200 280 220 262 Q200 270 180 262 Z" fill="#5a1f2e" stroke="#4a1a26" strokeWidth={2} strokeLinejoin="round" />
          <path d="M190 268 Q200 274 210 268" fill="none" stroke="#f9a8d4" strokeWidth={2.5} strokeLinecap="round" />
        </>
      )}

      {/* bangs falling in strands, side locks, shine */}
      <path
        d="M126 182 C112 104 156 60 204 60 C254 60 292 104 276 184 L264 150 L252 176 L240 138 L226 170 L210 132 L194 168 L180 134 L166 172 L154 140 L140 180 L132 160 Z"
        fill={`url(#${p("hair")})`}
      />
      <path d="M210 132 L204 160 L194 168 Z M240 138 L236 160 L226 170 Z M180 134 L176 158 L166 172 Z" fill="#5b21b6" opacity={0.55} />
      <path d="M124 176 C118 220 126 262 140 290 L150 220 C146 200 146 186 152 170 Z" fill="#6d28d9" />
      <path d="M278 180 C284 222 276 262 262 290 L252 220 C256 200 256 186 248 170 Z" fill="#6d28d9" />
      <path d="M160 92 C176 82 200 80 222 86 C204 90 186 96 172 108 Z" fill="#ede4ff" opacity={0.8} />

      {/* high bun with a pink band */}
      <circle cx={200} cy={58} r={26} fill="#7c3aed" />
      <path d="M180 50 C190 38 210 38 220 50" fill="none" stroke="#ede4ff" strokeWidth={3} opacity={0.7} />
      <path d="M176 70 L224 70" stroke="#f472b6" strokeWidth={6} strokeLinecap="round" />

      {/* headphones */}
      <path d="M120 176 C110 90 290 90 280 176" fill="none" stroke="#0f172a" strokeWidth={10} />
      <path d="M120 176 C110 90 290 90 280 176" fill="none" stroke="#38bdf8" strokeWidth={3} />
      <rect x={104} y={166} width={30} height={46} rx={12} fill="#0f172a" />
      <rect x={108} y={172} width={8} height={34} rx={4} fill="#f472b6" />
      <rect x={266} y={166} width={30} height={46} rx={12} fill="#0f172a" />
      <rect x={284} y={172} width={8} height={34} rx={4} fill="#38bdf8" />
      {mood === "sing" && (
        <>
          <path d="M120 208 C124 250 150 272 176 274" fill="none" stroke="#0f172a" strokeWidth={5} strokeLinecap="round" />
          <rect x={170} y={266} width={16} height={12} rx={6} fill="#38bdf8" />
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
        <linearGradient id={p("hair")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#67e8f9" />
          <stop offset="0.5" stopColor="#0ea5e9" />
          <stop offset="1" stopColor="#1e3a8a" />
        </linearGradient>
        <linearGradient id={p("iris")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#082f49" />
          <stop offset="0.55" stopColor="#0ea5e9" />
          <stop offset="1" stopColor="#a5f3fc" />
        </linearGradient>
        <linearGradient id={p("hood")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0f172a" />
          <stop offset="1" stopColor="#1e293b" />
        </linearGradient>
        <clipPath id={p("eyeL")}>
          <path d="M140 202 Q162 188 188 194 Q186 214 166 220 Q146 216 140 202 Z" />
        </clipPath>
        <clipPath id={p("eyeR")}>
          <path d="M260 202 Q238 188 212 194 Q214 214 234 220 Q254 216 260 202 Z" />
        </clipPath>
      </defs>

      {/* hoodie with drawstrings and a lightning bolt */}
      <path d="M60 520 C64 404 104 350 160 334 L240 334 C296 350 336 404 340 520 Z" fill={`url(#${p("hood")})`} />
      <path d="M150 334 C150 376 250 376 250 334 L240 334 C232 356 168 356 160 334 Z" fill="#334155" />
      <path d="M176 360 L172 420 M224 360 L228 420" stroke="#38bdf8" strokeWidth={3} strokeLinecap="round" />
      <circle cx={172} cy={424} r={4} fill="#38bdf8" />
      <circle cx={228} cy={424} r={4} fill="#38bdf8" />
      <path d="M206 384 L186 424 L202 424 L194 456 L222 412 L206 412 L216 384 Z" fill="#fde047" stroke="#fef9c3" strokeWidth={1.5} strokeLinejoin="round" />

      {/* neck and ears */}
      <path d="M178 276 L222 276 L226 340 L174 340 Z" fill="#6b3f24" />
      <path d="M178 286 C190 302 210 302 222 286 L222 306 C210 316 190 316 178 306 Z" fill="#4e2c18" />
      <ellipse cx={134} cy={210} rx={10} ry={16} fill="#6b3f24" />
      <ellipse cx={266} cy={210} rx={10} ry={16} fill="#6b3f24" />

      {/* face: a stronger jaw */}
      <path d="M136 170 C136 120 168 100 200 100 C232 100 264 120 264 170 C264 214 256 246 238 268 C224 284 212 292 200 294 C188 292 176 284 162 268 C144 246 136 214 136 170 Z" fill="#7a4a2b" />
      <path d="M136 170 C136 214 144 246 162 268 C176 284 188 292 200 294 C178 274 158 236 154 192 Z" fill="#5f3720" opacity={0.6} />

      {/* sharper, confident eyes */}
      <path d="M140 202 Q162 188 188 194 Q186 214 166 220 Q146 216 140 202 Z" fill="#fff" />
      <g clipPath={`url(#${p("eyeL")})`}>
        <ellipse cx={168} cy={206} rx={13} ry={16} fill={`url(#${p("iris")})`} />
        <ellipse cx={168} cy={206} rx={6} ry={8} fill="#03141f" />
        <circle cx={163} cy={200} r={4} fill="#fff" />
        <path d="M140 190 L190 190 L190 200 Q164 190 140 204 Z" fill="#0c1a2e" opacity={0.4} />
      </g>
      <path d="M260 202 Q238 188 212 194 Q214 214 234 220 Q254 216 260 202 Z" fill="#fff" />
      <g clipPath={`url(#${p("eyeR")})`}>
        <ellipse cx={232} cy={206} rx={13} ry={16} fill={`url(#${p("iris")})`} />
        <ellipse cx={232} cy={206} rx={6} ry={8} fill="#03141f" />
        <circle cx={227} cy={200} r={4} fill="#fff" />
        <path d="M260 190 L210 190 L210 200 Q236 190 260 204 Z" fill="#0c1a2e" opacity={0.4} />
      </g>
      <g fill="none" stroke="#0b1220" strokeLinecap="round">
        <path d="M136 204 Q158 184 192 192 M264 204 Q242 184 208 192" strokeWidth={5.5} />
        <path d="M140 176 L186 182 M260 176 L214 182" strokeWidth={6} />
      </g>

      {/* nose, a big grin, a plaster on the cheek */}
      <path d="M202 232 Q207 240 198 242" fill="none" stroke="#4e2c18" strokeWidth={2.5} strokeLinecap="round" />
      <path d="M172 254 Q200 262 230 250 Q222 278 200 280 Q178 278 172 254 Z" fill="#3b0d1a" />
      <path d="M174 256 Q200 263 228 252 L226 260 Q200 268 176 262 Z" fill="#fff" />
      <path d="M186 274 Q200 282 214 274" fill="none" stroke="#f472b6" strokeWidth={3} strokeLinecap="round" />
      <g transform="rotate(-18 242 238)">
        <rect x={228} y={232} width={30} height={12} rx={4} fill="#fef3c7" />
        <path d="M238 236 v4 M243 236 v4 M248 236 v4" stroke="#d6b77a" strokeWidth={1.5} />
      </g>

      {/* spiky hair swept up, with light and shadow facets */}
      <path
        d="M128 186 C120 150 126 120 140 102 L110 92 L146 80 L124 46 L168 64 L170 22 L198 58 L222 14 L232 58 L270 30 L262 72 L304 64 L272 100 L298 116 L266 122 C276 140 276 164 270 188 L262 156 L250 168 L246 138 L228 158 L222 130 L204 150 L196 124 L178 150 L172 128 L156 156 L150 134 L138 168 Z"
        fill={`url(#${p("hair")})`}
      />
      <path d="M168 64 L186 96 L198 58 Z M222 14 L222 84 L232 58 Z M270 30 L246 90 L262 72 Z M124 46 L156 92 L146 80 Z" fill="#a5f3fc" opacity={0.6} />
      <path d="M196 124 L200 146 L204 150 Z M222 130 L226 152 L228 158 Z M172 128 L174 146 L178 150 Z" fill="#1e3a8a" opacity={0.6} />

      {/* headband with tails in the wind */}
      <path d="M132 150 C168 128 232 128 270 150 L268 164 C232 142 168 142 134 164 Z" fill="#f472b6" />
      <path d="M270 152 L306 140 L298 160 L320 168 L284 168 Z" fill="#f472b6" />
    </g>
  );
}

/** A captain still in the shadows, for games that are coming soon. */
export function Mystery({ color }: { color: string }) {
  return (
    <g>
      <path d="M70 520 C74 390 112 346 160 334 L240 334 C288 346 326 390 330 520 Z" fill="#0b0d20" stroke={color} strokeWidth={3} />
      <path d="M178 270 L222 270 L226 340 L174 340 Z" fill="#0b0d20" />
      <path
        d="M132 168 C132 118 166 96 200 96 C234 96 268 118 268 168 C268 214 254 250 232 274 C220 288 210 298 200 300 C190 298 180 288 168 274 C146 250 132 214 132 168 Z"
        fill="#0b0d20"
        stroke={color}
        strokeWidth={3}
      />
      <path d="M124 180 C110 100 156 56 204 56 C256 56 294 100 278 184 L262 146 L246 172 L232 132 L214 164 L196 128 L178 166 L162 134 L146 176 Z" fill="#12153a" stroke={color} strokeWidth={3} strokeLinejoin="round" />
      <path d="M150 200 L186 206 M250 200 L214 206" stroke={color} strokeWidth={6} strokeLinecap="round" />
    </g>
  );
}

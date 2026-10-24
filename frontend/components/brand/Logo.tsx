/** The VOXPLAY mark: a play triangle inside a pulse ring, the shape of a voice entering a game. */
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden className="logo-mark">
      <defs>
        <linearGradient id="vx-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#38bdf8" />
          <stop offset="0.55" stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
      </defs>
      <path d="M32 3 57 17.5v29L32 61 7 46.5v-29Z" fill="none" stroke="url(#vx-mark)" strokeWidth="4" strokeLinejoin="round" />
      <path d="M25 20v24l20-12Z" fill="url(#vx-mark)" />
      <path d="M15 27v10M19 23v18M49 29v6" stroke="#38bdf8" strokeWidth="3" strokeLinecap="round" opacity="0.8" />
    </svg>
  );
}

/** Mark + wordmark, for the navigation and the footer. */
export function Logo({ size = 30 }: { size?: number }) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      <span className="wordmark">
        VOX<span>PLAY</span>
      </span>
    </span>
  );
}

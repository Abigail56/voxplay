// Artwork slots. Every illustrated spot in VOXPLAY has a name here.
//
// Each slot shows an original SVG scene (components/art/Scenes.tsx) until you give it an image:
// put a licensed or commissioned picture in frontend/public/art/ and set its path below, e.g.
//   hero: { src: "/art/hero.webp", alt: "A hero facing the Nexus portal" },
// Use a wide image (about 1600 x 1000, WebP or AVIF, under ~250 KB). Text is never placed
// on top of artwork without an overlay, so any picture works.

export type ArtSlot = "hero" | "brainClash" | "whosTalking" | "comingSoon" | "lobby" | "victory" | "empty";

export const ART: Record<ArtSlot, { src: string; alt: string } | null> = {
  hero: null,
  brainClash: null,
  whosTalking: null,
  comingSoon: null,
  lobby: null,
  victory: null,
  empty: null,
};

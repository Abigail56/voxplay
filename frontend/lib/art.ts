// Every illustrated spot in VOXPLAY, and the image file that fills it.
//
// The images live in frontend/public/images/voxplay/ (see docs/ART_PROMPTS.md for the prompt behind
// each one). scripts/scan-art.mjs lists the files that exist before every build, so a slot uses its
// image only when the file is really there; until then it shows its drawn SVG scene
// (components/art/Scenes.tsx). To add art: drop the file at its path and rebuild. Nothing else changes.

import { AVAILABLE_ART } from "./art.available";

export type ModeArt =
  | "african-knowledge"
  | "music-challenge"
  | "culture-challenge"
  | "word-association"
  | "riddles"
  | "quick-fire"
  | "general-knowledge"
  | "team-battle"
  | "name-it-fast";
export type StateArt = "searching" | "waiting" | "empty-room" | "creating-room" | "no-games" | "reconnecting";

export type ArtSlot =
  | "hero"
  | "lobby"
  | "brainClash"
  | "victory"
  | "defeat"
  | "beatDrop"
  | "storyForge"
  | "whosTalking"
  | "comingSoon"
  | "empty"
  | `mode-${ModeArt}`
  | `state-${StateArt}`;

/** Where an image sits and how it's cropped. `position` is its CSS object-position (keep the faces in view). */
export type ArtFile = { file: string; alt: string; position?: string; mobile?: string };

const BASE = "/images/voxplay";
const MODES: Record<ModeArt, string> = {
  "african-knowledge": "A captain surrounded by glowing holographic maps and facts about Africa",
  "music-challenge": "A futuristic stage pulsing with sound waves and coloured light",
  "culture-challenge": "Captains in modern outfits inspired by African traditions, under festival lights",
  "word-association": "Glowing words and symbols linked by threads of light",
  "riddles": "A mysterious chamber of floating puzzle pieces lit in violet",
  "quick-fire": "A captain racing a countdown, light streaking past",
  "general-knowledge": "A captain reaching into a cloud of holographic knowledge panels",
  "team-battle": "Two teams charging at each other across a neon arena",
  "name-it-fast": "A captain racing to fill a glowing list before the clock runs out",
};
const STATES: Record<StateArt, string> = {
  searching: "A captain scanning a holographic radar for players",
  waiting: "Captains relaxing on the arena steps, waiting for friends",
  "empty-room": "An empty, softly lit arena waiting for players",
  "creating-room": "A captain building a glowing room portal",
  "no-games": "A quiet arena with the lights dimmed",
  reconnecting: "A captain reconnecting a glowing signal cable",
};

export const ART: Record<ArtSlot, ArtFile> = {
  hero: {
    file: `${BASE}/hero/voxplay-hero.webp`,
    mobile: `${BASE}/hero/voxplay-hero-mobile.webp`,
    alt: "Nova and Pulse, headphones on, in a neon VOXPLAY esports arena",
    position: "50% 30%",
  },
  lobby: { file: `${BASE}/brain-clash/arena.webp`, alt: "Nova and Pulse in the neon Brain Clash arena", position: "50% 30%" },
  brainClash: { file: `${BASE}/brain-clash/team-versus.webp`, alt: "Two rivals face to face as blue and violet energy clashes between them", position: "50% 40%" },
  victory: { file: `${BASE}/brain-clash/victory.webp`, alt: "The champions celebrate under a burst of light", position: "50% 30%" },
  defeat: { file: `${BASE}/brain-clash/defeat.webp`, alt: "The captains, determined, ready for a rematch", position: "50% 30%" },
  beatDrop: { file: `${BASE}/brain-clash/beat-drop.webp`, alt: "A DJ hits the decks on a neon stage in front of a cheering crowd", position: "50% 28%" },
  storyForge: { file: `${BASE}/story-forge/story-forge.webp`, alt: "A storyteller writes in a glowing book as a castle and a dragon rise from its pages", position: "60% 30%" },
  whosTalking: { file: `${BASE}/whos-talking/whos-talking.webp`, alt: "Two friends chat as a sound wave flows between them", position: "50% 35%" },
  comingSoon: { file: `${BASE}/states/coming-soon.webp`, alt: "A new challenger waits in the shadows", position: "50% 40%" },
  empty: { file: `${BASE}/states/no-games.webp`, alt: STATES["no-games"], position: "50% 50%" },
  ...(Object.fromEntries(Object.entries(MODES).map(([k, alt]) => [`mode-${k}`, { file: `${BASE}/game-modes/${k}.webp`, alt, position: "50% 35%" }])) as Record<
    `mode-${ModeArt}`,
    ArtFile
  >),
  ...(Object.fromEntries(Object.entries(STATES).map(([k, alt]) => [`state-${k}`, { file: `${BASE}/states/${k}.webp`, alt, position: "50% 40%" }])) as Record<
    `state-${StateArt}`,
    ArtFile
  >),
};

const available = new Set(AVAILABLE_ART);

/** The image path if that file exists, otherwise null (show the drawn fallback). */
export function artSrc(path: string | undefined): string | null {
  return path && available.has(path) ? path : null;
}

/** VOXPLAY's recurring cast. Portraits are square (see docs/ART_PROMPTS.md); Nova and Pulse also have drawn busts. */
export type CrewMember = {
  id: "nova" | "pulse" | "zuri" | "ayo";
  name: string;
  role: string;
  bio: string;
  colors: [string, string];
  portrait: string;
};

export const CREW: CrewMember[] = [
  {
    id: "nova",
    name: "Nova",
    role: "Team Nova captain · Brain Clash",
    bio: "The strategist. Calm under pressure, never forgets a fact, and always has a plan for the steal.",
    colors: ["#a78bfa", "#f472b6"],
    portrait: `${BASE}/characters/nova.webp`,
  },
  {
    id: "pulse",
    name: "Pulse",
    role: "Team Pulse captain · Brain Clash",
    bio: "The hype machine. Fastest buzzer in the arena, loudest celebration, and never without his headphones.",
    colors: ["#22d3ee", "#fde047"],
    portrait: `${BASE}/characters/pulse.webp`,
  },
  {
    id: "zuri",
    name: "Zuri",
    role: "Keeper of tales · Story Forge",
    bio: "The dreamer. Turns one strange word into a legend, and her stories always have a twist.",
    colors: ["#2dd4bf", "#fbbf24"],
    portrait: `${BASE}/characters/zuri.webp`,
  },
  {
    id: "ayo",
    name: "DJ Ayo",
    role: "Host of the drop · Beat Drop",
    bio: "The showman. Knows every Afrobeats and amapiano hook, and can hear a cheat from across the room.",
    colors: ["#f472b6", "#fb923c"],
    portrait: `${BASE}/characters/ayo.webp`,
  },
];

/** Every category has its own picture slot: categories/<id>.webp (see docs/ART_PROMPTS.md). */
export const CATEGORY_LOOK: Record<string, { icon: string; extras: [string, string]; hue: string; glow: string; alt: string }> = {
  african_general: { icon: "🌍", extras: ["🦒", "🏔️"], hue: "#6d28d9", glow: "#fbbf24", alt: "Africa's landmarks and wildlife" },
  nigerian_general: { icon: "🦅", extras: ["🏙️", "🟢"], hue: "#15803d", glow: "#a3e635", alt: "Nigeria's cities and symbols" },
  african_music: { icon: "🥁", extras: ["🎶", "🎤"], hue: "#be185d", glow: "#22d3ee", alt: "Drums, mics and African music" },
  nigerian_entertainment: { icon: "🎬", extras: ["⭐", "🎤"], hue: "#7e22ce", glow: "#f472b6", alt: "Stars and screens of Nigerian entertainment" },
  african_history: { icon: "🏛️", extras: ["👑", "📜"], hue: "#92400e", glow: "#fde68a", alt: "Ancient kingdoms, crowns and scrolls" },
  current_affairs: { icon: "📰", extras: ["🗳️", "🌐"], hue: "#1d4ed8", glow: "#67e8f9", alt: "News, votes and the world today" },
  african_football: { icon: "⚽", extras: ["🏆", "🥅"], hue: "#15803d", glow: "#fde047", alt: "Football, goals and trophies" },
  animals_nature: { icon: "🦁", extras: ["🐘", "🌿"], hue: "#a16207", glow: "#86efac", alt: "Lions, elephants and the wild" },
  african_food: { icon: "🍲", extras: ["🌶️", "🍗"], hue: "#c2410c", glow: "#fdba74", alt: "Jollof, pepper soup and spice" },
  languages: { icon: "🗣️", extras: ["🔤", "💬"], hue: "#0e7490", glow: "#a78bfa", alt: "Languages and words of Africa" },
  pidgin: { icon: "💬", extras: ["😎", "🔥"], hue: "#166534", glow: "#fde047", alt: "Naija Pidgin chat" },
  african_movies: { icon: "🎥", extras: ["🍿", "🎞️"], hue: "#be123c", glow: "#fda4af", alt: "Nollywood and African cinema" },
  riddles: { icon: "🧩", extras: ["❓", "🔮"], hue: "#4c1d95", glow: "#c084fc", alt: "Puzzles and riddles" },
  word_challenges: { icon: "🔤", extras: ["✏️", "📖"], hue: "#0f766e", glow: "#5eead4", alt: "Letters, words and spelling" },
  everyday: { icon: "💡", extras: ["🏠", "⏰"], hue: "#1e40af", glow: "#93c5fd", alt: "Everyday knowledge" },
  funny: { icon: "😂", extras: ["🎭", "🤪"], hue: "#a21caf", glow: "#fde047", alt: "Jokes and funny challenges" },
  hum_afrobeats: { icon: "🎧", extras: ["🔥", "🎶"], hue: "#9d174d", glow: "#22d3ee", alt: "Afrobeats hits" },
  hum_amapiano: { icon: "🎹", extras: ["💃", "🪘"], hue: "#6d28d9", glow: "#fde047", alt: "Amapiano and South African hits" },
  hum_classics: { icon: "📻", extras: ["🎷", "⭐"], hue: "#92400e", glow: "#fbbf24", alt: "Naija classics" },
  story_lagos: { icon: "🚌", extras: ["🌆", "🍛"], hue: "#c2410c", glow: "#fde047", alt: "Lagos life: danfos, traffic and owambe" },
  story_legends: { icon: "🐢", extras: ["🌙", "🥁"], hue: "#1e3a8a", glow: "#fde68a", alt: "Myths and legends: tortoises, drums and the moon" },
  story_chaos: { icon: "🐐", extras: ["💍", "😱"], hue: "#a21caf", glow: "#fda4af", alt: "Comedy chaos: goats at weddings" },
};

export function categoryFile(id: string): string {
  return `${BASE}/categories/${id}.webp`;
}

/** Player portraits: an avatar is picked by name, so the same player always gets the same face. */
export const AVATARS = Array.from({ length: 12 }, (_, i) => `${BASE}/avatars/avatar-${String(i + 1).padStart(2, "0")}.webp`);

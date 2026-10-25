// The VOXPLAY game catalogue: what the landing page and /games show.
// Only games with status "live" have a working Play button; the others are clearly marked Coming soon.

import type { ArtSlot } from "./art";

export type GameInfo = {
  id: string;
  title: string;
  tagline: string;
  description: string;
  category: string;
  players: string;
  status: "live" | "soon";
  href?: string;
  art: ArtSlot;
  featured?: boolean;
};

export const GAMES: GameInfo[] = [
  {
    id: "brain-clash",
    title: "Brain Clash",
    tagline: "Two teams. One battle. One champion.",
    description:
      "Twenty seconds on the clock, your squad against theirs. Afrobeats, Nollywood, football, jollof wars and Pidgin riddles: shout the answer before they steal it.",
    category: "Team quiz",
    players: "2+ players, two teams",
    status: "live",
    href: "/brain-clash",
    art: "brainClash",
    featured: true,
  },
  {
    id: "whos-talking",
    title: "Who's Talking?",
    tagline: "The AI knows your voice. Make it wrong.",
    description:
      "Fake an accent, copy your friend, disguise your voice. The AI is listening, and every time you fool it the points are yours.",
    category: "Voice party game",
    players: "1-12 players",
    status: "live",
    href: "/whos-talking",
    art: "whosTalking",
  },
  {
    id: "beat-drop",
    title: "Beat Drop",
    tagline: "Hum it. Name it. Before the drop.",
    description:
      "One secret song, zero words. Hum the hook from Burna, Wizkid, Tems or an amapiano banger and watch your team scream the title. Say it out loud and the AI catches you.",
    category: "Music battle",
    players: "2+ players, two teams",
    status: "live",
    href: "/beat-drop",
    art: "beatDrop",
  },
  {
    id: "story-forge",
    title: "Story Forge",
    tagline: "One line each. One legend together.",
    description: "Danfo drivers, talking tortoises, chaotic weddings: build a wild story with your squad one line at a time, and win the room's fire 🔥.",
    category: "Storytelling",
    players: "2+ players, two teams",
    status: "live",
    href: "/story-forge",
    art: "storyForge",
  },
  {
    id: "accent-roulette",
    title: "Accent Roulette",
    tagline: "Spin the wheel. Say it like a local.",
    description: "Spin for an accent, get a line, own the stage while your friends judge the delivery. Dropping soon.",
    category: "Voice party game",
    players: "3-10 players",
    status: "soon",
    art: "comingSoon",
  },
  {
    id: "word-bomb",
    title: "Word Bomb",
    tagline: "Say a word before it blows.",
    description: "A ticking bomb, three letters, one second to think. Shout a word and pass it on before it explodes. Dropping soon.",
    category: "Word game",
    players: "2-12 players",
    status: "soon",
    art: "comingSoon",
  },
];

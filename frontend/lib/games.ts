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
      "Team quiz battles: African and Nigerian knowledge, music, football, food, Pidgin, riddles and more. Answer by voice or by typing, against the clock.",
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
      "Read silly lines while an AI works out who's speaking. Be yourself, do impressions, disguise your voice or pass one down a broken telephone.",
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
      "One player hums a secret song (Afrobeats, amapiano, Naija classics), their team races to name it. No words allowed: the AI is listening.",
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
    description: "Two teams build one wild story, a line at a time, using the spark word each turn throws in. The other team fires 🔥 at the best lines.",
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
    description: "Spin for an accent and a line, then perform it. Your friends score the delivery. Not playable yet.",
    category: "Voice party game",
    players: "3-10 players",
    status: "soon",
    art: "comingSoon",
  },
  {
    id: "word-bomb",
    title: "Word Bomb",
    tagline: "Say a word before it blows.",
    description: "A ticking bomb and a few letters: shout a word that contains them and pass it on before it explodes. Not playable yet.",
    category: "Word game",
    players: "2-12 players",
    status: "soon",
    art: "comingSoon",
  },
];

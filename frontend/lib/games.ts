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
    tagline: "Name that tune before the drop.",
    description: "A music guessing game built on Afrobeats, highlife and amapiano. Not playable yet.",
    category: "Music",
    players: "2-8 players",
    status: "soon",
    art: "comingSoon",
  },
  {
    id: "story-forge",
    title: "Story Forge",
    tagline: "One line each. One legend together.",
    description: "Build a story out loud, one sentence at a time, with twists the game throws in. Not playable yet.",
    category: "Storytelling",
    players: "3-10 players",
    status: "soon",
    art: "comingSoon",
  },
];

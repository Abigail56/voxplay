// Brain Clash, Beat Drop and Story Forge: how their modes are described to players. The rules
// themselves live on the server (backend/app/brain_clash.py); keep this text in step with them.

import type { BcGame, BcMode } from "./api";
import type { ArtSlot, ModeArt } from "./art";

export const BC_MODES: { id: BcMode; icon: string; name: string; blurb: string; rules: string[]; art: ArtSlot }[] = [
  {
    id: "battle",
    art: "mode-team-battle",
    icon: "⚔️",
    name: "Brain Battle",
    blurb: "Teams take turns. Miss, and the other team can steal it.",
    rules: [
      "Only the team whose turn it is may answer, with up to 3 tries.",
      "10 points a question, 20 for hard ones.",
      "Miss, and the other team gets 10 seconds to steal it for half.",
    ],
  },
  {
    id: "quickfire",
    art: "mode-quick-fire",
    icon: "⚡",
    name: "Quick-Fire",
    blurb: "Short questions, both teams race. Fastest right answer wins.",
    rules: ["Both teams answer at once; one try each.", "First right answer takes the round.", "Up to 5 bonus points for speed."],
  },
  {
    id: "namefast",
    art: "mode-african-knowledge",
    icon: "📝",
    name: "Name It Fast",
    blurb: "Name five African countries… before the clock runs out.",
    rules: ["Each team builds its own list.", "5 points for every valid answer.", "Say one again and it scores nothing. You can name several at once."],
  },
  {
    id: "association",
    art: "mode-word-association",
    icon: "🔗",
    name: "Word Association",
    blurb: "A word appears. Say something that goes with it, fast.",
    rules: ["One try each.", "Each team scores once per word (10 points).", "Only related words from the game's list count."],
  },
];

/** Everything that differs between the three games that share Brain Clash rooms. */
export type RoomGame = {
  id: BcGame;
  title: string;
  path: string; // /brain-clash, /beat-drop, /story-forge (rooms live at path/CODE)
  mode: BcMode; // the mode a new room starts in
  eyebrow: string;
  tagline: string;
  lede: string;
  art: ArtSlot;
  howTitle: string;
  how: { icon: string; name: string; rules: string[]; art: ArtSlot }[];
  catsTitle: string;
  startLabel: string;
};

export const ROOM_GAMES: Record<BcGame, RoomGame> = {
  "brain-clash": {
    id: "brain-clash",
    title: "Brain Clash",
    path: "/brain-clash",
    mode: "battle",
    eyebrow: "A VOXPLAY team quiz",
    tagline: "Two teams. One battle. One champion.",
    lede: "Split into two teams and battle through questions on African and Nigerian knowledge, music, football, food, Pidgin, riddles and more. Shout your answer into your phone or type it. The server keeps score.",
    art: "brainClash",
    howTitle: "Four ways to clash",
    how: BC_MODES,
    catsTitle: "Sixteen ways to win",
    startLabel: "Start the clash",
  },
  "beat-drop": {
    id: "beat-drop",
    title: "Beat Drop",
    path: "/beat-drop",
    mode: "hum",
    eyebrow: "A VOXPLAY music battle",
    tagline: "Hum it. Name it. Before the drop.",
    lede: "One player secretly gets a song, from Afrobeats bangers to amapiano and Naija classics, and has to hum it. No words allowed: the AI is listening. Their team races to name the tune before the other team steals it.",
    art: "beatDrop",
    howTitle: "How Beat Drop works",
    how: [
      { icon: "🎵", name: "Hum it", art: "mode-music-challenge", rules: ["Every round a new hummer sees a secret song.", "20 seconds to record a hum: no words!", "The hum plays on every phone."] },
      { icon: "🎯", name: "Name it", art: "mode-quick-fire", rules: ["The hummer's team guesses first: 3 tries.", "10 points for the title (20 for hard ones), +5 for the hummer.", "Say it or type it: \"Essence by Wizkid\" counts."] },
      { icon: "🥷", name: "Steal it", art: "mode-team-battle", rules: ["Missed it? The other team gets 10 seconds to steal it for half.", "Teams take turns to hum.", "Three rounds won in a row: you're on fire, +5 a round."] },
      { icon: "🤖", name: "No cheating", art: "mode-riddles", rules: ["The AI listens to every hum.", "Say the title out loud and the hum is flagged.", "The host decides: allow it or void it."] },
    ],
    catsTitle: "Pick your playlist",
    startLabel: "Drop the beat",
  },
  "story-forge": {
    id: "story-forge",
    title: "Story Forge",
    path: "/story-forge",
    mode: "story",
    eyebrow: "A VOXPLAY storytelling battle",
    tagline: "One line each. One legend together.",
    lede: "Two teams build one wild story, a line at a time. Every turn throws in a spark word you must use and a twist to inspire you. Write it or say it out loud, and the other team fires 🔥 at the lines they love.",
    art: "storyForge",
    howTitle: "How Story Forge works",
    how: [
      { icon: "✍️", name: "Your line", art: "mode-culture-challenge", rules: ["The teams take turns; everyone gets a go.", "20 seconds to add one line: type it or say it.", "The game writes the first line for you."] },
      { icon: "⚡", name: "The spark", art: "mode-word-association", rules: ["Every turn has a spark word, like \"danfo\" or \"tortoise\".", "Use it in your line: +10 points.", "A twist suggests where the story could go."] },
      { icon: "🔥", name: "Fire", art: "mode-team-battle", rules: ["The other team has 12 seconds to fire at your line.", "+3 points for every 🔥.", "No hyping your own team!"] },
      { icon: "📜", name: "The legend", art: "mode-riddles", rules: ["At the end the whole story is shown, and read out loud.", "The team with the most points wins.", "Copied lines get flagged by the AI."] },
    ],
    catsTitle: "Choose your world",
    startLabel: "Start the story",
  },
};

/** Which game-mode artwork a category's tile shows. */
export const CATEGORY_ART: Record<string, ModeArt> = {
  african_general: "african-knowledge",
  current_affairs: "african-knowledge",
  nigerian_general: "general-knowledge",
  everyday: "general-knowledge",
  animals_nature: "general-knowledge",
  african_music: "music-challenge",
  nigerian_entertainment: "music-challenge",
  african_movies: "music-challenge",
  hum_afrobeats: "music-challenge",
  hum_amapiano: "music-challenge",
  hum_classics: "music-challenge",
  african_history: "culture-challenge",
  african_food: "culture-challenge",
  pidgin: "culture-challenge",
  languages: "culture-challenge",
  story_lagos: "culture-challenge",
  story_legends: "riddles",
  story_chaos: "word-association",
  african_football: "team-battle",
  riddles: "riddles",
  funny: "riddles",
  word_challenges: "word-association",
};

const EXTRA_MODES: Partial<Record<BcMode, string>> = { hum: "Beat Drop", story: "Story Forge" };
export const modeName = (m: BcMode) => BC_MODES.find((x) => x.id === m)?.name ?? EXTRA_MODES[m] ?? m;

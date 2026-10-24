// Brain Clash: how the modes are described to players. The rules themselves live on the server
// (backend/app/brain_clash.py); keep this text in step with them.

import type { BcMode } from "./api";

export const BC_MODES: { id: BcMode; icon: string; name: string; blurb: string; rules: string[] }[] = [
  {
    id: "battle",
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
    icon: "⚡",
    name: "Quick-Fire",
    blurb: "Short questions, both teams race. Fastest right answer wins.",
    rules: ["Both teams answer at once; one try each.", "First right answer takes the round.", "Up to 5 bonus points for speed."],
  },
  {
    id: "namefast",
    icon: "📝",
    name: "Name It Fast",
    blurb: "Name five African countries… before the clock runs out.",
    rules: ["Each team builds its own list.", "5 points for every valid answer.", "Say one again and it scores nothing. You can name several at once."],
  },
  {
    id: "association",
    icon: "🔗",
    name: "Word Association",
    blurb: "A word appears. Say something that goes with it, fast.",
    rules: ["One try each.", "Each team scores once per word (10 points).", "Only related words from the game's list count."],
  },
];

export const modeName = (m: BcMode) => BC_MODES.find((x) => x.id === m)?.name ?? m;

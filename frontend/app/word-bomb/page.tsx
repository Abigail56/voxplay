import { GameEntry } from "@/components/brain-clash/Entry";

export const metadata = {
  title: "Word Bomb",
  description: "Say a word before it blows. Three letters, a ticking bomb and two teams passing it back and forth.",
};

export default function WordBomb() {
  return <GameEntry game="word-bomb" />;
}

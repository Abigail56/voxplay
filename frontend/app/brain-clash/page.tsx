import { GameEntry } from "@/components/brain-clash/Entry";

export const metadata = {
  title: "Brain Clash",
  description: "Two teams. One battle. One champion. A team quiz on African and Nigerian knowledge, music, football, food, Pidgin and riddles.",
};

export default function BrainClash() {
  return <GameEntry game="brain-clash" />;
}

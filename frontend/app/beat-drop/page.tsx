import { GameEntry } from "@/components/brain-clash/Entry";

export const metadata = {
  title: "Beat Drop",
  description: "Hum it. Name it. Before the drop. One player hums a secret Afrobeats, amapiano or Naija classic; their team races to name it.",
};

export default function BeatDrop() {
  return <GameEntry game="beat-drop" />;
}

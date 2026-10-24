import { GameEntry } from "@/components/brain-clash/Entry";

export const metadata = {
  title: "Story Forge",
  description: "One line each. One legend together. Two teams build one wild story, a line at a time, around a spark word.",
};

export default function StoryForge() {
  return <GameEntry game="story-forge" />;
}

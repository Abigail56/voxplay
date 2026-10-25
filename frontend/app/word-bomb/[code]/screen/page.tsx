import { PartyScreen } from "@/components/brain-clash/Screen";

export const metadata = { title: "Word Bomb party screen" };

export default async function Screen({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  return <PartyScreen code={decodeURIComponent(code).toUpperCase()} game="word-bomb" />;
}

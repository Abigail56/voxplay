import { BrainClashRoomPage } from "@/components/brain-clash/Room";

export const metadata = { title: "Brain Clash room" };

export default async function Room({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  return <BrainClashRoomPage code={decodeURIComponent(code).toUpperCase()} />;
}

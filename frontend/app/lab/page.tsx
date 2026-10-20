import { MysteryVoice } from "@/components/MysteryVoice";
import { VoiceMap } from "@/components/VoiceMap";

export const metadata = { title: "Voice lab · Who's Talking?" };

export default function Lab() {
  return (
    <>
      <header>
        <h1>Voice lab</h1>
        <p>Two party tricks: put a name to a mystery voice, and find out who sounds like whom.</p>
      </header>

      <div className="grid">
        <MysteryVoice />
        <VoiceMap />
      </div>
    </>
  );
}

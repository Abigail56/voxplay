import { EnrollForm } from "@/components/EnrollForm";
import { IdentifyPanel } from "@/components/IdentifyPanel";
import { SpeakerList } from "@/components/SpeakerList";

export default function Home() {
  return (
    <main>
      <header>
        <h1>Voice ID</h1>
        <p>Enroll people by voice, then find out who is speaking.</p>
      </header>

      <div className="grid">
        <EnrollForm />
        <IdentifyPanel />
      </div>
      <SpeakerList />

      <footer>
        <strong>Privacy:</strong> a voiceprint is biometric data. Only enroll people who have agreed. Raw
        recordings are not stored, only the voiceprint numbers, and deleting a speaker removes them for good.
      </footer>
    </main>
  );
}

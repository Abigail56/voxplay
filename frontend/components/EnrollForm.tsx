"use client";

import { useState } from "react";

import type { Clip } from "@/lib/api";
import { useSpeakerStore } from "@/store/useSpeakerStore";

import { ClipInput } from "./ClipInput";

export function EnrollForm() {
  const enroll = useSpeakerStore((s) => s.enroll);
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [clips, setClips] = useState<Clip[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const canSubmit = name.trim() !== "" && consent && clips.length > 0 && !busy;

  function removeClip(id: string) {
    setClips((cs) => cs.filter((c) => c.id !== id));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const speaker = await enroll(name.trim(), consent, clips);
      setMessage({ kind: "ok", text: `Enrolled ${speaker.name} with ${speaker.sample_count} sample(s).` });
      setName("");
      setClips([]);
      setConsent(false);
    } catch (err) {
      setMessage({ kind: "error", text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>1. Enroll a speaker</h2>
      <p className="hint">Add 2–3 clips of 5–10 seconds of natural speech for best results.</p>

      <label className="field">
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ada" maxLength={100} />
      </label>

      <ClipInput multiple onClip={(c) => setClips((cs) => [...cs, c])} disabled={busy} />

      {clips.length > 0 && (
        <ul className="clips">
          {clips.map((c) => (
            <li key={c.id}>
              <audio src={c.url} controls />
              <span className="filename">{c.filename}</span>
              <button type="button" className="link" onClick={() => removeClip(c.id)}>
                remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <label className="consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        This person agrees to have their voiceprint stored for identification and knows they can ask for it
        to be deleted.
      </label>

      <button className="btn primary" disabled={!canSubmit}>
        {busy ? "Enrolling…" : "Enroll speaker"}
      </button>
      {message && <p className={message.kind === "ok" ? "success" : "error"}>{message.text}</p>}
    </form>
  );
}

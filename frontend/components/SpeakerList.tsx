"use client";

import { useEffect } from "react";

import { useSpeakerStore } from "@/store/useSpeakerStore";

export function SpeakerList() {
  const { speakers, loading, error, fetchSpeakers, remove } = useSpeakerStore();

  useEffect(() => {
    fetchSpeakers();
  }, [fetchSpeakers]);

  async function onDelete(id: number, name: string) {
    if (!confirm(`Permanently delete ${name} and all of their voiceprints?`)) return;
    try {
      await remove(id);
    } catch (e) {
      alert((e as Error).message);
    }
  }

  return (
    <section className="card">
      <h2>Enrolled speakers</h2>
      {loading && <p className="hint">Loading…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && speakers.length === 0 && <p className="hint">Nobody enrolled yet.</p>}
      <ul className="speakers">
        {speakers.map((s) => (
          <li key={s.id}>
            <div>
              <strong>{s.name}</strong>
              <span className="hint">
                {" "}
                · {s.sample_count} sample{s.sample_count === 1 ? "" : "s"} · consent{" "}
                {new Date(s.consent_given_at).toLocaleDateString()}
              </span>
            </div>
            <button className="btn danger small" onClick={() => onDelete(s.id, s.name)}>
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

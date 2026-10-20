"use client";

import { useState } from "react";

import { api, type Me } from "@/lib/api";
import { countryName, flag } from "@/lib/countries";
import { level } from "@/lib/game";
import { useAuthStore } from "@/store/useAuthStore";

import { Avatar } from "./Avatar";
import { LocationPicker, type Where } from "./LocationPicker";
import { VoiceSetup } from "./VoiceSetup";

export function PlayerCard({ me }: { me: Me }) {
  const { setMe, signOut } = useAuthStore();
  const [rerecord, setRerecord] = useState(false);
  const [moving, setMoving] = useState(false);
  const [where, setWhere] = useState<Where>({ country: me.country ?? "", place: me.place ?? "", found: null });
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const lvl = level(me.total_points);

  async function save(body: { share: boolean; country?: string; place?: string }) {
    setBusy(true);
    setNote(null);
    try {
      setMe(await api.setLocation(body));
      setMoving(false);
    } catch (e) {
      setNote((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function deletePlayer() {
    if (!confirm("Delete your player, voiceprint, scores and location for good?")) return;
    await api.deleteMe();
    signOut();
  }

  if (rerecord) return <VoiceSetup again onDone={() => setRerecord(false)} />;

  return (
    <section className="card player-card">
      <div className="player-head">
        <Avatar name={me.username} size={56} />
        <div>
          <div className="player-name">{me.username}</div>
          <div className="hint">
            Level {lvl.level} · {lvl.title}
          </div>
        </div>
      </div>
      <div className="xp" title={`${me.total_points} points`}>
        <div className="xp-fill" style={{ width: `${Math.round(lvl.progress * 100)}%` }} />
      </div>
      <div className="stats">
        <div>
          <strong>{me.total_points}</strong>
          <span className="hint">points</span>
        </div>
        <div>
          <strong>{me.turns}</strong>
          <span className="hint">turns</span>
        </div>
        <div>
          <strong>{me.wins}</strong>
          <span className="hint">wins</span>
        </div>
      </div>

      <p className="hint">
        Voiceprint: {me.voice_samples - me.learned_samples} recorded takes
        {me.learned_samples > 0 ? ` + ${me.learned_samples} learned from your games` : ", and it learns as you play"}
      </p>

      <div className="badge-shelf" aria-label={`${me.badges.filter((b) => b.earned).length} of ${me.badges.length} badges`}>
        {me.badges.map((b) => (
          <span
            key={b.id}
            className={`badge-icon ${b.earned ? "earned" : ""}`}
            title={`${b.name}: ${b.description}${b.earned ? " ✓" : ` (${b.progress}/${b.goal})`}`}
          >
            {b.emoji}
            {!b.earned && b.goal > 1 && <small>{b.progress}/{b.goal}</small>}
          </span>
        ))}
      </div>
      <p className="hint badge-count">
        {me.badges.filter((b) => b.earned).length} of {me.badges.length} badges. Tap one to see how to earn it.
      </p>

      <div className="my-place">
        <span>
          Playing from{" "}
          <strong>
            {me.place ?? "somewhere"}
            {me.country && `, ${countryName(me.country)} ${flag(me.country)}`}
          </strong>
        </span>
        {!moving && (
          <button className="link plain" onClick={() => setMoving(true)}>
            change
          </button>
        )}
      </div>
      {moving && (
        <div className="move">
          <LocationPicker value={where} onChange={setWhere} />
          <div className="row">
            <button
              className="btn small primary"
              disabled={busy || !where.found}
              onClick={() => save({ share: me.share_location, country: where.country, place: where.place })}
            >
              Move my pin
            </button>
            <button className="btn small ghost" onClick={() => setMoving(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      <label className="consent">
        <input type="checkbox" checked={me.share_location} disabled={busy} onChange={(e) => save({ share: e.target.checked })} />
        <span>
          Show me on the players&apos; map
          <span className="hint"> (your area, never your address)</span>
        </span>
      </label>
      {note && <p className="error">{note}</p>}

      <div className="row">
        <button className="btn small" onClick={() => setRerecord(true)}>
          Re-record voice
        </button>
        <button className="btn small ghost" onClick={signOut}>
          Sign out
        </button>
        <button className="link" onClick={deletePlayer}>
          Delete player
        </button>
      </div>
    </section>
  );
}

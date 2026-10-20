"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type Place } from "@/lib/api";
import { countries, countryName, flag } from "@/lib/countries";

export type Where = { country: string; place: string; found: Place | null };

/** Country + town/area, with a live "you'll appear at …" check and a "use my location" button. */
export function LocationPicker({ value, onChange }: { value: Where; onChange: (w: Where) => void }) {
  const list = useMemo(countries, []);
  const [status, setStatus] = useState<"idle" | "looking" | "found" | "missing">(value.found ? "found" : "idle");
  const [note, setNote] = useState<string | null>(null);

  // Check the place on the map shortly after typing stops.
  useEffect(() => {
    const { country, place } = value;
    if (!country || place.trim().length < 2) {
      setStatus("idle");
      return;
    }
    if (value.found && value.found.country === country && value.found.name === place) return;
    setStatus("looking");
    setNote(null);
    const id = setTimeout(async () => {
      try {
        const found = await api.searchPlace(place.trim(), country);
        onChange({ country, place, found });
        setStatus("found");
      } catch (e) {
        onChange({ country, place, found: null });
        setStatus("missing");
        setNote((e as Error).message); // "couldn't find it", or "the map service isn't answering"
      }
    }, 700);
    return () => clearTimeout(id);
  }, [value.country, value.place]); // only re-check when what the player typed changes

  function detectLocation() {
    if (!("geolocation" in navigator)) return setNote("This browser can't share its location.");
    setNote("Asking your browser…");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const found = await api.placeHere(pos.coords.latitude, pos.coords.longitude);
          onChange({ country: found.country, place: found.name, found });
          setStatus("found");
          setNote(null);
        } catch (e) {
          setNote((e as Error).message);
        }
      },
      (err) => setNote(err.code === err.PERMISSION_DENIED ? "Location permission was denied. Type your town instead." : "Couldn't get your location."),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 10 * 60 * 1000 },
    );
  }

  return (
    <div className="location-picker">
      <label className="field">
        Country
        <select value={value.country} onChange={(e) => onChange({ ...value, country: e.target.value, found: null })} required>
          <option value="">Choose your country…</option>
          {list.map((c) => (
            <option key={c.code} value={c.code}>
              {flag(c.code)} {c.name}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Town or area
        <input
          value={value.place}
          onChange={(e) => onChange({ ...value, place: e.target.value, found: null })}
          placeholder="e.g. Yaba, Lagos"
          maxLength={120}
          required
        />
      </label>
      <button type="button" className="btn small ghost" onClick={detectLocation}>
        Use my current location
      </button>
      <p className={`place-check ${status}`} aria-live="polite">
        {status === "looking" && "Finding it on the map…"}
        {status === "found" && value.found && (
          <>
            ✓ You&apos;ll appear at{" "}
            <strong>
              {value.found.name}, {countryName(value.found.country)} {flag(value.found.country)}
            </strong>
          </>
        )}
        {status === "missing" && !note && "We couldn't find that place. Try your town or area, e.g. 'Yaba, Lagos'."}
        {status === "idle" && note === null && "Your pin goes on your area, never your exact address."}
      </p>
      {note && <p className="hint">{note}</p>}
    </div>
  );
}

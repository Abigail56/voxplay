"use client";

// Leaflet touches `window`, so this file is only loaded in the browser (see World.tsx and the admin page).
import "leaflet/dist/leaflet.css";

import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";

export type Place = {
  key: string;
  label: string; // e.g. "🇳🇬 Yaba, Lagos"
  lat: number;
  lon: number;
  online: boolean; // someone here is online right now
  players: { name: string; online: boolean; points: number; room: string | null }[];
};

// Leaflet styles its own SVG, so colours are set here: the game's accent for places
// with someone online, a neutral grey otherwise, each with a white ring.
const ONLINE = { color: "#ffffff", weight: 2, fillColor: "#c8401f", fillOpacity: 0.9 };
const OFFLINE = { color: "#ffffff", weight: 2, fillColor: "#8f8676", fillOpacity: 0.75 };

/** Zoom to the pins whenever the set of places changes (they arrive after the map is created). */
function FitToPlaces({ places }: { places: Place[] }) {
  const map = useMap();
  const key = places.map((p) => p.key).join("|");
  useEffect(() => {
    if (places.length > 0) {
      map.fitBounds(
        places.map((p) => [p.lat, p.lon] as [number, number]),
        { padding: [40, 40], maxZoom: 6 },
      );
    }
  }, [map, key]); // key: refit only when the set of places changes
  return null;
}

export default function PlayersMapLeaflet({ places }: { places: Place[] }) {
  return (
    <MapContainer
      className="play-map"
      center={[15, 10]}
      zoom={2}
      minZoom={1}
      maxZoom={10} // locations are only city-level, so zooming further would suggest false precision
      worldCopyJump
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitToPlaces places={places} />
      {places.map((p) => (
        <CircleMarker
          key={p.key}
          center={[p.lat, p.lon]}
          radius={Math.min(20, 8 + 3 * Math.sqrt(p.players.length))}
          pathOptions={p.online ? ONLINE : OFFLINE}
        >
          <Tooltip direction="top" offset={[0, -8]}>
            <div className="map-place">{p.label}</div>
            {p.players.map((pl) => (
              <div key={pl.name}>
                <strong>{pl.name}</strong> · {pl.points} pts{pl.online && <> · online</>}
                {pl.room && <> · in {pl.room}</>}
              </div>
            ))}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}

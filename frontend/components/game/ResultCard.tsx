"use client";

import { useEffect, useRef, useState } from "react";

import type { Me, Room } from "@/lib/api";
import { avatarSlot } from "@/lib/game";

import { modeName } from "./ModePicker";

const W = 1080;
const H = 1080;
// The avatar colours (the same palette as the --series-* tokens), for drawing on a canvas.
const COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#3d9a3d", "#9085e9", "#e66767"];

// The VOXPLAY palette (see the tokens at the top of globals.css).
const NIGHT = "#080a16";
const INK = "#f8fafc";
const MUTED = "#a5b4d4";
const VIOLET = "#a78bfa";
const RULE = "#2b3163";
const SANS = "system-ui, sans-serif";

/** Draws the final scoreboard as a square image, ready for WhatsApp or Instagram. */
function draw(canvas: HTMLCanvasElement, room: Room, me: Me) {
  const ctx = canvas.getContext("2d")!;
  const SERIF = getComputedStyle(document.documentElement).getPropertyValue("--font-display") || SANS;
  ctx.fillStyle = NIGHT;
  ctx.fillRect(0, 0, W, H);
  // Two soft light sources, like the site's background, and a neon rule along the top.
  for (const [x, y, color] of [[W * 0.9, 0, "rgba(124,58,237,0.35)"], [0, H * 0.25, "rgba(56,189,248,0.18)"]] as const) {
    const glow = ctx.createRadialGradient(x, y, 0, x, y, W * 0.7);
    glow.addColorStop(0, color);
    glow.addColorStop(1, "rgba(8,10,22,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, W, H);
  }
  const rule = ctx.createLinearGradient(0, 0, W, 0);
  rule.addColorStop(0, "#38bdf8");
  rule.addColorStop(0.5, "#8b5cf6");
  rule.addColorStop(1, "#f472b6");
  ctx.fillStyle = rule;
  ctx.fillRect(0, 0, W, 14);

  ctx.textAlign = "left";
  ctx.fillStyle = MUTED;
  ctx.font = `700 28px ${SERIF}`;
  ctx.fillText("V O X P L A Y", 100, 95);
  ctx.fillStyle = INK;
  ctx.font = `700 64px ${SERIF}`;
  ctx.fillText("Who's Talking?", 100, 165);
  ctx.fillStyle = MUTED;
  ctx.font = `32px ${SANS}`;
  ctx.fillText(`${modeName(room.mode)}${room.speed ? " · speed round" : ""} · game ${room.code}`, 100, 215);

  const board = [...room.players].sort((a, b) => b.points - a.points);
  const winner = board[0];
  ctx.fillStyle = VIOLET;
  ctx.font = `600 30px ${SANS}`;
  ctx.fillText("WINNER", 100, 320);
  ctx.fillStyle = INK;
  ctx.font = `700 96px ${SERIF}`;
  ctx.fillText(winner.username, 100, 415);

  ctx.strokeStyle = RULE;
  ctx.lineWidth = 2;
  const rowH = Math.min(84, 460 / board.length);
  board.slice(0, 6).forEach((p, i) => {
    const y = 490 + i * rowH;
    const mid = y + rowH / 2;
    const mine = p.user_id === me.id;
    ctx.beginPath();
    ctx.moveTo(100, y + rowH);
    ctx.lineTo(W - 100, y + rowH);
    ctx.stroke();
    ctx.fillStyle = MUTED;
    ctx.textAlign = "left";
    ctx.font = `${Math.round(rowH * 0.4)}px ${SANS}`;
    ctx.fillText(`${i + 1}`, 100, mid + 12);
    ctx.fillStyle = COLORS[avatarSlot(p.username) - 1];
    ctx.beginPath();
    ctx.arc(185, mid, rowH * 0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.font = `bold ${Math.round(rowH * 0.3)}px ${SANS}`;
    ctx.fillText(p.username[0].toUpperCase(), 185, mid + rowH * 0.11);
    ctx.fillStyle = INK;
    ctx.textAlign = "left";
    ctx.font = `${mine ? "bold " : ""}${Math.round(rowH * 0.4)}px ${SANS}`;
    ctx.fillText(`${p.username}${mine ? " (me)" : ""}`, 240, mid + 12);
    ctx.textAlign = "right";
    ctx.font = `bold ${Math.round(rowH * 0.4)}px ${SANS}`;
    ctx.fillText(`${p.points}`, W - 100, mid + 12);
  });

  ctx.textAlign = "left";
  ctx.fillStyle = MUTED;
  ctx.font = `30px ${SANS}`;
  ctx.fillText("Enter the game. Own the moment. Play on VOXPLAY.", 100, H - 80);
}

/** "Share my result": the final scores as an image, via the phone's share menu or a download. */
export function ResultCard({ room, me }: { room: Room; me: Me }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    // Wait for the heading font, or the card is drawn in the fallback.
    document.fonts.ready.then(() => {
      draw(c, room, me);
      setUrl(c.toDataURL("image/png"));
    });
  }, [room, me]);

  async function share() {
    const blob = await new Promise<Blob | null>((ok) => canvas.current?.toBlob(ok, "image/png"));
    if (!blob) return;
    const file = new File([blob], `whos-talking-${room.code}.png`, { type: "image/png" });
    const rank = [...room.players].sort((a, b) => b.points - a.points).findIndex((p) => p.user_id === me.id) + 1;
    const text = `I came #${rank} in Who's Talking? on VOXPLAY. Think it can tell your voice apart? ${window.location.origin}`;
    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], text }).catch(() => {});
    } else {
      setNote("Your browser can't share images directly, so it's been downloaded instead.");
      const a = document.createElement("a");
      a.href = url ?? "";
      a.download = file.name;
      a.click();
    }
  }

  return (
    <div className="result-card">
      <canvas ref={canvas} width={W} height={H} hidden />
      {url && <img src={url} alt="Final scores of this game" className="result-preview" />}
      <div className="row">
        <button className="btn primary" onClick={share}>
          Share my result
        </button>
        {url && (
          <a className="btn ghost" href={url} download={`whos-talking-${room.code}.png`}>
            Download
          </a>
        )}
      </div>
      {note && <p className="hint">{note}</p>}
    </div>
  );
}

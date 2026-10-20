"use client";

import { useEffect, useRef, useState } from "react";

import type { Me, Room } from "@/lib/api";
import { avatarSlot } from "@/lib/game";

const W = 1080;
const H = 1080;
// The avatar colours (the same palette as the --series-* tokens), for drawing on a canvas.
const COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

const MODE = { yourself: "Be yourself", impersonate: "Impersonate", guess: "Guess Who" };
const PAPER = "#f3efe6";
const INK = "#1f1b16";
const MUTED = "#6e665a";
const RED = "#c8401f";
const SANS = "system-ui, sans-serif";

/** Draws the final scoreboard as a square image, ready for WhatsApp or Instagram. */
function draw(canvas: HTMLCanvasElement, room: Room, me: Me) {
  const ctx = canvas.getContext("2d")!;
  const SERIF = getComputedStyle(document.documentElement).getPropertyValue("--font-display") || "Georgia, serif";
  ctx.fillStyle = PAPER;
  ctx.fillRect(0, 0, W, H);
  // A thick red rule along the top, like a ticket stub.
  ctx.fillStyle = RED;
  ctx.fillRect(0, 0, W, 18);

  ctx.textAlign = "left";
  ctx.fillStyle = INK;
  ctx.font = `600 64px ${SERIF}`;
  ctx.fillText("Who's Talking?", 100, 150);
  ctx.fillStyle = MUTED;
  ctx.font = `32px ${SANS}`;
  ctx.fillText(`${MODE[room.mode]}${room.speed ? " · speed round" : ""} · game ${room.code}`, 100, 205);

  const board = [...room.players].sort((a, b) => b.points - a.points);
  const winner = board[0];
  ctx.fillStyle = RED;
  ctx.font = `600 30px ${SANS}`;
  ctx.fillText("WINNER", 100, 320);
  ctx.fillStyle = INK;
  ctx.font = `italic 600 96px ${SERIF}`;
  ctx.fillText(winner.username, 100, 415);

  ctx.strokeStyle = "#d9d0bf";
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
  ctx.fillText("Think it can tell your voice apart? Come and play.", 100, H - 80);
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
    const text = `I came #${rank} in Who's Talking? Think it can tell your voice apart? ${window.location.origin}`;
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

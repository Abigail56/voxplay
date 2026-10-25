"use client";

import { useEffect, useRef, useState } from "react";

import type { BcRoom, BcTeam } from "@/lib/api";
import { ART, artSrc } from "@/lib/art";
import { modeName, ROOM_GAMES } from "@/lib/brainClash";

const W = 1080;
const H = 1350; // 4:5, the tallest shape WhatsApp and Instagram show uncropped in a chat or feed
// The VOXPLAY palette (see the tokens at the top of globals.css), for drawing on a canvas.
const NIGHT = "#080a16";
const INK = "#f8fafc";
const MUTED = "#a5b4d4";
const GOLD = "#fbbf24";
const TEAM_COLOR: Record<BcTeam, string> = { A: "#a78bfa", B: "#38bdf8" };
const SANS = "system-ui, sans-serif";

const teamName = (room: BcRoom, t: BcTeam) => room.settings.team_names[t] || (t === "A" ? "Team Nova" : "Team Pulse");

/** The largest font size (down to `min`) at which `text` fits in `width`. */
function fit(ctx: CanvasRenderingContext2D, text: string, width: number, font: (px: number) => string, max: number, min = 28) {
  let px = max;
  for (; px > min; px -= 4) {
    ctx.font = font(px);
    if (ctx.measureText(text).width <= width) break;
  }
  ctx.font = font(px);
  return px;
}

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((ok) => {
    const img = new Image();
    img.onload = () => ok(img);
    img.onerror = () => ok(null);
    img.src = src;
  });
}

/** Rounds each team won, for the "7 of 10 rounds" line. */
function roundsWon(room: BcRoom): Record<BcTeam, number> {
  const won = { A: 0, B: 0 };
  for (const h of room.history) {
    const [a, b] = [h.scored.A ?? 0, h.scored.B ?? 0];
    if (a > b) won.A++;
    else if (b > a) won.B++;
  }
  return won;
}

async function draw(canvas: HTMLCanvasElement, room: BcRoom, site: string) {
  const ctx = canvas.getContext("2d")!;
  const DISPLAY = getComputedStyle(document.documentElement).getPropertyValue("--font-display").trim() || SANS;
  const g = ROOM_GAMES[room.game];
  const champ = room.winner === "draw" ? null : (room.winner as BcTeam | null);
  const accent = champ ? TEAM_COLOR[champ] : GOLD;

  ctx.fillStyle = NIGHT;
  ctx.fillRect(0, 0, W, H);
  // The victory artwork (or the game's own) across the top, fading into the night.
  const art = artSrc(ART.victory.file) ?? artSrc(ART[g.art].file) ?? artSrc(ART.lobby.file);
  const img = art ? await loadImage(art) : null;
  const artH = 560;
  if (img) {
    const scale = Math.max(W / img.width, artH / img.height);
    const w = img.width * scale;
    const h = img.height * scale;
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, W, artH);
    ctx.clip(); // a wide picture stays in its band, behind nothing else
    ctx.drawImage(img, (W - w) / 2, (artH - h) * 0.3, w, h);
    ctx.restore();
    const fade = ctx.createLinearGradient(0, artH * 0.35, 0, artH);
    fade.addColorStop(0, "rgba(8,10,22,0)");
    fade.addColorStop(1, NIGHT);
    ctx.fillStyle = fade;
    ctx.fillRect(0, 0, W, artH);
  } else {
    const glow = ctx.createRadialGradient(W / 2, 120, 0, W / 2, 120, W * 0.8);
    glow.addColorStop(0, "rgba(124,58,237,0.45)");
    glow.addColorStop(1, "rgba(8,10,22,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, W, artH);
  }
  const rule = ctx.createLinearGradient(0, 0, W, 0);
  rule.addColorStop(0, "#38bdf8");
  rule.addColorStop(0.5, "#8b5cf6");
  rule.addColorStop(1, "#f472b6");
  ctx.fillStyle = rule;
  ctx.fillRect(0, 0, W, 14);

  const X = 80;
  const inner = W - 2 * X;
  ctx.textAlign = "left";
  ctx.fillStyle = MUTED;
  ctx.font = `800 italic 30px ${DISPLAY}`;
  ctx.fillText(`VOXPLAY · ${g.title.toUpperCase()} · ${modeName(room.settings.mode).toUpperCase()}`, X, 600);

  // "Team Nova wins!"
  ctx.fillStyle = accent;
  ctx.shadowColor = accent;
  ctx.shadowBlur = 30;
  const headline = champ ? `${teamName(room, champ)} wins!` : "It's a draw!";
  const hpx = fit(ctx, headline, inner, (px) => `900 italic ${px}px ${DISPLAY}`, 130, 60);
  ctx.fillText(headline, X, 610 + hpx);
  ctx.shadowBlur = 0;

  // The two scores, side by side.
  const top = 660 + hpx;
  const boxW = (inner - 40) / 2;
  const won = roundsWon(room);
  (["A", "B"] as const).forEach((t, i) => {
    const x = X + i * (boxW + 40);
    ctx.fillStyle = champ === t ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.03)";
    ctx.strokeStyle = champ === t ? TEAM_COLOR[t] : "#2b3163";
    ctx.lineWidth = champ === t ? 4 : 2;
    ctx.beginPath();
    ctx.roundRect(x, top, boxW, 250, 28);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = TEAM_COLOR[t];
    fit(ctx, teamName(room, t), boxW - 60, (px) => `800 italic ${px}px ${DISPLAY}`, 40, 24);
    ctx.fillText(teamName(room, t), x + 30, top + 60);
    ctx.fillStyle = INK;
    ctx.font = `900 italic 120px ${DISPLAY}`;
    ctx.fillText(String(room.scores[t]), x + 30, top + 180);
    ctx.fillStyle = MUTED;
    ctx.font = `28px ${SANS}`;
    ctx.fillText(`${won[t]} of ${room.history.length} round${room.history.length === 1 ? "" : "s"}`, x + 30, top + 225);
  });

  // Star player, or the story's opening line.
  let y = top + 310;
  const star = [...room.players].sort((a, b) => b.points - a.points)[0];
  if (star && star.points > 0) {
    ctx.fillStyle = GOLD;
    ctx.font = `700 34px ${SANS}`;
    ctx.fillText("⭐ STAR PLAYER", X, y);
    ctx.fillStyle = INK;
    const line = `${star.name} · ${star.points} pts${room.game === "brain-clash" ? ` · ${star.correct} right` : ""}`;
    fit(ctx, line, inner, (px) => `800 italic ${px}px ${DISPLAY}`, 56, 30);
    ctx.fillText(line, X, y + 66);
    y += 130;
  }
  if (room.game === "story-forge" && room.opener) {
    ctx.fillStyle = MUTED;
    ctx.font = `italic 32px ${SANS}`;
    const words = `“${room.opener}”`.split(" ");
    let row = "";
    let rows = 0;
    for (const w of words) {
      if (ctx.measureText(`${row} ${w}`).width > inner && row) {
        ctx.fillText(row, X, y + rows * 44);
        row = w;
        if (++rows === 2) break;
      } else row = row ? `${row} ${w}` : w;
    }
    if (rows < 2) ctx.fillText(row, X, y + rows * 44);
  }

  // The invitation.
  ctx.fillStyle = INK;
  ctx.font = `800 italic 44px ${DISPLAY}`;
  ctx.fillText("Think your squad can beat us?", X, H - 120);
  ctx.fillStyle = accent;
  fit(ctx, site, inner, (px) => `600 ${px}px ${SANS}`, 32, 18);
  ctx.fillText(site, X, H - 66);
}

/** "Share the result": the final score as an image for WhatsApp or Instagram, with a link to play. */
export function ShareCard({ room }: { room: BcRoom }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const g = ROOM_GAMES[room.game];
  const file = `voxplay-${room.game}-${room.code}.png`;

  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const site = `${window.location.host}${g.path}`;
    // Wait for the heading font, or the card is drawn in the fallback.
    document.fonts.ready.then(() => draw(c, room, site)).then(() => setUrl(c.toDataURL("image/png")));
  }, [room, g.path]);

  async function share() {
    const blob = await new Promise<Blob | null>((ok) => canvas.current?.toBlob(ok, "image/png"));
    if (!blob) return;
    const champ = room.winner === "draw" ? null : (room.winner as BcTeam | null);
    const head = champ ? `${teamName(room, champ)} won` : "It was a draw";
    const text = `${head} ${room.scores.A}–${room.scores.B} on ${g.title}! 🔥 Think your squad can beat us? ${window.location.origin}${g.path}`;
    const image = new File([blob], file, { type: "image/png" });
    if (navigator.canShare?.({ files: [image] })) {
      await navigator.share({ files: [image], text }).catch(() => {});
    } else if (navigator.share) {
      await navigator.share({ text }).catch(() => {});
    } else {
      setNote("Your browser can't share images directly, so it's been downloaded instead.");
      const a = document.createElement("a");
      a.href = url ?? "";
      a.download = file;
      a.click();
    }
  }

  return (
    <div className="share-card">
      <canvas ref={canvas} width={W} height={H} hidden />
      {url && <img src={url} alt={`Final score of this ${g.title} match`} className="share-preview" />}
      <div className="row">
        <button className="btn primary" onClick={share} disabled={!url}>
          📤 Share the result
        </button>
        {url && (
          <a className="btn ghost" href={url} download={file}>
            Download
          </a>
        )}
      </div>
      {note && <p className="hint">{note}</p>}
    </div>
  );
}

// Small game helpers: levels, avatars, sound effects and the spoken announcer.

const TITLES = ["Rookie", "Whisperer", "Echo", "Voice Cadet", "Sound Ace", "Voice Master", "Voice Legend"];

/** Level from lifetime points: each level needs a bit more than the last. */
export function level(points: number): { level: number; title: string; progress: number } {
  const lvl = Math.floor(Math.sqrt(points / 50)) + 1;
  const start = 50 * (lvl - 1) ** 2;
  const next = 50 * lvl ** 2;
  return { level: lvl, title: TITLES[Math.min(lvl - 1, TITLES.length - 1)], progress: (points - start) / (next - start) };
}

/** A stable colour slot (1-8) per player name, for their avatar. */
export function avatarSlot(name: string): number {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return (h % 8) + 1;
}

let audio: AudioContext | null = null;

/** Short synthesised sound effects (no audio files needed). Silent if the browser blocks audio. */
export function sfx(kind: "join" | "turn" | "score" | "zero" | "win", enabled: boolean) {
  if (!enabled || typeof window === "undefined") return;
  try {
    audio ??= new AudioContext();
    const notes: Record<typeof kind, number[]> = {
      join: [523, 659],
      turn: [440, 554, 659],
      score: [523, 659, 784, 1047],
      zero: [330, 247],
      win: [523, 659, 784, 1047, 784, 1047],
    };
    notes[kind].forEach((freq, i) => {
      const osc = audio!.createOscillator();
      const gain = audio!.createGain();
      const t = audio!.currentTime + i * 0.11;
      osc.type = "triangle";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.18, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
      osc.connect(gain).connect(audio!.destination);
      osc.start(t);
      osc.stop(t + 0.2);
    });
  } catch {
    // no audio: the game works without it
  }
}

/** Read a sentence out loud with the browser's built-in voice (if it has one). */
export function announce(text: string, enabled: boolean) {
  if (!enabled || typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

const SOUND_KEY = "voice-id-sound";

export function loadSoundSetting(): boolean {
  try {
    return localStorage.getItem(SOUND_KEY) !== "off";
  } catch {
    return true;
  }
}

export function saveSoundSetting(on: boolean) {
  try {
    localStorage.setItem(SOUND_KEY, on ? "on" : "off");
  } catch {
    // ignore
  }
}

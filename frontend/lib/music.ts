// VOXPLAY's background music, made live with the Web Audio API (no audio files, nothing to licence).
// Two moods:
// - calm:   a lo-fi loop for browsing. Warm chord pads, a soft bass and the odd plucked note.
// - battle: for the game pages and matches. War drums, a driving minor-key bass line and brass-like
//           stabs on every bar.
// It's on by default but quiet, starts on the first tap (browsers don't allow sound before one),
// remembers if you mute it, and ducks out while anyone records or a hum plays, so it never ends up
// inside a recording.

const KEY = "voxplay-music";
export type Mood = "calm" | "battle";
const BPM: Record<Mood, number> = { calm: 70, battle: 112 };
const VOLUME: Record<Mood, number> = { calm: 0.11, battle: 0.1 };

// Am9 · Fmaj7 · Cmaj7 · Em7, one bar each (MIDI note numbers).
const CHORDS = [
  [57, 60, 64, 67, 71],
  [53, 57, 60, 64, 69],
  [48, 55, 59, 64, 67],
  [52, 55, 59, 62, 67],
];
// Battle: D minor, one bar each: Dm · B♭ · C · A (bass roots), with a power-chord stab on top.
const BATTLE = [
  { bass: [38, 38, 41, 38, 38, 38, 45, 43], stab: [50, 57, 62] },
  { bass: [34, 34, 38, 34, 34, 34, 41, 39], stab: [46, 53, 58] },
  { bass: [36, 36, 40, 36, 36, 36, 43, 41], stab: [48, 55, 60] },
  { bass: [33, 33, 37, 33, 33, 40, 38, 37], stab: [45, 52, 57] },
];
const hz = (n: number) => 440 * 2 ** ((n - 69) / 12);

let ctx: AudioContext | null = null;
let master: GainNode | null = null;
let input: GainNode | null = null;
let dry: GainNode | null = null; // drums skip the echo, so they stay punchy
let timer: ReturnType<typeof setInterval> | null = null;
let nextBeat = 0;
let beat = 0;
let ducked = false;
let mood: Mood = "calm";
let noise: AudioBuffer | null = null;
const listeners = new Set<(on: boolean) => void>();

export function musicWanted(): boolean {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

function build() {
  ctx = new AudioContext();
  master = ctx.createGain();
  master.gain.value = 0;
  const filter = ctx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.value = 1400;
  filter.Q.value = 0.4;
  const delay = ctx.createDelay(1);
  delay.delayTime.value = (60 / BPM.calm) * 0.75;
  const feedback = ctx.createGain();
  feedback.gain.value = 0.32;
  input = ctx.createGain();
  input.connect(filter);
  filter.connect(master);
  filter.connect(delay);
  delay.connect(feedback).connect(delay);
  delay.connect(master);
  master.connect(ctx.destination);
  dry = ctx.createGain();
  dry.connect(master);
  noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
  const data = noise.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
}

/** A drum hit: a sine that drops in pitch (kick, war drum) plus an optional burst of noise (snare). */
function drum(at: number, from: number, to: number, level: number, length: number, snare = 0) {
  const osc = ctx!.createOscillator();
  const gain = ctx!.createGain();
  osc.frequency.setValueAtTime(from, at);
  osc.frequency.exponentialRampToValueAtTime(to, at + length * 0.6);
  gain.gain.setValueAtTime(level, at);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + length);
  osc.connect(gain).connect(dry!);
  osc.start(at);
  osc.stop(at + length + 0.05);
  if (snare && noise) {
    const src = ctx!.createBufferSource();
    const hp = ctx!.createBiquadFilter();
    const ng = ctx!.createGain();
    src.buffer = noise;
    hp.type = "highpass";
    hp.frequency.value = 1500;
    ng.gain.setValueAtTime(snare, at);
    ng.gain.exponentialRampToValueAtTime(0.0001, at + 0.18);
    src.connect(hp).connect(ng).connect(dry!);
    src.start(at);
    src.stop(at + 0.2);
  }
}

function voice(freq: number, at: number, length: number, level: number, type: OscillatorType, attack: number) {
  const osc = ctx!.createOscillator();
  const gain = ctx!.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  osc.detune.value = (Math.random() - 0.5) * 8;
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.linearRampToValueAtTime(level, at + attack);
  gain.gain.setTargetAtTime(0.0001, at + length, length * 0.35);
  osc.connect(gain).connect(input!);
  osc.start(at);
  osc.stop(at + length * 2.5);
}

/** Schedule the beats that fall in the next half second (a look-ahead scheduler, so timing stays smooth). */
function schedule() {
  if (mood === "battle") return scheduleBattle();
  const BEAT = 60 / BPM.calm;
  while (nextBeat < ctx!.currentTime + 0.5) {
    const chord = CHORDS[Math.floor(beat / 4) % CHORDS.length];
    if (beat % 4 === 0) {
      chord.forEach((n) => voice(hz(n), nextBeat, BEAT * 3.6, 0.03, "triangle", 1.2)); // the pad
      voice(hz(chord[0] - 12), nextBeat, BEAT * 1.6, 0.07, "sine", 0.05); // the bass
    }
    for (const half of [0, 0.5]) {
      if (Math.random() < 0.45) voice(hz(chord[Math.floor(Math.random() * chord.length)] + 12), nextBeat + half * BEAT, BEAT * 0.5, 0.022, "sine", 0.01); // a pluck
    }
    nextBeat += BEAT;
    beat += 1;
  }
}

function scheduleBattle() {
  const BEAT = 60 / BPM.battle;
  while (nextBeat < ctx!.currentTime + 0.5) {
    const bar = BATTLE[Math.floor(beat / 4) % BATTLE.length];
    const step = beat % 4;
    drum(nextBeat, 120, 45, 0.5, 0.35); // kick on every beat: the march
    if (step === 1 || step === 3) drum(nextBeat, 220, 160, 0.08, 0.12, 0.09); // snare on 2 and 4
    if (step === 3) drum(nextBeat + BEAT / 2, 95, 70, 0.3, 0.5); // a war-drum hit before the bar turns
    for (const half of [0, 1]) voice(hz(bar.bass[step * 2 + half]), nextBeat + (half * BEAT) / 2, BEAT * 0.42, 0.075, "sawtooth", 0.01); // the bass line
    if (step === 0) bar.stab.forEach((n) => voice(hz(n), nextBeat, BEAT * 1.4, 0.03, "sawtooth", 0.02)); // the brass stab
    nextBeat += BEAT;
    beat += 1;
  }
}

/** Calm for browsing, battle for the games. Switching fades across. */
export function setMood(next: Mood) {
  if (next === mood) return;
  mood = next;
  beat = 0;
  if (timer) {
    fadeTo(0);
    nextBeat = ctx!.currentTime + 0.9;
    setTimeout(() => timer && fadeTo(ducked ? 0 : VOLUME[mood]), 900);
  }
}

function fadeTo(level: number) {
  if (!ctx || !master) return;
  master.gain.cancelScheduledValues(ctx.currentTime);
  master.gain.setTargetAtTime(level, ctx.currentTime, 0.6);
}

/** Start playing (call from a tap or key press: browsers need one before any sound). */
export function startMusic() {
  if (typeof window === "undefined") return;
  if (!ctx) build();
  void ctx!.resume();
  if (!timer) {
    nextBeat = ctx!.currentTime + 0.1;
    timer = setInterval(schedule, 200);
  }
  fadeTo(ducked ? 0 : VOLUME[mood]);
}

export function stopMusic() {
  fadeTo(0);
  if (timer) clearInterval(timer);
  timer = null;
  setTimeout(() => !timer && ctx?.suspend(), 1500);
}

/** Mute or unmute, and remember the choice on this device. */
export function setMusic(on: boolean) {
  try {
    localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    // private mode: the choice lasts until the page closes
  }
  if (on) startMusic();
  else stopMusic();
  listeners.forEach((l) => l(on));
}

export function onMusicChange(listener: (on: boolean) => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Fade the music out while a microphone records or a clip plays, and back in afterwards. */
export function duckMusic(on: boolean) {
  ducked = on;
  if (timer) fadeTo(on ? 0 : VOLUME[mood]);
}

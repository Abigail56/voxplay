// Typed wrapper around the FastAPI backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

export type Liveness = {
  passed: boolean;
  phrase: string; // what they were asked to say
  heard: string; // what speech-to-text heard
  match: number; // share of the phrase heard in order (0..1)
};

// ---------- voice game ----------

export type Me = {
  id: number;
  username: string;
  is_admin: boolean;
  has_voice: boolean;
  voice_samples: number;
  learned_samples: number; // clips learned from your games
  country: string | null; // ISO code, e.g. "NG"
  place: string | null; // e.g. "Yaba, Lagos"
  share_location: boolean; // false = hidden from other players' map
  lat: number | null;
  lon: number | null;
  total_points: number;
  turns: number;
  wins: number;
  badges: Badge[];
};

export type Badge = { id: string; emoji: string; name: string; description: string; earned: boolean; progress: number; goal: number };

export type GameMode = "yourself" | "impersonate" | "disguise" | "guess" | "telephone";

/** What the host picks before starting. */
export type RoomOptions = {
  mode: GameMode;
  rounds: number;
  speed: boolean; // 20 seconds a turn
  twists: boolean; // a silly style every turn
  crowd: boolean; // impersonate: humans vs AI ratings
  double_final: boolean; // the last round counts double
  replay: boolean; // keep each turn's clip for an hour
};

export type RoomPlayer = { user_id: number; username: string; speaker_id: number; country: string | null; points: number; turns: number };
export type Turn = {
  player_id: number;
  target_id: number; // who to sound like: yourself, another player, or (telephone) the voice before
  twist: string | null; // e.g. "🤫 Whisper it"
  double: boolean; // final round: double points
  chain_start: boolean; // telephone: the first voice of a chain
};
export type TurnResult = {
  turn_number: number;
  player_id: number;
  player: string;
  target: string;
  points: number;
  message: string;
  liveness: Liveness | null;
  speed_bonus: number;
  twist: string | null;
  double: boolean;
  sounded_like: Record<string, number>; // player -> 0-100, best first
  score: number | null;
  has_clip: boolean; // can be replayed
  votes: Record<string, string>; // Guess Who: voter -> who they named
  ai_guess: string | null;
  points_by_player: Record<string, number>;
  stars: Record<string, number>; // humans vs AI: rater -> 1-5
  ai_points: number | null;
  crowd_points: number;
  chain_from: string | null; // telephone: who started the chain
  drift: number | null; // telephone: how much it still sounds like them (0-100)
};

export type Highlight = { emoji: string; title: string; player: string; detail: string; turn_number: number; has_clip: boolean };

export type Room = RoomOptions & {
  code: string;
  host_id: number;
  status: "lobby" | "playing" | "finished";
  game_no: number;
  players: RoomPlayer[];
  turn_index: number;
  turns_total: number;
  last_result: TurnResult | null;
  history: TurnResult[];
  highlights: Highlight[];
  current_turn: Turn | null; // null for everyone but the speaker in Guess Who
  phase: "speak" | "vote" | "rate";
  you_speak: boolean; // Guess Who: you're the secret speaker
  voted: number[];
  my_vote: number | null; // your suspect (vote) or your stars (rate)
  has_clip: boolean; // there's a clip to listen to right now
  deadline: string | null; // ISO time the turn runs out
  deadline_seconds: number | null; // how long that phase lasts
  winner_ids: number[];
};

export type SoloVoice = { speaker_id: number; name: string };
export type SoloInfo = { voices: SoloVoice[]; rounds: number; right: number; points: number };
export type SoloRound = { round_id: string; options: SoloVoice[]; expires_in_seconds: number };
export type SoloGuess = { right: boolean; answer: SoloVoice; ai_guess: SoloVoice | null; points: number; message: string };
export type SoloTurn = { points: number; message: string; score: number | null; liveness: Liveness | null; sounded_like: Record<string, number> };

export type DailyState = {
  day: string;
  phrase: string;
  attempts_left: number;
  best: number | null;
  streak: number;
  ends_in_seconds: number;
  leaderboard: { username: string; country: string | null; score: number }[];
  last_attempt: { score: number; voice_score: number; phrase_match: number; heard: string; message: string } | null;
};

export type WeeklyEntry = { username: string; country: string | null; points: number; wins: number };

export type Leaderboards = {
  week_start: string;
  week_ends_in_seconds: number;
  countries: { country: string; points: number; players: number }[];
  weekly_top: WeeklyEntry[];
  last_week_champion: WeeklyEntry | null;
};

export type DashboardPlayer = {
  user_id: number;
  username: string;
  online: boolean;
  has_voice: boolean;
  country: string | null;
  place: string | null; // null if they hide their pin
  lat: number | null;
  lon: number | null;
  room_code: string | null;
  room_status: string | null;
  total_points: number;
  turns: number;
};

export type Dashboard = {
  me: number;
  online: number;
  players: DashboardPlayer[];
  rooms: { code: string; host: string; mode: GameMode; status: string; players: string[]; turn: number; turns_total: number }[];
  recent_plays: { username: string; room_code: string | null; mode: GameMode; points: number; created_at: string }[];
};

export type Place = { name: string; country: string; lat: number; lon: number };

export type AdminOverview = {
  players: number;
  online: number;
  with_voice: number;
  countries: number;
  lab_speakers: number;
  games_live: number;
  games_total: number;
  turns_total: number;
  turns_today: number;
  cheat_attempts: number;
  points_total: number;
};

export type AdminPlayer = {
  user_id: number;
  username: string;
  is_admin: boolean;
  online: boolean;
  has_voice: boolean;
  country: string | null;
  place: string | null;
  lat: number | null;
  lon: number | null;
  share_location: boolean;
  room_code: string | null;
  total_points: number;
  turns: number;
  cheat_attempts: number;
  created_at: string | null;
  last_seen_at: string | null;
};

export type AdminPlay = {
  id: number;
  username: string;
  room_code: string | null;
  mode: GameMode | "guess_vote" | "solo_guess" | "solo_impersonate" | "solo_disguise";
  points: number;
  live_passed: boolean | null;
  created_at: string;
};

export type TakeCheck = { ok: boolean; speech_seconds: number; loudness_db: number; snr_db: number; problems: string[] };

export type AdminRoom = {
  code: string;
  host: string;
  mode: GameMode;
  status: string;
  players: string[];
  turn: number;
  turns_total: number;
  created_at: string;
  updated_at: string;
};

/** ws://… for http://…, wss://… for https://… */
export function liveUrl(token: string, room?: string | null, bc?: string | null): string {
  const url = new URL("/ws", API_URL.replace(/^http/, "ws"));
  url.searchParams.set("token", token);
  if (room) url.searchParams.set("room", room);
  if (bc) url.searchParams.set("bc", bc);
  return url.toString();
}

const json = (body: unknown): RequestInit => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export type Challenge = { challenge_id: string; phrase: string; expires_in_seconds: number };

export type MapSpeaker = {
  speaker_id: number;
  name: string;
  x: number; // [-1, 1]
  y: number;
  twin: { speaker_id: number; name: string; score: number } | null;
  consistency: number | null;
};

export type VoiceMap = {
  me: number | null; // your speaker_id
  speakers: MapSpeaker[];
  samples: { speaker_id: number; x: number; y: number }[];
};

/** A recorded or uploaded clip waiting to be sent. */
export type Clip = { id: string; blob: Blob; filename: string; url: string };

// ---------- Brain Clash ----------

export type BcMode = "battle" | "namefast" | "quickfire" | "association" | "hum" | "story";
/** The games that run on Brain Clash rooms. */
export type BcGame = "brain-clash" | "beat-drop" | "story-forge";
export type BcTeam = "A" | "B";
export type BcSettings = {
  mode: BcMode;
  categories: string[]; // empty = all
  rounds: number;
  seconds: number | null; // null = the mode's default
  win_score: number | null;
  speed_bonus: boolean;
  steals: boolean;
  team_names: Record<BcTeam, string>;
  scoring: { correct: number; hard: number; list_item: number; speed_max: number; hum_bonus: number; spark: number; fire: number };
};
export type BcPlayer = { user_id: number; name: string; team: BcTeam; points: number; correct: number; online: boolean };
export type BcFeed = {
  round: number;
  team: BcTeam;
  player: string;
  user_id: number;
  said: string;
  verdict: "correct" | "wrong" | "duplicate" | "item" | "steal" | "line" | "streak";
  points: number;
  items: string[];
  flag_id: string | null;
};
/** Something the fair-play detector thinks may be cheating, waiting for (or after) the host's decision. */
export type BcFlag = {
  id: string;
  round: number;
  user_id: number;
  player: string;
  team: BcTeam;
  kind: "answer" | "hum" | "line";
  said: string;
  reasons: string[];
  suspicion: number;
  held: number;
  status: "pending" | "allowed" | "voided";
  you_decide: boolean;
};
export type BcStoryLine = { round: number; team: BcTeam; player: string; user_id: number; line: string; spark: string; used_spark: boolean; fires: number };
/** What the answer box saw, for the fair-play detector. */
export type BcSignals = { away_ms: number; pasted: boolean; typing_ms: number | null };
export type BcRound = {
  number: number;
  phase: "hum" | "open" | "steal" | "vote" | "reveal";
  question: { id: string; kind: "question" | "list" | "association" | "song" | "spark"; category: string; category_name: string; difficulty: string; prompt: string; target: number | null; points: number; spark: string | null };
  opened_at: string;
  closes_at: string;
  turn_team: BcTeam | null;
  attempts: Record<string, number>;
  found: Record<BcTeam, string[]>;
  found_count: Record<BcTeam, number>;
  scored: Record<string, number>;
  winner_team: BcTeam | null;
  reveal_until: string | null;
  tiebreak: boolean;
  you_tried: boolean;
  performer_id: number | null; // Beat Drop's hummer, Story Forge's writer
  has_clip: boolean;
  line: string | null;
  fires: number;
  you_fired: boolean;
  flag_id: string | null;
  reveal: { answer: string; explanation: string | null; source: string | null; as_of: string | null; more: string[] } | null;
};
export type BcRoom = {
  code: string;
  host_id: number;
  status: "lobby" | "playing" | "finished";
  game_no: number;
  settings: BcSettings;
  players: BcPlayer[];
  scores: Record<BcTeam, number>;
  round: BcRound | null;
  rounds_total: number;
  feed: BcFeed[];
  history: { number: number; prompt: string; answer: string; scored: Record<string, number>; tiebreak: boolean }[];
  winner: BcTeam | "draw" | null;
  finish_reason: string | null;
  notice: string | null;
  game: BcGame;
  streaks: Record<BcTeam, number>;
  flags: BcFlag[];
  story: BcStoryLine[];
  opener: string | null;
  server_time: string;
  you: number;
};
export type BcCategory = { id: string; name: string; counts: Partial<Record<BcMode, number>> };

/** A fresh random id for every answer, so the server can refuse a replayed one. */
function answerId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

// The signed-in player's token (set by useAuthStore). Sent with every request.
let authToken: string | null = null;
export function setAuthToken(token: string | null) {
  authToken = token;
}

/** Thrown for 401s, so the app can send the player back to the sign-in screen. */
export class SignedOutError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const headers = new Headers(init?.headers);
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new Error(`Cannot reach the API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join("; ")
          : `Request failed (${res.status})`;
    if (res.status === 401 && authToken) throw new SignedOutError(message);
    throw new Error(message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

/** Audio that needs the sign-in token, so it's fetched rather than linked. */
async function audio(path: string): Promise<Blob> {
  const res = await fetch(`${API_URL}${path}`, { headers: authToken ? { Authorization: `Bearer ${authToken}` } : {} });
  if (!res.ok) throw new Error("That recording isn't available.");
  return res.blob();
}

export const api = {
  /** "line" for game turns (a silly sentence), "digits" for the plain voice check. */
  challenge: (kind: "digits" | "line" = "line") => request<Challenge>(`/challenge?kind=${kind}`),

  // ---------- voice game ----------
  signup: (username: string, password: string, country: string, place: string) =>
    request<{ token: string; user: Me }>("/auth/signup", { method: "POST", ...json({ username, password, country, place }) }),
  login: (username: string, password: string) =>
    request<{ token: string; user: Me }>("/auth/login", { method: "POST", ...json({ username, password }) }),
  me: () => request<Me>("/me"),
  enrollMyVoice(consent: boolean, clips: Clip[]) {
    const form = new FormData();
    form.append("consent", String(consent));
    clips.forEach((c) => form.append("files", c.blob, c.filename));
    return request<Me>("/me/voice", { method: "POST", body: form });
  },
  checkTake(clip: Clip) {
    const form = new FormData();
    form.append("file", clip.blob, clip.filename);
    return request<TakeCheck>("/me/voice/check", { method: "POST", body: form });
  },
  setLocation: (body: { share: boolean; country?: string; place?: string }) =>
    request<Me>("/me/location", { method: "PUT", ...json(body) }),
  searchPlace: (q: string, country: string) =>
    request<Place>(`/places/search?${new URLSearchParams({ q, country })}`),
  placeHere: (lat: number, lon: number) => request<Place>(`/places/here?lat=${lat}&lon=${lon}`),
  deleteMe: () => request<void>("/me", { method: "DELETE" }),

  dashboard: () => request<Dashboard>("/dashboard"),
  voiceTwins: () => request<VoiceMap>("/voice-twins"),
  createRoom: (options: RoomOptions) => request<Room>("/rooms", { method: "POST", ...json(options) }),
  room: (code: string) => request<Room>(`/rooms/${encodeURIComponent(code)}`),
  joinRoom: (code: string) => request<Room>(`/rooms/${encodeURIComponent(code)}/join`, { method: "POST" }),
  leaveRoom: (code: string) => request<Room | null>(`/rooms/${encodeURIComponent(code)}/leave`, { method: "POST" }),
  changeRoom: (code: string, options: RoomOptions) =>
    request<Room>(`/rooms/${encodeURIComponent(code)}`, { method: "PATCH", ...json(options) }),
  vote: (code: string, suspectId: number) =>
    request<Room>(`/rooms/${encodeURIComponent(code)}/vote`, { method: "POST", ...json({ suspect_id: suspectId }) }),
  rate: (code: string, stars: number) =>
    request<Room>(`/rooms/${encodeURIComponent(code)}/rate`, { method: "POST", ...json({ stars }) }),
  advance: (code: string) => request<Room>(`/rooms/${encodeURIComponent(code)}/advance`, { method: "POST" }),
  react: (code: string, emoji: string) =>
    request<void>(`/rooms/${encodeURIComponent(code)}/react`, { method: "POST", ...json({ emoji }) }),
  /** The clip to listen to now: Guess Who's mystery voice, the impression to rate, or the voice to copy. */
  clip: (code: string) => audio(`/rooms/${encodeURIComponent(code)}/clip`),
  /** A finished turn of this game, for the replay. */
  replay: (code: string, turn: number) => audio(`/rooms/${encodeURIComponent(code)}/replay/${turn}`),

  solo: () => request<SoloInfo>("/solo"),
  soloIntro: (speakerId: number) => audio(`/solo/voices/${speakerId}/intro`),
  soloNewGuess: () => request<SoloRound>("/solo/guess", { method: "POST" }),
  soloGuessClip: (roundId: string) => audio(`/solo/guess/${encodeURIComponent(roundId)}/clip`),
  soloGuess: (roundId: string, speakerId: number) =>
    request<SoloGuess>(`/solo/guess/${encodeURIComponent(roundId)}`, { method: "POST", ...json({ speaker_id: speakerId }) }),
  soloTurn(mode: "impersonate" | "disguise", clip: Clip, challengeId: string, speakerId?: number) {
    const form = new FormData();
    form.append("mode", mode);
    form.append("file", clip.blob, clip.filename);
    form.append("challenge_id", challengeId);
    if (speakerId !== undefined) form.append("speaker_id", String(speakerId));
    return request<SoloTurn>("/solo/turn", { method: "POST", body: form });
  },

  daily: () => request<DailyState>("/daily"),
  tryDaily(clip: Clip) {
    const form = new FormData();
    form.append("file", clip.blob, clip.filename);
    return request<DailyState>("/daily", { method: "POST", body: form });
  },
  leaderboards: () => request<Leaderboards>("/leaderboards"),
  startRoom: (code: string) => request<Room>(`/rooms/${encodeURIComponent(code)}/start`, { method: "POST" }),
  admin: {
    overview: () => request<AdminOverview>("/admin/overview"),
    players: () => request<AdminPlayer[]>("/admin/players"),
    plays: (cheatsOnly = false) => request<AdminPlay[]>(`/admin/plays?cheats_only=${cheatsOnly}`),
    rooms: () => request<AdminRoom[]>("/admin/rooms"),
    endRoom: (code: string) => request<AdminRoom>(`/admin/rooms/${encodeURIComponent(code)}/end`, { method: "POST" }),
    deletePlayer: (id: number) => request<void>(`/admin/players/${id}`, { method: "DELETE" }),
  },
  bc: {
    categories: (game: BcGame = "brain-clash") => request<BcCategory[]>(`/brain-clash/categories?game=${game}`),
    create: (settings: Partial<BcSettings>, name?: string) =>
      request<BcRoom>("/brain-clash/rooms", { method: "POST", ...json({ settings, name: name || null }) }),
    room: (code: string) => request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}`),
    join: (code: string, name?: string, team?: BcTeam) =>
      request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/join`, { method: "POST", ...json({ name: name || null, team: team ?? null }) }),
    leave: (code: string) => request<void>(`/brain-clash/rooms/${encodeURIComponent(code)}/leave`, { method: "POST" }),
    settings: (code: string, settings: BcSettings) =>
      request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/settings`, { method: "PATCH", ...json(settings) }),
    team: (code: string, userId: number, team: BcTeam) =>
      request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/team`, { method: "POST", ...json({ user_id: userId, team }) }),
    shuffle: (code: string) => request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/shuffle`, { method: "POST" }),
    start: (code: string) => request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/start`, { method: "POST" }),
    advance: (code: string) => request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/advance`, { method: "POST" }),
    end: (code: string) => request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/end`, { method: "POST" }),
    answer(code: string, round: number, answer: { text: string } | { clip: Clip }, signals?: BcSignals) {
      const form = new FormData();
      form.append("round", String(round));
      form.append("answer_id", answerId());
      if ("text" in answer) form.append("text", answer.text);
      else form.append("file", answer.clip.blob, answer.clip.filename);
      if (signals) {
        form.append("away_ms", String(Math.round(signals.away_ms)));
        form.append("pasted", String(signals.pasted));
        if (signals.typing_ms !== null) form.append("typing_ms", String(Math.round(signals.typing_ms)));
      }
      return request<{ room: BcRoom; feedback: BcFeed }>(`/brain-clash/rooms/${encodeURIComponent(code)}/answer`, { method: "POST", body: form });
    },
    hum(code: string, round: number, clip: Clip) {
      const form = new FormData();
      form.append("round", String(round));
      form.append("file", clip.blob, clip.filename);
      return request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/hum`, { method: "POST", body: form });
    },
    humClip: (code: string) => audio(`/brain-clash/rooms/${encodeURIComponent(code)}/hum`),
    fire: (code: string, round: number) => request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/fire`, { method: "POST", ...json({ round }) }),
    decide: (code: string, flagId: string, allow: boolean) =>
      request<BcRoom>(`/brain-clash/rooms/${encodeURIComponent(code)}/flags/${flagId}`, { method: "POST", ...json({ allow }) }),
    react: (code: string, emoji: string) => request<void>(`/brain-clash/rooms/${encodeURIComponent(code)}/react`, { method: "POST", ...json({ emoji }) }),
  },
  takeTurn(code: string, clip: Clip, challengeId: string) {
    const form = new FormData();
    form.append("file", clip.blob, clip.filename);
    form.append("challenge_id", challengeId);
    return request<Room>(`/rooms/${encodeURIComponent(code)}/turn`, { method: "POST", body: form });
  },
};

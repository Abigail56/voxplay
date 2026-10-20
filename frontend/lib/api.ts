// Typed wrapper around the FastAPI backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

export type Candidate = { speaker_id: number; name: string; score: number };

export type Liveness = {
  passed: boolean;
  phrase: string; // what they were asked to say
  heard: string; // what speech-to-text heard
  match: number; // share of the phrase heard in order (0..1)
};

export type IdentifyResult = {
  label: string; // speaker name or "unknown"
  is_match: boolean;
  speaker_id: number | null;
  score: number;
  threshold: number;
  reason: string;
  speech_seconds: number;
  candidates: Candidate[];
  liveness: Liveness | null;
};

export type VerifyResult = {
  speaker_id: number;
  name: string;
  score: number; // how much the clip sounds like this person (cosine similarity)
  threshold: number;
  is_match: boolean;
  reason: string;
  liveness: Liveness | null;
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

export type GameMode = "yourself" | "impersonate" | "guess";

export type RoomPlayer = { user_id: number; username: string; speaker_id: number; country: string | null; points: number; turns: number };
export type Turn = { player_id: number; target_id: number };
export type TurnResult = {
  turn_number: number;
  player_id: number;
  player: string;
  target: string;
  points: number;
  message: string;
  liveness: Liveness | null;
  speed_bonus: number;
  votes: Record<string, string>; // Guess Who: voter -> who they named
  ai_guess: string | null;
  points_by_player: Record<string, number>;
};

export type Room = {
  code: string;
  host_id: number;
  mode: GameMode;
  rounds: number;
  speed: boolean;
  status: "lobby" | "playing" | "finished";
  game_no: number;
  players: RoomPlayer[];
  turn_index: number;
  turns_total: number;
  last_result: TurnResult | null;
  current_turn: Turn | null; // null for everyone but the speaker in Guess Who
  phase: "speak" | "vote";
  you_speak: boolean; // Guess Who: you're the secret speaker
  voted: number[];
  my_vote: number | null;
  has_clip: boolean;
  deadline: string | null; // ISO time the turn runs out
  winner_ids: number[];
};

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
  mode: GameMode | "guess_vote";
  points: number;
  live_passed: boolean | null;
  created_at: string;
};

export type TakeCheck = { ok: boolean; speech_seconds: number; loudness_db: number; snr_db: number; problems: string[] };

export type Rates = { threshold: number; far: number; frr: number; recognition: number; wrong: number };

export type Accuracy = {
  genuine_count: number;
  impostor_count: number;
  current: Rates;
  recommended: Rates | null;
  eer: number | null;
  eer_threshold: number | null;
  enough_data: boolean;
  min_samples: number;
  target_far: number;
  histogram: [number, number, number][]; // [bin start, genuine, impostor]
  learned_samples: number;
};

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
export function liveUrl(token: string, room?: string | null): string {
  const url = new URL("/ws", API_URL.replace(/^http/, "ws"));
  url.searchParams.set("token", token);
  if (room) url.searchParams.set("room", room);
  return url.toString();
}

const json = (body: unknown): RequestInit => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export type Challenge = { challenge_id: string; phrase: string; expires_in_seconds: number };

export type Health = {
  status: string;
  model_loaded: boolean;
  threshold: number;
  speakers: number;
  demo_retention_hours: number;
  liveness_required: boolean;
};

export type MapSpeaker = {
  speaker_id: number;
  name: string;
  is_sample: boolean;
  x: number; // [-1, 1]
  y: number;
  twin: { speaker_id: number; name: string; score: number } | null;
  consistency: number | null;
};

export type VoiceMap = { speakers: MapSpeaker[]; samples: { speaker_id: number; x: number; y: number }[] };

/** A recorded or uploaded clip waiting to be sent. */
export type Clip = { id: string; blob: Blob; filename: string; url: string };

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

export const api = {
  health: () => request<Health>("/health"),

  challenge: () => request<Challenge>("/challenge"),

  identify(clip: Clip, challengeId?: string) {
    const form = new FormData();
    form.append("file", clip.blob, clip.filename);
    if (challengeId) form.append("challenge_id", challengeId);
    return request<IdentifyResult>("/identify", { method: "POST", body: form });
  },

  verify(speakerId: number, clip: Clip, challengeId: string) {
    const form = new FormData();
    form.append("file", clip.blob, clip.filename);
    form.append("challenge_id", challengeId);
    return request<VerifyResult>(`/speakers/${speakerId}/verify`, { method: "POST", body: form });
  },

  voiceMap: () => request<VoiceMap>("/speakers/map"),

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
  createRoom: (mode: GameMode, rounds: number, speed: boolean) =>
    request<Room>("/rooms", { method: "POST", ...json({ mode, rounds, speed }) }),
  room: (code: string) => request<Room>(`/rooms/${encodeURIComponent(code)}`),
  joinRoom: (code: string) => request<Room>(`/rooms/${encodeURIComponent(code)}/join`, { method: "POST" }),
  leaveRoom: (code: string) => request<Room | null>(`/rooms/${encodeURIComponent(code)}/leave`, { method: "POST" }),
  changeRoom: (code: string, mode: GameMode, rounds: number, speed: boolean) =>
    request<Room>(`/rooms/${encodeURIComponent(code)}`, { method: "PATCH", ...json({ mode, rounds, speed }) }),
  vote: (code: string, suspectId: number) =>
    request<Room>(`/rooms/${encodeURIComponent(code)}/vote`, { method: "POST", ...json({ suspect_id: suspectId }) }),
  advance: (code: string) => request<Room>(`/rooms/${encodeURIComponent(code)}/advance`, { method: "POST" }),
  react: (code: string, emoji: string) =>
    request<void>(`/rooms/${encodeURIComponent(code)}/react`, { method: "POST", ...json({ emoji }) }),
  /** Guess Who: the secret speaker's clip (needs the sign-in token, so it's fetched, not linked). */
  async clip(code: string): Promise<Blob> {
    const res = await fetch(`${API_URL}/rooms/${encodeURIComponent(code)}/clip`, {
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
    });
    if (!res.ok) throw new Error("The clip isn't available.");
    return res.blob();
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
    accuracy: () => request<Accuracy>("/admin/accuracy"),
    setThreshold: (threshold: number) =>
      request<Accuracy>("/admin/accuracy/threshold", { method: "POST", ...json({ threshold }) }),
  },
  takeTurn(code: string, clip: Clip, challengeId: string) {
    const form = new FormData();
    form.append("file", clip.blob, clip.filename);
    form.append("challenge_id", challengeId);
    return request<Room>(`/rooms/${encodeURIComponent(code)}/turn`, { method: "POST", body: form });
  },
};

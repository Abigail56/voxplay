// Typed wrapper around the FastAPI backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

export type Speaker = {
  id: number;
  name: string;
  sample_count: number;
  consent_given_at: string;
  created_at: string;
};

export type Candidate = { speaker_id: number; name: string; score: number };

export type IdentifyResult = {
  label: string; // speaker name or "unknown"
  is_match: boolean;
  speaker_id: number | null;
  score: number;
  threshold: number;
  reason: string;
  speech_seconds: number;
  candidates: Candidate[];
};

/** A recorded or uploaded clip waiting to be sent. */
export type Clip = { id: string; blob: Blob; filename: string; url: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
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
    throw new Error(message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  listSpeakers: () => request<Speaker[]>("/speakers"),

  enroll(name: string, consent: boolean, clips: Clip[]) {
    const form = new FormData();
    form.append("name", name);
    form.append("consent", String(consent));
    clips.forEach((c) => form.append("files", c.blob, c.filename));
    return request<Speaker>("/speakers", { method: "POST", body: form });
  },

  deleteSpeaker: (id: number) => request<void>(`/speakers/${id}`, { method: "DELETE" }),

  identify(clip: Clip) {
    const form = new FormData();
    form.append("file", clip.blob, clip.filename);
    return request<IdentifyResult>("/identify", { method: "POST", body: form });
  },
};

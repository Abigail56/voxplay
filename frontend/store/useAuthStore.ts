import { create } from "zustand";

import { api, setAuthToken, type Me } from "@/lib/api";

const KEY = "voice-id-token";

// Remembering the token is a per-device convenience: if storage is blocked (private
// windows, blocked site data) the player just signs in again.
function readToken(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null) {
  try {
    if (token) localStorage.setItem(KEY, token);
    else localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}

type AuthState = {
  token: string | null;
  me: Me | null;
  ready: boolean; // false until we've checked a remembered token
  restore: () => Promise<void>;
  signIn: (mode: "signup" | "login", username: string, password: string, where?: { country: string; place: string }) => Promise<void>;
  setMe: (me: Me) => void;
  refreshMe: () => Promise<void>;
  signOut: () => void;
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  me: null,
  ready: false,

  restore: async () => {
    if (get().ready) return; // already restored (the nav and pages both ask)
    const token = readToken();
    if (!token) return set({ ready: true });
    setAuthToken(token);
    try {
      set({ token, me: await api.me(), ready: true });
    } catch {
      get().signOut(); // expired or from a restarted dev server
    }
  },

  signIn: async (mode, username, password, where) => {
    const { token, user } = await (mode === "signup"
      ? api.signup(username, password, where?.country ?? "", where?.place ?? "")
      : api.login(username, password));
    setAuthToken(token);
    writeToken(token);
    set({ token, me: user, ready: true });
  },

  setMe: (me) => set({ me }),

  refreshMe: async () => set({ me: await api.me() }),

  signOut: () => {
    setAuthToken(null);
    writeToken(null);
    set({ token: null, me: null, ready: true });
  },
}));

import { create } from "zustand";

import { api, type Clip, type Speaker } from "@/lib/api";

type SpeakerState = {
  speakers: Speaker[];
  loading: boolean;
  error: string | null;
  fetchSpeakers: () => Promise<void>;
  enroll: (name: string, consent: boolean, clips: Clip[]) => Promise<Speaker>;
  remove: (id: number) => Promise<void>;
};

// Global store for the enrolled-speaker list, shared by the enroll form and the list.
export const useSpeakerStore = create<SpeakerState>((set) => ({
  speakers: [],
  loading: false,
  error: null,

  fetchSpeakers: async () => {
    set({ loading: true, error: null });
    try {
      set({ speakers: await api.listSpeakers() });
    } catch (e) {
      set({ error: (e as Error).message });
    } finally {
      set({ loading: false });
    }
  },

  enroll: async (name, consent, clips) => {
    const speaker = await api.enroll(name, consent, clips);
    set((s) => ({ speakers: [speaker, ...s.speakers] }));
    return speaker;
  },

  remove: async (id) => {
    await api.deleteSpeaker(id);
    set((s) => ({ speakers: s.speakers.filter((sp) => sp.id !== id) }));
  },
}));

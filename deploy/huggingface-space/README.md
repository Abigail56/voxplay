---
title: Voice ID API
emoji: 🎙️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Speaker recognition API (ECAPA-TDNN + pgvector + Whisper)
---

# Voice ID API

The backend of [Voice ID](https://github.com/Abigail56): enroll people by voice and identify who is speaking.
A pretrained SpeechBrain ECAPA-TDNN model turns each clip into a 192-number voiceprint, and pgvector
finds the closest enrolled speaker by cosine similarity.

- **Liveness check:** `/identify` needs a fresh 6-digit phrase from `GET /challenge`, read out in the clip
  (checked with Whisper), so old recordings can't be replayed.
- **Voice twins:** `GET /voice-twins` shows players who sounds like whom.

- Interactive API docs: open `/docs` on this Space.
- Try it with a microphone on the portfolio's live demo page.

**Privacy:** visitors' voiceprints are deleted automatically after 24 hours, raw audio is never stored,
and anyone can delete an enrollment at any time. Built-in sample voices are LibriSpeech readers (CC BY 4.0).

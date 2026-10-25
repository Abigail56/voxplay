---
title: VOXPLAY
emoji: 🎙️
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
short_description: Voice party games that know who's talking
---

# VOXPLAY

Party games played with your voice: a SpeechBrain ECAPA-TDNN voiceprint and pgvector tell who's talking,
and Whisper checks you said the line. The site, the API (`/api`), PostgreSQL and Redis all run in this Space.

Source: [github.com/Abigail56/voxplay](https://github.com/Abigail56/voxplay)

**Data:** accounts and voiceprints live only while the Space runs; they're cleared when it restarts or wakes
from sleep. Raw audio is never stored. Built-in sample voices are LibriSpeech readers (CC BY 4.0).

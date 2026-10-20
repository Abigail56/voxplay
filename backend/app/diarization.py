"""Who spoke when: label every part of a longer recording with a speaker.

Pure logic like matching.py: the embedding model is passed in as a function
(see embedding.embed_all), so the tests run with a fake one.

How it works
------------
1. Find the speech in the recording (voiced_mask, the same detector that trims
   silence for enrollment).
2. Slide a short window (2 s, moving 1 s at a time) over the recording and turn
   the speech inside each window into a voiceprint.
3. Match each window against the enrolled speakers, like /identify does.
   Windows that match nobody are grouped into "Unknown 1", "Unknown 2", ... so
   two different strangers are still told apart.
4. Smooth out one-window blips (A A B A A -> A A A A A): a single 2 s window is
   a much noisier guess than a whole clip.
5. Give every speech frame the label of the nearest window and join runs of
   the same label into segments: "0:00-0:12 Ada, 0:12-0:30 Bayo, ...".
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from .audio import FRAME_MS, SAMPLE_RATE, voiced_mask
from .matching import l2_normalize

FRAME_SECONDS = FRAME_MS / 1000


@dataclass(frozen=True)
class Window:
    start: float  # seconds
    end: float
    centre: float
    samples: np.ndarray  # only the voiced frames inside the window


@dataclass(frozen=True)
class WindowLabel:
    label: str  # speaker name, or "Unknown 1", "Unknown 2", ...
    speaker_id: int | None
    is_match: bool
    score: float  # similarity to the enrolled speaker (or to the unknown group)


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    label: str
    speaker_id: int | None
    is_match: bool
    score: float  # average window score inside the segment


def speech_windows(
    audio: np.ndarray,
    window_seconds: float = 2.0,
    hop_seconds: float = 1.0,
    min_speech_seconds: float = 1.0,
    sample_rate: int = SAMPLE_RATE,
) -> tuple[list[Window], np.ndarray]:
    """Cut the recording into overlapping windows that contain enough speech.

    Returns the windows and the per-frame voiced mask (used later to place
    segment boundaries on the actual speech, not on window edges).
    """
    voiced = voiced_mask(audio, sample_rate)
    frame_len = int(sample_rate * FRAME_SECONDS)
    per_window = max(1, round(window_seconds / FRAME_SECONDS))
    per_hop = max(1, round(hop_seconds / FRAME_SECONDS))
    min_frames = round(min_speech_seconds / FRAME_SECONDS)

    windows: list[Window] = []
    last_start = max(0, voiced.size - per_window)
    starts = list(range(0, last_start + 1, per_hop))
    if starts and starts[-1] != last_start:
        starts.append(last_start)  # make sure the end of the recording is covered
    for first in starts:
        idx = np.flatnonzero(voiced[first : first + per_window]) + first
        if idx.size < min_frames:
            continue
        samples = np.concatenate([audio[i * frame_len : (i + 1) * frame_len] for i in idx])
        windows.append(
            Window(
                start=first * FRAME_SECONDS,
                end=(first + per_window) * FRAME_SECONDS,
                centre=float(idx.mean() + 0.5) * FRAME_SECONDS,
                samples=samples.astype(np.float32),
            )
        )
    return windows, voiced


def label_windows(
    embeddings: Sequence[np.ndarray],
    speakers: Sequence[tuple[int, str, np.ndarray]],
    threshold: float,
) -> list[WindowLabel]:
    """Match each window to the best enrolled speaker, or to a group of unknowns."""
    ids = [sid for sid, _, _ in speakers]
    names = [name for _, name, _ in speakers]
    centroids = np.stack([l2_normalize(c) for _, _, c in speakers]) if speakers else np.zeros((0, 0))

    # Running sums of each unknown group's voiceprints (their direction is the group centroid).
    unknown_sums: list[np.ndarray] = []
    labels: list[WindowLabel] = []
    for emb in embeddings:
        emb = l2_normalize(emb)
        if len(ids):
            scores = centroids @ emb
            best = int(np.argmax(scores))
            if scores[best] >= threshold:
                labels.append(WindowLabel(names[best], ids[best], True, float(scores[best])))
                continue

        # Nobody enrolled is close enough: join the closest unknown group, or start a new one.
        group_scores = [float(l2_normalize(s) @ emb) for s in unknown_sums]
        if group_scores and max(group_scores) >= threshold:
            g = int(np.argmax(group_scores))
            unknown_sums[g] = unknown_sums[g] + emb
            score = group_scores[g]
        else:
            unknown_sums.append(emb.copy())
            g, score = len(unknown_sums) - 1, 1.0
        labels.append(WindowLabel(f"Unknown {g + 1}", None, False, score))
    return labels


def smooth_labels(labels: Sequence[WindowLabel]) -> list[WindowLabel]:
    """Replace a single window that disagrees with both (agreeing) neighbours."""
    out = list(labels)
    for i in range(1, len(labels) - 1):
        prev, cur, nxt = labels[i - 1], labels[i], labels[i + 1]
        if prev.label == nxt.label != cur.label:
            out[i] = WindowLabel(prev.label, prev.speaker_id, prev.is_match, (prev.score + nxt.score) / 2)
    return out


def build_segments(
    windows: Sequence[Window],
    labels: Sequence[WindowLabel],
    voiced: np.ndarray,
    max_gap_seconds: float = 0.6,
    min_segment_seconds: float = 0.3,
) -> list[Segment]:
    """Turn labelled windows into a clean timeline of speaker segments."""
    if not windows:
        return []
    centres = np.array([w.centre for w in windows])
    # Each voiced frame takes the label of the window whose speech is centred closest to it.
    frame_times = (np.flatnonzero(voiced) + 0.5) * FRAME_SECONDS
    nearest = np.abs(frame_times[:, None] - centres[None, :]).argmin(axis=1)

    # Runs of consecutive frames with the same label, bridging short pauses.
    runs: list[tuple[float, float, str, set[int]]] = []  # (start, end, label, window indices)
    for t, w in zip(frame_times, nearest.tolist()):
        if runs and runs[-1][2] == labels[w].label and t - runs[-1][1] <= max_gap_seconds:
            start, _, label, members = runs[-1]
            runs[-1] = (start, t + FRAME_SECONDS / 2, label, members | {w})
        else:
            runs.append((t - FRAME_SECONDS / 2, t + FRAME_SECONDS / 2, labels[w].label, {w}))

    # Drop tiny runs, then join neighbours with the same label that they separated.
    merged: list[tuple[float, float, str, set[int]]] = []
    for run in runs:
        if run[1] - run[0] < min_segment_seconds:
            continue
        if merged and merged[-1][2] == run[2] and run[0] - merged[-1][1] <= max_gap_seconds:
            prev = merged.pop()
            run = (prev[0], run[1], run[2], prev[3] | run[3])
        merged.append(run)

    segments = []
    for start, end, _, members in merged:
        lab = labels[min(members)]
        score = float(np.mean([labels[m].score for m in members]))
        segments.append(Segment(round(start, 2), round(end, 2), lab.label, lab.speaker_id, lab.is_match, round(score, 4)))
    return segments


def diarize(
    audio: np.ndarray,
    embed_many: Callable[[list[np.ndarray]], list[np.ndarray]],
    speakers: Sequence[tuple[int, str, np.ndarray]],
    threshold: float,
    window_seconds: float = 2.0,
    hop_seconds: float = 1.0,
) -> list[Segment]:
    """The whole pipeline: audio in, "who spoke when" segments out."""
    windows, voiced = speech_windows(audio, window_seconds, hop_seconds, min_speech_seconds=window_seconds / 2)
    embeddings = embed_many([w.samples for w in windows]) if windows else []
    labels = smooth_labels(label_windows(embeddings, speakers, threshold))
    return build_segments(windows, labels, voiced)

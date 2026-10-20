"""How well does "who spoke when" work on real voices?

Builds conversations out of LibriSpeech clips (fetch them first with
scripts/fetch_samples.py): turns of 3-8 s at random loudness with 0.4 s pauses,
two enrolled speakers plus one stranger. Enrollment uses each speaker's first
2 clips; the conversations use only their other clips.

Score = share of talk time with the right label. The stranger counts as right
when they get one consistent "Unknown N" label. 0.25 s at each turn edge is
not scored (nobody agrees on the exact millisecond a turn changes).

    docker compose run --rm api python scripts/eval_diarize.py
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audio import SAMPLE_RATE, AudioError, decode_to_mono_16k, preprocess  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.diarization import build_segments, label_windows, smooth_labels, speech_windows  # noqa: E402
from app.embedding import EcapaEmbedder  # noqa: E402
from app.matching import compute_centroid  # noqa: E402


def conversation(rng, held, names, turns=10):
    parts, truth, t = [], [], 0.0
    for k in range(turns):
        name = names[k] if k < len(names) else names[rng.integers(len(names))]
        if truth and truth[-1][2] == name:  # no one talks twice in a row
            name = names[(names.index(name) + 1) % len(names)]
        source = held[name][rng.integers(len(held[name]))]
        n = int(rng.uniform(3, 8) * SAMPLE_RATE)
        start = rng.integers(0, max(1, source.size - n))
        chunk = source[start : start + n]
        chunk = chunk / (np.abs(chunk).max() + 1e-9) * rng.uniform(0.3, 0.9)
        parts += [chunk, np.zeros(int(0.4 * SAMPLE_RATE), np.float32)]
        truth.append((t, t + chunk.size / SAMPLE_RATE, name))
        t += chunk.size / SAMPLE_RATE + 0.4
    return np.concatenate(parts).astype(np.float32), truth


def accuracy(segments, truth, enrolled, step=0.05, edge=0.25):
    def label_at(t):
        return next((s.label for s in segments if s.start <= t <= s.end), None)

    good = total = 0
    unknown_owner: dict[str, str] = {}
    for start, end, name in truth:
        for t in np.arange(start + edge, end - edge, step):
            total += 1
            label = label_at(t)
            if name in enrolled:
                good += label == name
            elif label and label.startswith("Unknown"):
                good += unknown_owner.setdefault(label, name) == name
    return good / total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="/data/samples")
    parser.add_argument("--conversations", type=int, default=15)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    settings = get_settings()
    embedder = EcapaEmbedder(settings.model_source, settings.model_dir, settings.torch_threads)
    rng = np.random.default_rng(args.seed)
    folders = sorted(p for p in Path(args.data).iterdir() if p.is_dir())

    speakers, held = [], {}
    for i, folder in enumerate(folders):
        clips = sorted(folder.iterdir())
        vectors = []
        for clip in clips[:2]:
            try:
                vectors.append(embedder.embed(preprocess(clip.read_bytes()).samples))
            except AudioError:
                pass
        speakers.append((i, folder.name, compute_centroid(vectors)))
        held[folder.name] = [decode_to_mono_16k(c.read_bytes()) for c in clips[2:]]

    convs = []
    for _ in range(args.conversations):
        names = [f.name for f in rng.permutation(folders)[:3]]
        enrolled = set(names[:2])  # the third speaker is a stranger
        # The database also holds other people, as in real use.
        database = [s for s in speakers if s[1] in enrolled] + [s for s in speakers if s[1] not in names][:3]
        convs.append((enrolled, database, *conversation(rng, held, names)))
    minutes = sum(audio.size for *_, audio, _ in convs) / SAMPLE_RATE / 60
    print(f"Data: {len(folders)} LibriSpeech speakers, {len(convs)} conversations, {minutes:.1f} min of audio\n")
    print("window  threshold  accuracy  worst conversation  CPU per audio minute")

    for window in [1.5, 2.0, 3.0]:
        started = time.time()
        cached = []
        for *_, audio, _ in convs:
            windows, voiced = speech_windows(audio, window, window / 2, window / 2)
            cached.append((windows, voiced, embedder.embed_many([w.samples for w in windows])))
        speed = (time.time() - started) / minutes
        for threshold in [0.25, 0.30, 0.35, 0.40]:
            scores = [
                accuracy(build_segments(w, smooth_labels(label_windows(e, database, threshold)), v), truth, enrolled)
                for (enrolled, database, _, truth), (w, v, e) in zip(convs, cached)
            ]
            print(
                f" {window:.1f} s     {threshold:.2f}     {np.mean(scores) * 100:5.1f} %      "
                f"{min(scores) * 100:5.1f} %           {speed:4.1f} s"
            )


if __name__ == "__main__":
    main()

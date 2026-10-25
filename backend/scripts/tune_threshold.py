"""Pick the "unknown" threshold from real data.

For every speaker folder in --data:
  * the first --enroll clips build that speaker's centroid (like enrollment),
  * every remaining clip is a test clip.
Each test clip is scored against its OWN centroid (a "genuine" score) and
against every OTHER speaker's centroid (an "impostor" score).

A good threshold sits between the two groups. We report:
  * the Equal Error Rate (EER) threshold - false accepts == false rejects,
  * a sweep of thresholds with false-accept / false-reject rates and
    open-set identification accuracy (where some speakers are "strangers").

    docker compose run --rm api python scripts/tune_threshold.py --data /data/samples
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audio import AudioError, preprocess  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.embedding import EcapaEmbedder  # noqa: E402
from app.matching import UNKNOWN_LABEL, compute_centroid, decide, equal_error_rate, rank_candidates  # noqa: E402

AUDIO_EXT = {".wav", ".flac", ".mp3", ".webm", ".ogg", ".opus", ".m4a", ".aac", ".mp4", ".3gp"}  # phone recorders and WhatsApp voice notes too


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="/data/samples")
    parser.add_argument("--enroll", type=int, default=2, help="clips per speaker used for enrollment")
    args = parser.parse_args()

    settings = get_settings()
    embedder = EcapaEmbedder(settings.model_source, settings.model_dir, settings.torch_threads)

    folders = sorted(p for p in Path(args.data).iterdir() if p.is_dir())
    centroids: dict[str, np.ndarray] = {}
    tests: list[tuple[str, np.ndarray]] = []
    for folder in folders:
        vecs = []
        for f in sorted(f for f in folder.iterdir() if f.suffix.lower() in AUDIO_EXT):
            try:
                vecs.append(embedder.embed(preprocess(f.read_bytes()).samples))
            except AudioError as exc:
                print(f"  skipping {f.name}: {exc}")
        if len(vecs) <= args.enroll:
            continue
        centroids[folder.name] = compute_centroid(vecs[: args.enroll])
        tests += [(folder.name, v) for v in vecs[args.enroll :]]
        print(f"speaker {folder.name}: {args.enroll} enroll + {len(vecs) - args.enroll} test clips")

    names = list(centroids)
    genuine, impostor = [], []
    for owner, vec in tests:
        for name in names:
            score = float(np.dot(vec, centroids[name]))
            (genuine if name == owner else impostor).append(score)

    g, i = np.array(genuine), np.array(impostor)
    print(f"\n{len(names)} speakers, {len(g)} genuine and {len(i)} impostor comparisons")
    print(f"genuine  scores: min {g.min():.3f}  mean {g.mean():.3f}  max {g.max():.3f}")
    print(f"impostor scores: min {i.min():.3f}  mean {i.mean():.3f}  max {i.max():.3f}")
    eer, eer_t = equal_error_rate(g, i)
    print(f"EER {eer:.1%} at threshold {eer_t:.3f}")

    # Open-set check: leave each speaker out of the database in turn, so their
    # clips must come back "unknown", while everyone else's must be named.
    print("\nthreshold   FAR     FRR    open-set accuracy")
    for t in np.arange(0.20, 0.71, 0.05):
        far, frr = float(np.mean(i >= t)), float(np.mean(g < t))
        correct = total = 0
        for left_out in names:
            enrolled = [(k, n, centroids[n]) for k, n in enumerate(names) if n != left_out]
            for owner, vec in tests:
                expected = UNKNOWN_LABEL if owner == left_out else owner
                correct += decide(rank_candidates(vec, enrolled), float(t)).label == expected
                total += 1
        print(f"  {t:.2f}     {far:6.1%}  {frr:6.1%}   {correct / total:6.1%}")


if __name__ == "__main__":
    main()

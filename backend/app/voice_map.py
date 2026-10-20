"""Voice map: squash 192-number voiceprints onto a 2D picture.

Pure NumPy, like matching.py.

- PCA finds the two directions in which the enrolled voices differ the most and
  places every voiceprint along them. People who sound alike land close together.
  It is only a shadow of 192 dimensions, so distances on the map are approximate.
- The "voice twin" of each speaker is found with the real cosine similarity on
  all 192 numbers, so it is exact even when the map looks different.
- "Consistency" is how similar a speaker's own enrollment clips are to their
  voiceprint. Low consistency means noisy or very different recordings.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .matching import l2_normalize


@dataclass(frozen=True)
class Twin:
    speaker_id: int
    name: str
    score: float


@dataclass(frozen=True)
class MapSpeaker:
    speaker_id: int
    name: str
    x: float
    y: float
    twin: Twin | None
    consistency: float | None  # mean similarity of their samples to their voiceprint


@dataclass(frozen=True)
class MapSample:
    speaker_id: int
    x: float
    y: float


def pca_2d(vectors: np.ndarray) -> np.ndarray:
    """Project each row onto the two directions in which the rows differ the most.

    The result is scaled so the largest coordinate is 1 (fits a [-1, 1] square).
    """
    vectors = np.asarray(vectors, dtype=np.float64)
    if vectors.shape[0] == 0:
        return np.zeros((0, 2))
    mean = vectors.mean(axis=0)
    centred = vectors - mean
    if vectors.shape[0] < 2 or not np.any(centred):
        return np.zeros((vectors.shape[0], 2))
    # The right singular vectors are the principal directions.
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    axes = vt[:2]
    if axes.shape[0] < 2:
        axes = np.vstack([axes, np.zeros_like(axes[0])])
    # SVD signs are arbitrary; fix them so the map doesn't flip between requests.
    for i, axis in enumerate(axes):
        if axis[np.argmax(np.abs(axis))] < 0:
            axes[i] = -axis
    coords = centred @ axes.T
    scale = float(np.abs(coords).max())
    return coords / scale if scale > 0 else coords


def voice_map(
    speakers: Sequence[tuple[int, str, np.ndarray]],
    samples: Sequence[tuple[int, np.ndarray]],
) -> tuple[list[MapSpeaker], list[MapSample]]:
    """Map positions, voice twins and consistency for every speaker and sample."""
    if not speakers:
        return [], []
    centroids = np.stack([l2_normalize(c) for _, _, c in speakers])
    sample_vecs = np.stack([l2_normalize(v) for _, v in samples]) if samples else np.zeros((0, centroids.shape[1]))

    # Voiceprints and individual clips share one map, so you can see each person's clips
    # gather around their voiceprint.
    coords = pca_2d(np.vstack([centroids, sample_vecs]))
    centroid_xy, sample_xy = coords[: len(speakers)], coords[len(speakers) :]

    similarity = centroids @ centroids.T
    np.fill_diagonal(similarity, -np.inf)

    out = []
    for i, (sid, name, _) in enumerate(speakers):
        twin = None
        if len(speakers) > 1:
            j = int(np.argmax(similarity[i]))
            twin = Twin(speakers[j][0], speakers[j][1], round(float(similarity[i, j]), 4))
        own = [k for k, (owner, _) in enumerate(samples) if owner == sid]
        consistency = round(float(np.mean(sample_vecs[own] @ centroids[i])), 4) if own else None
        out.append(MapSpeaker(sid, name, round(float(centroid_xy[i, 0]), 4), round(float(centroid_xy[i, 1]), 4), twin, consistency))

    dots = [MapSample(owner, round(float(x), 4), round(float(y), 4)) for (owner, _), (x, y) in zip(samples, sample_xy)]
    return out, dots

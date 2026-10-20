"""Pure matching logic: no database, no ML model, no I/O.

Everything here works on plain NumPy vectors, which keeps it easy to unit test.

How speaker matching works
--------------------------
1. Every voice clip is turned into a 192-number "embedding" (a voiceprint) by the
   ECAPA-TDNN model. Clips from the same person point in roughly the same direction.
2. A speaker can have several enrollment clips. We average their (normalised)
   embeddings into one "centroid" per speaker.
3. To identify a new clip we compute the cosine similarity between its embedding
   and every centroid. Cosine similarity is 1.0 for identical directions,
   about 0 for unrelated voices.
4. The best-scoring speaker wins, but only if the score is at least the
   threshold. Otherwise the answer is "unknown".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

UNKNOWN_LABEL = "unknown"


def l2_normalize(vector: Sequence[float] | np.ndarray) -> np.ndarray:
    """Scale a vector to length 1 so that a dot product equals cosine similarity."""
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0 or not np.isfinite(norm):
        raise ValueError("Cannot normalise a zero or non-finite vector")
    return arr / norm


def cosine_similarity(a: Sequence[float] | np.ndarray, b: Sequence[float] | np.ndarray) -> float:
    """Cosine similarity in [-1, 1]. Higher means more alike."""
    a_arr, b_arr = l2_normalize(a), l2_normalize(b)
    if a_arr.shape != b_arr.shape:
        raise ValueError(f"Shape mismatch: {a_arr.shape} vs {b_arr.shape}")
    # Clip to guard against tiny floating point overshoots such as 1.0000001.
    return float(np.clip(np.dot(a_arr, b_arr), -1.0, 1.0))


def compute_centroid(embeddings: Iterable[Sequence[float] | np.ndarray]) -> np.ndarray:
    """Average several embeddings of one speaker into a single unit-length voiceprint.

    Each embedding is normalised first so that a long, loud clip does not
    outweigh a short, quiet one.
    """
    normalised = [l2_normalize(e) for e in embeddings]
    if not normalised:
        raise ValueError("At least one embedding is required")
    return l2_normalize(np.mean(np.stack(normalised), axis=0))


@dataclass(frozen=True)
class Candidate:
    speaker_id: int
    name: str
    score: float


@dataclass(frozen=True)
class Decision:
    label: str  # speaker name, or "unknown"
    speaker_id: int | None
    score: float  # best cosine similarity (our confidence score)
    is_match: bool
    reason: str


def rank_candidates(
    query: Sequence[float] | np.ndarray,
    speakers: Iterable[tuple[int, str, Sequence[float] | np.ndarray]],
) -> list[Candidate]:
    """Score a query embedding against (id, name, centroid) tuples, best first."""
    candidates = [
        Candidate(speaker_id=sid, name=name, score=cosine_similarity(query, centroid))
        for sid, name, centroid in speakers
    ]
    return sorted(candidates, key=lambda c: c.score, reverse=True)


def decide(candidates: Sequence[Candidate], threshold: float, min_margin: float = 0.0) -> Decision:
    """Turn ranked candidates into a final answer.

    - No enrolled speakers           -> unknown
    - Best score below the threshold -> unknown (voice is not close enough to anyone)
    - Best and runner-up too close   -> unknown (only if min_margin > 0; avoids
      confidently picking between two similar voices)
    - Otherwise                      -> the best speaker
    """
    if not candidates:
        return Decision(UNKNOWN_LABEL, None, 0.0, False, "No speakers are enrolled yet.")

    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
    best = ranked[0]

    if best.score < threshold:
        return Decision(
            UNKNOWN_LABEL,
            None,
            best.score,
            False,
            f"Best match '{best.name}' scored {best.score:.3f}, below the threshold {threshold:.3f}.",
        )

    if min_margin > 0 and len(ranked) > 1:
        margin = best.score - ranked[1].score
        if margin < min_margin:
            return Decision(
                UNKNOWN_LABEL,
                None,
                best.score,
                False,
                f"'{best.name}' and '{ranked[1].name}' are too close to call "
                f"(margin {margin:.3f} < {min_margin:.3f}).",
            )

    return Decision(best.name, best.speaker_id, best.score, True, "Score is above the threshold.")


def equal_error_rate(genuine: Sequence[float], impostor: Sequence[float]) -> tuple[float, float]:
    """Find the threshold where false accepts and false rejects are (nearly) equal.

    genuine  = scores of clips compared with their *own* speaker
    impostor = scores of clips compared with *other* speakers
    Returns (eer, threshold). Used by scripts/tune_threshold.py.
    """
    g = np.asarray(genuine, dtype=np.float64)
    i = np.asarray(impostor, dtype=np.float64)
    if g.size == 0 or i.size == 0:
        raise ValueError("Need both genuine and impostor scores")

    best_gap, best = np.inf, (1.0, 0.0)
    for t in np.unique(np.concatenate([g, i])):
        far = float(np.mean(i >= t))  # impostors wrongly accepted
        frr = float(np.mean(g < t))  # genuine speakers wrongly rejected
        gap = abs(far - frr)
        if gap < best_gap:
            best_gap, best = gap, ((far + frr) / 2, float(t))
    return best

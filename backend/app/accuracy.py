"""How accurate is the AI on real players, and where should the threshold be?

Every real turn gives two numbers (see adaptation.record_scores):
- genuine:  how much the clip sounded like the person who really spoke;
- impostor: how much it sounded like the closest *other* player.

At a threshold t:
- recognition rate: genuine >= t AND genuine > impostor, i.e. the game names the right person;
- wrong player named: impostor >= t AND impostor > genuine;
- false reject rate (FRR): genuine < t, i.e. a real player wouldn't be recognised;
- false accept rate (FAR): impostor >= t. This is the stranger test: had the speaker
  NOT been enrolled, the game would have named the closest other player. It's the
  number that protects against naming a stranger, so the threshold is tuned on it.

The recommendation is the *lowest* threshold that keeps false accepts at or below
TARGET_FAR: as forgiving to real players as possible, without naming the wrong person.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .matching import equal_error_rate

TARGET_FAR = 0.01  # at most 1 wrong person in 100
MIN_SAMPLES = 20  # of each kind, before recommending anything
SEARCH = np.round(np.arange(0.20, 0.801, 0.01), 2)  # thresholds considered
BIN = 0.05  # histogram bins


@dataclass(frozen=True)
class Rates:
    threshold: float
    far: float
    frr: float
    recognition: float
    wrong: float


@dataclass(frozen=True)
class Report:
    genuine_count: int
    impostor_count: int
    current: Rates
    recommended: Rates | None  # None until there's enough data
    eer: float | None
    eer_threshold: float | None
    enough_data: bool
    histogram: list[tuple[float, int, int]]  # (bin start, genuine count, impostor count)


def rates(pairs: Sequence[tuple[float, float | None]], t: float) -> Rates:
    genuine = np.array([g for g, _ in pairs])
    impostor = np.array([i for _, i in pairs if i is not None])
    best_other = np.array([-1.0 if i is None else i for _, i in pairs])
    return Rates(
        threshold=round(float(t), 2),
        far=round(float(np.mean(impostor >= t)), 4) if impostor.size else 0.0,
        frr=round(float(np.mean(genuine < t)), 4) if genuine.size else 0.0,
        recognition=round(float(np.mean((genuine >= t) & (genuine > best_other))), 4) if genuine.size else 0.0,
        wrong=round(float(np.mean((best_other >= t) & (best_other > genuine))), 4) if genuine.size else 0.0,
    )


def report(pairs: Sequence[tuple[float, float | None]], current: float) -> Report:
    genuine = [g for g, _ in pairs]
    impostor = [i for _, i in pairs if i is not None]
    enough = len(genuine) >= MIN_SAMPLES and len(impostor) >= MIN_SAMPLES
    recommended = eer = eer_t = None
    if genuine and impostor:
        eer, eer_t = equal_error_rate(genuine, impostor)
        eer, eer_t = round(eer, 4), round(eer_t, 3)
    if enough:
        ok = [t for t in SEARCH if rates(pairs, t).far <= TARGET_FAR]
        recommended = rates(pairs, ok[0] if ok else SEARCH[-1])
    edges = np.round(np.arange(-0.2, 1.0001, BIN), 2)
    g_hist, _ = np.histogram(np.clip(genuine, -0.2, 0.999), bins=edges) if genuine else (np.zeros(len(edges) - 1, int), None)
    i_hist, _ = np.histogram(np.clip(impostor, -0.2, 0.999), bins=edges) if impostor else (np.zeros(len(edges) - 1, int), None)
    return Report(
        genuine_count=len(genuine),
        impostor_count=len(impostor),
        current=rates(pairs, current) if pairs else Rates(round(current, 2), 0.0, 0.0, 0.0, 0.0),
        recommended=recommended,
        eer=eer,
        eer_threshold=eer_t,
        enough_data=enough,
        histogram=[(float(e), int(g), int(i)) for e, g, i in zip(edges[:-1], g_hist, i_hist)],
    )

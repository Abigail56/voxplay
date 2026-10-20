import numpy as np
import pytest

from app.matching import (
    UNKNOWN_LABEL,
    Candidate,
    compute_centroid,
    cosine_similarity,
    decide,
    equal_error_rate,
    l2_normalize,
    rank_candidates,
)


def test_l2_normalize_gives_unit_length():
    v = l2_normalize([3.0, 4.0])
    assert np.allclose(v, [0.6, 0.8])
    assert np.isclose(np.linalg.norm(v), 1.0)


def test_l2_normalize_rejects_zero_vector():
    with pytest.raises(ValueError):
        l2_normalize([0.0, 0.0])


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ([1, 0], [1, 0], 1.0),  # same direction
        ([1, 0], [0, 1], 0.0),  # unrelated
        ([1, 0], [-1, 0], -1.0),  # opposite
        ([1, 0], [5, 0], 1.0),  # length does not matter
    ],
)
def test_cosine_similarity(a, b, expected):
    assert cosine_similarity(a, b) == pytest.approx(expected)


def test_cosine_similarity_shape_mismatch():
    with pytest.raises(ValueError):
        cosine_similarity([1, 0], [1, 0, 0])


def test_centroid_is_unit_length_average_direction():
    c = compute_centroid([[1, 0], [0, 1]])
    assert np.allclose(c, [np.sqrt(0.5), np.sqrt(0.5)])


def test_centroid_weights_each_clip_equally():
    # A "loud" clip (long vector) must not dominate a "quiet" one.
    assert np.allclose(compute_centroid([[100, 0], [0, 1]]), compute_centroid([[1, 0], [0, 1]]))


def test_centroid_needs_embeddings():
    with pytest.raises(ValueError):
        compute_centroid([])


def test_rank_candidates_orders_best_first():
    speakers = [(1, "Ada", [1, 0, 0]), (2, "Bayo", [0, 1, 0]), (3, "Chi", [0.7, 0.7, 0])]
    ranked = rank_candidates([0.9, 0.1, 0], speakers)
    assert [c.name for c in ranked] == ["Ada", "Chi", "Bayo"]
    assert ranked[0].score > ranked[1].score > ranked[2].score


def test_decide_returns_best_speaker_above_threshold():
    d = decide([Candidate(2, "Bayo", 0.30), Candidate(1, "Ada", 0.82)], threshold=0.4)
    assert d.is_match and d.label == "Ada" and d.speaker_id == 1
    assert d.score == pytest.approx(0.82)


def test_decide_unknown_below_threshold():
    d = decide([Candidate(1, "Ada", 0.25)], threshold=0.4)
    assert not d.is_match
    assert d.label == UNKNOWN_LABEL and d.speaker_id is None
    assert d.score == pytest.approx(0.25)  # still reported, for transparency


def test_decide_score_equal_to_threshold_is_a_match():
    assert decide([Candidate(1, "Ada", 0.4)], threshold=0.4).is_match


def test_decide_with_no_speakers():
    d = decide([], threshold=0.4)
    assert d.label == UNKNOWN_LABEL and not d.is_match


def test_decide_margin_rejects_ambiguous_result():
    cands = [Candidate(1, "Ada", 0.71), Candidate(2, "Bayo", 0.69)]
    assert decide(cands, threshold=0.4).label == "Ada"  # margin check off by default
    assert decide(cands, threshold=0.4, min_margin=0.05).label == UNKNOWN_LABEL


def test_end_to_end_with_synthetic_voiceprints():
    """Two 'people' whose clips scatter around their own true voiceprint."""
    rng = np.random.default_rng(0)
    ada_true, bayo_true, stranger = (l2_normalize(rng.normal(size=192)) for _ in range(3))

    def clip(true_vec):
        return l2_normalize(true_vec + rng.normal(scale=0.04, size=192))

    speakers = [
        (1, "Ada", compute_centroid([clip(ada_true) for _ in range(3)])),
        (2, "Bayo", compute_centroid([clip(bayo_true) for _ in range(3)])),
    ]
    assert decide(rank_candidates(clip(ada_true), speakers), 0.4).label == "Ada"
    assert decide(rank_candidates(clip(bayo_true), speakers), 0.4).label == "Bayo"
    assert decide(rank_candidates(clip(stranger), speakers), 0.4).label == UNKNOWN_LABEL


def test_equal_error_rate_perfect_separation():
    eer, threshold = equal_error_rate(genuine=[0.7, 0.8, 0.9], impostor=[0.1, 0.2, 0.3])
    assert eer == 0.0
    assert 0.3 < threshold <= 0.7


def test_equal_error_rate_overlap():
    eer, _ = equal_error_rate(genuine=[0.2, 0.8, 0.9], impostor=[0.1, 0.3, 0.85])
    assert 0.0 < eer < 0.5

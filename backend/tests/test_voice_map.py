import numpy as np
import pytest

from app.voice_map import pca_2d, voice_map


def unit(*xs):
    v = np.zeros(192)
    for i, x in enumerate(xs):
        v[i] = x
    return v / np.linalg.norm(v)


def test_pca_keeps_close_things_close_and_fits_in_unit_square():
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=192), rng.normal(size=192)
    pts = np.stack([a, a + 0.01, b, b + 0.01])
    xy = pca_2d(pts)
    assert xy.shape == (4, 2) and np.abs(xy).max() == pytest.approx(1.0)
    assert np.linalg.norm(xy[0] - xy[1]) < 0.1 < np.linalg.norm(xy[0] - xy[2])


def test_pca_with_one_point_is_the_centre():
    assert pca_2d(np.ones((1, 192))).tolist() == [[0.0, 0.0]]


def test_twins_and_consistency():
    ada, ada2, bayo = unit(1, 0.1), unit(1, 0.2), unit(0, 1)
    speakers = [(1, "Ada", ada), (2, "Ada's sister", ada2), (3, "Bayo", bayo)]
    samples = [(1, unit(1, 0.05)), (1, unit(1, 0.15)), (3, unit(0, 1))]
    points, dots = voice_map(speakers, samples)

    by_name = {p.name: p for p in points}
    assert by_name["Ada"].twin.name == "Ada's sister"
    assert by_name["Bayo"].twin.name in {"Ada", "Ada's sister"}
    assert by_name["Ada"].consistency > 0.99 and by_name["Bayo"].consistency == pytest.approx(1.0)
    assert by_name["Ada's sister"].consistency is None  # no samples stored
    assert len(dots) == 3 and {d.speaker_id for d in dots} == {1, 3}


def test_single_speaker_has_no_twin():
    points, _ = voice_map([(1, "Ada", unit(1))], [])
    assert points[0].twin is None and (points[0].x, points[0].y) == (0.0, 0.0)


def test_empty_map():
    assert voice_map([], []) == ([], [])

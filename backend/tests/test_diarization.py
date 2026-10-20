"""Who spoke when, with tone 'voices' and the fake embedder (no PyTorch)."""

import numpy as np

from app.diarization import WindowLabel, diarize, label_windows, smooth_labels, speech_windows
from app.embedding import embed_all

from .helpers import FakeEmbedder, tone_sequence

EMB = FakeEmbedder()


def embed_many(clips):
    return embed_all(EMB, clips)


def voiceprint(freq):
    return EMB.embed(tone_sequence((freq, 1.0), gap=0))


SPEAKERS = [(1, "Ada", voiceprint(200)), (2, "Bayo", voiceprint(600))]


def test_speech_windows_skip_silence():
    audio = tone_sequence((200, 3.0), gap=3.0)  # 3 s of speech, then 3 s of silence
    windows, voiced = speech_windows(audio, window_seconds=2.0, hop_seconds=1.0)
    assert windows and all(w.start < 3.0 for w in windows)
    assert voiced.sum() * 0.03 < 3.5


def test_two_enrolled_speakers_and_a_stranger():
    audio = tone_sequence((200, 4.0), (600, 4.0), (1500, 3.0), (200, 3.0))
    segments = diarize(audio, embed_many, SPEAKERS, threshold=0.3)

    assert [s.label for s in segments] == ["Ada", "Bayo", "Unknown 1", "Ada"]
    assert segments[0].speaker_id == 1 and segments[0].is_match
    assert segments[2].speaker_id is None and not segments[2].is_match
    # Boundaries land near the real turn changes (4.5 s, 9 s, 12.5 s) within a second.
    for seg, start in zip(segments[1:], [4.5, 9.0, 12.5]):
        assert abs(seg.start - start) < 1.0


def test_two_strangers_are_told_apart():
    audio = tone_sequence((1500, 4.0), (2500, 4.0), (1500, 4.0))
    labels = [s.label for s in diarize(audio, embed_many, SPEAKERS, threshold=0.3)]
    assert labels == ["Unknown 1", "Unknown 2", "Unknown 1"]


def test_nobody_enrolled_still_splits_voices():
    audio = tone_sequence((200, 4.0), (600, 4.0))
    assert [s.label for s in diarize(audio, embed_many, [], threshold=0.3)] == ["Unknown 1", "Unknown 2"]


def test_silence_gives_no_segments():
    assert diarize(np.zeros(16_000 * 5, dtype=np.float32), embed_many, SPEAKERS, threshold=0.3) == []


def test_single_window_blip_is_smoothed_away():
    a, b = WindowLabel("Ada", 1, True, 0.8), WindowLabel("Bayo", 2, True, 0.4)
    assert [w.label for w in smooth_labels([a, a, b, a, a])] == ["Ada"] * 5
    assert [w.label for w in smooth_labels([a, b, b, a])] == ["Ada", "Bayo", "Bayo", "Ada"]  # real turns stay


def test_label_windows_threshold():
    labels = label_windows([voiceprint(200), voiceprint(205), voiceprint(3000)], SPEAKERS, threshold=0.5)
    assert [w.label for w in labels] == ["Ada", "Ada", "Unknown 1"]

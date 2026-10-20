"""Make each player's voiceprint better as they play.

Enrollment happens once, in one room, on one phone. Real games happen elsewhere:
on the bus, in a noisy hall, on a friend's phone. So every turn where the AI was
*already confident* it was you (live check passed, recognised as you, similarity
at least LEARN_MIN_SCORE) is added to your voiceprint as a "game" sample, and the
average is recomputed. Your voiceprint slowly learns how you sound in real life.

Safety rails, so a voiceprint can't drift towards someone else:
- only turns where you were clearly recognised as yourself are used;
- impersonation and Guess Who clips are never used (those voices are disguised);
- only the most recent MAX_LEARNED_SAMPLES game clips are kept; enrollment clips always stay.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .matching import compute_centroid, l2_normalize
from .models import Speaker, VoiceSample


def inconsistent_takes(vectors: Sequence[np.ndarray], min_similarity: float) -> list[int]:
    """Indices of enrollment takes that don't sound like the rest (someone else, or lots of noise).

    Each take is compared with the average of the *other* takes.
    """
    if len(vectors) < 2:
        return []
    unit = [l2_normalize(v) for v in vectors]
    bad = []
    for i, v in enumerate(unit):
        others = compute_centroid([u for j, u in enumerate(unit) if j != i])
        if float(np.dot(v, others)) < min_similarity:
            bad.append(i)
    return bad


async def learn(session: AsyncSession, speaker_id: int, vector: np.ndarray, speech_seconds: float, keep: int) -> None:
    """Add a confidently recognised clip to the speaker's voiceprint (caller commits)."""
    session.add(VoiceSample(speaker_id=speaker_id, embedding=l2_normalize(vector).tolist(), speech_seconds=speech_seconds, source="game"))
    await session.flush()
    stale = (
        await session.exec(
            select(VoiceSample.id)
            .where(VoiceSample.speaker_id == speaker_id, VoiceSample.source == "game")
            .order_by(col(VoiceSample.created_at).desc(), col(VoiceSample.id).desc())
            .offset(keep)
        )
    ).all()
    if stale:
        await session.exec(delete(VoiceSample).where(col(VoiceSample.id).in_(stale)))
    vectors = (await session.exec(select(VoiceSample.embedding).where(VoiceSample.speaker_id == speaker_id))).all()
    speaker = await session.get(Speaker, speaker_id)
    if speaker is not None and vectors:
        speaker.embedding = compute_centroid(vectors).tolist()
        session.add(speaker)


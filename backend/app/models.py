from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .embedding import EMBEDDING_DIM


class Speaker(Base):
    """An enrolled person. `embedding` is the centroid of all their samples.

    Privacy by design: we store only voiceprints (192 numbers per clip), never
    the raw recordings.
    """

    __tablename__ = "speakers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    consent_given_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Built-in demo voices (public LibriSpeech readers): never expire, can't be deleted by visitors.
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # When this enrollment is deleted automatically (NULL = never). Used by the public demo.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    samples: Mapped[list["VoiceSample"]] = relationship(
        back_populates="speaker", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        # HNSW index for fast cosine-distance search once there are many speakers.
        Index(
            "ix_speakers_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class VoiceSample(Base):
    """The embedding of one enrollment clip (kept so the centroid can be recomputed)."""

    __tablename__ = "voice_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    speaker_id: Mapped[int] = mapped_column(ForeignKey("speakers.id", ondelete="CASCADE"), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    speech_seconds: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    speaker: Mapped[Speaker] = relationship(back_populates="samples")

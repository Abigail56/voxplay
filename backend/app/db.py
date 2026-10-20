from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Enable pgvector and create tables. (A bigger project would use Alembic migrations.)"""
    from . import models  # noqa: F401  - registers the tables on Base.metadata

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # create_all only creates missing tables. These bring databases made by an
        # older version of this app up to date (Alembic would do this in a bigger project).
        await conn.execute(text("ALTER TABLE speakers ADD COLUMN IF NOT EXISTS is_sample BOOLEAN NOT NULL DEFAULT false"))
        await conn.execute(text("ALTER TABLE speakers ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_speakers_expires_at ON speakers (expires_at)"))


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session

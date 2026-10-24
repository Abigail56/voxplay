from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


def create_engine(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Enable pgvector and create tables. (A bigger project would use Alembic migrations.)"""
    from . import models  # noqa: F401  - registers the tables on SQLModel.metadata

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(SQLModel.metadata.create_all)
        # create_all only creates missing tables. These bring databases made by an
        # older version of this app up to date (Alembic would do this in a bigger project).
        await conn.execute(text("ALTER TABLE speakers ADD COLUMN IF NOT EXISTS is_sample BOOLEAN NOT NULL DEFAULT false"))
        await conn.execute(text("ALTER TABLE speakers ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_speakers_expires_at ON speakers (expires_at)"))
        # game_plays from before accounts: plays now belong to a user and room, location is optional.
        await conn.execute(text("ALTER TABLE game_plays ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"))
        await conn.execute(text("ALTER TABLE game_plays ADD COLUMN IF NOT EXISTS room_code VARCHAR(20)"))
        await conn.execute(text("ALTER TABLE game_plays ALTER COLUMN lat DROP NOT NULL"))
        await conn.execute(text("ALTER TABLE game_plays ALTER COLUMN lon DROP NOT NULL"))
        # Players' country and area (sign-up asks for them), and cheat attempts for the admin page.
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS country VARCHAR(2)"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS place VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN share_location SET DEFAULT true"))
        await conn.execute(text("ALTER TABLE game_plays ADD COLUMN IF NOT EXISTS live_passed BOOLEAN"))
        await conn.execute(text("ALTER TABLE voice_samples ADD COLUMN IF NOT EXISTS source VARCHAR(10) NOT NULL DEFAULT 'enroll'"))
        await conn.execute(text("ALTER TABLE game_plays ADD COLUMN IF NOT EXISTS score DOUBLE PRECISION"))
        # Fair-play flags on finished Brain Clash / Beat Drop / Story Forge matches.
        await conn.execute(text("ALTER TABLE bc_results ADD COLUMN IF NOT EXISTS flags JSON NOT NULL DEFAULT '[]'"))


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session

import aiosqlite
from contextlib import asynccontextmanager
from config import DATABASE_PATH


@asynccontextmanager
async def get_db():
    """Async context manager — read/write with WAL mode for safe concurrency with the Discord bot."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db

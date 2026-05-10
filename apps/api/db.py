"""Async psycopg3 connection pool factory for FastAPI handlers.

Pool config respects the Supabase port-6543 PgBouncer transaction mode
(see CLAUDE.md "Database: psycopg3 only" + "Database: connection ports"):

  - poolclass = NullPool: PgBouncer IS the pool; psycopg should hand back
    every connection on release.
  - prepare_threshold = None: disables prepared statements. PgBouncer
    transaction mode rotates server-side connections per-statement, which
    causes 'prepared statement does not exist' crashes under load
    (Supabase issue #39227, asyncpg shares the same failure mode).
"""

import os
from collections.abc import AsyncIterator
from typing import cast

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncNullConnectionPool

_pool: AsyncNullConnectionPool | None = None


def get_pool() -> AsyncNullConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncNullConnectionPool(
            conninfo=os.environ["DATABASE_URL_POOLED"],
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=False,
        )
    return _pool


async def get_conn() -> AsyncIterator[AsyncConnection[DictRow]]:
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn:
        # psycopg-pool's typing doesn't propagate the row_factory=dict_row from kwargs.
        yield cast(AsyncConnection[DictRow], conn)

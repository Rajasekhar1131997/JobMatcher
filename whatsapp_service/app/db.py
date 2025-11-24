import os
import json
import asyncio
import ssl
from typing import Any, Dict, List, Optional
import asyncpg


class Database:
    """Simple asyncpg wrapper for persisting jobs."""

    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 5):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.pool.Pool] = None
        self.sslmode = os.getenv("PG_SSLMODE", "require")
        self.connect_timeout = float(os.getenv("PG_CONNECT_TIMEOUT", "10"))

    async def connect(self) -> None:
        ssl_ctx = None
        if self.sslmode and self.sslmode != "disable":
            ssl_ctx = ssl.create_default_context()
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
            timeout=self.connect_timeout,
            ssl=ssl_ctx,
        )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,
                    confirmation_code TEXT UNIQUE,
                    source_channel TEXT,
                    chat_id TEXT,
                    title TEXT NOT NULL,
                    pay_rate TEXT NOT NULL,
                    pay_type TEXT NOT NULL,
                    location TEXT NOT NULL,
                    shift_times TEXT NOT NULL,
                    contact_phone TEXT NOT NULL,
                    business_name TEXT NOT NULL,
                    business_type TEXT,
                    min_qualification TEXT,
                    description TEXT,
                    language_requirement TEXT,
                    images JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def add_job(self, payload: Dict[str, Any]) -> None:
        if not self.pool:
            return
        images = payload.get("images") or []
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO jobs (
                    confirmation_code, source_channel, chat_id,
                    title, pay_rate, pay_type, location, shift_times,
                    contact_phone, business_name, business_type,
                    min_qualification, description, language_requirement, images
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8,
                    $9, $10, $11, $12, $13, $14, $15
                )
                ON CONFLICT (confirmation_code) DO NOTHING;
                """,
                payload.get("confirmation_code"),
                payload.get("source_channel"),
                payload.get("chat_id"),
                payload.get("title"),
                payload.get("pay_rate"),
                payload.get("pay_type"),
                payload.get("location"),
                payload.get("shift_times"),
                payload.get("contact_phone"),
                payload.get("business_name"),
                payload.get("business_type"),
                payload.get("min_qualification"),
                payload.get("description"),
                payload.get("language_requirement"),
                json.dumps(images),
            )

    async def list_jobs(self, source: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.pool:
            return []
        async with self.pool.acquire() as conn:
            if source:
                rows = await conn.fetch(
                    """
                    SELECT * FROM jobs
                    WHERE source_channel = $1
                    ORDER BY created_at DESC;
                    """,
                    source,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM jobs ORDER BY created_at DESC;"
                )
        return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row: asyncpg.Record) -> Dict[str, Any]:
        d = dict(row)
        # images is stored as jsonb; ensure list
        if isinstance(d.get("images"), str):
            try:
                d["images"] = json.loads(d["images"])
            except json.JSONDecodeError:
                d["images"] = []
        return d

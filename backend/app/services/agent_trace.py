"""
NutriAgent — Agent Trace Service.

Unified observability with context manager support.

Usage:
    async with trace_agent(user_id, "RecommendationAgent") as t:
        t.input = "request summary"
        result = await agent.recommend(...)
        t.output = "output summary"
        t.tokens = 1500
    # auto: start_run → finish_run (or error_run on exception)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from app.database import get_session
from app.models.agent_observability import AgentRun
from sqlalchemy import select, text as sa_text


class TraceContext:
    """Mutable context for a single agent run."""

    def __init__(self, run_id: UUID, agent_name: str, user_id: UUID):
        self.run_id = run_id
        self.agent_name = agent_name
        self.user_id = user_id
        self.input = ""
        self.output = ""
        self.tokens = 0
        self._start = time.perf_counter()

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)


@asynccontextmanager
async def trace_agent(user_id: UUID, agent_name: str):
    """Context manager: auto start/finish/error an agent run."""
    run_id = uuid4()
    ctx = TraceContext(run_id, agent_name, user_id)

    # Start
    try:
        async with get_session() as db:
            db.add(AgentRun(
                id=run_id, user_id=user_id, agent_name=agent_name,
                status="running",
            ))
            await db.commit()
    except Exception:
        pass

    try:
        yield ctx
        # Success
        async with get_session() as db:
            r = await db.get(AgentRun, run_id)
            if r:
                r.status = "completed"
                r.input_summary = ctx.input[:500] if ctx.input else None
                r.output_summary = ctx.output[:500] if ctx.output else None
                r.latency_ms = ctx.latency_ms
                r.token_usage = ctx.tokens or None
                await db.commit()
    except Exception as e:
        # Error
        try:
            async with get_session() as db:
                r = await db.get(AgentRun, run_id)
                if r:
                    r.status = "error"
                    r.error_message = str(e)[:500]
                    r.latency_ms = ctx.latency_ms
                    await db.commit()
        except Exception:
            pass
        raise


async def get_recent_runs(user_id: UUID, limit: int = 20) -> list:
    """Get recent agent runs for a user."""
    async with get_session() as db:
        r = await db.execute(
            select(AgentRun)
            .where(AgentRun.user_id == user_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return [
            {"agent": row.agent_name, "status": row.status, "latency_ms": row.latency_ms,
             "input": (row.input_summary or "")[:100], "created": str(row.created_at)}
            for row in r.scalars().all()
        ]


async def cleanup_old_runs(days: int = 90) -> int:
    """Delete agent runs older than N days. Returns count deleted."""
    async with get_session() as db:
        r = await db.execute(
            sa_text("DELETE FROM agent_runs WHERE created_at < now() - make_interval(days => :d)"),
            {"d": days},
        )
        await db.commit()
        return r.rowcount

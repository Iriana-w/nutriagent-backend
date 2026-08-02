"""
NutriAgent Backend — Memory Store Tool.

pgvector-based persistent memory storage for the Memory Agent.

Operations:
- store: Insert a new memory with vector embedding
- search: Semantic similarity search via pgvector cosine distance
- update: Update memory metadata (importance, access_count, decay_factor)
- delete: Soft-delete or hard-delete memories
- consolidate: Find and merge similar memories, prune low-importance ones
- get_profile: Aggregate all preference memories for a user

Ebbinghaus Forgetting Curve:
- decay_factor = e^(-time_since_creation / half_life)
- half_life defaults to 30 days for normal memories, 90 for important ones
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.agent_memory import AgentMemory, AgentMemoryLink, AgentPreferenceSignal, MemoryTypeEnum
from app.tools.embedding import embedding_gen


class MemoryStore:
    """pgvector-backed persistent memory storage."""

    # Half-life in days for Ebbinghaus decay
    DEFAULT_HALF_LIFE_DAYS = 30
    IMPORTANT_HALF_LIFE_DAYS = 90

    # =========================================================================
    # STORE
    # =========================================================================

    async def store_memory(
        self,
        user_id: uuid.UUID,
        memory_type: str,  # fact | preference | episode | summary | goal
        title: str,
        content: str,
        *,
        embedding: list[float] | None = None,
        key_facts: list[dict] | None = None,
        importance: float = 0.5,
        confidence: float = 1.0,
        source: str = "manual",
        source_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> AgentMemory:
        """
        Store a new memory with vector embedding.

        If no embedding is provided, one is generated from the content.
        """
        # Generate embedding if not provided
        if embedding is None:
            embed_text = f"{title}\n{content}"
            embedding = await embedding_gen.embed_text(embed_text)

        embedding_str = embedding_gen.embedding_to_pgvector_string(embedding)

        # Merge tags into key_facts
        facts = key_facts or []
        if tags:
            facts.append({"type": "tags", "values": tags})

        async with get_session() as db:
            memory = AgentMemory(
                user_id=user_id,
                memory_type=MemoryTypeEnum(memory_type),
                title=title,
                content=content,
                key_facts=facts,
                importance=importance,
                confidence=confidence,
                source=source,
                source_id=source_id,
                decay_factor=1.0,
                access_count=0,
            )

            db.add(memory)
            await db.flush()

            # Set embedding via raw SQL (pgvector column)
            await db.execute(
                text(
                    "UPDATE agent_memories SET embedding = :emb::vector "
                    "WHERE id = :mem_id"
                ),
                {"emb": embedding_str, "mem_id": memory.id},
            )

            await db.commit()
            await db.refresh(memory)

        return memory

    async def store_batch(
        self,
        memories: list[dict],
    ) -> list[AgentMemory]:
        """
        Store multiple memories efficiently.
        Each dict: {user_id, memory_type, title, content, ...}
        """
        results = []
        for mem in memories:
            m = await self.store_memory(**mem)
            results.append(m)
        return results

    # =========================================================================
    # SEARCH (pgvector similarity)
    # =========================================================================

    async def search_semantic(
        self,
        user_id: uuid.UUID,
        query_text: str,
        *,
        query_embedding: list[float] | None = None,
        memory_type: str | None = None,
        min_importance: float = 0.0,
        min_confidence: float = 0.0,
        top_k: int = 10,
        include_expired: bool = False,
    ) -> list[dict]:
        """
        Semantic search over user memories using pgvector cosine similarity.

        Uses the <=> operator (cosine distance) for vector comparison.
        Results are ordered by similarity (closest first).
        """
        # Generate query embedding if not provided
        if query_embedding is None:
            query_embedding = await embedding_gen.embed_text(query_text)

        emb_str = embedding_gen.embedding_to_pgvector_string(query_embedding)

        async with get_session() as db:
            # Build conditions
            conditions = [f"user_id = :uid"]
            params: dict = {"uid": str(user_id), "emb": emb_str, "limit": top_k}

            if memory_type:
                conditions.append("memory_type = :mtype")
                params["mtype"] = memory_type

            if min_importance > 0:
                conditions.append("importance >= :min_imp")
                params["min_imp"] = min_importance

            if min_confidence > 0:
                conditions.append("confidence >= :min_conf")
                params["min_conf"] = min_confidence

            if not include_expired:
                conditions.append("(expires_at IS NULL OR expires_at > now())")

            where_clause = " AND ".join(conditions)

            # pgvector cosine similarity: 1 - cosine_distance
            # Using cosine_distance (<=>) for ordering
            sql = text(
                f"""
                SELECT
                    id, user_id, memory_type, title, content, key_facts,
                    importance, confidence, access_count,
                    last_accessed_at, decay_factor,
                    source, source_id,
                    created_at, updated_at, expires_at,
                    1 - (embedding <=> :emb::vector) AS similarity
                FROM agent_memories
                WHERE {where_clause}
                ORDER BY embedding <=> :emb::vector
                LIMIT :limit
                """
            )

            result = await db.execute(sql, params)
            rows = result.fetchall()

            memories = []
            for row in rows:
                memories.append({
                    "id": row.id,
                    "user_id": row.user_id,
                    "memory_type": row.memory_type.value if hasattr(row.memory_type, 'value') else row.memory_type,
                    "title": row.title,
                    "content": row.content,
                    "key_facts": row.key_facts or [],
                    "importance": float(row.importance) if row.importance else 0.5,
                    "confidence": float(row.confidence) if row.confidence else 1.0,
                    "access_count": row.access_count or 0,
                    "last_accessed_at": row.last_accessed_at,
                    "decay_factor": float(row.decay_factor) if row.decay_factor else 1.0,
                    "source": row.source,
                    "source_id": row.source_id,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "expires_at": row.expires_at,
                    "similarity_score": float(row.similarity) if row.similarity else 0.0,
                })

                # Update access count and last_accessed_at
                await db.execute(
                    text(
                        "UPDATE agent_memories SET access_count = access_count + 1, "
                        "last_accessed_at = now() WHERE id = :mid"
                    ),
                    {"mid": row.id},
                )

            await db.commit()

        return memories

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update_memory(
        self,
        memory_id: uuid.UUID,
        **kwargs,
    ) -> bool:
        """Update memory fields. Returns True if updated."""
        valid_fields = {
            "importance", "confidence", "decay_factor",
            "title", "content", "key_facts", "expires_at",
        }
        update_data = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not update_data:
            return False

        async with get_session() as db:
            result = await db.execute(
                text(
                    "UPDATE agent_memories SET "
                    + ", ".join(f"{k} = :{k}" for k in update_data)
                    + ", updated_at = now() WHERE id = :mid"
                ),
                {**update_data, "mid": str(memory_id)},
            )
            await db.commit()
            return result.rowcount > 0

    # =========================================================================
    # DELETE
    # =========================================================================

    async def delete_memory(self, memory_id: uuid.UUID) -> bool:
        """Hard-delete a memory. Returns True if deleted."""
        async with get_session() as db:
            result = await db.execute(
                text("DELETE FROM agent_memories WHERE id = :mid"),
                {"mid": str(memory_id)},
            )
            await db.commit()
            return result.rowcount > 0

    async def delete_user_memories(
        self,
        user_id: uuid.UUID,
        memory_type: str | None = None,
    ) -> int:
        """Delete all (or type-filtered) memories for a user. Returns count deleted."""
        async with get_session() as db:
            conditions = ["user_id = :uid"]
            params = {"uid": str(user_id)}
            if memory_type:
                conditions.append("memory_type = :mtype")
                params["mtype"] = memory_type

            result = await db.execute(
                text(f"DELETE FROM agent_memories WHERE {' AND '.join(conditions)}"),
                params,
            )
            await db.commit()
            return result.rowcount

    # =========================================================================
    # CONSOLIDATION
    # =========================================================================

    async def find_similar_memories(
        self,
        user_id: uuid.UUID,
        similarity_threshold: float = 0.85,
        memory_type: str | None = None,
    ) -> list[tuple[uuid.UUID, uuid.UUID, float]]:
        """
        Find pairs of similar memories for potential merging.
        Uses pgvector to compute pairwise cosine similarities.

        Returns list of (memory_id_1, memory_id_2, similarity).
        """
        async with get_session() as db:
            conditions = ["a.user_id = :uid", "a.id < b.id", "a.user_id = b.user_id"]
            params = {"uid": str(user_id), "threshold": similarity_threshold}

            if memory_type:
                conditions.append("a.memory_type = :mtype")
                conditions.append("b.memory_type = :mtype")
                params["mtype"] = memory_type

            where_clause = " AND ".join(conditions)

            sql = text(
                f"""
                SELECT
                    a.id AS id1, b.id AS id2,
                    1 - (a.embedding <=> b.embedding) AS similarity
                FROM agent_memories a
                JOIN agent_memories b ON {where_clause}
                WHERE 1 - (a.embedding <=> b.embedding) >= :threshold
                ORDER BY similarity DESC
                LIMIT 100
                """
            )

            result = await db.execute(sql, params)
            rows = result.fetchall()
            return [(row.id1, row.id2, float(row.similarity)) for row in rows]

    async def merge_memories(
        self,
        memory_id_1: uuid.UUID,
        memory_id_2: uuid.UUID,
    ) -> uuid.UUID | None:
        """
        Merge two similar memories into one. Keeps the older one,
        updates its content and importance, deletes the newer one.
        Returns the surviving memory_id.
        """
        async with get_session() as db:
            m1 = await db.get(AgentMemory, memory_id_1)
            m2 = await db.get(AgentMemory, memory_id_2)
            if not m1 or not m2:
                return None

            # Keep the older one as the base
            if (m2.created_at and m1.created_at and m2.created_at < m1.created_at) or \
               not m1.created_at:
                m1, m2 = m2, m1  # swap so m1 is older

            survivor_id = m1.id
            absorbed_id = m2.id

            # Merge key facts (dedup)
            merged_facts = list(m1.key_facts or [])
            existing_keys = {f.get("type", "") + f.get("value", "") for f in merged_facts}
            for fact in (m2.key_facts or []):
                key = fact.get("type", "") + fact.get("value", "")
                if key not in existing_keys:
                    merged_facts.append(fact)
                    existing_keys.add(key)

            # Update importance: weighted average
            total_weight = m1.access_count + m2.access_count + 1
            new_importance = (
                (m1.importance * (m1.access_count + 1) +
                 m2.importance * (m2.access_count + 1)) / total_weight
            )

            # Update confidence: max
            new_confidence = max(m1.confidence, m2.confidence)

            # Update content: concatenate if different
            new_content = m1.content
            if m2.content not in m1.content:
                new_content = m1.content + "\n---\n" + m2.content

            await db.execute(
                text(
                    "UPDATE agent_memories SET "
                    "key_facts = :facts, importance = :imp, confidence = :conf, "
                    "content = :content, access_count = access_count + :ac, "
                    "updated_at = now() "
                    "WHERE id = :mid"
                ),
                {
                    "facts": merged_facts,
                    "imp": min(1.0, new_importance),
                    "conf": min(1.0, new_confidence),
                    "content": new_content[:5000],
                    "ac": m2.access_count,
                    "mid": str(survivor_id),
                },
            )

            # Create a link record
            link = AgentMemoryLink(
                source_memory_id=survivor_id,
                target_memory_id=absorbed_id,
                relation="merged_into",
                weight=1.0,
            )
            db.add(link)

            # Delete absorbed memory
            await db.delete(m2)

            await db.commit()

        return survivor_id

    async def apply_decay(self, user_id: uuid.UUID) -> int:
        """
        Apply Ebbinghaus forgetting curve decay to all memories for a user.

        decay_factor = e^(-days_since_creation / half_life)
        - Normal memories: half_life = 30 days
        - Important memories (importance > 0.7): half_life = 90 days

        Returns number of memories updated.
        """
        async with get_session() as db:
            sql = text(
                """
                UPDATE agent_memories
                SET decay_factor =
                    CASE
                        WHEN importance > 0.7
                        THEN EXP(
                            -EXTRACT(EPOCH FROM (now() - created_at)) / 86400.0
                            / :important_hl
                        )
                        ELSE EXP(
                            -EXTRACT(EPOCH FROM (now() - created_at)) / 86400.0
                            / :default_hl
                        )
                    END,
                    updated_at = now()
                WHERE user_id = :uid
                """
            )
            result = await db.execute(
                sql,
                {
                    "uid": str(user_id),
                    "default_hl": self.DEFAULT_HALF_LIFE_DAYS,
                    "important_hl": self.IMPORTANT_HALF_LIFE_DAYS,
                },
            )
            await db.commit()
            return result.rowcount

    async def prune_low_importance(
        self,
        user_id: uuid.UUID,
        min_importance: float = 0.05,
        max_memories: int = 1000,
    ) -> int:
        """
        Remove low-importance, heavily decayed memories.
        Also enforces max_memories cap by removing the lowest-importance ones.

        Returns total number of pruned memories.
        """
        pruned = 0

        async with get_session() as db:
            # 1. Delete memories below importance threshold that are also
            # heavily decayed (decay_factor < 0.1 means >90% forgotten)
            result = await db.execute(
                text(
                    "DELETE FROM agent_memories WHERE user_id = :uid "
                    "AND importance < :min_imp AND decay_factor < 0.1"
                ),
                {"uid": str(user_id), "min_imp": min_importance},
            )
            pruned += result.rowcount

            # 2. If still over max, delete the lowest-importance ones
            count_result = await db.execute(
                text("SELECT COUNT(*) FROM agent_memories WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            current_count = count_result.scalar()

            if current_count > max_memories:
                excess = current_count - max_memories
                result = await db.execute(
                    text(
                        "DELETE FROM agent_memories WHERE id IN ("
                        "SELECT id FROM agent_memories WHERE user_id = :uid "
                        "ORDER BY (importance * decay_factor) ASC LIMIT :excess"
                        ")"
                    ),
                    {"uid": str(user_id), "excess": excess},
                )
                pruned += result.rowcount

            await db.commit()

        return pruned

    # =========================================================================
    # PREFERENCE AGGREGATION
    # =========================================================================

    async def get_all_preferences(
        self,
        user_id: uuid.UUID,
        include_decayed: bool = False,
    ) -> list[dict]:
        """
        Get all preference-type memories for a user, sorted by
        effective importance (importance * decay_factor).
        """
        async with get_session() as db:
            conditions = ["user_id = :uid", "memory_type = 'preference'"]
            if not include_decayed:
                conditions.append("decay_factor > 0.1")

            result = await db.execute(
                text(
                    f"SELECT id, title, content, key_facts, importance, "
                    f"confidence, decay_factor, source, created_at "
                    f"FROM agent_memories "
                    f"WHERE {' AND '.join(conditions)} "
                    f"ORDER BY (importance * decay_factor) DESC "
                    f"LIMIT 500"
                ),
                {"uid": str(user_id)},
            )
            rows = result.fetchall()
            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "content": row.content,
                    "key_facts": row.key_facts or [],
                    "importance": float(row.importance),
                    "confidence": float(row.confidence),
                    "decay_factor": float(row.decay_factor),
                    "source": row.source,
                    "created_at": row.created_at,
                }
                for row in rows
            ]

    async def count_memories(self, user_id: uuid.UUID) -> int:
        """Count total memories for a user."""
        async with get_session() as db:
            result = await db.execute(
                text("SELECT COUNT(*) FROM agent_memories WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            return result.scalar() or 0


# Singleton
memory_store = MemoryStore()

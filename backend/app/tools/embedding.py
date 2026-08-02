"""
NutriAgent Backend — Embedding Tool.

Vercel Serverless compatible. No local model dependencies.

Priority:
  1. Remote OpenAI-compatible API (text-embedding-3-small → 1536d)
  2. Fallback keyword hash (always available, zero dependencies)

pgvector compatibility: all backends output exactly 1536-dim vectors.

Usage:
    embedding_gen = EmbeddingGenerator()
    vec = await embedding_gen.embed_text("query text")
"""

from __future__ import annotations

import hashlib
import re

import httpx

from app.config import settings


class EmbeddingGenerator:
    """Multi-backend embedding generator for pgvector semantic search."""

    TARGET_DIM = 1536  # Must match VECTOR(1536) in schema

    def __init__(self):
        self._backend = None  # "remote" | "fallback"

    async def _ensure_backend(self):
        """Detect available backend once."""
        if self._backend is not None:
            return

        # Remote API: any OpenAI-compatible /embeddings endpoint (DeepSeek, OpenAI, etc.)
        if settings.OPENAI_API_KEY:
            self._backend = "remote"
            return

        # Fallback: keyword hashing (always available, zero dependencies)
        self._backend = "fallback"

    async def embed_text(self, text: str) -> list[float]:
        """Generate a 1536-dim embedding vector."""
        await self._ensure_backend()

        if self._backend == "remote":
            return await self._embed_remote(text)
        else:
            return self._embed_fallback(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
        await self._ensure_backend()
        if self._backend == "remote":
            return [await self._embed_remote(t) for t in texts]
        else:
            return [self._embed_fallback(t) for t in texts]

    # ── Remote backend ──────────────────────────────

    async def _embed_remote(self, text: str) -> list[float]:
        """Call OpenAI-compatible embeddings API (DeepSeek, OpenAI, etc.)."""
        base_url = (settings.OPENAI_BASE_URL or "https://api.deepseek.com/v1").rstrip("/")
        url = f"{base_url}/embeddings"

        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            response = await client.post(
                url,
                json={
                    "model": settings.DEFAULT_LLM_MODEL or "deepseek-chat",
                    "input": text,
                    "encoding_format": "float",
                },
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            return self._pad_to_target(data["data"][0]["embedding"])

    # ── Fallback backend ────────────────────────────

    @staticmethod
    def _embed_fallback(text: str) -> list[float]:
        """
        Keyword-hash embedding. Each token maps to a deterministic position
        in a 1536-dim unit vector. Cosine similarity finds exact/partial
        keyword matches — not semantic, but works without any API.
        """
        tokens = re.findall(r"[一-鿿]|[a-zA-Z]+", text.lower())
        dim = EmbeddingGenerator.TARGET_DIM
        vector = [0.0] * dim

        for token in tokens:
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % dim
            weight = min(1.0, len(token) / 10)
            vector[idx] += weight

        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    # ── Padding ─────────────────────────────────────

    @classmethod
    def _pad_to_target(cls, embedding: list[float]) -> list[float]:
        """Pad or truncate to TARGET_DIM."""
        if len(embedding) >= cls.TARGET_DIM:
            return embedding[:cls.TARGET_DIM]
        return embedding + [0.0] * (cls.TARGET_DIM - len(embedding))

    # ── pgvector Serialization ──────────────────────

    @classmethod
    def embedding_to_pgvector_string(cls, embedding: list[float]) -> str:
        """Convert Python list to pgvector string '[1.0,2.0,...]'."""
        embedding = cls._pad_to_target(embedding)
        return f"[{','.join(str(v) for v in embedding)}]"

    @staticmethod
    def pgvector_string_to_list(vector_str: str) -> list[float]:
        """Convert pgvector string back to Python list."""
        numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", vector_str)
        return [float(n) for n in numbers]


# Singleton
embedding_gen = EmbeddingGenerator()

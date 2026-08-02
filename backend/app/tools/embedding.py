"""
NutriAgent Backend — Embedding Tool.

Generates text embeddings with multi-backend support:

1. Local (default): sentence-transformers + all-MiniLM-L6-v2 (free, no API key)
2. Remote: OpenAI-compatible API (DeepSeek doesn't support this yet,
   but OpenAI, local vLLM/ollama with embedding endpoints work)

Auto-detection: tries local model first, falls back to remote API if
OPENAI_API_KEY is configured and the base URL supports /embeddings.
"""

from __future__ import annotations

from app.config import settings


class EmbeddingGenerator:
    """
    Multi-backend embedding generator.

    Priority:
    1. Local sentence-transformers model (free, runs on CPU)
    2. Remote OpenAI-compatible API
    3. Simple hash-based fallback (always works, zero dependencies)
    """

    # Local model: small, fast, multilingual, good enough for semantic search
    LOCAL_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
    LOCAL_MODEL_DIM = 384
    TARGET_DIM = 1536  # pgvector schema expects 1536d

    def __init__(self):
        self._local_model = None
        self._backend = None  # "local" | "remote" | "fallback"

    async def _ensure_backend(self):
        """Detect available backend once."""
        if self._backend is not None:
            return

        # 1. Try local sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(self.LOCAL_MODEL_NAME)
            self._backend = "local"
            return
        except (ImportError, Exception):
            pass

        # 2. Try remote API (only if API key is set and not DeepSeek)
        api_key = settings.OPENAI_API_KEY
        base_url = settings.OPENAI_BASE_URL or ""
        if api_key and "deepseek" not in base_url.lower():
            self._backend = "remote"
            return

        # 3. Fallback to keyword hashing
        self._backend = "fallback"

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate an embedding vector for a single text.
        Always returns a TARGET_DIM (1536) vector regardless of backend.
        """
        await self._ensure_backend()

        if self._backend == "local":
            return await self._embed_local(text)
        elif self._backend == "remote":
            return await self._embed_remote(text)
        else:
            return self._embed_fallback(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        await self._ensure_backend()

        if self._backend == "local":
            return [await self._embed_local(t) for t in texts]
        elif self._backend == "remote":
            return [await self._embed_remote(t) for t in texts]
        else:
            return [self._embed_fallback(t) for t in texts]

    # --- Local backend ---

    async def _embed_local(self, text: str) -> list[float]:
        """Generate embedding using local sentence-transformers model."""
        import asyncio
        # sentence-transformers is synchronous, run in thread pool
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, self._local_model.encode, text)
        return self._pad_to_target(raw.tolist())

    # --- Remote backend ---

    async def _embed_remote(self, text: str) -> list[float]:
        """Generate embedding via OpenAI-compatible API."""
        import httpx

        api_key = settings.OPENAI_API_KEY
        base_url = (settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        url = f"{base_url}/embeddings"

        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            response = await client.post(
                url,
                json={
                    "model": "text-embedding-3-small",
                    "input": text,
                    "encoding_format": "float",
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            raw = data["data"][0]["embedding"]
            return self._pad_to_target(raw)

    # --- Fallback backend (TF-IDF-like keyword hash) ---

    @staticmethod
    def _embed_fallback(text: str) -> list[float]:
        """
        Simple keyword-based vector generation.
        Each Chinese character / English word maps to a deterministic
        position in the 1536-dim vector. Not as good as real embeddings
        but enables pgvector similarity search to work without any API.
        """
        import hashlib
        import re

        # Tokenize: split Chinese chars and English words
        tokens = re.findall(r"[一-鿿]|[a-zA-Z]+", text.lower())

        dim = EmbeddingGenerator.TARGET_DIM
        vector = [0.0] * dim

        for token in tokens:
            # Deterministic position for each token
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % dim
            # Weight: longer tokens = more signal
            weight = min(1.0, len(token) / 10)
            vector[idx] += weight

        # Normalize to unit vector for cosine similarity
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    # --- Padding ---

    @classmethod
    def _pad_to_target(cls, embedding: list[float]) -> list[float]:
        """Pad or truncate embedding to TARGET_DIM."""
        dim = cls.TARGET_DIM
        if len(embedding) > dim:
            return embedding[:dim]
        elif len(embedding) < dim:
            return embedding + [0.0] * (dim - len(embedding))
        return embedding

    # --- Serialization ---

    @classmethod
    def embedding_to_pgvector_string(cls, embedding: list[float]) -> str:
        """Convert a Python list to pgvector-compatible string '[1.0,2.0,...]'."""
        embedding = cls._pad_to_target(embedding)
        values = ",".join(str(v) for v in embedding)
        return f"[{values}]"

    @staticmethod
    def pgvector_string_to_list(vector_str: str) -> list[float]:
        """Convert pgvector string back to Python list."""
        import re
        numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", vector_str)
        return [float(n) for n in numbers]


# Singleton
embedding_gen = EmbeddingGenerator()

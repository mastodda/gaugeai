"""
embedding_client.py — Embedding API client with disk caching.

Handles:
  - Embedding single texts and batches via OpenAI's API
  - Disk caching of reference set anchor embeddings (computed once, reused forever)
  - In-memory caching of response embeddings within a pipeline run

The cache is critical for reference sets: you embed 30 anchor statements once
(6 sets × 5 anchors) and never call the API for them again.
"""

import json
import hashlib
import numpy as np
from pathlib import Path


class EmbeddingClient:
    """
    Thin wrapper around OpenAI's embedding API with caching.

    Usage:
        client = EmbeddingClient(model="text-embedding-3-small")
        vec = client.embed("I'd probably buy this.")
        vecs = client.embed_batch(["text1", "text2", "text3"])
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        cache_dir: str | Path = ".cache/embeddings",
        api_key: str | None = None,
    ):
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, np.ndarray] = {}
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def _cache_key(self, text: str) -> str:
        """Deterministic cache key from model + text."""
        raw = f"{self.model}::{text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _load_from_disk(self, key: str) -> np.ndarray | None:
        """Try to load a cached embedding from disk."""
        path = self.cache_dir / f"{key}.npy"
        if path.exists():
            return np.load(path)
        return None

    def _save_to_disk(self, key: str, vec: np.ndarray):
        """Save an embedding to disk cache."""
        path = self.cache_dir / f"{key}.npy"
        np.save(path, vec)

    def embed(self, text: str) -> np.ndarray:
        """
        Embed a single text string. Checks memory cache, then disk, then API.
        """
        key = self._cache_key(text)

        # Memory cache
        if key in self._memory_cache:
            return self._memory_cache[key]

        # Disk cache
        cached = self._load_from_disk(key)
        if cached is not None:
            self._memory_cache[key] = cached
            return cached

        # API call
        response = self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        vec = np.array(response.data[0].embedding, dtype=np.float32)

        # Cache both
        self._memory_cache[key] = vec
        self._save_to_disk(key, vec)
        return vec

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """
        Embed multiple texts. Uses cache for any already-seen texts,
        batches the rest into a single API call.
        """
        results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._memory_cache:
                results[i] = self._memory_cache[key]
                continue
            cached = self._load_from_disk(key)
            if cached is not None:
                self._memory_cache[key] = cached
                results[i] = cached
                continue
            uncached_indices.append(i)
            uncached_texts.append(text)

        if uncached_texts:
            response = self._client.embeddings.create(
                model=self.model,
                input=uncached_texts,
            )
            for j, idx in enumerate(uncached_indices):
                vec = np.array(response.data[j].embedding, dtype=np.float32)
                key = self._cache_key(uncached_texts[j])
                self._memory_cache[key] = vec
                self._save_to_disk(key, vec)
                results[idx] = vec

        return results

    def embed_reference_sets(self, config_path: str | Path) -> dict:
        """
        Load reference sets from config and embed all anchors.
        Returns dict: {set_name: {rating_int: np.ndarray}}.

        This is the primary setup step — run once, results are cached to disk.
        """
        with open(config_path) as f:
            config = json.load(f)

        all_texts = []
        index_map = []  # (set_name, rating_int)

        for set_name, set_data in config["sets"].items():
            for rating_str, text in set_data["anchors"].items():
                all_texts.append(text)
                index_map.append((set_name, int(rating_str)))

        print(f"  Embedding {len(all_texts)} anchor statements...")
        vectors = self.embed_batch(all_texts)

        result = {}
        for (set_name, rating), vec in zip(index_map, vectors):
            if set_name not in result:
                result[set_name] = {}
            result[set_name][rating] = vec

        print(f"  Done. {len(result)} reference sets ready.")
        return result

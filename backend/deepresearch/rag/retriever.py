"""Chroma 向量检索 + 简单重排。

核心能力：
  1. add_page(url, text, task_id)  → chunk → embed → store in Chroma
  2. query(query_text, n)          → retrieve top-n relevant chunks
  3. dedup                         → 同一 URL 不重复入库（联动 Episodic 记忆）

向量库选型说明（对应 PRD §8.4）：
  选 Chroma：嵌入式、pip 一行装好、零额外部署。
  Embedding：chromadb 默认 DefaultEmbeddingFunction（ONNX all-MiniLM-L6-v2，首次运行自动下载 ~23MB）。
"""

from __future__ import annotations

import uuid
from functools import lru_cache

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from deepresearch.common.logging import get_logger
from deepresearch.rag.chunking import chunk_text
from deepresearch.schemas.models import Source

log = get_logger("rag.retriever")

COLLECTION_NAME = "deepresearch"


class ChromaRetriever:
    def __init__(self, run_id: str, chroma_path: str) -> None:
        self.run_id = run_id
        self._seen_urls: set[str] = set()

        client = chromadb.PersistentClient(path=chroma_path)
        self._col = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=DefaultEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )
        log.info("chroma_ready", collection=COLLECTION_NAME, path=chroma_path)

    # ── Ingest ────────────────────────────────────────────────────────────────

    def add_page(
        self,
        url: str,
        text: str,
        task_id: str,
        title: str = "",
    ) -> int:
        """Chunk, embed and store a page. Returns number of chunks added (0 if deduped)."""
        if url in self._seen_urls:
            log.info("chroma_skip_dedup", url=url)
            return 0

        self._seen_urls.add(url)
        chunks = chunk_text(text)
        if not chunks:
            return 0

        ids = [str(uuid.uuid4()) for _ in chunks]
        metas = [
            {
                "run_id": self.run_id,
                "task_id": task_id,
                "url": url,
                "title": title,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]

        self._col.add(documents=chunks, metadatas=metas, ids=ids)
        log.info("chroma_add", url=url, chunks=len(chunks))
        return len(chunks)

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        task_id: str | None = None,
    ) -> list[dict]:
        """
        Retrieve top-n relevant chunks for query_text.
        Returns list of {text, url, title, score}.
        """
        # Chroma requires multiple metadata filters to be wrapped in $and
        conditions: list[dict] = [{"run_id": self.run_id}]
        if task_id:
            conditions.append({"task_id": task_id})
        where = conditions[0] if len(conditions) == 1 else {"$and": conditions}

        total = self._col.count()
        if total == 0:
            return []

        n = min(n_results, total)
        try:
            result = self._col.query(
                query_texts=[query_text],
                n_results=n,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            log.warning("chroma_query_failed", error=str(exc))
            return []

        docs = result["documents"][0]
        metas = result["metadatas"][0]
        dists = result["distances"][0]

        hits = []
        for doc, meta, dist in zip(docs, metas, dists):
            hits.append({
                "text": doc,
                "url": meta.get("url", ""),
                "title": meta.get("title", ""),
                "score": round(1 - dist, 4),  # cosine distance → similarity
            })

        # Simple rerank: boost chunks that contain query keywords
        keywords = query_text.lower().split()
        for h in hits:
            kw_bonus = sum(1 for kw in keywords if kw in h["text"].lower()) * 0.02
            h["score"] = min(1.0, h["score"] + kw_bonus)

        hits.sort(key=lambda x: x["score"], reverse=True)
        log.info("chroma_query", query=query_text[:50], results=len(hits))
        return hits

    def known_urls(self) -> set[str]:
        return set(self._seen_urls)


@lru_cache(maxsize=32)
def get_retriever(run_id: str, chroma_path: str) -> ChromaRetriever:
    return ChromaRetriever(run_id=run_id, chroma_path=chroma_path)

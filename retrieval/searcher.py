"""
Hybrid search engine.

Combines BM25 (lexical) and semantic (vector) retrieval
using Reciprocal Rank Fusion for stable, high-quality results.
"""

from typing import Optional
from dataclasses import dataclass

from .config import RetrievalConfig
from .store import Store
from .tokenizer import tokenize


@dataclass
class SearchResult:
    """A single search result with score and metadata."""

    chunk_id: int
    text: str
    source_file: str
    header_path: list[str]
    domain: Optional[str]
    tags: list[str]
    score: float
    bm25_rank: Optional[int] = None
    semantic_rank: Optional[int] = None

    @property
    def context_label(self) -> str:
        parts = [self.source_file]
        if self.header_path:
            parts.append(" > ".join(self.header_path))
        return " | ".join(parts)


def _reciprocal_rank_fusion(
    ranked_lists: list[list[int]],
    weights: list[float],
    k: int = 60,
) -> list[tuple[int, float]]:
    """
    Combine multiple ranked lists using Reciprocal Rank Fusion.

    RRF score = sum(weight_i / (k + rank_i)) for each list i.
    Higher k smooths differences between top and bottom ranks.

    Returns list of (chunk_id, fused_score) sorted by score descending.
    """
    scores: dict[int, float] = {}

    for ranked_list, weight in zip(ranked_lists, weights):
        for rank, chunk_id in enumerate(ranked_list):
            if chunk_id not in scores:
                scores[chunk_id] = 0.0
            scores[chunk_id] += weight / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class Searcher:
    """Hybrid BM25 + semantic search with reciprocal rank fusion."""

    def __init__(self, config: RetrievalConfig, adapter=None):
        self.config = config
        self.store = Store(config.db_path, config.store_dir)
        self.bm25 = self.store.load_bm25()
        self.embeddings = None
        self.model = None
        self._chunks = None
        self.adapter = adapter

        if config.use_semantic:
            self.embeddings = self.store.load_embeddings()
            # Apply embedding adapter if available and trained
            if self.adapter and self.adapter.is_ready and self.embeddings is not None:
                self.embeddings = self.adapter.adapt(self.embeddings)

    @property
    def chunks(self) -> list[dict]:
        if self._chunks is None:
            self._chunks = self.store.get_all_chunks()
        return self._chunks

    def _get_semantic_model(self):
        """Lazy-load the embedding model (only when needed for queries)."""
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.config.embedding_model)
        return self.model

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        domain_filter: Optional[str] = None,
        file_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Run hybrid search.

        Args:
            query: Natural language search query
            top_k: Number of results to return
            domain_filter: Only return results from this domain
            file_filter: Only return results from files matching this substring

        Returns:
            List of SearchResult sorted by relevance
        """
        if top_k is None:
            top_k = self.config.default_top_k

        chunks = self.chunks
        if not chunks:
            return []

        # Build chunk_id to index mapping
        id_to_idx = {c["id"]: i for i, c in enumerate(chunks)}

        # Pre-compute the set of allowed chunk IDs when filters are active.
        # This ensures filtered chunks are excluded BEFORE ranking and fusion,
        # so top-k always returns the best K results within the filter scope.
        allowed_ids = None
        if domain_filter or file_filter:
            allowed_ids = set()
            for c in chunks:
                if domain_filter and c["domain"] != domain_filter:
                    continue
                if file_filter and file_filter not in c["source_file"]:
                    continue
                allowed_ids.add(c["id"])
            if not allowed_ids:
                return []

        rerank_n = self.config.rerank_top_n

        # BM25 retrieval
        bm25_ranked = self._bm25_search(query, rerank_n)
        if allowed_ids is not None:
            bm25_ranked = [cid for cid in bm25_ranked if cid in allowed_ids]

        ranked_lists = [bm25_ranked]
        weights = [self.config.bm25_weight]

        # Semantic retrieval
        if self.config.use_semantic and self.embeddings is not None:
            semantic_ranked = self._semantic_search(query, rerank_n)
            if allowed_ids is not None:
                semantic_ranked = [cid for cid in semantic_ranked if cid in allowed_ids]
            ranked_lists.append(semantic_ranked)
            weights.append(self.config.semantic_weight)

        # Fuse
        fused = _reciprocal_rank_fusion(ranked_lists, weights)

        # Apply feedback boost: chunks with positive feedback get a score bump
        feedback_scores = self.store.get_chunk_feedback_scores()
        if feedback_scores:
            boosted = []
            for chunk_id, score in fused:
                fb = feedback_scores.get(chunk_id, 0.0)
                # Feedback multiplier: +10% per point of avg feedback
                boosted_score = score * (1.0 + 0.1 * fb)
                boosted.append((chunk_id, boosted_score))
            fused = sorted(boosted, key=lambda x: x[1], reverse=True)

        # Build results with rank info
        bm25_rank_map = {cid: rank for rank, cid in enumerate(bm25_ranked)}
        semantic_rank_map = {}
        if len(ranked_lists) > 1:
            semantic_rank_map = {cid: rank for rank, cid in enumerate(ranked_lists[1])}

        results = []
        for chunk_id, score in fused:
            if chunk_id not in id_to_idx:
                continue
            chunk = chunks[id_to_idx[chunk_id]]

            results.append(SearchResult(
                chunk_id=chunk_id,
                text=chunk["text"],
                source_file=chunk["source_file"],
                header_path=chunk["header_path"],
                domain=chunk["domain"],
                tags=chunk["tags"],
                score=score,
                bm25_rank=bm25_rank_map.get(chunk_id),
                semantic_rank=semantic_rank_map.get(chunk_id),
            ))

            if len(results) >= top_k:
                break

        # Log query difficulty for gap detection
        self._log_difficulty(query, results, domain_filter)

        return results

    def _log_difficulty(self, query: str, results: list[SearchResult],
                        domain: Optional[str] = None):
        """Compute and log how hard this query was for the retrieval system."""
        if not results:
            self.store.log_difficulty(query, 0.0, 0.0, 0, domain or "unknown", 1.0)
            return

        top_score = results[0].score
        second_score = results[1].score if len(results) > 1 else 0.0
        score_gap = top_score - second_score

        # Difficulty heuristic: low top score + small gap = hard query
        # Normalized so 0 = easy, 1 = very hard
        # top_score typically ranges 0.001 to 0.02 for RRF scores
        score_confidence = min(top_score / 0.015, 1.0)
        gap_confidence = min(score_gap / 0.005, 1.0)
        difficulty = 1.0 - (0.6 * score_confidence + 0.4 * gap_confidence)
        difficulty = max(0.0, min(1.0, difficulty))

        result_domain = domain or (results[0].domain if results else "unknown")
        self.store.log_difficulty(
            query, top_score, score_gap, len(results), result_domain, difficulty
        )

    def _bm25_search(self, query: str, top_n: int) -> list[int]:
        """Return chunk IDs ranked by BM25 score."""
        tokens = tokenize(query)
        if not tokens or self.bm25 is None:
            return []

        scores = self.bm25.get_scores(tokens)
        chunks = self.chunks

        # Get top N indices
        ranked_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_n]

        return [chunks[i]["id"] for i in ranked_indices if scores[i] > 0]

    def _semantic_search(self, query: str, top_n: int) -> list[int]:
        """Return chunk IDs ranked by cosine similarity."""
        import numpy as np

        if self.embeddings is None:
            return []

        model = self._get_semantic_model()
        query_emb = model.encode([query], normalize_embeddings=True)[0]

        # Cosine similarity (embeddings already normalized)
        similarities = np.dot(self.embeddings, query_emb)

        ranked_indices = np.argsort(similarities)[::-1][:top_n]
        chunks = self.chunks

        return [
            chunks[i]["id"]
            for i in ranked_indices
            if similarities[i] > 0.1  # minimum threshold
        ]

    def search_bm25_only(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> list[SearchResult]:
        """BM25-only search. No ML dependencies needed."""
        if top_k is None:
            top_k = self.config.default_top_k

        ranked_ids = self._bm25_search(query, top_k)
        chunks_by_id = {c["id"]: c for c in self.chunks}

        results = []
        for rank, chunk_id in enumerate(ranked_ids[:top_k]):
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            results.append(SearchResult(
                chunk_id=chunk_id,
                text=chunk["text"],
                source_file=chunk["source_file"],
                header_path=chunk["header_path"],
                domain=chunk["domain"],
                tags=chunk["tags"],
                score=1.0 / (60 + rank + 1),
                bm25_rank=rank,
            ))
        return results

    def search_hyde(
        self,
        query: str,
        top_k: Optional[int] = None,
        domain_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Hypothetical Document Embedding (HyDE) search.

        Instead of searching with the raw query, this method:
        1. Finds the top BM25 result for the query
        2. Uses that result's text as a "hypothetical answer"
        3. Searches semantically using the hypothetical answer

        This bridges the vocabulary gap between queries and documents.
        Works without any LLM API calls by using the best BM25 match
        as a proxy for a hypothetical answer.
        """
        if top_k is None:
            top_k = self.config.default_top_k

        if not self.config.use_semantic or self.embeddings is None:
            # Fall back to regular search if semantic is unavailable
            return self.search(query, top_k, domain_filter)

        # Step 1: Get top BM25 result as pseudo-document
        bm25_results = self._bm25_search(query, top_n=3)
        if not bm25_results:
            return self.search(query, top_k, domain_filter)

        # Build the hypothetical document from top BM25 matches
        id_to_idx = {c["id"]: i for i, c in enumerate(self.chunks)}
        hypo_parts = []
        for cid in bm25_results[:2]:
            if cid in id_to_idx:
                chunk_text = self.chunks[id_to_idx[cid]]["text"]
                hypo_parts.append(chunk_text[:500])

        if not hypo_parts:
            return self.search(query, top_k, domain_filter)

        hypo_doc = f"{query}\n\n" + "\n".join(hypo_parts)

        # Step 2: Encode the hypothetical document
        import numpy as np
        model = self._get_semantic_model()
        hypo_emb = model.encode([hypo_doc], normalize_embeddings=True)[0]

        # Step 3: Find chunks most similar to the hypothetical document
        similarities = np.dot(self.embeddings, hypo_emb)

        # Apply domain filter
        allowed_ids = None
        if domain_filter:
            allowed_ids = set()
            for c in self.chunks:
                if c["domain"] == domain_filter:
                    allowed_ids.add(c["id"])

        ranked_indices = np.argsort(similarities)[::-1]

        # Step 4: Fuse HyDE semantic results with original BM25 results
        hyde_ranked = []
        for idx in ranked_indices:
            if idx >= len(self.chunks):
                continue
            cid = self.chunks[idx]["id"]
            if allowed_ids is not None and cid not in allowed_ids:
                continue
            if similarities[idx] > 0.1:
                hyde_ranked.append(cid)
            if len(hyde_ranked) >= self.config.rerank_top_n:
                break

        # Fuse: BM25 + HyDE semantic (replacing regular semantic)
        bm25_for_fusion = self._bm25_search(query, self.config.rerank_top_n)
        if allowed_ids is not None:
            bm25_for_fusion = [cid for cid in bm25_for_fusion if cid in allowed_ids]

        fused = _reciprocal_rank_fusion(
            [bm25_for_fusion, hyde_ranked],
            [self.config.bm25_weight, self.config.semantic_weight],
        )

        # Apply feedback boost
        feedback_scores = self.store.get_chunk_feedback_scores()
        if feedback_scores:
            boosted = []
            for chunk_id, score in fused:
                fb = feedback_scores.get(chunk_id, 0.0)
                boosted_score = score * (1.0 + 0.1 * fb)
                boosted.append((chunk_id, boosted_score))
            fused = sorted(boosted, key=lambda x: x[1], reverse=True)

        # Build results
        results = []
        for chunk_id, score in fused:
            if chunk_id not in id_to_idx:
                continue
            chunk = self.chunks[id_to_idx[chunk_id]]
            results.append(SearchResult(
                chunk_id=chunk_id,
                text=chunk["text"],
                source_file=chunk["source_file"],
                header_path=chunk["header_path"],
                domain=chunk["domain"],
                tags=chunk["tags"],
                score=score,
            ))
            if len(results) >= top_k:
                break

        self._log_difficulty(query, results, domain_filter)
        return results

    def get_stats(self) -> dict:
        feedback_count = self.store.feedback_count()
        return {
            "total_chunks": len(self.chunks),
            "domains": self.store.list_domains(),
            "files": self.store.list_source_files(),
            "bm25_loaded": self.bm25 is not None,
            "semantic_loaded": self.embeddings is not None,
            "last_indexed": self.store.get_meta("last_indexed"),
            "feedback_entries": feedback_count,
        }

    def close(self):
        self.store.close()

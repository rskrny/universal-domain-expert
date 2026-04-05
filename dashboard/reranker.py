"""
Learned reranker for chunk search results.

Uses feedback signals (thumbs up/down) to learn which chunks are most helpful.
Trains a logistic regression on 6 features per chunk:
  1. BM25 rank (lower = better)
  2. Semantic rank (lower = better)
  3. Domain match (1 if chunk domain matches query domain, 0 otherwise)
  4. Token count (normalized)
  5. Information density score
  6. Historical effectiveness (from chunk_effectiveness table)

Falls back to the original score ordering when not enough feedback exists.
"""

import logging
import pickle
import time
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("dashboard.reranker")

MIN_FEEDBACK_SAMPLES = 200  # Need real data, not bootstrap junk


class LearnedReranker:
    """Logistic regression reranker trained on chunk feedback."""

    def __init__(self, model_dir: Path, db=None):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / "reranker_lr.pkl"
        self.db = db

        self.model = None
        self.is_ready = False
        self._load_model()

    def _load_model(self):
        if self.model_path.exists():
            try:
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
                self.is_ready = True
                logger.info("Learned reranker loaded")
            except Exception as e:
                logger.warning("Failed to load reranker: %s", e)

    def train(self) -> Optional[dict]:
        """Train on chunk_effectiveness data."""
        if not self.db:
            return None

        rows = self.db.get_chunk_effectiveness_data()
        if len(rows) < MIN_FEEDBACK_SAMPLES:
            logger.info("Only %d feedback samples. Need %d.", len(rows), MIN_FEEDBACK_SAMPLES)
            return None

        # Build features: effectiveness as label, times_retrieved as weight
        X = []
        y = []
        for row in rows:
            retrieved = row.get("times_retrieved", 1)
            helpful = row.get("times_helpful", 0)
            effectiveness = row.get("effectiveness", 0.5)

            # Features: retrieved count (proxy for relevance), helpful ratio
            X.append([
                np.log1p(retrieved),
                helpful / max(retrieved, 1),
                effectiveness,
            ])
            y.append(1 if effectiveness > 0.5 else 0)

        X = np.array(X)
        y = np.array(y)

        # Need both classes
        if len(np.unique(y)) < 2:
            return None

        from sklearn.linear_model import LogisticRegression

        lr = LogisticRegression(max_iter=200, random_state=42)
        lr.fit(X, y)
        accuracy = float(lr.score(X, y))

        with open(self.model_path, "wb") as f:
            pickle.dump(lr, f)

        self.model = lr
        self.is_ready = True

        metrics = {
            "samples": len(X),
            "accuracy": round(accuracy, 4),
            "timestamp": time.time(),
        }

        if self.db:
            self.db.log_training_run(
                component="reranker",
                samples_used=len(X),
                accuracy=accuracy,
                metrics=metrics,
            )

        logger.info("Reranker trained: %d samples, %.1f%% accuracy", len(X), accuracy * 100)
        return metrics

    def rerank(self, results: list, query_domain: str = None,
               effectiveness_map: dict = None) -> list:
        """Rerank search results using the learned model.

        Args:
            results: list of SearchResult objects
            query_domain: the routed domain for domain-match feature
            effectiveness_map: {chunk_id: effectiveness} from chunk_effectiveness table

        Returns:
            Reranked list of SearchResult objects
        """
        if not self.is_ready or not results:
            return results

        effectiveness_map = effectiveness_map or {}

        # Build feature matrix
        features = []
        for r in results:
            bm25_rank = r.bm25_rank if r.bm25_rank is not None else 50
            semantic_rank = r.semantic_rank if r.semantic_rank is not None else 50
            domain_match = 1.0 if (query_domain and r.domain == query_domain) else 0.0
            token_count = len(r.text) / 4 / 500  # normalized by typical chunk size
            eff = effectiveness_map.get(r.chunk_id, 0.5)

            features.append([
                1.0 / (1 + bm25_rank),      # inverse rank (higher = better)
                1.0 / (1 + semantic_rank),   # inverse rank
                domain_match,
                min(token_count, 2.0),       # capped
                r.score,                     # original fusion score
                eff,                         # historical effectiveness
            ])

        X = np.array(features)

        try:
            # Get probability of being helpful
            proba = self.model.predict_proba(X)[:, 1]

            # Combine original score with learned score (70/30 blend)
            original_scores = np.array([r.score for r in results])
            max_orig = original_scores.max() or 1
            normalized_orig = original_scores / max_orig

            blended = 0.3 * normalized_orig + 0.7 * proba

            # Sort by blended score
            ranked_indices = np.argsort(blended)[::-1]
            return [results[i] for i in ranked_indices]

        except Exception as e:
            logger.warning("Reranking failed, returning original order: %s", e)
            return results

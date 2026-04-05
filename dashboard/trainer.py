"""
Self-improving training orchestrator.

Monitors feedback signal count and auto-triggers training for all neural
components when thresholds are met. Runs training in-process (no background
threads) to avoid concurrency issues on a single-machine setup.

Training is triggered:
- After every 10 new feedback signals
- Manually via POST /api/neural/train
- On server startup if models are stale

Components trained (in order):
1. Neural router (MLP classifier on routing_log)
2. Reranker (logistic regression on chunk_effectiveness)
3. Embedding adapter (contrastive bottleneck on feedback triplets)
"""

import logging
import time

logger = logging.getLogger("dashboard.trainer")

# Train after every N new feedback signals
FEEDBACK_INTERVAL = 10


class TrainingOrchestrator:
    """Monitors feedback and triggers training when thresholds are met."""

    def __init__(self, db, neural_router, reranker, adapter):
        self.db = db
        self.neural_router = neural_router
        self.reranker = reranker
        self.adapter = adapter
        self._last_feedback_count = 0
        self._last_train_time = 0

        # Check initial state
        self._sync_feedback_count()

    def _sync_feedback_count(self):
        """Read current feedback count from db."""
        try:
            status = self.db.get_neural_status()
            self._last_feedback_count = status.get("feedback_count", 0)
        except Exception:
            pass

    def on_feedback(self):
        """Called after each feedback submission. Checks if training should run."""
        try:
            status = self.db.get_neural_status()
            current_count = status.get("feedback_count", 0)
            delta = current_count - self._last_feedback_count

            if delta >= FEEDBACK_INTERVAL:
                logger.info("Training triggered: %d new feedback signals since last train", delta)
                self.train_all()
                self._last_feedback_count = current_count
                self._last_train_time = time.time()

        except Exception as e:
            logger.warning("Training check failed: %s", e)

    def train_all(self) -> dict:
        """Train all components. Returns results dict."""
        results = {}

        # 1. Neural router
        try:
            r = self.neural_router.train()
            results["router"] = r or {"status": "not_enough_data"}
        except Exception as e:
            results["router"] = {"status": "error", "error": str(e)}
            logger.warning("Router training failed: %s", e)

        # 2. Reranker
        try:
            r = self.reranker.train()
            results["reranker"] = r or {"status": "not_enough_data"}
        except Exception as e:
            results["reranker"] = {"status": "error", "error": str(e)}
            logger.warning("Reranker training failed: %s", e)

        # 3. Embedding adapter
        try:
            r = self.adapter.train()
            results["adapter"] = r or {"status": "not_enough_data"}
        except Exception as e:
            results["adapter"] = {"status": "error", "error": str(e)}
            logger.warning("Adapter training failed: %s", e)

        return results

    def get_status(self) -> dict:
        """Get orchestrator status."""
        return {
            "last_feedback_count": self._last_feedback_count,
            "last_train_time": self._last_train_time,
            "feedback_interval": FEEDBACK_INTERVAL,
            "components": {
                "router": {"ready": self.neural_router.is_ready},
                "reranker": {"ready": self.reranker.is_ready},
                "adapter": {"ready": self.adapter.is_ready},
            },
        }

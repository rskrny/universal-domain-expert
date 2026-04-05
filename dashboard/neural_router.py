"""
Trainable MLP domain router.

Replaces keyword matching with a neural classifier trained on routing_log data.
Falls back to keyword routing when confidence is below threshold or insufficient
training data exists.

Architecture:
- Input: 384-dim query embedding (from all-MiniLM-L6-v2)
- Hidden: 128 neurons, ReLU
- Output: N classes (one per domain)
- Training: scikit-learn MLPClassifier on routing_log entries
- Inference: predict_proba -> use neural if confidence > threshold, else keyword fallback
"""

import logging
import pickle
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .router import classify as keyword_classify, RouteResult, DOMAIN_REGISTRY

logger = logging.getLogger("dashboard.neural_router")

# Minimum samples before neural routing activates
MIN_TRAINING_SAMPLES = 50

# Neural prediction must exceed this confidence to override keyword routing
CONFIDENCE_THRESHOLD = 0.75  # Higher bar: only override keyword routing when confident


class NeuralRouter:
    """MLP-based domain router with keyword fallback."""

    def __init__(self, model_dir: Path, db=None):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / "router_mlp.pkl"
        self.db = db

        self.model = None
        self.label_encoder = None
        self.is_ready = False
        self._load_model()

    def _load_model(self):
        """Load a previously trained model from disk."""
        if self.model_path.exists():
            try:
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                self.model = data["model"]
                self.label_encoder = data["label_encoder"]
                self.is_ready = True
                logger.info("Neural router loaded (%d classes)", len(self.label_encoder.classes_))
            except Exception as e:
                logger.warning("Failed to load neural router model: %s", e)
                self.is_ready = False

    def train(self) -> Optional[dict]:
        """Train the MLP on routing_log data. Returns metrics or None if not enough data."""
        if not self.db:
            return None

        rows = self.db.get_routing_training_data()
        if len(rows) < MIN_TRAINING_SAMPLES:
            logger.info("Only %d routing samples. Need %d to train.", len(rows), MIN_TRAINING_SAMPLES)
            return None

        # Build training data
        X = []
        y = []
        for row in rows:
            emb_bytes = row.get("query_embedding")
            # Use actual_domain if available (corrected by user), else predicted
            domain = row.get("actual_domain") or row.get("predicted_domain")
            if emb_bytes is None or domain is None:
                continue
            if domain not in DOMAIN_REGISTRY:
                continue
            emb = np.frombuffer(emb_bytes, dtype=np.float32)
            if len(emb) != 384:
                continue
            X.append(emb)
            y.append(domain)

        if len(X) < MIN_TRAINING_SAMPLES:
            return None

        X = np.array(X)
        y_arr = np.array(y)

        from sklearn.preprocessing import LabelEncoder
        from sklearn.neural_network import MLPClassifier
        from sklearn.model_selection import cross_val_score

        le = LabelEncoder()
        y_encoded = le.fit_transform(y_arr)

        # Train MLP
        mlp = MLPClassifier(
            hidden_layer_sizes=(128,),
            activation="relu",
            max_iter=300,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
            verbose=False,
        )
        mlp.fit(X, y_encoded)

        # Cross-validation accuracy (if enough data)
        accuracy = 0.0
        if len(X) >= 30:
            try:
                scores = cross_val_score(mlp, X, y_encoded, cv=min(5, len(X) // 10), scoring="accuracy")
                accuracy = float(scores.mean())
            except Exception:
                accuracy = float(mlp.score(X, y_encoded))
        else:
            accuracy = float(mlp.score(X, y_encoded))

        # Save model
        with open(self.model_path, "wb") as f:
            pickle.dump({"model": mlp, "label_encoder": le}, f)

        self.model = mlp
        self.label_encoder = le
        self.is_ready = True

        metrics = {
            "samples": len(X),
            "classes": len(le.classes_),
            "accuracy": round(accuracy, 4),
            "timestamp": time.time(),
        }

        # Log the training run
        if self.db:
            self.db.log_training_run(
                component="neural_router",
                samples_used=len(X),
                accuracy=accuracy,
                metrics=metrics,
            )

        logger.info("Neural router trained: %d samples, %d classes, %.1f%% accuracy",
                     len(X), len(le.classes_), accuracy * 100)
        return metrics

    def classify(self, message: str, query_embedding: Optional[np.ndarray] = None) -> RouteResult:
        """Classify a message using neural model with keyword fallback.

        Returns RouteResult. If neural model is confident, uses neural prediction.
        Otherwise falls back to keyword routing.
        """
        # Always run keyword routing as baseline
        keyword_result = keyword_classify(message)

        # If neural model isn't ready or no embedding provided, use keyword
        if not self.is_ready or query_embedding is None:
            return keyword_result

        try:
            emb = query_embedding.reshape(1, -1).astype(np.float32)
            proba = self.model.predict_proba(emb)[0]
            top_idx = np.argmax(proba)
            confidence = float(proba[top_idx])
            predicted_domain = self.label_encoder.inverse_transform([top_idx])[0]

            if confidence >= CONFIDENCE_THRESHOLD and predicted_domain in DOMAIN_REGISTRY:
                return RouteResult(
                    primary_domain=predicted_domain,
                    supporting_domains=keyword_result.supporting_domains,
                    tier=keyword_result.tier,
                    domain_file=DOMAIN_REGISTRY[predicted_domain]["file"],
                )
        except Exception as e:
            logger.warning("Neural routing failed, using keyword fallback: %s", e)

        return keyword_result

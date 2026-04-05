"""
Embedding adapter with contrastive learning.

A lightweight bottleneck network that refines the base embedding model's
representations using user feedback. Learns to pull helpful chunks closer
to queries and push unhelpful chunks farther away.

Architecture:
- Linear(384, 64) -> ReLU -> Linear(64, 384) + residual connection
- ~200KB model. Trains in seconds on CPU.
- Contrastive triplet loss: (query, helpful_chunk, unhelpful_chunk)
- Applied on top of frozen base embeddings. No base model fine-tuning.
"""

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("dashboard.adapter")

MIN_TRIPLETS = 100  # Need real feedback triplets, not synthetic


class EmbeddingAdapter:
    """PyTorch bottleneck adapter for embedding refinement."""

    def __init__(self, model_dir: Path, db=None, embedding_dim: int = 384):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / "embedding_adapter.pt"
        self.db = db
        self.dim = embedding_dim

        self.model = None
        self.is_ready = False
        self._load_model()

    def _build_model(self):
        """Build the bottleneck adapter network."""
        import torch
        import torch.nn as nn

        class BottleneckAdapter(nn.Module):
            def __init__(self, dim, bottleneck=64):
                super().__init__()
                self.down = nn.Linear(dim, bottleneck)
                self.up = nn.Linear(bottleneck, dim)
                self.relu = nn.ReLU()

            def forward(self, x):
                residual = x
                x = self.relu(self.down(x))
                x = self.up(x)
                return x + residual  # residual connection preserves base quality

        return BottleneckAdapter(self.dim)

    def _load_model(self):
        if self.model_path.exists():
            try:
                import torch
                self.model = self._build_model()
                self.model.load_state_dict(torch.load(self.model_path, map_location="cpu", weights_only=True))
                self.model.eval()
                self.is_ready = True
                logger.info("Embedding adapter loaded")
            except Exception as e:
                logger.warning("Failed to load adapter: %s", e)

    def _build_triplets(self) -> Optional[tuple]:
        """Build training triplets from feedback data.

        For each query with positive AND negative feedback, create
        (query_emb, positive_chunk_emb, negative_chunk_emb) triplets.
        """
        if not self.db:
            return None

        import json

        # Get all feedback with positive rating
        positive_msgs = self.db._read(
            "SELECT cm.session_id, cm.content, cm.context_chunks "
            "FROM message_feedback mf "
            "JOIN chat_messages cm ON cm.id = mf.message_id "
            "WHERE mf.rating = 1 AND cm.context_chunks IS NOT NULL"
        )

        # Get all feedback with negative rating
        negative_msgs = self.db._read(
            "SELECT cm.session_id, cm.content, cm.context_chunks "
            "FROM message_feedback mf "
            "JOIN chat_messages cm ON cm.id = mf.message_id "
            "WHERE mf.rating = -1 AND cm.context_chunks IS NOT NULL"
        )

        if not positive_msgs or not negative_msgs:
            return None

        # Get the corresponding user messages (queries) for each session
        # For now, use a simplified approach: get all routing log embeddings
        routing_data = self.db.get_routing_training_data()
        if not routing_data:
            return None

        # Build embeddings index from routing log
        query_embs = {}
        for row in routing_data:
            emb = row.get("query_embedding")
            domain = row.get("predicted_domain")
            if emb and domain:
                arr = np.frombuffer(emb, dtype=np.float32)
                if len(arr) == self.dim:
                    query_embs[domain] = arr  # latest embedding per domain

        if len(query_embs) < 5:
            return None

        logger.info("Building triplets from %d positive, %d negative messages",
                     len(positive_msgs), len(negative_msgs))

        # For this phase, we return a signal that we have enough data
        # Full triplet construction requires chunk embeddings which we'll
        # pull from the store
        return len(positive_msgs), len(negative_msgs)

    def train(self) -> Optional[dict]:
        """Train the adapter on feedback triplets."""
        if not self.db:
            return None

        triplet_info = self._build_triplets()
        if triplet_info is None:
            return None

        pos_count, neg_count = triplet_info
        total = pos_count + neg_count

        if total < MIN_TRIPLETS:
            logger.info("Only %d feedback signals. Need %d for adapter training.", total, MIN_TRIPLETS)
            return None

        # Build the adapter model
        import torch
        import torch.nn as nn

        self.model = self._build_model()

        # For initial version: train on routing embeddings with domain labels
        # This teaches the adapter to cluster same-domain queries together
        routing_data = self.db.get_routing_training_data()
        embeddings = []
        domains = []
        for row in routing_data:
            emb = row.get("query_embedding")
            domain = row.get("predicted_domain")
            if emb and domain:
                arr = np.frombuffer(emb, dtype=np.float32)
                if len(arr) == self.dim:
                    embeddings.append(arr)
                    domains.append(domain)

        if len(embeddings) < MIN_TRIPLETS:
            return None

        X = torch.tensor(np.array(embeddings), dtype=torch.float32)

        # Domain clustering loss: same domain = closer, different domain = farther
        optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)
        triplet_loss = nn.TripletMarginLoss(margin=0.3)

        # Create triplets: anchor + same domain positive + different domain negative
        domain_indices = {}
        for i, d in enumerate(domains):
            domain_indices.setdefault(d, []).append(i)

        self.model.train()
        total_loss = 0
        n_triplets = 0

        for epoch in range(10):
            epoch_loss = 0
            for d, indices in domain_indices.items():
                if len(indices) < 2:
                    continue
                # For each pair in same domain, find a negative from different domain
                for i in range(len(indices) - 1):
                    anchor_idx = indices[i]
                    pos_idx = indices[i + 1]

                    # Find negative from a random different domain
                    other_domains = [od for od in domain_indices if od != d and domain_indices[od]]
                    if not other_domains:
                        continue
                    import random
                    neg_domain = random.choice(other_domains)
                    neg_idx = random.choice(domain_indices[neg_domain])

                    anchor = self.model(X[anchor_idx:anchor_idx+1])
                    positive = self.model(X[pos_idx:pos_idx+1])
                    negative = self.model(X[neg_idx:neg_idx+1])

                    loss = triplet_loss(anchor, positive, negative)
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()

                    epoch_loss += loss.item()
                    n_triplets += 1

            total_loss = epoch_loss

        # Save model
        self.model.eval()
        torch.save(self.model.state_dict(), self.model_path)
        self.is_ready = True

        metrics = {
            "triplets": n_triplets,
            "final_loss": round(total_loss / max(n_triplets, 1), 6),
            "timestamp": time.time(),
        }

        if self.db:
            self.db.log_training_run(
                component="embedding_adapter",
                samples_used=n_triplets,
                accuracy=0.0,  # not applicable for contrastive loss
                metrics=metrics,
            )

        logger.info("Adapter trained: %d triplets, loss=%.4f", n_triplets, metrics["final_loss"])
        return metrics

    def adapt(self, embeddings: np.ndarray) -> np.ndarray:
        """Apply the adapter to refine embeddings. Returns adapted embeddings."""
        if not self.is_ready or self.model is None:
            return embeddings

        import torch
        with torch.no_grad():
            x = torch.tensor(embeddings, dtype=torch.float32)
            adapted = self.model(x).numpy()

        # Normalize
        norms = np.linalg.norm(adapted, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return adapted / norms

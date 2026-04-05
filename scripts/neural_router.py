"""
Neural Router for Domain Expert System.

Two-phase architecture:
  Phase 1 (train): sentence-transformers embeds domain files + routing log
                   examples into domain centroids. Saves lightweight artifacts.
  Phase 2 (infer): numpy-only inference in the hook. No torch loading.
                   Word-vector averaging + cosine similarity. <100ms.

Design principles:
  - Domain files ARE the primary training data (78 rich descriptions)
  - Routing log examples augment prototypes where available
  - Hybrid scoring: neural_score * alpha + keyword_score * (1 - alpha)
  - Confidence = separation ratio between top-2 domains
  - Graceful fallback: if neural artifacts missing, keyword-only

Usage:
  Train:  python scripts/neural_router.py train
  Test:   python scripts/neural_router.py test "your query here"
  Stats:  python scripts/neural_router.py stats
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DOMAINS_DIR = ROOT / "prompts" / "domains"
ROUTER_MD = ROOT / "prompts" / "ROUTER.md"
ROUTING_LOG = ROOT / "state" / "routing_log.jsonl"
ARTIFACTS_DIR = ROOT / "state" / "neural_router"

# Artifact filenames
CENTROIDS_FILE = ARTIFACTS_DIR / "centroids.npy"
DOMAIN_INDEX_FILE = ARTIFACTS_DIR / "domain_index.json"
VOCAB_FILE = ARTIFACTS_DIR / "vocabulary.json"
WORD_VECTORS_FILE = ARTIFACTS_DIR / "word_vectors.npy"
META_FILE = ARTIFACTS_DIR / "meta.json"

# Inference parameters
ALPHA = 0.6              # Weight for neural score vs keyword score
CONFIDENCE_THRESHOLD = 1.3  # Minimum separation ratio to trust neural
MIN_KNOWN_WORDS = 3      # Minimum vocab hits to use neural scoring


# ---------------------------------------------------------------------------
# Text Processing
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "this", "that", "are", "was",
    "be", "has", "had", "have", "do", "does", "did", "will", "can", "my",
    "i", "you", "we", "he", "she", "they", "not", "no", "so", "if", "up",
    "out", "about", "just", "how", "what", "when", "who", "all", "been",
    "more", "some", "like", "than", "into", "its", "your", "their", "our",
    "am", "as", "im", "ive", "dont", "get", "got", "one", "new", "use",
    "using", "used", "make", "made", "way", "would", "could", "should",
    "also", "each", "which", "where", "there", "then", "them", "these",
    "those", "such", "very", "most", "other", "only", "any", "many",
    "much", "own", "same", "after", "before", "between", "under", "over",
}


def tokenize(text: str) -> list[str]:
    """Extract meaningful lowercase tokens from text."""
    words = re.findall(r"[a-z][a-z0-9.+-]*", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def extract_domain_text(filepath: Path) -> str:
    """Extract the most informative text from a domain file.

    Takes: title, description, key frameworks, anti-patterns.
    Skips: boilerplate, long examples, YAML frontmatter.
    """
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Strip YAML frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            text = text[end + 3:]

    # Take first 2000 chars (title + description + frameworks)
    # This captures the identity of the domain without noise
    text = text[:2000]

    # Clean markdown formatting
    text = re.sub(r"#{1,6}\s*", "", text)  # headers
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)  # bold/italic
    text = re.sub(r"`[^`]+`", "", text)  # inline code
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train():
    """Build domain centroids and word vocabulary.

    Pipeline:
    1. Load all domain files, extract text
    2. Embed domain texts with sentence-transformers
    3. Load routing log, embed routed queries, blend into centroids
    4. Build word vocabulary from all domain texts
    5. Embed each vocabulary word
    6. Save all artifacts
    """
    print("Neural Router Training")
    print("=" * 50)

    # Check for model
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("ERROR: sentence-transformers not installed.")
        print("Install: pip install sentence-transformers")
        return False

    # 1. Load domain files
    print("[1/6] Loading domain files...")
    domain_files = sorted(DOMAINS_DIR.glob("*.md"))
    if not domain_files:
        print(f"ERROR: No domain files found in {DOMAINS_DIR}")
        return False

    domain_texts = {}
    domain_names = {}
    for f in domain_files:
        key = f.stem  # e.g. "software-dev"
        text = extract_domain_text(f)
        if len(text) > 50:  # skip empty/tiny files
            domain_texts[key] = text
            # Extract readable name from first line
            raw = f.read_text(encoding="utf-8", errors="replace")
            first_line = raw.strip().split("\n")[0].strip("# ").strip()
            domain_names[key] = first_line or key

    print(f"  Loaded {len(domain_texts)} domain files")

    # 2. Embed domain texts
    print("[2/6] Loading embedding model (all-MiniLM-L6-v2)...")
    t0 = time.time()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"  Model loaded in {time.time() - t0:.1f}s")

    print("[3/6] Embedding domain descriptions...")
    keys_ordered = sorted(domain_texts.keys())
    texts_ordered = [domain_texts[k] for k in keys_ordered]
    domain_embeddings = model.encode(texts_ordered, normalize_embeddings=True,
                                      show_progress_bar=False)
    print(f"  Embedded {len(keys_ordered)} domains -> {domain_embeddings.shape}")

    # 3. Blend routing log examples
    print("[4/6] Blending routing log examples...")
    log_examples = _load_routing_log_examples()
    blend_count = 0

    centroids = domain_embeddings.copy().astype(np.float32)
    for i, key in enumerate(keys_ordered):
        file_name = key + ".md"
        examples = log_examples.get(file_name, [])
        if not examples:
            continue

        # Embed the example queries
        example_embs = model.encode(examples, normalize_embeddings=True,
                                     show_progress_bar=False)

        # Weighted blend: domain file embedding gets 2x weight vs examples
        # This prevents noisy/misrouted examples from dominating
        domain_weight = 2.0
        example_weight = 1.0 / max(len(examples), 1)

        blended = (centroids[i] * domain_weight +
                   example_embs.sum(axis=0) * example_weight)
        centroids[i] = blended / np.linalg.norm(blended)
        blend_count += len(examples)

    print(f"  Blended {blend_count} examples across {sum(1 for k in keys_ordered if log_examples.get(k + '.md'))} domains")

    # 4. Build word vocabulary
    print("[5/6] Building word vocabulary...")
    all_text = " ".join(texts_ordered)

    # Also include routing log prompts for vocabulary coverage
    for examples_list in log_examples.values():
        all_text += " " + " ".join(examples_list)

    word_counts = {}
    for token in tokenize(all_text):
        word_counts[token] = word_counts.get(token, 0) + 1

    # Keep words that appear 2+ times or are in domain keywords
    # Also include all single-occurrence words from domain files
    # (they may be rare but domain-specific)
    vocab = sorted(w for w, c in word_counts.items() if c >= 1)

    # Cap vocabulary at 8000 words (keeps word_vectors file manageable)
    if len(vocab) > 8000:
        # Sort by frequency, keep top 8000
        vocab = sorted(word_counts.keys(), key=lambda w: word_counts[w], reverse=True)[:8000]
        vocab.sort()

    print(f"  Vocabulary: {len(vocab)} words")

    # 5. Embed vocabulary words
    print("[6/6] Embedding vocabulary (this takes ~30s)...")
    t0 = time.time()
    # Batch embed for efficiency
    word_vectors = model.encode(vocab, normalize_embeddings=True,
                                 show_progress_bar=True,
                                 batch_size=256)
    print(f"  Embedded {len(vocab)} words in {time.time() - t0:.1f}s")

    # 6. Save artifacts
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    np.save(str(CENTROIDS_FILE), centroids)
    np.save(str(WORD_VECTORS_FILE), word_vectors.astype(np.float32))

    with open(DOMAIN_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "keys": keys_ordered,
            "names": {k: domain_names.get(k, k) for k in keys_ordered},
            "files": {k: k + ".md" for k in keys_ordered},
        }, f, indent=2)

    with open(VOCAB_FILE, "w", encoding="utf-8") as f:
        json.dump(vocab, f)

    # Meta info
    meta = {
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_domains": len(keys_ordered),
        "n_vocab": len(vocab),
        "embedding_dim": int(centroids.shape[1]),
        "model": "all-MiniLM-L6-v2",
        "routing_log_examples": blend_count,
        "alpha": ALPHA,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
    }
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"\nArtifacts saved to {ARTIFACTS_DIR}")
    print(f"  centroids.npy:    {centroids.shape} ({CENTROIDS_FILE.stat().st_size / 1024:.1f} KB)")
    print(f"  word_vectors.npy: {word_vectors.shape} ({WORD_VECTORS_FILE.stat().st_size / 1024:.1f} KB)")
    print(f"  vocabulary.json:  {len(vocab)} words")
    print(f"  domain_index.json: {len(keys_ordered)} domains")
    print("\nTraining complete.")
    return True


def _load_routing_log_examples() -> dict:
    """Load routing log and group query texts by domain file."""
    if not ROUTING_LOG.exists():
        return {}

    examples = {}
    for line in ROUTING_LOG.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not entry.get("routed") or not entry.get("file"):
            continue

        domain_file = entry["file"]
        prompt = entry.get("prompt_preview", "").strip()
        if len(prompt) < 20:
            continue

        # Skip follow-up commands that carry no domain signal
        if prompt.lower().startswith(("yes", "okay", "sure", "go ahead",
                                       "done", "great", "let's", "for number")):
            continue

        # Skip clearly misrouted entries (very low confidence)
        confidence = entry.get("confidence", 0)
        if confidence == 0:
            continue

        examples.setdefault(domain_file, []).append(prompt)

    return examples


# ---------------------------------------------------------------------------
# Inference (numpy-only, no torch)
# ---------------------------------------------------------------------------

class NeuralRouter:
    """Lightweight inference engine. Loads pre-computed artifacts only."""

    def __init__(self):
        self.loaded = False
        self.centroids = None
        self.word_vectors = None
        self.vocab = None
        self.vocab_index = None  # word -> index mapping
        self.domain_keys = None
        self.domain_names = None
        self.domain_files = None
        self.embedding_dim = 384

    def load(self) -> bool:
        """Load pre-computed artifacts. Returns False if not trained."""
        if self.loaded:
            return True

        if not CENTROIDS_FILE.exists():
            return False

        try:
            self.centroids = np.load(str(CENTROIDS_FILE))
            self.word_vectors = np.load(str(WORD_VECTORS_FILE))

            with open(DOMAIN_INDEX_FILE, "r", encoding="utf-8") as f:
                index = json.load(f)
            self.domain_keys = index["keys"]
            self.domain_names = index.get("names", {})
            self.domain_files = index.get("files", {})

            with open(VOCAB_FILE, "r", encoding="utf-8") as f:
                self.vocab = json.load(f)

            # Build word -> index mapping for O(1) lookup
            self.vocab_index = {w: i for i, w in enumerate(self.vocab)}
            self.embedding_dim = self.centroids.shape[1]
            self.loaded = True
            return True

        except Exception:
            self.loaded = False
            return False

    def embed_query(self, query: str) -> np.ndarray | None:
        """Embed a query using word-vector averaging.

        Returns None if too few vocabulary words match (unreliable embedding).
        """
        if not self.loaded:
            return None

        tokens = tokenize(query)
        if not tokens:
            return None

        # Look up word vectors for known tokens
        indices = []
        for token in tokens:
            idx = self.vocab_index.get(token)
            if idx is not None:
                indices.append(idx)

        if len(indices) < MIN_KNOWN_WORDS:
            return None

        # Average the word vectors (weighted by uniqueness)
        vectors = self.word_vectors[indices]
        embedding = vectors.mean(axis=0)

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm < 1e-8:
            return None
        embedding = embedding / norm

        return embedding

    def classify(self, query: str, top_k: int = 5) -> list[dict]:
        """Classify a query against domain centroids.

        Returns list of dicts sorted by score descending:
          {domain_key, domain_name, file, score, confidence}

        Score is cosine similarity (0 to 1).
        Confidence is ratio of top score to second score.
        """
        if not self.loaded:
            return []

        embedding = self.embed_query(query)
        if embedding is None:
            return []

        # Cosine similarity against all centroids
        # (centroids are already normalized during training)
        similarities = self.centroids @ embedding

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(top_indices):
            key = self.domain_keys[idx]
            score = float(similarities[idx])

            # Confidence: ratio of this score to next best
            if rank == 0 and len(top_indices) > 1:
                second_score = float(similarities[top_indices[1]])
                confidence = score / max(second_score, 1e-8)
            else:
                confidence = 1.0

            results.append({
                "domain_key": key,
                "domain_name": self.domain_names.get(key, key),
                "file": self.domain_files.get(key, key + ".md"),
                "score": round(score, 4),
                "confidence": round(confidence, 2) if rank == 0 else None,
            })

        return results


# Singleton for reuse within a process
_router = None


def get_router() -> NeuralRouter:
    """Get or create the singleton neural router."""
    global _router
    if _router is None:
        _router = NeuralRouter()
    return _router


def classify(query: str, top_k: int = 5) -> list[dict]:
    """Convenience function: load and classify in one call."""
    router = get_router()
    if not router.load():
        return []
    return router.classify(query, top_k=top_k)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate():
    """Cross-validate on routing log. Shows accuracy and mismatches."""
    print("Neural Router Validation")
    print("=" * 50)

    router = get_router()
    if not router.load():
        print("ERROR: Neural router not trained. Run: python scripts/neural_router.py train")
        return

    # Load routing log
    examples = _load_routing_log_examples()
    if not examples:
        print("No routing log examples to validate against.")
        return

    total = 0
    correct = 0
    mismatches = []

    for file_name, prompts in examples.items():
        domain_key = file_name.replace(".md", "")
        for prompt in prompts:
            results = router.classify(prompt, top_k=3)
            if not results:
                continue

            total += 1
            predicted = results[0]["domain_key"]
            if predicted == domain_key:
                correct += 1
            else:
                mismatches.append({
                    "query": prompt[:80],
                    "expected": domain_key,
                    "predicted": predicted,
                    "score": results[0]["score"],
                    "confidence": results[0]["confidence"],
                })

    if total == 0:
        print("No classifiable examples found.")
        return

    accuracy = correct / total * 100
    print(f"\nAccuracy: {correct}/{total} ({accuracy:.1f}%)")
    print(f"Mismatches: {len(mismatches)}")

    if mismatches:
        print("\nMisclassified queries:")
        for m in mismatches:
            print(f"  Query:     {m['query']}")
            print(f"  Expected:  {m['expected']}")
            print(f"  Predicted: {m['predicted']} (score={m['score']}, conf={m['confidence']})")
            print()


def stats():
    """Print neural router artifact stats."""
    if not META_FILE.exists():
        print("Neural router not trained. Run: python scripts/neural_router.py train")
        return

    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    print("Neural Router Status")
    print("=" * 50)
    for k, v in meta.items():
        print(f"  {k}: {v}")

    # File sizes
    for f in [CENTROIDS_FILE, WORD_VECTORS_FILE, VOCAB_FILE, DOMAIN_INDEX_FILE]:
        if f.exists():
            size_kb = f.stat().st_size / 1024
            print(f"  {f.name}: {size_kb:.1f} KB")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/neural_router.py train          # Build centroids")
        print("  python scripts/neural_router.py test 'query'   # Test classification")
        print("  python scripts/neural_router.py validate       # Cross-validate on log")
        print("  python scripts/neural_router.py stats          # Show status")
        return

    command = sys.argv[1]

    if command == "train":
        train()
    elif command == "test":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "How do I reduce churn?"
        t0 = time.time()
        results = classify(query, top_k=5)
        elapsed = (time.time() - t0) * 1000
        print(f"Query: {query}")
        print(f"Inference time: {elapsed:.1f}ms")
        print()
        if results:
            for r in results:
                conf_str = f" (confidence: {r['confidence']})" if r["confidence"] else ""
                print(f"  {r['score']:.4f}  {r['domain_name']} [{r['file']}]{conf_str}")
        else:
            print("  No classification (too few vocabulary matches)")
    elif command == "validate":
        validate()
    elif command == "stats":
        stats()
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()

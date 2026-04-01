#!/usr/bin/env python3
"""
Rebuild the search index after adding or modifying knowledge files.

Usage:
    python scripts/reindex.py
"""

import sys
from pathlib import Path

root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from retrieval.config import RetrievalConfig
from retrieval.indexer import build_index


def main():
    config = RetrievalConfig()
    config.knowledge_root = root
    config.store_dir = root / "retrieval" / "store"
    config.db_path = config.store_dir / "metadata.db"

    # Check if semantic was previously used
    from retrieval.store import Store
    store = Store(config.db_path, config.store_dir)
    was_semantic = store.get_meta("semantic_enabled")
    store.close()

    if was_semantic == "False":
        config.use_semantic = False

    build_index(config, verbose=True)


if __name__ == "__main__":
    main()

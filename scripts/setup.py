#!/usr/bin/env python3
"""
First-time setup for the retrieval system.

Usage:
    python scripts/setup.py              Full setup (BM25 + semantic)
    python scripts/setup.py --lite       BM25 only (no ML dependencies)
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    lite_mode = "--lite" in sys.argv

    root = Path(__file__).parent.parent
    os.chdir(root)

    print("Context Engineering Retrieval System - Setup")
    print("=" * 50)

    # Install dependencies
    if lite_mode:
        print("\nInstalling core dependencies (BM25 only)...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "rank-bm25>=0.2.2"
        ])
    else:
        print("\nInstalling all dependencies (BM25 + semantic)...")
        req_path = root / "retrieval" / "requirements.txt"
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(req_path)
        ])

    # Create store directory
    store_dir = root / "retrieval" / "store"
    store_dir.mkdir(parents=True, exist_ok=True)

    # Build initial index
    print("\nBuilding initial index...")
    sys.path.insert(0, str(root))

    from retrieval.config import RetrievalConfig
    from retrieval.indexer import build_index

    config = RetrievalConfig()
    config.knowledge_root = root
    config.store_dir = store_dir
    config.db_path = store_dir / "metadata.db"
    config.use_semantic = not lite_mode

    stats = build_index(config, verbose=True)

    print("\nSetup complete.")
    print(f"  Mode: {'BM25 only' if lite_mode else 'Full hybrid (BM25 + semantic)'}")
    print(f"  Indexed: {stats['chunks']} chunks from {stats['files']} files")
    print(f"\nTest it:")
    print(f'  python -m retrieval search "pipeline stages"')


if __name__ == "__main__":
    main()

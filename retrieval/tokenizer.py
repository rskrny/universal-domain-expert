"""
Shared tokenizer for BM25 indexing and search.

This MUST be the single source of truth. If the tokenizer changes,
both indexing and search use the same logic automatically.
Changing this module requires a full reindex (python -m retrieval index --full).
"""

import re


def tokenize(text: str) -> list[str]:
    """Tokenize text for BM25. Used by both indexer and searcher.

    Lowercase, strip punctuation, drop single-char tokens.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]

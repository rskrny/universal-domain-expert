"""
Sync knowledge chunks from Brain Feed D1 to the local retrieval index.

Fetches pending chunks from the Brain Feed worker API,
writes them as markdown files in the context directory,
marks them as synced, and triggers a reindex.

Usage:
    python scripts/sync_brainfeed.py
    python scripts/sync_brainfeed.py --dry-run
"""

import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

BRAINFEED_URL = os.getenv("BRAINFEED_URL", "https://brainfeed.hanahaulers.com")
AUTH_TOKEN = os.getenv("BRAINFEED_AUTH_TOKEN", "")


def fetch_pending_chunks() -> list[dict]:
    """Fetch chunks that haven't been synced to local index yet."""
    url = f"{BRAINFEED_URL}/api/chunks/pending"
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except URLError as e:
        print(f"Failed to fetch pending chunks: {e}")
        return []


def mark_synced(chunk_ids: list[int]):
    """Mark chunks as synced in the remote D1 database."""
    if not chunk_ids or not AUTH_TOKEN:
        return

    url = f"{BRAINFEED_URL}/api/chunks/synced"
    body = json.dumps({"ids": chunk_ids}).encode()
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {AUTH_TOKEN}")

    try:
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            print(f"  Marked {result.get('synced', 0)} chunks as synced")
    except URLError as e:
        print(f"  Warning: Failed to mark synced: {e}")


def write_chunk_file(chunk: dict, context_dir: Path) -> Path:
    """Write a Brain Feed chunk as a markdown file in the context directory."""
    domain = chunk.get("domain", "general")
    chunk_id = chunk.get("id", int(time.time()))
    title = chunk.get("title", "Untitled")
    summary = chunk.get("summary", "")
    content = chunk.get("content", "")
    source_url = chunk.get("source_url", "")
    tags = chunk.get("tags", "[]")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = []
    created = chunk.get("created_at", "")

    # Determine output directory
    if domain and domain != "general":
        out_dir = context_dir / "by-domain" / domain
    else:
        out_dir = context_dir / "shared" / "brainfeed"

    out_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
    safe_title = safe_title.strip().replace(" ", "-")[:60]
    filename = f"brainfeed-{chunk_id}-{safe_title}.md"
    filepath = out_dir / filename

    # Write markdown with frontmatter
    lines = [
        f"# {title}",
        "",
    ]
    if source_url:
        lines.append(f"Source: {source_url}")
        lines.append("")
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")
        lines.append("")
    if created:
        lines.append(f"Ingested: {created}")
        lines.append("")
    lines.append("---")
    lines.append("")
    if summary:
        lines.append(f"**Summary:** {summary}")
        lines.append("")
    if content and content != summary:
        lines.append(content[:5000])  # Cap content at 5000 chars
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def main():
    dry_run = "--dry-run" in sys.argv

    print("Brain Feed Sync")
    print(f"  Remote: {BRAINFEED_URL}")
    print(f"  Auth: {'configured' if AUTH_TOKEN else 'MISSING'}")
    print()

    # Fetch pending
    chunks = fetch_pending_chunks()
    print(f"Found {len(chunks)} pending chunks")

    if not chunks:
        print("Nothing to sync.")
        return

    context_dir = ROOT / "prompts" / "context"
    synced_ids = []

    for chunk in chunks:
        title = chunk.get("title", "Untitled")
        domain = chunk.get("domain", "general")
        chunk_id = chunk.get("id", "?")

        if dry_run:
            print(f"  [DRY RUN] Would sync: [{domain}] {title} (id:{chunk_id})")
        else:
            filepath = write_chunk_file(chunk, context_dir)
            print(f"  Synced: [{domain}] {title} -> {filepath.relative_to(ROOT)}")
            synced_ids.append(chunk_id)

    if dry_run:
        print(f"\nDry run complete. {len(chunks)} chunks would be synced.")
        return

    # Mark synced
    if synced_ids:
        mark_synced(synced_ids)

    # Reindex
    print("\nReindexing...")
    os.chdir(str(ROOT))
    os.system(f"{sys.executable} -m retrieval index")

    print(f"\nDone. {len(synced_ids)} chunks synced to local index.")


if __name__ == "__main__":
    main()

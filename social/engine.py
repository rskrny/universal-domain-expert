"""
Social Distribution Engine -- Unified posting interface.

Routes content to the correct platform adapter, handles validation,
retry logic, and logging.

Usage:
    from social.engine import post, dry_run

    result = post("linkedin", "text", body="Hello world")
    result = dry_run("linkedin", "text", body="Test")
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseAdapter, ContentSpec, PostResult, PostStatus

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "state" / "social_post_log.jsonl"

# ---------------------------------------------------------------------------
# Adapter Registry
# ---------------------------------------------------------------------------

_adapters: dict = {}


def _get_adapter(platform: str) -> BaseAdapter:
    """Get or create the adapter for a platform."""
    if platform not in _adapters:
        if platform == "linkedin":
            from .adapters.linkedin import LinkedInAdapter
            _adapters[platform] = LinkedInAdapter()
        else:
            raise ValueError(
                f"Platform '{platform}' not supported. "
                f"Available: {list(_adapters.keys()) + ['linkedin']}"
            )
    return _adapters[platform]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log_post(result: PostResult, spec: ContentSpec):
    """Append post result to the log."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": result.platform,
        "status": result.status.value,
        "content_type": spec.content_type,
        "body_preview": spec.body[:100] if spec.body else "",
        "post_id": result.post_id,
        "post_url": result.post_url,
        "error": result.error,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def post(
    platform: str,
    content_type: str,
    body: str = "",
    media: list = None,
    hashtags: list = None,
    schedule_at: Optional[str] = None,
    metadata: dict = None,
) -> PostResult:
    """
    Post content to a social platform.

    Args:
        platform: Target platform ("linkedin", "youtube", etc.)
        content_type: "text", "image", "video", "carousel", "document"
        body: Text content (caption, post body, description)
        media: List of file paths or URLs to media assets
        hashtags: List of hashtag strings (without #)
        schedule_at: ISO 8601 timestamp for scheduled publishing
        metadata: Platform-specific extras

    Returns:
        PostResult with status, post_id, post_url, or error
    """
    adapter = _get_adapter(platform)
    spec = ContentSpec(
        content_type=content_type,
        body=body,
        media=media or [],
        hashtags=hashtags or [],
        schedule_at=schedule_at,
        metadata=metadata or {},
    )

    result = adapter.publish(spec)
    _log_post(result, spec)
    return result


def dry_run(
    platform: str,
    content_type: str,
    body: str = "",
    media: list = None,
    hashtags: list = None,
    metadata: dict = None,
) -> PostResult:
    """
    Validate content without posting. Returns validation result.
    """
    adapter = _get_adapter(platform)
    spec = ContentSpec(
        content_type=content_type,
        body=body,
        media=media or [],
        hashtags=hashtags or [],
        metadata=metadata or {},
    )

    errors = adapter.validate(spec)
    if errors:
        result = PostResult(
            platform=platform,
            status=PostStatus.FAILED,
            error="; ".join(errors),
        )
    else:
        result = PostResult(
            platform=platform,
            status=PostStatus.DRY_RUN,
        )

    _log_post(result, spec)
    return result


def health(platform: str = None) -> dict:
    """Check health of one or all platform adapters."""
    if platform:
        adapter = _get_adapter(platform)
        return adapter.check_health()

    # Check all registered + known platforms
    results = {}
    for p in ["linkedin"]:
        try:
            adapter = _get_adapter(p)
            results[p] = adapter.check_health()
        except Exception as e:
            results[p] = {"status": f"error: {e}"}
    return results

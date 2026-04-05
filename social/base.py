"""
Base adapter interface and shared types for the social distribution engine.

Every platform adapter extends BaseAdapter and implements the same interface.
This ensures consistency when adding new platforms.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class PostStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    DRY_RUN = "dry_run"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"


@dataclass
class PostResult:
    """Standardized result from any platform adapter."""
    platform: str
    status: PostStatus
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def ok(self) -> bool:
        return self.status in (PostStatus.SUCCESS, PostStatus.DRY_RUN)


@dataclass
class ContentSpec:
    """Platform-agnostic content specification."""
    content_type: str  # "text", "image", "video", "carousel", "document"
    body: str = ""
    media: list = field(default_factory=list)  # file paths or URLs
    hashtags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    schedule_at: Optional[str] = None  # ISO 8601


class BaseAdapter:
    """
    Abstract base for all platform adapters.

    Every adapter must implement:
    - validate(spec) -> list of errors (empty = valid)
    - publish(spec) -> PostResult
    - refresh_token() -> bool
    - check_health() -> dict with status info
    """

    platform_name: str = "unknown"

    def validate(self, spec: ContentSpec) -> list:
        """
        Validate content against platform specs.
        Returns a list of error strings. Empty list = valid.
        """
        raise NotImplementedError

    def publish(self, spec: ContentSpec) -> PostResult:
        """
        Publish content to the platform.
        Must call validate() first.
        """
        raise NotImplementedError

    def refresh_token(self) -> bool:
        """
        Refresh the OAuth access token.
        Returns True if successful, False if re-auth needed.
        """
        raise NotImplementedError

    def check_health(self) -> dict:
        """
        Check adapter health: token validity, rate limit headroom, etc.
        Returns dict with status, token_valid, rate_limit_remaining, etc.
        """
        raise NotImplementedError

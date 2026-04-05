"""
LinkedIn Adapter -- Post content to LinkedIn via REST API.

Handles:
- Text posts (personal profile and company pages)
- Image posts (upload + attach)
- Document posts (PDF carousel upload)
- Video posts (upload + attach)

LinkedIn API docs: https://learn.microsoft.com/en-us/linkedin/
Auth: OAuth 2.0 with w_member_social scope (personal) or
      w_organization_social scope (company pages)

Rate limits: 100-500 API calls per day per app.

Required .env variables:
    LINKEDIN_CLIENT_ID
    LINKEDIN_CLIENT_SECRET
    LINKEDIN_ACCESS_TOKEN
    LINKEDIN_PERSON_URN        (e.g., "urn:li:person:abc123")
    LINKEDIN_ORG_URN           (optional, for company pages: "urn:li:organization:12345")

First-time setup:
    1. Create app at https://www.linkedin.com/developers/apps
    2. Request w_member_social and openid scopes
    3. Run: python -m social.adapters.linkedin --setup
    4. Follow the OAuth flow to get your access token
    5. Token lasts 60 days. Refresh token lasts 365 days.
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Add project root
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from social.base import BaseAdapter, ContentSpec, PostResult, PostStatus

# Bypass proxy (Clash Verge fix)
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

API_BASE = "https://api.linkedin.com"
AUTH_BASE = "https://www.linkedin.com/oauth/v2"

# Platform specs from social-distribution.md Framework 4
LINKEDIN_SPECS = {
    "text_max_chars": 3000,
    "hashtag_max": 5,
    "image_formats": ["jpg", "jpeg", "png", "gif"],
    "image_max_bytes": 10 * 1024 * 1024,  # 10MB
    "video_max_bytes": 200 * 1024 * 1024,  # 200MB
    "video_max_duration_sec": 600,  # 10 min
    "document_max_bytes": 100 * 1024 * 1024,  # 100MB
    "best_times": ["07:00-09:00", "17:00-18:00"],  # weekdays, audience timezone
}


def _load_env():
    """Load .env from project root."""
    env_path = ROOT / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('"'))


def _api_request(method, endpoint, token, data=None, headers_extra=None):
    """Make a LinkedIn API request. Returns parsed JSON response."""
    url = f"{API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": "202401",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if headers_extra:
        headers.update(headers_extra)

    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    else:
        body = None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            if resp_body:
                return json.loads(resp_body)
            # 201 Created often has no body but has a header with the post URN
            return {
                "status": resp.status,
                "headers": dict(resp.headers),
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise LinkedInAPIError(e.code, error_body)


class LinkedInAPIError(Exception):
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body
        super().__init__(f"LinkedIn API {status_code}: {body[:200]}")


class LinkedInAdapter(BaseAdapter):
    """LinkedIn platform adapter."""

    platform_name = "linkedin"

    def __init__(self):
        _load_env()
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
        self.access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        self.person_urn = os.getenv("LINKEDIN_PERSON_URN", "")
        self.org_urn = os.getenv("LINKEDIN_ORG_URN", "")

    def _get_author(self, use_org: bool = False) -> str:
        """Get the author URN for posting."""
        if use_org and self.org_urn:
            return self.org_urn
        return self.person_urn

    # ----- Validation -----

    def validate(self, spec: ContentSpec) -> list:
        """Validate content against LinkedIn specs."""
        errors = []

        if not self.access_token:
            errors.append("LINKEDIN_ACCESS_TOKEN not set in .env")
        if not self.person_urn and not self.org_urn:
            errors.append("LINKEDIN_PERSON_URN or LINKEDIN_ORG_URN required in .env")

        # Text validation
        if spec.body and len(spec.body) > LINKEDIN_SPECS["text_max_chars"]:
            errors.append(
                f"Text exceeds {LINKEDIN_SPECS['text_max_chars']} chars "
                f"(got {len(spec.body)})"
            )

        # Hashtag count
        if spec.hashtags and len(spec.hashtags) > LINKEDIN_SPECS["hashtag_max"]:
            errors.append(
                f"Too many hashtags ({len(spec.hashtags)}, max {LINKEDIN_SPECS['hashtag_max']})"
            )

        # Media validation
        if spec.content_type == "image" and spec.media:
            for path in spec.media:
                p = Path(path)
                if p.exists():
                    if p.stat().st_size > LINKEDIN_SPECS["image_max_bytes"]:
                        errors.append(f"Image {p.name} exceeds 10MB")
                    ext = p.suffix.lower().lstrip(".")
                    if ext not in LINKEDIN_SPECS["image_formats"]:
                        errors.append(f"Image format .{ext} not supported (use jpg/png/gif)")

        if spec.content_type == "video" and spec.media:
            for path in spec.media:
                p = Path(path)
                if p.exists() and p.stat().st_size > LINKEDIN_SPECS["video_max_bytes"]:
                    errors.append(f"Video {p.name} exceeds 200MB")

        # Content type validation
        valid_types = ["text", "image", "video", "document"]
        if spec.content_type not in valid_types:
            errors.append(f"Content type '{spec.content_type}' not supported. Use: {valid_types}")

        # Empty post check
        if not spec.body and not spec.media:
            errors.append("Post must have body text or media (or both)")

        return errors

    # ----- Publishing -----

    def publish(self, spec: ContentSpec) -> PostResult:
        """Publish content to LinkedIn."""
        errors = self.validate(spec)
        if errors:
            return PostResult(
                platform=self.platform_name,
                status=PostStatus.FAILED,
                error="; ".join(errors),
            )

        try:
            if spec.content_type == "text":
                return self._post_text(spec)
            elif spec.content_type == "image":
                return self._post_image(spec)
            elif spec.content_type == "document":
                return self._post_document(spec)
            elif spec.content_type == "video":
                return self._post_video(spec)
            else:
                return PostResult(
                    platform=self.platform_name,
                    status=PostStatus.FAILED,
                    error=f"Unsupported content type: {spec.content_type}",
                )
        except LinkedInAPIError as e:
            if e.status_code == 429:
                return PostResult(
                    platform=self.platform_name,
                    status=PostStatus.RATE_LIMITED,
                    error=f"Rate limited: {e.body[:200]}",
                )
            elif e.status_code == 401:
                return PostResult(
                    platform=self.platform_name,
                    status=PostStatus.AUTH_ERROR,
                    error="Access token expired or invalid. Run refresh_token() or re-auth.",
                )
            else:
                return PostResult(
                    platform=self.platform_name,
                    status=PostStatus.FAILED,
                    error=str(e),
                )
        except Exception as e:
            return PostResult(
                platform=self.platform_name,
                status=PostStatus.FAILED,
                error=f"Unexpected error: {e}",
            )

    def _post_text(self, spec: ContentSpec) -> PostResult:
        """Post a text-only update."""
        use_org = spec.metadata.get("use_org", False)
        author = self._get_author(use_org)

        # Build post body with hashtags appended
        body = spec.body
        if spec.hashtags:
            tags = " ".join(f"#{h}" for h in spec.hashtags)
            body = f"{body}\n\n{tags}"

        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": body,
                    },
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
            },
        }

        result = _api_request("POST", "/v2/ugcPosts", self.access_token, payload)

        # Extract post ID from response
        post_id = result.get("id", result.get("headers", {}).get("x-restli-id", ""))
        post_url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None

        return PostResult(
            platform=self.platform_name,
            status=PostStatus.SUCCESS,
            post_id=post_id,
            post_url=post_url,
        )

    def _post_image(self, spec: ContentSpec) -> PostResult:
        """Post with an image attachment."""
        if not spec.media:
            return PostResult(
                platform=self.platform_name,
                status=PostStatus.FAILED,
                error="No image file provided",
            )

        use_org = spec.metadata.get("use_org", False)
        author = self._get_author(use_org)

        # Step 1: Register the image upload
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": author,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }],
            }
        }

        reg_result = _api_request(
            "POST", "/v2/assets?action=registerUpload",
            self.access_token, register_payload,
        )

        upload_url = reg_result["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn = reg_result["value"]["asset"]

        # Step 2: Upload the image binary
        image_path = Path(spec.media[0])
        with open(image_path, "rb") as f:
            image_data = f.read()

        upload_req = urllib.request.Request(
            upload_url,
            data=image_data,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/octet-stream",
            },
            method="PUT",
        )
        urllib.request.urlopen(upload_req, timeout=60)

        # Step 3: Create the post with the image
        body = spec.body
        if spec.hashtags:
            tags = " ".join(f"#{h}" for h in spec.hashtags)
            body = f"{body}\n\n{tags}"

        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": body},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status": "READY",
                        "media": asset_urn,
                        "title": {"text": spec.metadata.get("title", "")},
                    }],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
            },
        }

        result = _api_request("POST", "/v2/ugcPosts", self.access_token, payload)
        post_id = result.get("id", result.get("headers", {}).get("x-restli-id", ""))

        return PostResult(
            platform=self.platform_name,
            status=PostStatus.SUCCESS,
            post_id=post_id,
            post_url=f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None,
        )

    def _post_document(self, spec: ContentSpec) -> PostResult:
        """Post a document (PDF carousel). Placeholder for future implementation."""
        return PostResult(
            platform=self.platform_name,
            status=PostStatus.FAILED,
            error="Document posting not yet implemented. Coming in v2.",
        )

    def _post_video(self, spec: ContentSpec) -> PostResult:
        """Post a video. Placeholder for future implementation."""
        return PostResult(
            platform=self.platform_name,
            status=PostStatus.FAILED,
            error="Video posting not yet implemented. Coming in v2.",
        )

    # ----- Auth -----

    def refresh_token(self) -> bool:
        """Refresh the LinkedIn access token using the refresh token."""
        refresh = os.getenv("LINKEDIN_REFRESH_TOKEN", "")
        if not refresh:
            print("No LINKEDIN_REFRESH_TOKEN in .env. Re-authorize manually.")
            return False

        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }).encode()

        req = urllib.request.Request(
            f"{AUTH_BASE}/accessToken",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
            new_token = result.get("access_token", "")
            if new_token:
                self.access_token = new_token
                print(f"Token refreshed. Expires in {result.get('expires_in', '?')} seconds.")
                print(f"Update LINKEDIN_ACCESS_TOKEN in .env with: {new_token[:20]}...")
                return True
        except Exception as e:
            print(f"Token refresh failed: {e}")

        return False

    # ----- Health -----

    def check_health(self) -> dict:
        """Check LinkedIn adapter health."""
        health = {
            "platform": self.platform_name,
            "client_id_set": bool(self.client_id),
            "access_token_set": bool(self.access_token),
            "person_urn_set": bool(self.person_urn),
            "org_urn_set": bool(self.org_urn),
            "token_valid": False,
        }

        if not self.access_token:
            health["status"] = "no_token"
            return health

        # Test token by making a lightweight API call
        # w_member_social scope can't access /v2/userinfo (needs openid).
        # Instead, try a small UGC query scoped to the author.
        try:
            author = self.person_urn or self.org_urn
            endpoint = f"/v2/ugcPosts?q=authors&authors=List({urllib.parse.quote(author, safe='')})"
            result = _api_request("GET", endpoint, self.access_token)
            health["token_valid"] = True
            health["recent_posts"] = len(result.get("elements", []))
            health["status"] = "healthy"
        except LinkedInAPIError as e:
            if e.status_code == 401:
                health["status"] = "token_expired"
            elif e.status_code == 403:
                # Token works but endpoint restricted. Token is still valid.
                health["token_valid"] = True
                health["status"] = "healthy_limited"
            else:
                health["status"] = f"api_error_{e.status_code}"
        except Exception as e:
            health["status"] = f"error: {e}"

        return health


# ---------------------------------------------------------------------------
# OAuth Setup Helper
# ---------------------------------------------------------------------------

def run_oauth_setup():
    """Interactive OAuth setup for LinkedIn."""
    _load_env()
    client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first.")
        print("Create an app at: https://www.linkedin.com/developers/apps")
        return

    redirect_uri = "http://localhost:8888/callback"
    scopes = "openid profile w_member_social"

    auth_url = (
        f"{AUTH_BASE}/authorization?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"scope={urllib.parse.quote(scopes)}"
    )

    print("LinkedIn OAuth Setup")
    print("=" * 50)
    print(f"\n1. Open this URL in your browser:\n\n{auth_url}\n")
    print("2. Authorize the app.")
    print("3. You'll be redirected to localhost. Copy the 'code' parameter from the URL.")
    print("   (It will look like: http://localhost:8888/callback?code=AQ...)\n")

    code = input("4. Paste the authorization code here: ").strip()

    if not code:
        print("No code provided. Aborting.")
        return

    # Exchange code for token
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }).encode()

    req = urllib.request.Request(
        f"{AUTH_BASE}/accessToken",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Token exchange failed: {e}")
        return

    access_token = result.get("access_token", "")
    refresh_token = result.get("refresh_token", "")
    expires_in = result.get("expires_in", 0)

    if not access_token:
        print(f"No access token received: {result}")
        return

    print(f"\nAccess token received (expires in {expires_in // 3600} hours)")

    # Get person URN
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        req = urllib.request.Request(
            f"{API_BASE}/v2/userinfo",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            userinfo = json.loads(resp.read().decode())
        person_sub = userinfo.get("sub", "")
        person_name = userinfo.get("name", "")
        print(f"Authenticated as: {person_name} (sub: {person_sub})")
    except Exception as e:
        print(f"Could not fetch profile: {e}")
        person_sub = ""

    print("\n5. Add these to your .env file:\n")
    print(f"LINKEDIN_ACCESS_TOKEN={access_token}")
    if refresh_token:
        print(f"LINKEDIN_REFRESH_TOKEN={refresh_token}")
    if person_sub:
        print(f"LINKEDIN_PERSON_URN=urn:li:person:{person_sub}")
    print(f"\nToken expires in {expires_in // 86400} days. Set a reminder to refresh.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if "--setup" in sys.argv:
        run_oauth_setup()
        return

    if "--health" in sys.argv:
        adapter = LinkedInAdapter()
        health = adapter.check_health()
        print(json.dumps(health, indent=2))
        return

    if "--test" in sys.argv:
        # Dry run test
        adapter = LinkedInAdapter()
        spec = ContentSpec(
            content_type="text",
            body="Testing the social distribution engine. This is a dry run.",
            hashtags=["automation", "test"],
        )
        errors = adapter.validate(spec)
        if errors:
            print("Validation errors:")
            for e in errors:
                print(f"  - {e}")
        else:
            print("Validation passed. Ready to post.")
            print(f"  Body: {spec.body[:80]}...")
            print(f"  Hashtags: {spec.hashtags}")
            print(f"  Author: {adapter.person_urn or adapter.org_urn or 'NOT SET'}")
        return

    print("LinkedIn Adapter")
    print("  --setup   Run OAuth setup flow")
    print("  --health  Check adapter health")
    print("  --test    Dry run validation test")


if __name__ == "__main__":
    main()

"""
Social Distribution Engine.

Unified interface for posting content across social media platforms.
Each platform has its own adapter in social/adapters/ that handles
OAuth, content validation, and API calls.

Usage:
    from social import post, dry_run

    # Post text to LinkedIn
    result = post("linkedin", "text", body="Hello from the pipeline")

    # Dry run (validate without posting)
    result = dry_run("linkedin", "text", body="Test post")
"""

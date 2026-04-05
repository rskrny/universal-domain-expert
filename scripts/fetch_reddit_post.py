"""Fetch a specific Reddit post and all comments, save to file."""
import requests
import json
import textwrap

# Reddit API credentials
CLIENT_ID = "osNVGC2jcDVmnAdrfVFfQQ"
CLIENT_SECRET = "EHHuKbDkF6Lvkq21VQaXd_Y1MZGoyw"
USERNAME = "slamjacket"
PASSWORD = "m@c@r@nI1"
USER_AGENT = "python:universal-domain-expert:v1.0 (by /u/slamjacket)"

OUTPUT_PATH = r"C:\Users\rskrn\Desktop\universal-domain-expert - Copy\state\reddit_post_output.txt"

TARGET_AUTHOR = "Medium_Island_2795"
TARGET_TITLE_FRAGMENT = "anthropic isn't the only reason"
SUBREDDIT = "ClaudeCode"


def authenticate():
    """Get OAuth token from Reddit."""
    session = requests.Session()
    session.trust_env = False  # bypass proxy
    session.headers.update({"User-Agent": USER_AGENT})

    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD,
    }
    resp = session.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=auth,
        data=data,
    )
    resp.raise_for_status()
    token_data = resp.json()
    if "access_token" not in token_data:
        raise RuntimeError(f"Auth failed: {token_data}")

    session.headers.update({
        "Authorization": f"Bearer {token_data['access_token']}"
    })
    print(f"Authenticated successfully. Token type: {token_data.get('token_type')}")
    return session


def find_post(session):
    """Search for the target post in r/ClaudeCode."""
    # Try search first
    print("Searching for post...")
    resp = session.get(
        f"https://oauth.reddit.com/r/{SUBREDDIT}/search",
        params={
            "q": f"author:{TARGET_AUTHOR}",
            "restrict_sr": "on",
            "sort": "new",
            "limit": 25,
            "type": "link",
        },
    )
    resp.raise_for_status()
    data = resp.json()

    posts = data.get("data", {}).get("children", [])
    print(f"  Search returned {len(posts)} posts")

    for post in posts:
        pd = post["data"]
        if TARGET_AUTHOR.lower() in pd.get("author", "").lower():
            if TARGET_TITLE_FRAGMENT.lower() in pd.get("title", "").lower():
                print(f"  Found via search: {pd['title'][:80]}")
                return pd

    # Fallback: browse new posts
    print("  Not found via search, browsing new posts...")
    for sort in ["new", "hot", "rising"]:
        resp = session.get(
            f"https://oauth.reddit.com/r/{SUBREDDIT}/{sort}",
            params={"limit": 100},
        )
        resp.raise_for_status()
        listing = resp.json()
        posts = listing.get("data", {}).get("children", [])
        print(f"  Checked {sort}: {len(posts)} posts")

        for post in posts:
            pd = post["data"]
            if TARGET_AUTHOR.lower() in pd.get("author", "").lower():
                if TARGET_TITLE_FRAGMENT.lower() in pd.get("title", "").lower():
                    print(f"  Found via {sort}: {pd['title'][:80]}")
                    return pd
            # Also print author matches for debugging
            if TARGET_AUTHOR.lower() in pd.get("author", "").lower():
                print(f"    Author match: {pd['title'][:80]}")

    # Last resort: search without author filter
    print("  Trying broader search...")
    resp = session.get(
        f"https://oauth.reddit.com/r/{SUBREDDIT}/search",
        params={
            "q": "anthropic limits",
            "restrict_sr": "on",
            "sort": "new",
            "limit": 50,
            "type": "link",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    posts = data.get("data", {}).get("children", [])
    print(f"  Broad search returned {len(posts)} posts")
    for post in posts:
        pd = post["data"]
        if TARGET_TITLE_FRAGMENT.lower() in pd.get("title", "").lower():
            print(f"  Found via broad search: {pd['title'][:80]}")
            return pd
        if TARGET_AUTHOR.lower() in pd.get("author", "").lower():
            print(f"    Author match: {pd['title'][:80]}")

    return None


def get_all_comments(session, post_id, permalink):
    """Fetch all comments for a post, handling 'more' comment stubs."""
    print(f"Fetching comments for post {post_id}...")
    resp = session.get(
        f"https://oauth.reddit.com/comments/{post_id}",
        params={"limit": 500, "depth": 10, "sort": "top"},
    )
    resp.raise_for_status()
    data = resp.json()

    comments = []
    if len(data) > 1:
        comment_listing = data[1]
        parse_comments(comment_listing.get("data", {}).get("children", []), comments, depth=0)

    # Try to expand "more" comments
    more_ids = collect_more_ids(data)
    if more_ids:
        print(f"  Expanding {len(more_ids)} 'more' comment stubs...")
        # Process in batches of 100
        for i in range(0, len(more_ids), 100):
            batch = more_ids[i:i+100]
            try:
                resp = session.post(
                    "https://oauth.reddit.com/api/morechildren",
                    data={
                        "api_type": "json",
                        "link_id": f"t3_{post_id}",
                        "children": ",".join(batch),
                        "sort": "top",
                    },
                )
                resp.raise_for_status()
                more_data = resp.json()
                things = more_data.get("json", {}).get("data", {}).get("things", [])
                for thing in things:
                    if thing["kind"] == "t1":
                        cd = thing["data"]
                        indent = "  " * cd.get("depth", 0)
                        comments.append({
                            "author": cd.get("author", "[deleted]"),
                            "score": cd.get("score", 0),
                            "body": cd.get("body", ""),
                            "depth": cd.get("depth", 0),
                        })
                print(f"    Batch {i//100 + 1}: got {len(things)} more comments")
            except Exception as e:
                print(f"    Error expanding more comments: {e}")

    print(f"  Total comments collected: {len(comments)}")
    return comments


def parse_comments(children, comments, depth):
    """Recursively parse comment tree."""
    for child in children:
        if child["kind"] == "t1":
            cd = child["data"]
            comments.append({
                "author": cd.get("author", "[deleted]"),
                "score": cd.get("score", 0),
                "body": cd.get("body", ""),
                "depth": depth,
            })
            # Recurse into replies
            replies = cd.get("replies", "")
            if isinstance(replies, dict):
                reply_children = replies.get("data", {}).get("children", [])
                parse_comments(reply_children, comments, depth + 1)
        elif child["kind"] == "more":
            pass  # handled separately


def collect_more_ids(data):
    """Collect all 'more' comment IDs from the response."""
    ids = []
    if len(data) > 1:
        _collect_more_recursive(data[1].get("data", {}).get("children", []), ids)
    return ids


def _collect_more_recursive(children, ids):
    for child in children:
        if child["kind"] == "more":
            more_children = child.get("data", {}).get("children", [])
            ids.extend(more_children)
        elif child["kind"] == "t1":
            replies = child["data"].get("replies", "")
            if isinstance(replies, dict):
                _collect_more_recursive(replies.get("data", {}).get("children", []), ids)


def extract_links(text):
    """Extract URLs from text."""
    import re
    urls = re.findall(r'https?://[^\s\)>\]]+', text or "")
    return urls


def write_output(post_data, comments):
    """Write everything to the output file."""
    links_in_post = extract_links(post_data.get("selftext", ""))
    if post_data.get("url") and post_data["url"] not in links_in_post:
        links_in_post.insert(0, post_data["url"])

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("REDDIT POST CAPTURE\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Title: {post_data.get('title', 'N/A')}\n")
        f.write(f"Author: u/{post_data.get('author', 'N/A')}\n")
        f.write(f"Score: {post_data.get('score', 'N/A')}\n")
        f.write(f"Upvote Ratio: {post_data.get('upvote_ratio', 'N/A')}\n")
        f.write(f"Subreddit: r/{post_data.get('subreddit', 'N/A')}\n")
        f.write(f"URL: https://reddit.com{post_data.get('permalink', '')}\n")
        f.write(f"Created UTC: {post_data.get('created_utc', 'N/A')}\n")
        f.write(f"Num Comments: {post_data.get('num_comments', 'N/A')}\n")
        f.write(f"Link Flair: {post_data.get('link_flair_text', 'N/A')}\n")

        f.write("\n" + "-" * 80 + "\n")
        f.write("LINKS FOUND IN POST\n")
        f.write("-" * 80 + "\n")
        if links_in_post:
            for link in links_in_post:
                f.write(f"  {link}\n")
        else:
            f.write("  (none)\n")

        f.write("\n" + "-" * 80 + "\n")
        f.write("FULL POST TEXT (selftext)\n")
        f.write("-" * 80 + "\n\n")
        selftext = post_data.get("selftext", "(no text)")
        f.write(selftext)
        f.write("\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write(f"COMMENTS ({len(comments)} total)\n")
        f.write("=" * 80 + "\n\n")

        for i, c in enumerate(comments):
            indent = "  " * c["depth"]
            f.write(f"{indent}--- Comment #{i+1} (depth {c['depth']}) ---\n")
            f.write(f"{indent}Author: u/{c['author']}\n")
            f.write(f"{indent}Score: {c['score']}\n")
            f.write(f"{indent}Body:\n")
            for line in c["body"].split("\n"):
                f.write(f"{indent}  {line}\n")
            f.write("\n")

            # Extract links from comments too
            comment_links = extract_links(c["body"])
            if comment_links:
                f.write(f"{indent}Links in comment:\n")
                for link in comment_links:
                    f.write(f"{indent}  {link}\n")
                f.write("\n")

    print(f"\nOutput written to: {OUTPUT_PATH}")
    print(f"File size: {len(open(OUTPUT_PATH, encoding='utf-8').read())} characters")


def main():
    session = authenticate()

    post_data = find_post(session)
    if not post_data:
        print("\nERROR: Could not find the target post.")
        print(f"  Looking for author: {TARGET_AUTHOR}")
        print(f"  Looking for title containing: {TARGET_TITLE_FRAGMENT}")

        # Dump recent posts for debugging
        print("\nRecent posts in r/ClaudeCode:")
        resp = session.get(
            f"https://oauth.reddit.com/r/{SUBREDDIT}/new",
            params={"limit": 20},
        )
        for p in resp.json().get("data", {}).get("children", []):
            pd = p["data"]
            print(f"  [{pd.get('author')}] {pd.get('title')[:70]}")
        return

    post_id = post_data["id"]
    permalink = post_data.get("permalink", "")

    comments = get_all_comments(session, post_id, permalink)
    write_output(post_data, comments)
    print("Done!")


if __name__ == "__main__":
    main()

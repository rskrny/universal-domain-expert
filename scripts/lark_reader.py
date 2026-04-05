"""
Read Lark/Feishu messages for situational awareness.

Supports TWO organizations:
  - Brain Feed (ShopMyRoom, Lark international): personal/startup comms
  - FlipBot (BrandPal, Feishu China): Flip Side team comms

Usage:
    python scripts/lark_reader.py chats                          -- list all chats (both orgs)
    python scripts/lark_reader.py chats --org brainfeed          -- list Brain Feed chats only
    python scripts/lark_reader.py chats --org flipbot            -- list FlipBot chats only
    python scripts/lark_reader.py messages CHAT_ID               -- get recent messages (default 10)
    python scripts/lark_reader.py messages CHAT_ID --count 20    -- get last 20 messages
    python scripts/lark_reader.py search CHAT_ID "keyword"       -- search messages for keyword
    python scripts/lark_reader.py all --count 5                  -- get last 5 messages from ALL chats

Chat IDs starting with 'oc_9' are auto-routed to FlipBot/Feishu.
Chat IDs starting with 'oc_a' are auto-routed to Brain Feed/Lark.

Requires .env with BRAINFEED_APP_ID, BRAINFEED_APP_SECRET, LARK_APP_ID, LARK_APP_SECRET.
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# Bypass proxy (Clash Verge fix for China networking)
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Two org configurations
ORGS = {
    "brainfeed": {
        "name": "Brain Feed (ShopMyRoom/Lark)",
        "base_url": "https://open.larksuite.com/open-apis",
        "app_id_env": "BRAINFEED_APP_ID",
        "app_secret_env": "BRAINFEED_APP_SECRET",
    },
    "flipbot": {
        "name": "FlipBot (BrandPal/Feishu)",
        "base_url": "https://open.feishu.cn/open-apis",
        "app_id_env": "LARK_APP_ID",
        "app_secret_env": "LARK_APP_SECRET",
    },
}


def load_env():
    """Load .env files from both projects."""
    env_files = [
        os.path.join(BASE_DIR, ".env"),
        os.path.join(os.path.expanduser("~"), "Desktop", "The Flip Side", ".env"),
    ]
    for env_path in env_files:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ.setdefault(key.strip(), val.strip().strip('"'))


def get_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def detect_org(chat_id):
    """Auto-detect which org a chat_id belongs to based on prefix."""
    # FlipBot chats tend to start with oc_9, Brain Feed with oc_a
    # This is a heuristic. We also cache known mappings.
    known = {
        "oc_ab26f9abaea8f93912614f7e7284abd6": "brainfeed",
        "oc_9b7177c2360c422b47af8a9c890635f8": "flipbot",
        "oc_9ab63146985ea87abe6718c9ea304822": "flipbot",
    }
    if chat_id in known:
        return known[chat_id]
    # Try both orgs and see which one works
    return None


def get_token(opener, org_key="brainfeed"):
    """Get a tenant access token for the specified org."""
    org = ORGS[org_key]
    app_id = os.environ.get(org["app_id_env"])
    app_secret = os.environ.get(org["app_secret_env"])
    if not app_id or not app_secret:
        raise ValueError(f"{org['app_id_env']} and {org['app_secret_env']} required in .env for {org['name']}")

    req = urllib.request.Request(
        f"{org['base_url']}/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with opener.open(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        raise RuntimeError(f"Token error for {org['name']}: {data}")
    return data["tenant_access_token"]


def get_base_url(org_key="brainfeed"):
    return ORGS[org_key]["base_url"]


def api_get(opener, token, path, params=None, org_key="brainfeed"):
    """Make an authenticated GET request to Lark/Feishu API."""
    url = f"{get_base_url(org_key)}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with opener.open(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {e.code}: {body}")
    return data


def list_chats(opener, token, org_key="brainfeed"):
    """List all chats the bot is a member of."""
    chats = []
    page_token = None

    while True:
        params = {"page_size": 50}
        if page_token:
            params["page_token"] = page_token

        data = api_get(opener, token, "/im/v1/chats", params, org_key=org_key)

        if data.get("code") != 0:
            print(f"Error listing chats for {ORGS[org_key]['name']}: {data.get('msg', 'Unknown error')}")
            print(f"Error code: {data.get('code')}")
            if data.get("code") == 99991663:
                print("\nPermission missing: im:chat:readonly scope required.")
            return chats

        items = data.get("data", {}).get("items", [])
        for item in items:
            item["_org"] = org_key
        chats.extend(items)

        page_token = data.get("data", {}).get("page_token")
        if not page_token or not data.get("data", {}).get("has_more"):
            break

    return chats


def get_messages(opener, token, chat_id, count=10, org_key="brainfeed"):
    """Get recent messages from a chat. Returns newest first."""
    messages = []
    page_token = None
    remaining = count

    while remaining > 0:
        params = {
            "container_id_type": "chat",
            "container_id": chat_id,
            "page_size": min(remaining, 50),
            "sort_type": "ByCreateTimeDesc",
        }
        if page_token:
            params["page_token"] = page_token

        data = api_get(opener, token, "/im/v1/messages", params, org_key=org_key)

        if data.get("code") != 0:
            print(f"Error reading messages from {ORGS[org_key]['name']}: {data.get('msg', 'Unknown error')}")
            print(f"Error code: {data.get('code')}")
            if data.get("code") in (99991663, 230027):
                print("\nPermission missing. Required scopes:")
                print("  - im:message (or im:message:readonly)")
                print("  - im:message.group_msg (for group chat messages)")
            return messages

        items = data.get("data", {}).get("items", [])
        for item in items:
            item["_org"] = org_key
        messages.extend(items)
        remaining -= len(items)

        page_token = data.get("data", {}).get("page_token")
        if not page_token or not data.get("data", {}).get("has_more") or not items:
            break

    return messages


def format_timestamp(ts_ms):
    """Convert millisecond timestamp string to readable datetime."""
    try:
        ts = int(ts_ms) / 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return ts_ms


def extract_text_content(body_json):
    """Extract readable text from a Lark message body JSON string."""
    try:
        body = json.loads(body_json) if isinstance(body_json, str) else body_json
    except (json.JSONDecodeError, TypeError):
        return str(body_json)

    # Plain text message
    if isinstance(body, dict) and "text" in body:
        return body["text"]

    # Post (rich text) message
    if isinstance(body, dict) and ("content" in body or "title" in body):
        parts = []
        if body.get("title"):
            parts.append(f"[{body['title']}]")
        content = body.get("content", [])
        if isinstance(content, list):
            for paragraph in content:
                if isinstance(paragraph, list):
                    line_parts = []
                    for elem in paragraph:
                        if isinstance(elem, dict):
                            tag = elem.get("tag", "")
                            if tag == "text":
                                line_parts.append(elem.get("text", ""))
                            elif tag == "a":
                                line_parts.append(f"{elem.get('text', '')} ({elem.get('href', '')})")
                            elif tag == "at":
                                line_parts.append(f"@{elem.get('user_name', elem.get('user_id', 'someone'))}")
                            elif tag == "img":
                                line_parts.append("[image]")
                            elif tag == "media":
                                line_parts.append("[media]")
                            else:
                                line_parts.append(elem.get("text", f"[{tag}]"))
                    parts.append("".join(line_parts))
        return "\n".join(parts) if parts else str(body)

    # Interactive card
    if isinstance(body, dict) and "header" in body:
        title = body.get("header", {}).get("title", {}).get("content", "")
        elements = body.get("elements", [])
        texts = [f"[Card: {title}]"]
        for elem in elements:
            if isinstance(elem, dict):
                text_obj = elem.get("text", {})
                if isinstance(text_obj, dict):
                    texts.append(text_obj.get("content", ""))
        return "\n".join(texts)

    # Image message
    if isinstance(body, dict) and "image_key" in body:
        return "[image]"

    # File message
    if isinstance(body, dict) and "file_key" in body:
        return f"[file: {body.get('file_name', 'unknown')}]"

    return str(body)


def format_message(msg):
    """Format a single message for display."""
    sender = msg.get("sender", {})
    sender_type = sender.get("sender_type", "unknown")
    sender_id = sender.get("id", "unknown")
    msg_type = msg.get("msg_type", "unknown")
    create_time = format_timestamp(msg.get("create_time", ""))
    body = msg.get("body", {}).get("content", "{}")

    # Sender label
    if sender_type == "app":
        sender_label = "Bot"
    else:
        sender_label = f"User:{sender_id[:8]}"

    content = extract_text_content(body)

    return {
        "time": create_time,
        "sender": sender_label,
        "type": msg_type,
        "content": content,
        "message_id": msg.get("message_id", ""),
    }


def print_chats(chats):
    """Print chat list in readable format."""
    if not chats:
        print("No chats found. The bot may not be in any chats, or im:chat:readonly scope is missing.")
        return

    print(f"\nFound {len(chats)} chat(s):\n")
    print(f"{'Chat ID':<45} {'Name':<30} {'Type':<10} {'Members'}")
    print("-" * 100)
    for chat in chats:
        chat_id = chat.get("chat_id", "")
        name = chat.get("name", "(unnamed)")
        chat_type = chat.get("chat_type", "")
        member_count = chat.get("user_count", "?")
        print(f"{chat_id:<45} {name:<30} {chat_type:<10} {member_count}")


def print_messages(messages):
    """Print messages in readable format."""
    if not messages:
        print("No messages found. The chat may be empty, or im:message:readonly scope is missing.")
        return

    formatted = [format_message(m) for m in messages]
    # Reverse so oldest is first (chronological order)
    formatted.reverse()

    print(f"\n--- {len(formatted)} messages (oldest first) ---\n")
    for m in formatted:
        print(f"[{m['time']}] {m['sender']} ({m['type']})")
        # Indent multiline content
        for line in m["content"].split("\n"):
            print(f"  {line}")
        print()


def search_messages(opener, token, chat_id, keyword, max_pages=5):
    """Search through recent messages for a keyword. Fetches up to max_pages * 50 messages."""
    all_messages = get_messages(opener, token, chat_id, count=max_pages * 50)
    matches = []
    keyword_lower = keyword.lower()

    for msg in all_messages:
        formatted = format_message(msg)
        if keyword_lower in formatted["content"].lower():
            matches.append(formatted)

    return matches


def messages_to_text(messages):
    """Convert messages to plain text for digest/export."""
    formatted = [format_message(m) for m in messages]
    formatted.reverse()  # chronological

    lines = []
    for m in formatted:
        lines.append(f"[{m['time']}] {m['sender']} ({m['type']}): {m['content']}")
    return "\n".join(lines)


def resolve_org_for_chat(chat_id, opener):
    """Determine which org a chat_id belongs to. Try known mapping first, then probe both."""
    org = detect_org(chat_id)
    if org:
        return org
    # Probe both orgs
    for org_key in ORGS:
        try:
            token = get_token(opener, org_key)
            data = api_get(opener, token, "/im/v1/messages", {
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 1,
            }, org_key=org_key)
            if data.get("code") == 0:
                return org_key
        except Exception:
            continue
    return "brainfeed"  # default


if __name__ == "__main__":
    load_env()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    opener = get_opener()

    # Parse --org flag
    org_filter = None
    if "--org" in sys.argv:
        idx = sys.argv.index("--org")
        if idx + 1 < len(sys.argv):
            org_filter = sys.argv[idx + 1].lower()

    if cmd == "chats":
        orgs_to_check = [org_filter] if org_filter else list(ORGS.keys())
        all_chats = []
        for org_key in orgs_to_check:
            try:
                token = get_token(opener, org_key)
                chats = list_chats(opener, token, org_key)
                all_chats.extend(chats)
                print(f"\n[{ORGS[org_key]['name']}]")
                print_chats(chats)
            except Exception as e:
                print(f"\n[{ORGS[org_key]['name']}] Error: {e}")

    elif cmd == "messages" and len(sys.argv) >= 3:
        chat_id = sys.argv[2]
        count = 10
        if "--count" in sys.argv:
            idx = sys.argv.index("--count")
            if idx + 1 < len(sys.argv):
                count = int(sys.argv[idx + 1])

        org_key = org_filter or resolve_org_for_chat(chat_id, opener)
        token = get_token(opener, org_key)
        print(f"[{ORGS[org_key]['name']}]")
        messages = get_messages(opener, token, chat_id, count=count, org_key=org_key)
        print_messages(messages)

    elif cmd == "all":
        count = 5
        if "--count" in sys.argv:
            idx = sys.argv.index("--count")
            if idx + 1 < len(sys.argv):
                count = int(sys.argv[idx + 1])

        for org_key in ORGS:
            try:
                token = get_token(opener, org_key)
                chats = list_chats(opener, token, org_key)
                print(f"\n{'='*60}")
                print(f"  {ORGS[org_key]['name']} ({len(chats)} chats)")
                print(f"{'='*60}")
                for chat in chats:
                    chat_id = chat.get("chat_id", "")
                    chat_name = chat.get("name", "(unnamed)")
                    print(f"\n--- {chat_name} ---")
                    try:
                        messages = get_messages(opener, token, chat_id, count=count, org_key=org_key)
                        print_messages(messages)
                    except Exception as e:
                        print(f"  Error reading: {e}")
            except Exception as e:
                print(f"\n[{ORGS[org_key]['name']}] Error: {e}")

    elif cmd == "search" and len(sys.argv) >= 4:
        chat_id = sys.argv[2]
        keyword = sys.argv[3]
        org_key = org_filter or resolve_org_for_chat(chat_id, opener)
        token = get_token(opener, org_key)
        matches = search_messages(opener, token, chat_id, keyword)
        if matches:
            matches.reverse()
            print(f"\nFound {len(matches)} message(s) matching '{keyword}':\n")
            for m in matches:
                print(f"[{m['time']}] {m['sender']} ({m['type']})")
                for line in m["content"].split("\n"):
                    print(f"  {line}")
                print()
        else:
            print(f"No messages found matching '{keyword}'.")

    else:
        print(__doc__)
        sys.exit(1)

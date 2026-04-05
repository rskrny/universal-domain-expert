"""
Lark/Feishu Message Sync -- Automatic cross-org message capture.

Polls all monitored chats from both orgs (Brain Feed + FlipBot),
captures new messages since last sync, and sends a consolidated
digest to Brain Feed. Tracks state to avoid duplicates.

Usage:
    python scripts/lark_sync.py                   -- sync all monitored chats
    python scripts/lark_sync.py --send-digest      -- sync + send digest card to Brain Feed
    python scripts/lark_sync.py --status            -- show sync state (last sync per chat)

State file: state/lark_sync_state.json
Digest file: state/lark_digest.md
"""

import json
import os
import sys
import time
from datetime import datetime

# Add scripts dir to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

from lark_reader import (
    load_env, get_opener, get_token, list_chats, get_messages,
    format_message, ORGS
)

STATE_FILE = os.path.join(BASE_DIR, "state", "lark_sync_state.json")
DIGEST_FILE = os.path.join(BASE_DIR, "state", "lark_digest.md")

# Chats to monitor. Add new ones as FlipBot joins more groups.
# Format: (chat_id, org_key, display_name)
MONITORED_CHATS = [
    ("oc_ab26f9abaea8f93912614f7e7284abd6", "brainfeed", "Brain Feed (Personal)"),
    ("oc_9b7177c2360c422b47af8a9c890635f8", "flipbot", "Flip Side AI - Test"),
    ("oc_9ab63146985ea87abe6718c9ea304822", "flipbot", "FlipBot DM"),
    # Add team chats here as FlipBot joins them:
    # ("oc_XXXXXXXXX", "flipbot", "Flip Side Team"),
]


def load_state():
    """Load last-sync timestamps per chat."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    """Save sync state."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def sync_chat(opener, token, chat_id, org_key, display_name, state, max_messages=50):
    """Fetch new messages from a chat since last sync. Returns list of formatted messages."""
    last_ts = state.get(chat_id, {}).get("last_message_ts", "0")
    last_count = state.get(chat_id, {}).get("total_synced", 0)

    messages = get_messages(opener, token, chat_id, count=max_messages, org_key=org_key)

    if not messages:
        return []

    # Filter to only new messages (timestamp > last_ts)
    new_messages = []
    newest_ts = last_ts
    for msg in messages:
        msg_ts = msg.get("create_time", "0")
        if msg_ts > last_ts:
            formatted = format_message(msg)
            formatted["chat_name"] = display_name
            formatted["org"] = org_key
            new_messages.append(formatted)
            if msg_ts > newest_ts:
                newest_ts = msg_ts

    # Update state
    if newest_ts > last_ts:
        state[chat_id] = {
            "last_message_ts": newest_ts,
            "last_sync": datetime.now().isoformat(),
            "display_name": display_name,
            "org": org_key,
            "total_synced": last_count + len(new_messages),
        }

    # Return in chronological order (oldest first)
    new_messages.reverse()
    return new_messages


def build_digest(all_new_messages):
    """Build a markdown digest from new messages."""
    if not all_new_messages:
        return None

    lines = [
        "# Lark Message Digest",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> New messages: {len(all_new_messages)}",
        "",
        "---",
        "",
    ]

    # Group by chat
    by_chat = {}
    for msg in all_new_messages:
        chat = msg.get("chat_name", "Unknown")
        if chat not in by_chat:
            by_chat[chat] = []
        by_chat[chat].append(msg)

    for chat_name, messages in by_chat.items():
        org_label = messages[0].get("org", "")
        org_display = ORGS.get(org_label, {}).get("name", org_label)
        lines.append(f"## {chat_name}")
        lines.append(f"*{org_display}* | {len(messages)} new message(s)")
        lines.append("")

        for msg in messages:
            sender = msg.get("sender", "?")
            time_str = msg.get("time", "?")
            content = msg.get("content", "").replace("\n", "\n  ")
            msg_type = msg.get("type", "text")

            if msg_type in ("system",):
                continue

            lines.append(f"**[{time_str}] {sender}** ({msg_type})")
            lines.append(f"  {content}")
            lines.append("")

    return "\n".join(lines)


def build_card_digest(all_new_messages):
    """Build a Lark card for the digest summary."""
    if not all_new_messages:
        return None

    # Count by chat
    by_chat = {}
    for msg in all_new_messages:
        chat = msg.get("chat_name", "Unknown")
        if chat not in by_chat:
            by_chat[chat] = 0
        by_chat[chat] += 1

    summary_lines = []
    for chat, count in by_chat.items():
        summary_lines.append(f"- **{chat}**: {count} new message(s)")

    # Extract key content snippets (first 3 non-bot messages)
    highlights = []
    for msg in all_new_messages:
        if msg.get("sender", "").startswith("Bot"):
            continue
        content = msg.get("content", "")[:100]
        if content and len(highlights) < 3:
            chat = msg.get("chat_name", "")
            highlights.append(f"- [{chat}] {content}")

    body = "\n".join(summary_lines)
    if highlights:
        body += "\n\n**Highlights:**\n" + "\n".join(highlights)

    return {
        "title": f"Message Sync: {len(all_new_messages)} new",
        "body": body,
        "color": "blue",
    }


def run_sync(send_digest=False):
    """Main sync loop. Polls all monitored chats and builds digest."""
    load_env()
    opener = get_opener()
    state = load_state()

    all_new = []
    tokens = {}

    print(f"Syncing {len(MONITORED_CHATS)} chats...")
    print(f"State file: {STATE_FILE}")
    print()

    for chat_id, org_key, display_name in MONITORED_CHATS:
        # Cache tokens per org
        if org_key not in tokens:
            try:
                tokens[org_key] = get_token(opener, org_key)
            except Exception as e:
                print(f"  SKIP {display_name}: token error ({e})")
                continue

        token = tokens[org_key]
        try:
            new_messages = sync_chat(opener, token, chat_id, org_key, display_name, state)
            print(f"  {display_name}: {len(new_messages)} new message(s)")
            all_new.extend(new_messages)
        except Exception as e:
            print(f"  {display_name}: ERROR ({e})")

    # Save state
    save_state(state)

    # Build and save digest
    if all_new:
        digest = build_digest(all_new)
        if digest:
            os.makedirs(os.path.dirname(DIGEST_FILE), exist_ok=True)
            with open(DIGEST_FILE, "w", encoding="utf-8") as f:
                f.write(digest)
            print(f"\nDigest saved: {DIGEST_FILE} ({len(all_new)} messages)")

        # Send card to Brain Feed
        if send_digest and all_new:
            card = build_card_digest(all_new)
            if card:
                try:
                    from send_to_lark import load_env as load_bf_env, send_card
                    load_bf_env()
                    send_card(card["title"], card["body"], card["color"])
                    print("Digest card sent to Brain Feed.")
                except Exception as e:
                    print(f"Failed to send digest card: {e}")
    else:
        print("\nNo new messages since last sync.")

    print(f"\nSync complete at {datetime.now().strftime('%H:%M:%S')}")
    return all_new


def show_status():
    """Show current sync state."""
    state = load_state()
    if not state:
        print("No sync history. Run `python scripts/lark_sync.py` first.")
        return

    print(f"\n{'Chat':<35} {'Last Sync':<22} {'Total Synced':<15} {'Org'}")
    print("-" * 90)
    for chat_id, info in state.items():
        name = info.get("display_name", chat_id[:20])
        last = info.get("last_sync", "never")[:19]
        total = info.get("total_synced", 0)
        org = info.get("org", "?")
        print(f"{name:<35} {last:<22} {total:<15} {org}")


if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()
    elif "--send-digest" in sys.argv:
        run_sync(send_digest=True)
    else:
        run_sync(send_digest=False)

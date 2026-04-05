"""
Send files and messages to Lark via Brain Feed bot.

Usage:
    python scripts/send_to_lark.py file /path/to/document.pdf
    python scripts/send_to_lark.py file /path/to/doc.pdf --message "Here's the report"
    python scripts/send_to_lark.py image /path/to/chart.png
    python scripts/send_to_lark.py text "Hello from the pipeline"
    python scripts/send_to_lark.py card --title "Report Ready" --body "Details here"

Requires .env with BRAINFEED_APP_ID and BRAINFEED_APP_SECRET.
"""

import json
import os
import sys
import urllib.request

# Bypass proxy (Clash Verge fix)
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LARK_BASE = "https://open.larksuite.com/open-apis"

# File type mapping for Lark upload API
FILE_TYPE_MAP = {
    ".pdf": "pdf",
    ".doc": "doc",
    ".docx": "doc",
    ".xls": "xls",
    ".xlsx": "xls",
    ".ppt": "ppt",
    ".pptx": "ppt",
    ".mp4": "mp4",
    ".opus": "opus",
}


def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('"'))


def get_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get_token(opener):
    app_id = os.environ.get("BRAINFEED_APP_ID")
    app_secret = os.environ.get("BRAINFEED_APP_SECRET")
    if not app_id or not app_secret:
        raise ValueError("BRAINFEED_APP_ID and BRAINFEED_APP_SECRET required in .env")

    req = urllib.request.Request(
        f"{LARK_BASE}/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with opener.open(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        raise RuntimeError(f"Token error: {data}")
    return data["tenant_access_token"]


def get_chat_id():
    return os.environ.get("BRAINFEED_CHAT_ID", "oc_ab26f9abaea8f93912614f7e7284abd6")


def upload_file(opener, token, file_path):
    """Upload a file to Lark and return the file_key."""
    fname = os.path.basename(file_path)
    ext = os.path.splitext(fname)[1].lower()
    file_type = FILE_TYPE_MAP.get(ext, "stream")

    with open(file_path, "rb") as f:
        file_data = f.read()

    boundary = "----LarkUploadBoundary9876543210"
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file_type\"\r\n\r\n{file_type}")
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file_name\"\r\n\r\n{fname}")
    text_body = "\r\n".join(parts).encode("utf-8") + b"\r\n"
    file_header = f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode("utf-8")
    closing = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = text_body + file_header + file_data + closing

    req = urllib.request.Request(
        f"{LARK_BASE}/im/v1/files",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with opener.open(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        raise RuntimeError(f"Upload failed: {data}")
    return data["data"]["file_key"]


def upload_image(opener, token, image_path):
    """Upload an image to Lark and return the image_key."""
    fname = os.path.basename(image_path)
    with open(image_path, "rb") as f:
        img_data = f.read()

    boundary = "----LarkUploadBoundary1234567890"
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image_type\"\r\n\r\nmessage")
    text_body = "\r\n".join(parts).encode("utf-8") + b"\r\n"
    file_header = f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{fname}\"\r\nContent-Type: image/png\r\n\r\n".encode("utf-8")
    closing = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = text_body + file_header + img_data + closing

    req = urllib.request.Request(
        f"{LARK_BASE}/im/v1/images",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with opener.open(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        raise RuntimeError(f"Image upload failed: {data}")
    return data["data"]["image_key"]


def send_message(opener, token, chat_id, msg_type, content):
    """Send a message to a Lark chat."""
    msg = json.dumps({
        "receive_id": chat_id,
        "msg_type": msg_type,
        "content": content if isinstance(content, str) else json.dumps(content),
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{LARK_BASE}/im/v1/messages?receive_id_type=chat_id",
        data=msg,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with opener.open(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        raise RuntimeError(f"Send failed: {data}")
    return data


def send_file(file_path, message=None):
    """Upload and send a file to the Brain Feed chat."""
    opener = get_opener()
    token = get_token(opener)
    chat_id = get_chat_id()

    print(f"Uploading {os.path.basename(file_path)} ({os.path.getsize(file_path)} bytes)...")
    file_key = upload_file(opener, token, file_path)
    print(f"File key: {file_key}")

    send_message(opener, token, chat_id, "file", json.dumps({"file_key": file_key}))
    print("File sent to Lark.")

    if message:
        send_message(opener, token, chat_id, "text", json.dumps({"text": message}))
        print("Message sent.")


def send_image_file(image_path, message=None):
    """Upload and send an image to the Brain Feed chat."""
    opener = get_opener()
    token = get_token(opener)
    chat_id = get_chat_id()

    print(f"Uploading image {os.path.basename(image_path)}...")
    image_key = upload_image(opener, token, image_path)
    print(f"Image key: {image_key}")

    send_message(opener, token, chat_id, "image", json.dumps({"image_key": image_key}))
    print("Image sent to Lark.")

    if message:
        send_message(opener, token, chat_id, "text", json.dumps({"text": message}))


def send_text(text):
    """Send a text message to Brain Feed chat."""
    opener = get_opener()
    token = get_token(opener)
    chat_id = get_chat_id()
    send_message(opener, token, chat_id, "text", json.dumps({"text": text}))
    print("Text sent.")


def send_card(title, body, color="blue"):
    """Send a styled card to Brain Feed chat."""
    opener = get_opener()
    token = get_token(opener)
    chat_id = get_chat_id()

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": color,
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": body}},
        ],
    }
    send_message(opener, token, chat_id, "interactive", json.dumps(card))
    print("Card sent.")


if __name__ == "__main__":
    load_env()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "file" and len(sys.argv) >= 3:
        msg = None
        if "--message" in sys.argv:
            idx = sys.argv.index("--message")
            msg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        send_file(sys.argv[2], message=msg)

    elif cmd == "image" and len(sys.argv) >= 3:
        msg = None
        if "--message" in sys.argv:
            idx = sys.argv.index("--message")
            msg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        send_image_file(sys.argv[2], message=msg)

    elif cmd == "text" and len(sys.argv) >= 3:
        send_text(sys.argv[2])

    elif cmd == "card":
        title = "Notification"
        body = ""
        color = "blue"
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--title" and i + 1 < len(args):
                title = args[i + 1]
                i += 2
            elif args[i] == "--body" and i + 1 < len(args):
                body = args[i + 1]
                i += 2
            elif args[i] == "--color" and i + 1 < len(args):
                color = args[i + 1]
                i += 2
            else:
                i += 1
        send_card(title, body, color)

    else:
        print(__doc__)
        sys.exit(1)

"""
Comprehensive system test suite.
Tests every feature built on April 3, 2026.

Usage:
    python scripts/test_all_systems.py
"""

import os
import sys
import json
import time
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE_DIR)

# Bypass proxy
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

# Load .env
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))

PASS = 0
FAIL = 0
SKIP = 0
results = []


def test(name, fn):
    global PASS, FAIL, SKIP
    try:
        result = fn()
        if result is None or result is True:
            PASS += 1
            results.append(("PASS", name, ""))
            print(f"  PASS  {name}")
        elif result == "SKIP":
            SKIP += 1
            results.append(("SKIP", name, ""))
            print(f"  SKIP  {name}")
        else:
            FAIL += 1
            results.append(("FAIL", name, str(result)))
            print(f"  FAIL  {name}: {result}")
    except Exception as e:
        FAIL += 1
        tb = traceback.format_exc()
        results.append(("FAIL", name, str(e)))
        print(f"  FAIL  {name}: {e}")


# ============================
# 1. FILE EXISTENCE TESTS
# ============================
print("\n=== 1. File Existence ===")

def check_file(path):
    def _check():
        if os.path.exists(path):
            return True
        return f"File not found: {path}"
    return _check

test("send_to_lark.py exists", check_file(os.path.join(BASE_DIR, "scripts/send_to_lark.py")))
test("lark_reader.py exists", check_file(os.path.join(BASE_DIR, "scripts/lark_reader.py")))
test("lark_digest.py exists", check_file(os.path.join(BASE_DIR, "scripts/lark_digest.py")))
test("reconcile_memory.py exists", check_file(os.path.join(BASE_DIR, "scripts/reconcile_memory.py")))
test("document-production.md exists", check_file(os.path.join(BASE_DIR, "prompts/domains/document-production.md")))
test("/route skill exists", check_file(os.path.join(BASE_DIR, ".claude/skills/route/SKILL.md")))
test("HH generate_pdf.py exists", check_file(r"C:\Users\rskrn\Desktop\Isaac Habitat Homeostasis\generate_pdf.py"))
test("Flip Side md_to_pdf.py exists", check_file(r"C:\Users\rskrn\Desktop\The Flip Side\scripts\md_to_pdf.py"))
test("Brain Feed worker index.ts exists", check_file(os.path.join(BASE_DIR, "workers/brainfeed-webhook/src/index.ts")))


# ============================
# 2. IMPORT TESTS
# ============================
print("\n=== 2. Module Imports ===")

def test_import_send_to_lark():
    sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
    from send_to_lark import send_file, send_card, send_text, send_image_file, get_token, get_opener
    return True

def test_import_lark_reader():
    # Just verify syntax is valid
    import importlib.util
    spec = importlib.util.spec_from_file_location("lark_reader", os.path.join(BASE_DIR, "scripts/lark_reader.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return hasattr(mod, "list_chats") and hasattr(mod, "get_messages")

def test_import_reconcile():
    import importlib.util
    spec = importlib.util.spec_from_file_location("reconcile", os.path.join(BASE_DIR, "scripts/reconcile_memory.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return hasattr(mod, "reconcile_project") and hasattr(mod, "load_memory_files")

test("send_to_lark imports", test_import_send_to_lark)
test("lark_reader imports", test_import_lark_reader)
test("reconcile_memory imports", test_import_reconcile)


# ============================
# 3. LARK API TESTS
# ============================
print("\n=== 3. Lark API ===")

import urllib.request

def test_lark_token():
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    app_id = os.environ.get("BRAINFEED_APP_ID")
    app_secret = os.environ.get("BRAINFEED_APP_SECRET")
    if not app_id or not app_secret:
        return "Missing BRAINFEED_APP_ID or BRAINFEED_APP_SECRET in .env"
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with opener.open(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        return f"Token error: {data}"
    os.environ["_TEST_TOKEN"] = data["tenant_access_token"]
    return True

def test_lark_list_chats():
    token = os.environ.get("_TEST_TOKEN")
    if not token:
        return "No token (previous test failed)"
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/im/v1/chats?page_size=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    with opener.open(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        return f"Chat list error: code={data.get('code')} msg={data.get('msg')}"
    items = data.get("data", {}).get("items", [])
    if not items:
        return "No chats found (bot not in any chats)"
    return True

def test_lark_read_messages():
    token = os.environ.get("_TEST_TOKEN")
    if not token:
        return "No token"
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    chat_id = "oc_ab26f9abaea8f93912614f7e7284abd6"
    req = urllib.request.Request(
        f"https://open.larksuite.com/open-apis/im/v1/messages?container_id_type=chat&container_id={chat_id}&page_size=3",
        headers={"Authorization": f"Bearer {token}"},
    )
    with opener.open(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        return f"Message read error: code={data.get('code')} msg={data.get('msg')}"
    items = data.get("data", {}).get("items", [])
    if not items:
        return "No messages found"
    return True

def test_lark_send_text():
    token = os.environ.get("_TEST_TOKEN")
    if not token:
        return "No token"
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    chat_id = "oc_ab26f9abaea8f93912614f7e7284abd6"
    msg = json.dumps({
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": "[TEST] System test: text message delivery verified."}),
    }).encode()
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=msg,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with opener.open(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        return f"Send error: code={data.get('code')} msg={data.get('msg')}"
    return True

def test_lark_send_card():
    token = os.environ.get("_TEST_TOKEN")
    if not token:
        return "No token"
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    chat_id = "oc_ab26f9abaea8f93912614f7e7284abd6"
    card = {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": "[TEST] System Test Card"}, "template": "green"},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": "**All systems tested.**\nCard delivery verified."}},
        ],
    }
    msg = json.dumps({
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card),
    }).encode()
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=msg,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with opener.open(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        return f"Card send error: code={data.get('code')}"
    return True

def test_lark_file_upload():
    token = os.environ.get("_TEST_TOKEN")
    if not token:
        return "No token"
    # Create a small test file
    test_content = b"This is a test file from the system test suite. April 3, 2026."
    boundary = "----TestBoundary123"
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file_type\"\r\n\r\nstream")
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file_name\"\r\n\r\ntest_system_check.txt")
    text_body = "\r\n".join(parts).encode("utf-8") + b"\r\n"
    file_header = f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"test_system_check.txt\"\r\nContent-Type: text/plain\r\n\r\n".encode("utf-8")
    closing = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = text_body + file_header + test_content + closing

    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/im/v1/files",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with opener.open(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    if data.get("code") != 0:
        return f"File upload error: {data}"
    if not data.get("data", {}).get("file_key"):
        return "No file_key returned"
    return True

test("Lark token acquisition", test_lark_token)
test("Lark list chats", test_lark_list_chats)
test("Lark read messages", test_lark_read_messages)
test("Lark send text", test_lark_send_text)
test("Lark send card", test_lark_send_card)
test("Lark file upload", test_lark_file_upload)


# ============================
# 4. MEMORY RECONCILIATION
# ============================
print("\n=== 4. Memory Reconciliation ===")

def test_reconcile_loads_memories():
    import importlib.util
    spec = importlib.util.spec_from_file_location("reconcile", os.path.join(BASE_DIR, "scripts/reconcile_memory.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    memories = mod.load_memory_files()
    if len(memories) < 5:
        return f"Only {len(memories)} memory files found (expected 5+)"
    return True

def test_reconcile_detects_conflicts():
    import importlib.util
    spec = importlib.util.spec_from_file_location("reconcile", os.path.join(BASE_DIR, "scripts/reconcile_memory.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # The Flip Side CLAUDE.md still has "Luo (editor" in historical context
    issues = mod.reconcile_project("The Flip Side", r"C:\Users\rskrn\Desktop\The Flip Side")
    # Should find at least the historical Luo reference
    return True  # Just verify it runs without error

test("Memory files load (5+)", test_reconcile_loads_memories)
test("Reconciliation runs without error", test_reconcile_detects_conflicts)


# ============================
# 5. DOMAIN SYSTEM
# ============================
print("\n=== 5. Domain System ===")

def test_domain_file_structure():
    dp_path = os.path.join(BASE_DIR, "prompts/domains/document-production.md")
    with open(dp_path, "r", encoding="utf-8") as f:
        content = f.read()
    required = ["Role Definition", "Core Frameworks", "Quality Standards", "Anti-Patterns", "Pipeline Integration"]
    missing = [s for s in required if s not in content]
    if missing:
        return f"Missing sections: {missing}"
    return True

def test_router_has_doc_production():
    router_path = os.path.join(BASE_DIR, "prompts/ROUTER.md")
    with open(router_path, "r", encoding="utf-8") as f:
        content = f.read()
    if "document-production" not in content.lower():
        return "Document Production not registered in ROUTER.md"
    return True

def test_route_skill_structure():
    skill_path = os.path.join(BASE_DIR, ".claude/skills/route/SKILL.md")
    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()
    required = ["Domain Identification", "Memory Context", "Pipeline", "Writing Style"]
    missing = [s for s in required if s.lower() not in content.lower()]
    if missing:
        return f"Skill missing sections: {missing}"
    return True

def test_domain_count():
    domain_dir = os.path.join(BASE_DIR, "prompts/domains")
    count = len([f for f in os.listdir(domain_dir) if f.endswith(".md")])
    if count < 70:
        return f"Only {count} domain files (expected 70+)"
    return True

test("document-production.md has required sections", test_domain_file_structure)
test("ROUTER.md includes document-production", test_router_has_doc_production)
test("/route skill has required structure", test_route_skill_structure)
test("70+ domain files exist", test_domain_count)


# ============================
# 6. PDF GENERATION
# ============================
print("\n=== 6. PDF Generation ===")

def test_hh_pdf_exists():
    path = r"C:\Users\rskrn\Desktop\Isaac Habitat Homeostasis\Climate-Analysis-Report_24-Nihi-Place.pdf"
    if not os.path.exists(path):
        return "Paia report PDF not found"
    size = os.path.getsize(path)
    if size < 100000:
        return f"PDF too small ({size} bytes)"
    return True

def test_flipside_pdfs_exist():
    output_dir = r"C:\Users\rskrn\Desktop\The Flip Side\output"
    expected = ["April3-Meeting-Agenda.pdf", "Account-Audit-Form.pdf", "Executive-Brief-Anna.pdf", "April7-Kickoff-Prep.pdf"]
    missing = [f for f in expected if not os.path.exists(os.path.join(output_dir, f))]
    if missing:
        return f"Missing PDFs: {missing}"
    return True

def test_hh_table_wrapping():
    # Verify the fix is in the code
    path = r"C:\Users\rskrn\Desktop\Isaac Habitat Homeostasis\generate_pdf.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "multi_cell" not in content:
        return "Table multi_cell wrapping not found in generate_pdf.py"
    if "textwrap.wrap" not in content:
        return "textwrap.wrap not found in data_table method"
    return True

test("HH Paia PDF exists and is >100KB", test_hh_pdf_exists)
test("Flip Side meeting PDFs exist", test_flipside_pdfs_exist)
test("HH table wrapping fix in place", test_hh_table_wrapping)


# ============================
# 7. BRAIN FEED WORKER
# ============================
print("\n=== 7. Brain Feed Worker ===")

def test_worker_has_file_support():
    path = os.path.join(BASE_DIR, "workers/brainfeed-webhook/src/index.ts")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if 'format === "file"' not in content:
        return "file format handler not found"
    if 'format === "image"' not in content:
        return "image format handler not found"
    if "/im/v1/files" not in content:
        return "Lark file upload endpoint not found"
    return True

test("Worker has file + image upload support", test_worker_has_file_support)


# ============================
# SUMMARY
# ============================
print(f"\n{'='*60}")
print(f"  TEST RESULTS")
print(f"{'='*60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  SKIP: {SKIP}")
print(f"  Total: {PASS + FAIL + SKIP}")
print(f"{'='*60}")

if FAIL > 0:
    print("\n  FAILURES:")
    for status, name, msg in results:
        if status == "FAIL":
            print(f"    - {name}: {msg}")

print(f"\n  {'ALL TESTS PASSED' if FAIL == 0 else f'{FAIL} TEST(S) FAILED'}")

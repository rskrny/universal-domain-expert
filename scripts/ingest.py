"""
Unified Knowledge Ingestion Pipeline.

Single entry point for all knowledge sources:
  - Reddit saved posts -> categorized context chunks
  - Brain Feed D1 -> synced context chunks
  - Manual files -> indexed on demand

Each source goes through: Collect -> Classify -> Write -> Index

The FULL pipeline (ingest.py pipeline) runs all three stages:
  1. Collect: Gather Reddit saves + upvotes + comments
  2. Extract: Use Claude API to extract structured claims from posts
  3. Enrich: Compare claims against domain files, propose/apply updates

Usage:
    python scripts/ingest.py reddit          # Process Reddit saves into knowledge
    python scripts/ingest.py reddit --dry-run # Show what would be processed
    python scripts/ingest.py brainfeed       # Sync Brain Feed D1 chunks
    python scripts/ingest.py all             # Run all sources
    python scripts/ingest.py status          # Show ingestion stats
    python scripts/ingest.py pipeline        # FULL: collect -> extract -> enrich -> reindex
    python scripts/ingest.py pipeline --dry-run  # Preview the full pipeline
"""

import json
import os
import re
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


# ── Domain Classification ────────────────────────────────────────────────────

# Maps keywords in titles/content to canonical domain file names.
# Every domain file in prompts/domains/ should have entries here.
DOMAIN_KEYWORDS = {
    "ai-machine-learning": [
        "machine learning", "deep learning", "neural network", "transformer",
        "llm", "gpt", "claude", "fine-tuning", "inference", "pytorch",
        "training data", "model", "embeddings", "nlp", "computer vision",
        "tensorflow", "huggingface", "diffusion", "reinforcement learning",
    ],
    "software-dev": [
        "programming", "coding", "api", "database", "architecture", "testing",
        "refactoring", "backend", "fullstack", "devops", "git", "deployment",
        "microservices", "monolith", "rest api", "graphql", "orm",
    ],
    "context-engineering": [
        "rag", "retrieval", "chunking", "vector database", "search index",
        "context window", "prompt engineering", "token optimization", "mcp",
        "retrieval augmented", "knowledge base", "embedding model",
    ],
    "vibecoding": [
        "vibe coding", "vibecoding", "vibe-coding", "cursor", "claude code",
        "codex", "ai coding", "copilot", "ai agent", "autonomous agent",
        "ai-assisted development", "prompt-driven coding",
    ],
    "saas-building": [
        "saas", "subscription", "mrr", "arr", "churn", "pricing model",
        "stripe", "freemium", "product-led", "plg", "multi-tenant",
        "onboarding", "trial conversion",
    ],
    "personal-finance": [
        "investing", "portfolio", "fire", "passive income", "budgeting",
        "retirement", "index fund", "real estate investing", "wealth",
        "compound interest", "dividend", "401k", "ira", "brokerage",
    ],
    "cybersecurity": [
        "security", "hacking", "penetration testing", "vulnerability",
        "encryption", "password", "zero trust", "owasp", "malware",
        "firewall", "intrusion detection", "siem", "incident response",
    ],
    "data-analytics": [
        "data analysis", "dashboard", "metrics", "kpi", "sql query",
        "visualization", "analytics", "a/b test", "cohort analysis",
        "funnel", "retention", "tableau", "looker", "power bi",
    ],
    "psychology-persuasion": [
        "psychology", "persuasion", "influence", "behavioral economics",
        "cognitive bias", "charisma", "manipulation", "social proof",
        "anchoring", "framing", "heuristic", "decision making",
    ],
    "marketing-content": [
        "marketing", "seo", "content strategy", "copywriting",
        "social media marketing", "growth hacking", "email marketing",
        "organic growth", "content calendar", "keyword research",
    ],
    "frontend-development": [
        "react", "vue", "angular", "css", "typescript", "next.js",
        "responsive design", "tailwind", "frontend", "svelte", "vite",
        "state management", "component", "webpack", "dom",
    ],
    "blockchain-web3": [
        "blockchain", "web3", "crypto", "defi", "smart contract",
        "nft", "token", "ethereum", "solidity", "wallet", "dao",
        "consensus", "layer 2", "zk proof", "staking",
    ],
    "cloud-infrastructure": [
        "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
        "serverless", "cloudflare", "workers", "iac", "load balancer",
        "cdn", "auto-scaling", "vpc", "lambda",
    ],
    "business-consulting": [
        "strategy", "consulting", "mckinsey", "bcg", "competitive analysis",
        "market entry", "due diligence", "organizational design", "m&a",
        "growth strategy", "business model", "value chain",
    ],
    "accounting-tax": [
        "accounting", "tax", "bookkeeping", "gaap", "revenue recognition",
        "tax planning", "financial statement", "audit", "depreciation",
        "1099", "w-2", "irs", "deduction", "cpa",
    ],
    "business-law": [
        "contract", "liability", "incorporation", "terms of service",
        "intellectual property", "compliance", "litigation", "corporate law",
        "nda", "indemnification", "arbitration",
    ],
    "gtm-strategy": [
        "go-to-market", "gtm", "launch", "positioning", "messaging",
        "customer acquisition", "channel strategy", "product launch",
        "market fit", "ideal customer profile",
    ],
    "product-design": [
        "ux design", "ui design", "usability", "accessibility", "wireframe",
        "prototype", "figma", "user research", "design system",
        "information architecture", "user flow", "conversion optimization",
    ],
    "course-creation": [
        "curriculum", "learning objectives", "online course", "assessment",
        "lesson plan", "e-learning", "instructional design", "lms",
    ],
    "research-authoring": [
        "literature review", "methodology", "academic writing", "citation",
        "peer review", "thesis", "dissertation", "journal", "publication",
    ],
    "operations-automation": [
        "workflow", "sop", "automation", "no-code", "zapier", "make.com",
        "process design", "efficiency", "standard operating procedure",
    ],
    "project-management": [
        "project plan", "milestone", "scope", "prioritization", "kanban",
        "agile", "sprint", "deadline", "roadmap", "gantt", "jira",
    ],
    "mobile-development": [
        "ios", "android", "react native", "flutter", "swift", "kotlin",
        "mobile app", "app store", "push notification", "xcode",
    ],
    "devops-sre": [
        "ci/cd", "monitoring", "observability", "slo", "sli", "sla",
        "incident management", "prometheus", "grafana", "gitops",
        "reliability", "on-call", "runbook",
    ],
    "data-engineering": [
        "etl", "data pipeline", "data warehouse", "spark", "airflow",
        "dbt", "snowflake", "kafka", "streaming", "data lake",
    ],
    "sales": [
        "prospecting", "pipeline", "crm", "closing", "objection handling",
        "b2b sales", "enterprise sales", "demo", "cold email", "outreach",
    ],
    "negotiation": [
        "negotiation", "negotiate", "batna", "zopa", "anchoring", "mediation",
        "deal-making", "leverage", "concession", "counter-offer", "salary negotiation",
    ],
    "venture-capital": [
        "fundraising", "pitch deck", "term sheet", "valuation", "cap table",
        "due diligence", "equity", "series a", "seed round", "angel",
    ],
    "statistics": [
        "regression", "hypothesis testing", "bayesian", "sampling",
        "distribution", "anova", "p-value", "confidence interval",
    ],
    "mathematics": [
        "algebra", "calculus", "linear algebra", "probability", "proof",
        "optimization", "discrete math", "differential equation",
    ],
    "economics": [
        "microeconomics", "macroeconomics", "supply and demand",
        "monetary policy", "fiscal policy", "game theory", "gdp",
        "inflation", "trade", "market equilibrium",
    ],
    "social-media": [
        "instagram", "tiktok", "linkedin", "youtube", "twitter",
        "content calendar", "engagement rate", "algorithm", "follower",
    ],
    "creative-writing": [
        "fiction", "narrative", "plot", "character development", "dialogue",
        "worldbuilding", "poetry", "screenwriting", "short story",
    ],
    "video-production": [
        "filming", "editing", "cinematography", "color grading",
        "sound design", "premiere", "davinci resolve", "camera",
    ],
    "public-speaking": [
        "presentation", "keynote", "audience engagement", "delivery",
        "stage presence", "pitch", "toastmasters", "ted talk",
    ],
    "medicine-health": [
        "diagnosis", "treatment", "pharmacology", "clinical", "patient",
        "medical", "doctor", "healthcare", "hospital", "disease",
        "surgery", "oncology", "immunotherapy", "prescription",
    ],
    "mental-health": [
        "therapy", "cbt", "anxiety", "depression", "trauma", "mindfulness",
        "stress management", "burnout", "psychiatry", "counseling",
    ],
    "nutrition-fitness": [
        "diet", "exercise", "macros", "strength training", "meal plan",
        "body composition", "protein", "cardio", "workout", "gym",
    ],
    "real-estate": [
        "property", "mortgage", "reit", "appraisal", "rental",
        "commercial real estate", "cap rate", "landlord", "tenant",
    ],
    "customer-success": [
        "retention", "nps", "onboarding", "churn prevention", "health score",
        "expansion revenue", "customer success manager",
    ],
    "hr-talent": [
        "hiring", "recruiting", "performance review", "compensation",
        "culture", "retention", "interview", "job description",
    ],
    "neuroscience": [
        "brain", "cognition", "neuroplasticity", "memory", "learning",
        "perception", "neural pathway", "dopamine", "serotonin",
    ],
    "electrical-engineering": [
        "circuit", "electronics", "power system", "embedded", "pcb",
        "signal processing", "microcontroller", "arduino", "fpga",
    ],
    "civil-engineering": [
        "structural", "construction", "infrastructure", "geotechnical",
        "building code", "concrete", "bridge", "foundation",
    ],
    "mechanical-engineering": [
        "thermodynamics", "fluid mechanics", "materials", "cad",
        "manufacturing", "fea", "dynamics", "heat transfer",
    ],
    "political-science": [
        "government", "policy", "democracy", "election", "legislation",
        "international relations", "governance", "political party",
    ],
    "linguistics": [
        "syntax", "semantics", "phonology", "sociolinguistics",
        "translation", "language acquisition", "grammar", "morphology",
    ],
    "journalism": [
        "reporting", "investigative", "editorial", "fact-checking",
        "source verification", "press", "breaking news",
    ],
    "philosophy": [
        "ethics", "epistemology", "metaphysics", "logic", "existentialism",
        "critical thinking", "moral philosophy", "stoicism",
    ],
    "history": [
        "historical", "primary source", "historiography", "civilization",
        "ancient", "medieval", "colonial", "revolution", "world war",
    ],
    "photography": [
        "composition", "lighting", "exposure", "lightroom", "portrait",
        "landscape", "studio", "aperture", "shutter speed",
    ],
    "environmental-science": [
        "climate", "sustainability", "ecology", "conservation",
        "renewable energy", "biodiversity", "carbon", "pollution",
    ],
    "music-production": [
        "daw", "mixing", "mastering", "synthesis", "ableton", "logic pro",
        "audio engineering", "arrangement", "eq", "compression",
    ],
    "graphic-design": [
        "figma", "illustrator", "typography", "layout", "color theory",
        "visual identity", "print design", "branding design", "logo",
    ],
    "robotics": [
        "ros", "actuator", "sensor", "kinematics", "path planning",
        "slam", "autonomous", "robot", "servo", "lidar",
    ],
    "branding": [
        "brand strategy", "brand identity", "brand voice", "positioning",
        "brand architecture", "naming", "brand guidelines", "rebranding",
    ],
    "architecture-design": [
        "building design", "floor plan", "zoning", "urban planning",
        "interior design", "bim", "architectural", "blueprint",
    ],
    "energy-systems": [
        "solar", "wind", "battery", "grid", "power generation", "nuclear",
        "energy storage", "efficiency", "renewable", "photovoltaic",
    ],
    "crisis-management": [
        "emergency", "disaster recovery", "business continuity", "risk",
        "reputation management", "crisis communication",
    ],
    "quantum-computing": [
        "qubit", "quantum gate", "superposition", "entanglement", "qiskit",
        "quantum algorithm", "quantum supremacy",
    ],
    "podcasting": [
        "podcast", "audio recording", "interview", "episode", "rss",
        "hosting", "audience growth", "microphone",
    ],
    "event-planning": [
        "conference", "workshop", "venue", "catering", "logistics",
        "virtual event", "hybrid event", "registration",
    ],
    "nonprofit": [
        "fundraising", "grant writing", "donor", "social impact",
        "board governance", "501c3", "volunteer", "philanthropy",
    ],
    "education-pedagogy": [
        "teaching", "learning theory", "assessment", "bloom taxonomy",
        "differentiated instruction", "pedagogy", "student",
    ],
    "education": [
        "k-12", "higher education", "edtech", "online learning",
        "accreditation", "adult education", "tutoring",
    ],
    "insurance": [
        "underwriting", "claims", "risk assessment", "premium",
        "actuarial", "coverage", "reinsurance", "policy",
    ],
    "international-trade": [
        "import", "export", "tariff", "customs", "incoterms",
        "trade finance", "cross-border", "wto",
    ],
    "intellectual-property": [
        "patent", "trademark", "copyright", "trade secret", "licensing",
        "ip strategy", "ip valuation", "infringement",
    ],
    "employment-law": [
        "labor law", "wrongful termination", "discrimination",
        "wage", "fmla", "ada", "employment contract", "severance",
    ],
    "game-development": [
        "unity", "unreal", "game design", "game mechanics", "level design",
        "multiplayer", "game engine", "sprite", "shader",
    ],
    "criminal-law": [
        "prosecution", "defense", "felony", "misdemeanor", "sentencing",
        "constitutional rights", "trial", "plea", "bail",
    ],
    "document-production": [
        "pdf", "docx", "pptx", "xlsx", "document design", "template",
        "typography", "report generation", "slide deck",
    ],
    "feishu-lark": [
        "lark", "feishu", "lark api", "feishu api", "lark bot",
        "webhook", "lark message", "lark group",
    ],
    "social-distribution": [
        "content distribution", "cross-platform", "social posting",
        "content repurposing", "scheduling", "social automation",
    ],
    "productivity": [
        "time management", "focus", "gtd", "pkm", "deep work",
        "habit formation", "energy management", "pomodoro",
        "second brain", "note-taking", "obsidian", "notion",
    ],
    "career-development": [
        "career strategy", "skill development", "networking",
        "personal branding", "resume", "interview", "career transition",
        "promotion", "mentorship",
    ],
    "supply-chain": [
        "logistics", "procurement", "inventory", "warehousing",
        "distribution", "demand planning", "lean", "supply chain",
    ],
}


def _load_domain_aliases() -> dict:
    """Load domain alias mapping from config.yaml."""
    config_path = ROOT / "retrieval" / "config.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("domain_aliases", {})
    return {}


# Cache aliases at module load
_DOMAIN_ALIASES = _load_domain_aliases()


def classify_domain(title: str, text: str = "") -> str:
    """Classify content into the most relevant canonical domain.

    Uses keyword matching against all 78+ registered domains.
    Falls back to 'general' only if no keywords match.
    """
    combined = f"{title} {text}".lower()
    scores = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in combined:
                score += 1
                # Bonus for title match (stronger signal)
                if kw in title.lower():
                    score += 2
        if score > 0:
            scores[domain] = score

    if not scores:
        return "general"

    best = max(scores, key=scores.get)
    # Apply alias normalization in case the keyword map uses a non-canonical name
    return _DOMAIN_ALIASES.get(best, best)


# ── Reddit Ingestion ─────────────────────────────────────────────────────────

def ingest_reddit(dry_run: bool = False, days: int = 180) -> dict:
    """
    Process Reddit saved posts into knowledge chunks.

    Reads saved_posts_raw.json, classifies each post by domain,
    writes as markdown files in the context directory, then reindexes.
    """
    reddit_path = Path("C:/Users/rskrn/Desktop/reddit api/saved_posts_raw.json")
    if not reddit_path.exists():
        print("No saved posts file found. Run the Reddit collector first.")
        print("  cd 'C:\\Users\\rskrn\\Desktop\\reddit api'")
        print("  python -c \"import collector; import json; posts=collector.fetch_saved_posts(); open('saved_posts_raw.json','w').write(json.dumps(posts))\"")
        return {"processed": 0, "skipped": 0, "errors": 0}

    posts = json.loads(reddit_path.read_text(encoding="utf-8"))

    # Filter to recent posts
    cutoff = time.time() - days * 86400
    recent = [p for p in posts if p.get("created_utc", 0) > cutoff]
    print(f"Reddit: {len(posts)} total saves, {len(recent)} in last {days} days")

    # Track what's already been ingested
    tracking_file = ROOT / "state" / "reddit_ingested.json"
    ingested_ids = set()
    if tracking_file.exists():
        ingested_ids = set(json.loads(tracking_file.read_text()))

    stats = {"processed": 0, "skipped": 0, "errors": 0, "by_domain": {}}
    new_ids = []

    for post in recent:
        post_id = post.get("id", "")
        if post_id in ingested_ids:
            stats["skipped"] += 1
            continue

        title = post.get("title", "Untitled")
        selftext = post.get("selftext", "")
        subreddit = post.get("subreddit", "unknown")
        score = post.get("score", 0)
        permalink = post.get("permalink", "")
        created = post.get("created_date", "")
        url = post.get("url", "")

        # Skip low-quality posts (memes, low effort)
        if score < 10 and len(selftext) < 100:
            stats["skipped"] += 1
            continue

        # Classify
        domain = classify_domain(title, selftext)
        stats["by_domain"][domain] = stats["by_domain"].get(domain, 0) + 1

        if dry_run:
            print(f"  [{domain}] r/{subreddit}: {title[:80]}")
            stats["processed"] += 1
            continue

        # Write markdown file
        try:
            out_dir = ROOT / "prompts" / "context" / "by-domain" / domain
            if domain == "general":
                out_dir = ROOT / "prompts" / "context" / "shared" / "reddit"
            out_dir.mkdir(parents=True, exist_ok=True)

            safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip().replace(' ', '-').lower()
            safe_title = re.sub(r'-+', '-', safe_title)
            filename = f"reddit-{post_id}-{safe_title}.md"
            filepath = out_dir / filename

            lines = [
                f"# {title}",
                "",
                f"Source: https://reddit.com{permalink}",
                f"Subreddit: r/{subreddit} | Score: {score} | Date: {created}",
                "",
                "---",
                "",
            ]

            if selftext:
                # Truncate very long posts
                content = selftext[:3000]
                if len(selftext) > 3000:
                    content += "\n\n[Truncated. See original post for full content.]"
                lines.append(content)
            elif url and "reddit.com" not in url:
                lines.append(f"External link: {url}")
            else:
                lines.append(f"[Discussion post with {post.get('num_comments', 0)} comments]")

            # Add top comments if available
            comments = post.get("comments", [])
            if comments:
                lines.append("")
                lines.append("## Top Comments")
                lines.append("")
                for c in comments[:3]:
                    body = c.get("body", "")[:500]
                    author = c.get("author", "anon")
                    cscore = c.get("score", 0)
                    lines.append(f"**u/{author}** ({cscore} pts):")
                    lines.append(f"> {body}")
                    lines.append("")

            filepath.write_text("\n".join(lines), encoding="utf-8")
            new_ids.append(post_id)
            stats["processed"] += 1

        except Exception as e:
            print(f"  Error processing {post_id}: {e}")
            stats["errors"] += 1

    # Update tracking
    if new_ids and not dry_run:
        all_ingested = ingested_ids | set(new_ids)
        tracking_file.parent.mkdir(parents=True, exist_ok=True)
        tracking_file.write_text(json.dumps(sorted(all_ingested)), encoding="utf-8")

    return stats


# ── Brain Feed Ingestion ─────────────────────────────────────────────────────

def ingest_brainfeed(dry_run: bool = False) -> dict:
    """Sync pending chunks from Brain Feed D1."""
    from urllib.request import Request, urlopen
    from urllib.error import URLError

    brainfeed_url = os.getenv("BRAINFEED_URL", "https://brainfeed.hanahaulers.com")
    auth_token = os.getenv("BRAINFEED_AUTH_TOKEN", "")

    stats = {"processed": 0, "skipped": 0, "errors": 0}

    # Fetch pending
    try:
        req = Request(f"{brainfeed_url}/api/chunks/pending", method="GET")
        with urlopen(req, timeout=30) as resp:
            chunks = json.loads(resp.read().decode())
    except (URLError, Exception) as e:
        print(f"Brain Feed: Failed to fetch pending chunks: {e}")
        return stats

    print(f"Brain Feed: {len(chunks)} pending chunks")

    if not chunks:
        return stats

    context_dir = ROOT / "prompts" / "context"
    synced_ids = []

    for chunk in chunks:
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

        if dry_run:
            print(f"  [{domain}] {title[:80]}")
            stats["processed"] += 1
            continue

        try:
            if domain and domain != "general":
                out_dir = context_dir / "by-domain" / domain
            else:
                out_dir = context_dir / "shared" / "brainfeed"
            out_dir.mkdir(parents=True, exist_ok=True)

            safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip().replace(' ', '-').lower()
            safe_title = re.sub(r'-+', '-', safe_title)
            filename = f"brainfeed-{chunk_id}-{safe_title}.md"
            filepath = out_dir / filename

            lines = [f"# {title}", ""]
            if source_url:
                lines.extend([f"Source: {source_url}", ""])
            if tags:
                lines.extend([f"Tags: {', '.join(tags)}", ""])
            lines.extend(["---", ""])
            if summary:
                lines.extend([f"**Summary:** {summary}", ""])
            if content and content != summary:
                lines.extend([content[:5000], ""])

            filepath.write_text("\n".join(lines), encoding="utf-8")
            synced_ids.append(chunk_id)
            stats["processed"] += 1

        except Exception as e:
            print(f"  Error: {e}")
            stats["errors"] += 1

    # Mark synced in D1
    if synced_ids and auth_token and not dry_run:
        try:
            body = json.dumps({"ids": synced_ids}).encode()
            req = Request(f"{brainfeed_url}/api/chunks/synced", data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {auth_token}")
            with urlopen(req, timeout=30) as resp:
                pass
        except Exception:
            pass

    return stats


# ── Reindex ──────────────────────────────────────────────────────────────────

def reindex():
    """Run incremental reindex after ingestion."""
    print("\nReindexing...")
    os.chdir(str(ROOT))
    os.system(f'"{sys.executable}" -m retrieval index')


# ── Status ───────────────────────────────────────────────────────────────────

def show_status():
    """Show what's been ingested and what's pending."""
    tracking_file = ROOT / "state" / "reddit_ingested.json"

    print("Knowledge Ingestion Status")
    print("=" * 50)

    # Reddit
    reddit_path = Path("C:/Users/rskrn/Desktop/reddit api/saved_posts_raw.json")
    if reddit_path.exists():
        posts = json.loads(reddit_path.read_text(encoding="utf-8"))
        ingested = set()
        if tracking_file.exists():
            ingested = set(json.loads(tracking_file.read_text()))
        cutoff = time.time() - 180 * 86400
        recent = [p for p in posts if p.get("created_utc", 0) > cutoff]
        pending = [p for p in recent if p["id"] not in ingested]
        print(f"\n  Reddit:")
        print(f"    Total saves: {len(posts)}")
        print(f"    Last 6 months: {len(recent)}")
        print(f"    Already ingested: {len(ingested)}")
        print(f"    Pending: {len(pending)}")
    else:
        print(f"\n  Reddit: No data (run collector first)")

    # Brain Feed
    brainfeed_url = os.getenv("BRAINFEED_URL", "https://brainfeed.hanahaulers.com")
    try:
        from urllib.request import Request, urlopen
        req = Request(f"{brainfeed_url}/api/stats", method="GET")
        with urlopen(req, timeout=10) as resp:
            bf_stats = json.loads(resp.read().decode())
        print(f"\n  Brain Feed:")
        print(f"    Total chunks: {bf_stats.get('total_chunks', 0)}")
        print(f"    Pending sync: {bf_stats.get('pending_sync', 0)}")
    except Exception:
        print(f"\n  Brain Feed: Unreachable")

    # Local index
    from retrieval.config import RetrievalConfig
    from retrieval.store import Store
    config = RetrievalConfig(knowledge_root=ROOT)
    config.store_dir = ROOT / "retrieval" / "store"
    config.db_path = config.store_dir / "metadata.db"
    store = Store(config.db_path, config.store_dir)
    agg = store.get_aggregate_stats()
    store.close()
    print(f"\n  Local Index:")
    print(f"    Chunks: {agg['total_chunks']}")
    print(f"    Tokens: {agg['total_tokens']:,}")
    print(f"    Domains: {agg['domain_count']}")
    print(f"    Files: {agg['file_count']}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if cmd == "reddit":
        stats = ingest_reddit(dry_run=dry_run)
        print(f"\nReddit: {stats['processed']} processed, {stats['skipped']} skipped, {stats['errors']} errors")
        if stats["by_domain"]:
            print("  By domain:")
            for d, c in sorted(stats["by_domain"].items(), key=lambda x: -x[1]):
                print(f"    {d}: {c}")
        if not dry_run and stats["processed"] > 0:
            reindex()

    elif cmd == "brainfeed":
        stats = ingest_brainfeed(dry_run=dry_run)
        print(f"\nBrain Feed: {stats['processed']} processed, {stats['skipped']} skipped, {stats['errors']} errors")
        if not dry_run and stats["processed"] > 0:
            reindex()

    elif cmd == "all":
        print("=== Reddit ===")
        r_stats = ingest_reddit(dry_run=dry_run)
        print(f"  {r_stats['processed']} processed, {r_stats['skipped']} skipped")

        print("\n=== Brain Feed ===")
        b_stats = ingest_brainfeed(dry_run=dry_run)
        print(f"  {b_stats['processed']} processed, {b_stats['skipped']} skipped")

        total = r_stats["processed"] + b_stats["processed"]
        if not dry_run and total > 0:
            reindex()
        print(f"\nTotal ingested: {total}")

    elif cmd == "pipeline":
        run_full_pipeline(dry_run=dry_run)

    elif cmd == "status":
        show_status()

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


def run_full_pipeline(dry_run: bool = False):
    """
    Full knowledge pipeline: Collect -> Extract -> Enrich -> Reindex.

    This is the main loop that turns Reddit engagement into domain expertise:
    1. Collect all Reddit signals (saves, upvotes, comments)
    2. Extract structured claims from posts via Claude API
    3. Compare claims against domain files and propose updates
    4. Apply high-confidence updates and reindex
    """
    print("=" * 60)
    print("  FULL KNOWLEDGE PIPELINE")
    print("=" * 60)

    # Step 1: Collect
    print("\n--- STEP 1: Collect Reddit Data ---")
    try:
        from scripts.collect_reddit import run_collection
        run_collection(saved_only=False, dry_run=dry_run)
    except ImportError:
        # Try running as subprocess if import fails
        import subprocess
        cmd = [sys.executable, str(ROOT / "scripts" / "collect_reddit.py")]
        if dry_run:
            cmd.append("--dry-run")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

    # Step 2: Extract claims
    print("\n--- STEP 2: Extract Claims ---")
    try:
        from scripts.extract_claims import run_extraction
        run_extraction(dry_run=dry_run)
    except ImportError:
        import subprocess
        cmd = [sys.executable, str(ROOT / "scripts" / "extract_claims.py")]
        if dry_run:
            cmd.append("--dry-run")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

    # Step 3: Enrich domains
    print("\n--- STEP 3: Enrich Domain Files ---")
    try:
        from scripts.enrich_domains import cmd_propose, cmd_apply
        cmd_propose()
        if not dry_run:
            cmd_apply()
    except ImportError:
        import subprocess
        cmd_p = [sys.executable, str(ROOT / "scripts" / "enrich_domains.py"), "propose"]
        result = subprocess.run(cmd_p, capture_output=True, text=True, cwd=str(ROOT))
        print(result.stdout)
        if not dry_run:
            cmd_a = [sys.executable, str(ROOT / "scripts" / "enrich_domains.py"), "apply"]
            result = subprocess.run(cmd_a, capture_output=True, text=True, cwd=str(ROOT))
            print(result.stdout)

    # Step 4: Reindex
    if not dry_run:
        print("\n--- STEP 4: Reindex ---")
        reindex()

    # Step 5: Improvement report
    print("\n--- STEP 5: Improvement Report ---")
    try:
        from scripts.improve import cmd_report
        cmd_report()
    except ImportError:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "improve.py"), "report"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        print(result.stdout)

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()

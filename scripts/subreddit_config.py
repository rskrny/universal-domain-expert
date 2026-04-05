"""
Subreddit Configuration for the Knowledge Pipeline.

Two purposes:
  1. ALLOWLIST: Filter saved/upvoted posts during ingestion (skip noise subs)
  2. SCAN_TARGETS: Subreddits to actively scan for new posts (daily scanner)

Organized by how they map to Ryan's projects, domains, and interests.
Update this file as projects and interests evolve.

Last updated: 2026-04-05
"""

# ── ALLOWLIST ───────────────────────────────────────────────────────────────
# Posts from these subreddits pass through to extraction.
# Posts from unlisted subreddits get skipped during ingestion.
# Grouped by purpose. The pipeline doesn't care about groups, only membership.

ALLOWLIST = {

    # ── AI & LLM Engineering ──────────────────────────────────────────────
    # WHY: Core to everything you build. Domain expert system, Claude Code,
    # AI course, Goldie email triage, ShopMyRoom video pipeline.
    # DOMAINS: ai-machine-learning, context-engineering, vibecoding
    "ClaudeAI",
    "ChatGPTCoding",
    "ChatGPTPro",
    "vibecoding",
    "LocalLLaMA",
    "LocalLLM",
    "Rag",
    "PromptEngineering",
    "artificial",
    "MachineLearning",
    "AI_Agents",
    "AIAgentsInAction",
    "mcp",                  # MCP protocol, servers, tools
    "OpenSourceeAI",
    "codex",
    "cursor",
    "clawdbot",
    "openclaw",
    "BlackboxAI_",
    "aitubers",             # AI YouTube content (AI course project)
    "LangChain",
    "ollama",
    "ClaudeCode",           # NEW: Dedicated Claude Code sub. MCP setups, workflow tips. 96K.
    "LLMDevs",              # NEW: LLM engineering practitioners. RAG, fine-tuning. 125K.
    "AIPromptProgramming",  # NEW: Tactical prompt crafting for code generation. 69K.

    # ── Software & Web Development ────────────────────────────────────────
    # WHY: Bloodline Charters (Next.js), Sullivan site rebuild, Goldie MVP,
    # all the tools you build daily.
    # DOMAINS: software-dev, frontend-development, cloud-infrastructure
    "webdev",
    "nextjs",
    "reactjs",
    "node",
    "typescript",
    "programming",
    "selfhosted",           # Self-hosting patterns (relevant for VPS work)
    "devops",
    "cloudflare",           # Workers, D1, R2 (Brain Feed, FlipBot infra)
    "vba",                  # You saved one. Excel/automation adjacent.

    # ── Cybersecurity ─────────────────────────────────────────────────────
    # WHY: Security review patterns, Pepper crypto safety, client systems.
    # DOMAINS: cybersecurity
    "Pentesting",
    "netsec",
    "cybersecurity",
    "hacking",

    # ── Business & SaaS ───────────────────────────────────────────────────
    # WHY: Goldie Group consulting, GES business development, pricing,
    # client acquisition. Sullivan proposals. Future SaaS products.
    # DOMAINS: business-consulting, saas-building, gtm-strategy, sales
    "Entrepreneur",
    "startups",
    "SaaS",
    "indiehackers",
    "microsaas",
    "smallbusiness",
    "consulting",
    "freelance",
    "msp",                  # NEW: Managed Service Providers. Your ideal client profile. 188K.
    "Bootstrapped",         # NEW: Profitable businesses without VC. Revenue transparency.
    "nocode",               # NEW: What non-technical clients build and where they fail.

    # ── Finance & Crypto ──────────────────────────────────────────────────
    # WHY: Personal finance (FIRE path), Pepper crypto operations,
    # investment decisions, tax planning.
    # DOMAINS: personal-finance, accounting-tax, blockchain-web3
    "personalfinance",
    "financialindependence", # FIRE community
    "investing",
    "stocks",
    "Daytrading",
    "Bitcoin",
    "cryptocurrency",
    "CryptoMarkets",
    "defi",
    "fatFIRE",              # NEW: High-income FIRE. Business owners targeting $2M+.
    "Bogleheads",           # NEW: Index investing. Highest signal-to-noise finance sub.
    "ExpatFIRE",            # NEW: Expats pursuing FI. International tax, banking. You are this.

    # ── Video & Content Production ────────────────────────────────────────
    # WHY: The Flip Side podcast/video, AI course video pipeline,
    # ShopMyRoom short-form video, social distribution engine.
    # DOMAINS: video-production, social-media, podcasting
    "VideoEditing",
    "NewTubers",
    "youtubers",
    "podcasting",
    "Filmmakers",
    "videography",
    "ContentCreators",
    "aivideo",              # NEW: AI video generation. Runway, Kling, Minimax pipelines.
    "StableDiffusion",      # NEW: ComfyUI workflows, AnimateDiff. Video pipeline techniques.

    # ── Marketing & Growth ────────────────────────────────────────────────
    # WHY: LinkedIn launch for Turboquant, social distribution,
    # BrandPal content strategy, Sullivan SEO.
    # DOMAINS: marketing-content, social-media, social-distribution
    "SEO",
    "digital_marketing",
    "socialmedia",
    "content_marketing",
    "copywriting",
    "LinkedInLunatics",     # LinkedIn culture awareness (you post there)
    "bigseo",               # NEW: Serious SEO practitioners only. Case studies. 100K.

    # ── Real Estate & Auctions ────────────────────────────────────────────
    # WHY: Sullivan Auctioneers (NH Tax Deed, online auctions).
    # DOMAINS: real-estate
    "RealEstate",
    "realestateinvesting",
    "Flipping",             # Adjacent to auction business
    "taxliens",             # NEW: Tax lien/deed investing. Niche for Sullivan NH Tax Deed.

    # ── China & Expat Life ────────────────────────────────────────────────
    # WHY: You live in Chengdu. Business operates across US-China.
    # The Flip Side is literally about US-China relations.
    # DOMAINS: (cross-domain, enriches context-engineering and project knowledge)
    "China",
    "chinalife",
    "shanghai",
    "AskChina",
    "ChineseLanguage",
    "chineseknowledge",

    # ── Psychology & Persuasion ───────────────────────────────────────────
    # WHY: Sales (Goldie, Sullivan), negotiation, content that converts,
    # podcast engagement. Also personal interest per your saved posts.
    # DOMAINS: psychology-persuasion, negotiation, sales
    "psychology",
    "BehavioralEconomics",
    "seduction",            # You have 13 saves here. Communication/influence.
    "socialskills",
    "DecidingToBeBetter",

    # ── Fishing & Cape Cod ────────────────────────────────────────────────
    # WHY: Bloodline Charters is a fishing charter business.
    # DOMAINS: (enriches project-specific knowledge)
    "Fishing",
    "flyfishing",
    "CapeCod",
    "boating",

    # ── Personal Development ──────────────────────────────────────────────
    # WHY: Nootropics, fitness, productivity. Your saves show this interest.
    # DOMAINS: nutrition-fitness, mental-health
    "Nootropics",
    "Fitness",
    "bodyweightfitness",
    "productivity",
    "getdisciplined",
    "Biohackers",           # NEW: Sleep, HRV, cold exposure, supplements. 757K.

    # ── General Knowledge (selective) ─────────────────────────────────────
    # WHY: These sometimes have useful content but are mostly noise.
    # The engagement + content length filters will handle the noise.
    # Only allow posts with substantive selftext (>200 chars) from these.
    "IAmA",                 # Founder/expert AMAs can be gold
    "YouShouldKnow",        # Practical knowledge tips
    "LifeProTips",          # Occasionally useful
    "personalfinance",      # Already above, but confirming
    "explainlikeimfive",    # Good for mental models
    "Futurology",           # Tech/society trends
    "science",              # Research findings
    "dataisbeautiful",      # Data literacy
    "todayilearned",        # Random knowledge (low priority but not noise)

    # ── Data & Analytics ──────────────────────────────────────────────────
    # WHY: Goldie email analysis, ShopMyRoom metrics, dashboard work.
    # DOMAINS: data-analytics, data-engineering
    "datascience",
    "dataengineering",
    "SQL",
    "analytics",

    # ── Automation & Pipelines ────────────────────────────────────────────
    # WHY: Goldie email triage architecture, ShopMyRoom video pipeline,
    # Brain Feed webhook chains, general workflow automation.
    # DOMAINS: operations-automation
    "n8n",                  # NEW: Open-source workflow automation. Email parsing, webhooks.
    "Automate",             # NEW: General automation scripts and workflows.

    # ── Foundational Theory ──────────────────────────────────────────────
    # WHY: Domain agent reasoning, knowledge architecture, inference
    # quality. High-level thinking that makes agents smarter.
    # DOMAINS: ai-machine-learning, context-engineering
    "QuantumComputing",     # Quantum logic, superposition of states, measurement theory.
    "InformationTheory",    # Shannon entropy, compression, signal vs noise.
    "compsci",              # Computation theory, algorithms, complexity classes.
    "PhilosophyofScience",  # Epistemology, falsifiability, reasoning frameworks.
    "CognitiveScience",     # How humans reason. Mental models, biases, decision-making.
    "complexity",           # Complex systems, emergence, network effects.
    "SystemsThinking",      # Feedback loops, stocks/flows, system dynamics.
    "CategoryTheory",       # Mathematical abstractions. Compositional reasoning patterns.
    "math",                 # General mathematics. Proof techniques, structures.
    "AskPhilosophy",        # Epistemology, logic, knowledge justification.
}


# ── SCAN TARGETS ────────────────────────────────────────────────────────────
# Actively scanned by the daily scanner for new high-quality posts.
# Smaller list than ALLOWLIST. Only subs where cutting-edge knowledge appears
# fast enough to matter. Weighted by priority.

SCAN_TARGETS = {
    # Tier 1: Check daily. The absolute frontier of AI tooling.
    # These subs move fast. A post today could become a new skill tomorrow.
    "tier1": {
        "subs": [
            "ClaudeAI",
            "ClaudeCode",           # NEW: Claude Code specific. MCP, CLAUDE.md, workflows.
            "vibecoding",
            "LocalLLaMA",
            "LLMDevs",             # NEW: LLM engineering practitioners.
            "Rag",
            "mcp",
            "AI_Agents",
            "AIAgentsInAction",
            "MachineLearning",
        ],
        "weight": 1.5,
        "posts_per_sub": 10,
        "time_filter": "day",
    },

    # Tier 2: Check daily. Tools and platforms you build on.
    "tier2": {
        "subs": [
            "ChatGPTCoding",
            "PromptEngineering",
            "OpenSourceeAI",
            "codex",
            "cursor",
            "artificial",
            "selfhosted",
            "cloudflare",
            "aivideo",             # NEW: AI video tools and pipelines.
            "n8n",                 # NEW: Workflow automation patterns.
        ],
        "weight": 1.2,
        "posts_per_sub": 8,
        "time_filter": "day",
    },

    # Tier 3: Check weekly. Business intelligence and client landscape.
    "tier3": {
        "subs": [
            "SaaS",
            "startups",
            "Entrepreneur",
            "indiehackers",
            "SEO",
            "microsaas",
            "msp",                 # NEW: Your ideal consulting client base.
            "bigseo",              # NEW: Serious SEO practitioners.
            "smallbusiness",       # NEW: Prospect pain points.
        ],
        "weight": 1.0,
        "posts_per_sub": 5,
        "time_filter": "week",
    },

    # Tier 4: Check weekly. Personal enrichment and life optimization.
    "tier4": {
        "subs": [
            "personalfinance",
            "financialindependence",
            "fatFIRE",             # NEW: High-income FIRE. Your bracket.
            "ExpatFIRE",           # NEW: Expat financial independence. Your situation.
            "Bogleheads",          # NEW: Evidence-based investing.
            "cryptocurrency",
            "China",
            "Nootropics",
            "Biohackers",          # NEW: Broader biohacking community.
        ],
        "weight": 0.8,
        "posts_per_sub": 5,
        "time_filter": "week",
    },

    # Tier 5: Check weekly. Foundational theory for agent reasoning.
    "tier5_theory": {
        "subs": [
            "QuantumComputing",
            "InformationTheory",
            "compsci",
            "PhilosophyofScience",
            "CognitiveScience",
            "complexity",
            "SystemsThinking",
            "CategoryTheory",
        ],
        "weight": 1.1,
        "posts_per_sub": 5,
        "time_filter": "week",
    },
}


# ── DENYLIST ────────────────────────────────────────────────────────────────
# Explicitly blocked. These will never pass through even if they somehow
# appear in saves or upvotes. Pure noise.

DENYLIST = {
    "funny", "gifs", "pics", "me_irl", "mfw",
    "rickandmorty", "ChildrenFallingOver", "oddlysatisfying",
    "BlackPeopleTwitter", "WatchPeopleDieInside", "madlads",
    "AdviceAnimals", "mildlyinteresting", "sbubby", "YouFellForItFool",
    "blackmagicfuckery", "Jokes", "PenmanshipPorn", "EarthPorn",
    "Sneakers", "Creatures_of_earth", "shittyaskscience", "creepy",
    "WTF", "gaming", "PUBATTLEGROUNDS", "movies", "television",
    "sports", "Music", "Art", "BMW", "skiing",
    "nottheonion", "fatlogic", "Celebs",
    # Lifestyle/entertainment noise
    "Tinder", "trees", "nosleep", "opiates",
    "GetMotivated", "DIY", "lifehacks",
    "news", "worldnews", "UpliftingNews",
    "grandrapids", "space", "nextfuckinglevel",
    "pcgamingtechsupport", "gadgets",
    "malefashionadvice",    # 8 saves but all image posts, no extractable knowledge
    "TheRedPill",           # 5 saves but dating strategy, not actionable domain knowledge
    "ClassActionRobinHood", "FreeEBOOKS",
    "Documentaries",        # All link posts, no selftext
    "InternetIsBeautiful",  # All link posts
    "AskReddit",            # Mostly discussion threads with no structured knowledge
    "languagelearning",     # One save, too thin to matter
    "cars",                 # Car tour videos, no extractable knowledge
}


# ── Helper Functions ────────────────────────────────────────────────────────

def is_allowed(subreddit: str) -> bool:
    """Check if a subreddit passes the filter."""
    if subreddit in DENYLIST:
        return False
    if subreddit in ALLOWLIST:
        return True
    # Unknown subs: allow if they have substantive content (handled by caller)
    return False


def is_denied(subreddit: str) -> bool:
    """Check if a subreddit is explicitly blocked."""
    return subreddit in DENYLIST

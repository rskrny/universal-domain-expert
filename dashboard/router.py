"""
Domain router. Classifies user messages into domains and complexity tiers.

Mirrors the logic in prompts/ROUTER.md but runs as fast Python code.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class RouteResult:
    primary_domain: str
    supporting_domains: list[str]
    tier: int
    domain_file: str

    @property
    def all_domains(self) -> list[str]:
        return [self.primary_domain] + self.supporting_domains


# Domain registry with trigger patterns (extracted from ROUTER.md)
# 70 domains covering tech, business, law, science, engineering, arts, health, humanities
DOMAIN_REGISTRY = {
    "software-dev": {
        "file": "software-dev.md",
        "triggers": [
            "code", "build", "debug", "deploy", "api", "database", "frontend",
            "backend", "devops", "architecture", "testing", "refactor", "bug",
            "python", "javascript", "typescript", "react", "next.js", "node",
            "server", "endpoint", "git", "docker", "ci/cd", "css", "html",
        ],
    },
    "business-consulting": {
        "file": "business-consulting.md",
        "triggers": [
            "strategy", "operations", "growth", "market analysis", "competitive",
            "organizational", "process improvement", "business model", "pricing",
            "scaling", "consulting", "framework", "mckinsey",
        ],
    },
    "gtm-strategy": {
        "file": "gtm-strategy.md",
        "triggers": [
            "launch", "positioning", "messaging", "channels", "customer acquisition",
            "product-market fit", "icp", "gtm", "go-to-market", "landing page",
            "conversion", "funnel", "onboarding", "churn", "retention",
        ],
    },
    "business-law": {
        "file": "business-law.md",
        "triggers": [
            "contract", "liability", "compliance", "corporate structure",
            "regulatory", "terms of service", "nda", "legal", "privacy policy",
        ],
    },
    "accounting-tax": {
        "file": "accounting-tax.md",
        "triggers": [
            "tax", "bookkeeping", "financial statements", "deductions", "filing",
            "gaap", "revenue recognition", "payroll", "1099", "w-2", "depreciation",
            "accounting", "invoice", "balance sheet", "p&l", "cash flow",
        ],
    },
    "course-creation": {
        "file": "course-creation.md",
        "triggers": [
            "curriculum", "course", "lesson plan", "learning objectives",
            "student engagement", "online education", "content delivery", "module",
            "quiz", "certification",
        ],
    },
    "research-authoring": {
        "file": "research-authoring.md",
        "triggers": [
            "literature review", "methodology", "peer review", "thesis", "publication",
            "citation", "hypothesis", "academic writing", "research paper", "journal",
        ],
    },
    "context-engineering": {
        "file": "context-engineering.md",
        "triggers": [
            "rag", "retrieval", "knowledge base", "embeddings", "chunking", "bm25",
            "semantic search", "context window", "token optimization", "vector search",
            "information density", "prompt engineering",
        ],
    },
    "product-design": {
        "file": "product-design.md",
        "triggers": [
            "ux", "ui", "user experience", "wireframe", "usability",
            "accessibility", "design system", "user flow", "interaction design",
            "prototype", "mockup",
        ],
    },
    "data-analytics": {
        "file": "data-analytics.md",
        "triggers": [
            "analytics", "metrics", "kpis", "a/b testing",
            "cohort analysis", "funnel analysis", "sql", "data visualization",
            "experimentation", "statistical significance", "tableau", "looker",
        ],
    },
    "marketing-content": {
        "file": "marketing-content.md",
        "triggers": [
            "seo", "content marketing", "copywriting", "email marketing",
            "blog", "newsletter", "landing page copy",
            "keyword research", "organic growth", "content strategy",
        ],
    },
    "psychology-persuasion": {
        "file": "psychology-persuasion.md",
        "triggers": [
            "psychology", "persuasion", "behavioral economics", "cognitive bias",
            "decision making", "conversion psychology", "pricing psychology",
            "motivation", "social proof", "anchoring", "scarcity",
        ],
    },
    "operations-automation": {
        "file": "operations-automation.md",
        "triggers": [
            "operations", "automation", "workflow", "sop", "process design",
            "no-code", "zapier", "make", "scheduling", "efficiency",
            "passive income", "delegation", "n8n",
        ],
    },
    "personal-finance": {
        "file": "personal-finance.md",
        "triggers": [
            "personal finance", "investing", "portfolio", "fire", "retirement",
            "savings", "budgeting", "compound interest", "stock", "bond",
            "index fund", "net worth", "wealth", "emergency fund", "debt",
        ],
    },
    "project-management": {
        "file": "project-management.md",
        "triggers": [
            "project management", "task tracking", "sprint", "milestone",
            "roadmap", "prioritization", "backlog", "deadline", "scope",
            "dependencies", "shipping", "timeline", "kanban",
        ],
    },
    "mobile-development": {
        "file": "mobile-development.md",
        "triggers": [
            "mobile", "ios", "android", "swift", "kotlin", "react native",
            "flutter", "app store", "push notifications", "swiftui",
            "jetpack compose", "xcode", "testflight", "deep linking", "kmp",
        ],
    },
    "blockchain-web3": {
        "file": "blockchain-web3.md",
        "triggers": [
            "blockchain", "web3", "smart contract", "defi", "nft", "token",
            "dao", "cryptocurrency", "ethereum", "solana", "consensus",
            "decentralized", "wallet", "gas", "staking", "tokenomics",
        ],
    },
    "cybersecurity": {
        "file": "cybersecurity.md",
        "triggers": [
            "security", "penetration testing", "vulnerability", "threat modeling",
            "encryption", "firewall", "siem", "incident response", "soc",
            "red team", "blue team", "owasp", "zero trust", "malware",
        ],
    },
    "cloud-infrastructure": {
        "file": "cloud-infrastructure.md",
        "triggers": [
            "aws", "azure", "gcp", "cloud", "infrastructure", "iac", "terraform",
            "kubernetes", "containers", "serverless", "lambda", "ec2", "s3",
            "vpc", "load balancer", "auto-scaling", "cdn",
        ],
    },
    "devops-sre": {
        "file": "devops-sre.md",
        "triggers": [
            "sre", "pipeline", "monitoring", "observability", "reliability",
            "slo", "sla", "incident management", "on-call", "prometheus",
            "grafana", "gitops", "helm",
        ],
    },
    "sales": {
        "file": "sales.md",
        "triggers": [
            "sales", "closing", "prospecting", "crm", "cold outreach",
            "demo", "objection handling", "quota", "b2b", "enterprise sales",
            "sdr", "pipeline", "deal",
        ],
    },
    "saas-building": {
        "file": "saas-building.md",
        "triggers": [
            "saas", "subscription", "mrr", "arr", "multi-tenant", "billing",
            "stripe", "freemium", "product-led growth", "feature flags",
            "saas metrics", "recurring revenue",
        ],
    },
    "data-engineering": {
        "file": "data-engineering.md",
        "triggers": [
            "data pipeline", "etl", "elt", "data warehouse", "data lake",
            "spark", "airflow", "dbt", "snowflake", "bigquery", "streaming",
            "kafka", "batch processing", "data modeling", "schema",
        ],
    },
    "ai-machine-learning": {
        "file": "ai-machine-learning.md",
        "triggers": [
            "machine learning", "deep learning", "neural network", "nlp",
            "computer vision", "transformer", "fine-tuning", "training",
            "inference", "pytorch", "tensorflow", "llm", "gpt", "model",
        ],
    },
    "frontend-development": {
        "file": "frontend-development.md",
        "triggers": [
            "react", "vue", "angular", "svelte", "responsive design",
            "state management", "component", "next.js", "tailwind", "webpack",
            "vite", "spa", "ssr",
        ],
    },
    "ecommerce": {
        "file": "ecommerce.md",
        "triggers": [
            "ecommerce", "online store", "shopify", "woocommerce", "cart",
            "checkout", "inventory", "fulfillment", "dropshipping",
            "product catalog", "payment gateway", "order management",
        ],
    },
    "mathematics": {
        "file": "mathematics.md",
        "triggers": [
            "math", "algebra", "calculus", "linear algebra", "probability",
            "proof", "theorem", "optimization", "differential equations",
            "discrete math", "number theory", "topology",
        ],
    },
    "economics": {
        "file": "economics.md",
        "triggers": [
            "economics", "microeconomics", "macroeconomics", "supply and demand",
            "monetary policy", "fiscal policy", "gdp", "inflation",
            "market structure", "game theory", "trade theory",
        ],
    },
    "negotiation": {
        "file": "negotiation.md",
        "triggers": [
            "negotiation", "deal-making", "batna", "zopa", "anchoring",
            "concession", "mediation", "conflict resolution", "bargaining",
            "leverage", "win-win",
        ],
    },
    "venture-capital": {
        "file": "venture-capital.md",
        "triggers": [
            "vc", "venture capital", "fundraising", "pitch deck", "term sheet",
            "valuation", "cap table", "series a", "seed round", "angel investor",
            "due diligence", "equity", "dilution",
        ],
    },
    "statistics": {
        "file": "statistics.md",
        "triggers": [
            "statistics", "regression", "hypothesis testing", "p-value",
            "confidence interval", "bayesian", "sampling", "distribution",
            "variance", "correlation", "anova", "statistical modeling",
        ],
    },
    "social-media": {
        "file": "social-media.md",
        "triggers": [
            "social media", "instagram", "tiktok", "twitter", "linkedin",
            "youtube", "content calendar", "engagement", "followers", "viral",
            "algorithm", "influencer", "community management",
        ],
    },
    "creative-writing": {
        "file": "creative-writing.md",
        "triggers": [
            "fiction", "storytelling", "narrative", "plot", "character development",
            "dialogue", "worldbuilding", "poetry", "screenplay", "short story",
            "novel", "creative nonfiction",
        ],
    },
    "video-production": {
        "file": "video-production.md",
        "triggers": [
            "video", "editing", "filming", "cinematography", "color grading",
            "sound design", "youtube production", "premiere", "davinci resolve",
            "storyboard", "b-roll", "thumbnail",
        ],
    },
    "public-speaking": {
        "file": "public-speaking.md",
        "triggers": [
            "presentation", "public speaking", "speech", "keynote",
            "audience engagement", "slide deck", "delivery", "stage presence",
            "ted talk", "pitch",
        ],
    },
    "medicine-health": {
        "file": "medicine-health.md",
        "triggers": [
            "medicine", "health", "diagnosis", "treatment", "anatomy",
            "pharmacology", "clinical", "symptoms", "pathology", "patient care",
            "medical research", "evidence-based medicine",
        ],
    },
    "mental-health": {
        "file": "mental-health.md",
        "triggers": [
            "mental health", "therapy", "cbt", "anxiety", "depression",
            "trauma", "counseling", "mindfulness", "stress management",
            "burnout", "emotional regulation", "well-being",
        ],
    },
    "supply-chain": {
        "file": "supply-chain.md",
        "triggers": [
            "supply chain", "logistics", "procurement", "inventory management",
            "warehousing", "distribution", "vendor management", "demand planning",
            "lean manufacturing", "jit",
        ],
    },
    "real-estate": {
        "file": "real-estate.md",
        "triggers": [
            "real estate", "property", "mortgage", "rental", "investment property",
            "reits", "appraisal", "closing", "tenant", "landlord",
            "commercial real estate", "cap rate",
        ],
    },
    "customer-success": {
        "file": "customer-success.md",
        "triggers": [
            "customer success", "nps", "churn prevention", "upsell",
            "health score", "renewal", "customer journey", "qbr",
            "expansion revenue", "customer retention",
        ],
    },
    "nutrition-fitness": {
        "file": "nutrition-fitness.md",
        "triggers": [
            "nutrition", "fitness", "diet", "exercise", "macros", "calories",
            "strength training", "cardio", "meal planning", "supplements",
            "body composition", "workout",
        ],
    },
    "hr-talent": {
        "file": "hr-talent.md",
        "triggers": [
            "hr", "hiring", "recruiting", "talent acquisition",
            "performance review", "compensation", "benefits", "culture",
            "job description", "interview",
        ],
    },
    "neuroscience": {
        "file": "neuroscience.md",
        "triggers": [
            "neuroscience", "brain", "cognition", "neuroplasticity",
            "neurotransmitter", "memory", "learning", "perception",
            "consciousness", "neural pathways", "cognitive science",
        ],
    },
    "electrical-engineering": {
        "file": "electrical-engineering.md",
        "triggers": [
            "electrical engineering", "circuits", "electronics", "power systems",
            "embedded systems", "pcb", "microcontroller", "signal processing",
            "control systems", "semiconductor",
        ],
    },
    "civil-engineering": {
        "file": "civil-engineering.md",
        "triggers": [
            "civil engineering", "structural", "construction", "infrastructure",
            "concrete", "steel", "foundations", "geotechnical", "transportation",
            "water resources", "building codes",
        ],
    },
    "political-science": {
        "file": "political-science.md",
        "triggers": [
            "politics", "government", "policy", "democracy", "elections",
            "legislation", "international relations", "political theory",
            "governance", "public administration",
        ],
    },
    "linguistics": {
        "file": "linguistics.md",
        "triggers": [
            "linguistics", "language", "syntax", "semantics", "phonology",
            "morphology", "pragmatics", "sociolinguistics", "translation",
            "language acquisition", "discourse analysis",
        ],
    },
    "journalism": {
        "file": "journalism.md",
        "triggers": [
            "journalism", "reporting", "news", "investigative", "editorial",
            "press", "media", "fact-checking", "source verification",
            "story angle",
        ],
    },
    "philosophy": {
        "file": "philosophy.md",
        "triggers": [
            "philosophy", "ethics", "epistemology", "metaphysics", "logic",
            "aesthetics", "existentialism", "moral philosophy",
            "critical thinking", "philosophical argument",
        ],
    },
    "history": {
        "file": "history.md",
        "triggers": [
            "history", "historical analysis", "primary sources", "historiography",
            "civilization", "era", "war", "revolution", "cultural history",
            "economic history", "political history",
        ],
    },
    "photography": {
        "file": "photography.md",
        "triggers": [
            "photography", "camera", "composition", "lighting", "exposure",
            "aperture", "shutter speed", "iso", "lightroom", "photoshop",
            "portrait", "landscape", "studio",
        ],
    },
    "mechanical-engineering": {
        "file": "mechanical-engineering.md",
        "triggers": [
            "mechanical engineering", "thermodynamics", "fluid mechanics",
            "materials science", "cad", "manufacturing", "hvac", "dynamics",
            "kinematics", "stress analysis", "fea",
        ],
    },
    "environmental-science": {
        "file": "environmental-science.md",
        "triggers": [
            "environment", "climate", "sustainability", "ecology", "conservation",
            "pollution", "renewable energy", "carbon", "biodiversity",
            "environmental policy", "ecosystem",
        ],
    },
    "music-production": {
        "file": "music-production.md",
        "triggers": [
            "music production", "daw", "mixing", "mastering", "synthesis",
            "sampling", "beat making", "ableton", "logic pro", "fl studio",
            "audio engineering", "arrangement", "eq",
        ],
    },
    "graphic-design": {
        "file": "graphic-design.md",
        "triggers": [
            "graphic design", "illustrator", "typography", "layout",
            "color theory", "branding design", "print design", "vector",
            "raster", "visual identity",
        ],
    },
    "robotics": {
        "file": "robotics.md",
        "triggers": [
            "robotics", "robot", "ros", "actuator", "sensor", "kinematics",
            "path planning", "slam", "autonomous", "servo", "manipulation",
        ],
    },
    "branding": {
        "file": "branding.md",
        "triggers": [
            "branding", "brand strategy", "brand identity", "brand voice",
            "brand architecture", "rebrand", "brand guidelines", "brand equity",
            "naming", "brand positioning",
        ],
    },
    "architecture-design": {
        "file": "architecture-design.md",
        "triggers": [
            "building design", "floor plan", "zoning", "urban planning",
            "interior design", "sustainable design", "bim", "rendering",
            "space planning", "architect",
        ],
    },
    "energy-systems": {
        "file": "energy-systems.md",
        "triggers": [
            "energy", "solar", "wind", "battery", "grid", "power generation",
            "renewable", "fossil fuel", "nuclear", "energy storage",
            "smart grid", "energy efficiency",
        ],
    },
    "crisis-management": {
        "file": "crisis-management.md",
        "triggers": [
            "crisis", "emergency", "disaster recovery", "business continuity",
            "risk management", "communication plan", "reputation management",
            "stakeholder management",
        ],
    },
    "quantum-computing": {
        "file": "quantum-computing.md",
        "triggers": [
            "quantum", "qubit", "quantum gate", "superposition", "entanglement",
            "quantum algorithm", "qiskit", "quantum error correction",
            "quantum advantage", "decoherence",
        ],
    },
    "podcasting": {
        "file": "podcasting.md",
        "triggers": [
            "podcast", "audio recording", "episode", "show notes",
            "rss feed", "podcast hosting", "microphone", "audience growth",
            "monetization",
        ],
    },
    "event-planning": {
        "file": "event-planning.md",
        "triggers": [
            "event", "conference", "workshop", "venue", "catering",
            "agenda", "registration", "speaker management", "virtual event",
            "hybrid event", "event marketing",
        ],
    },
    "nonprofit": {
        "file": "nonprofit.md",
        "triggers": [
            "nonprofit", "ngo", "fundraising", "grant writing", "donor management",
            "social impact", "board governance", "volunteer management",
            "501c3", "mission-driven",
        ],
    },
    "education-pedagogy": {
        "file": "education-pedagogy.md",
        "triggers": [
            "education", "pedagogy", "learning theory", "assessment",
            "classroom management", "differentiated instruction", "bloom",
            "educational technology", "student outcomes",
        ],
    },
    "insurance": {
        "file": "insurance.md",
        "triggers": [
            "insurance", "underwriting", "claims", "risk assessment", "premium",
            "deductible", "coverage", "actuarial", "reinsurance", "policy",
            "health insurance", "property insurance",
        ],
    },
    "international-trade": {
        "file": "international-trade.md",
        "triggers": [
            "international trade", "import", "export", "tariff", "customs",
            "trade agreement", "incoterms", "letter of credit", "freight",
            "cross-border", "trade finance", "wto",
        ],
    },
    "intellectual-property": {
        "file": "intellectual-property.md",
        "triggers": [
            "patent", "trademark", "copyright", "trade secret", "ip strategy",
            "licensing", "infringement", "prior art", "ip portfolio",
            "patent filing", "ip valuation",
        ],
    },
    "employment-law": {
        "file": "employment-law.md",
        "triggers": [
            "employment law", "labor law", "wrongful termination", "discrimination",
            "harassment", "wage and hour", "fmla", "ada", "workers comp",
            "employment contract", "at-will",
        ],
    },
    "game-development": {
        "file": "game-development.md",
        "triggers": [
            "game dev", "unity", "unreal", "game design", "game mechanics",
            "level design", "game engine", "sprite", "shader", "physics engine",
            "multiplayer", "game loop", "gdd",
        ],
    },
    "criminal-law": {
        "file": "criminal-law.md",
        "triggers": [
            "criminal law", "prosecution", "defense", "felony", "misdemeanor",
            "sentencing", "plea bargain", "constitutional rights", "evidence",
            "criminal procedure", "trial",
        ],
    },

    # --- User Projects (routed to relevant knowledge domain + project context) ---
    "project-flip-side": {
        "file": "marketing-content.md",  # closest domain for media/podcast
        "triggers": [
            "flip side", "podcast", "episode", "chris sun", "brandpal",
            "lark bot", "intelligence bot", "briefing", "yang jinfeng",
            "editor luo", "us china podcast",
        ],
    },
    "project-bloodline": {
        "file": "software-dev.md",
        "triggers": [
            "bloodline", "charter", "booking", "fishing bloodline",
            "railway", "next.js site", "bloodline charters",
        ],
    },
    "project-shopmyroom": {
        "file": "marketing-content.md",
        "triggers": [
            "shopmyroom", "shop my room", "short video", "short vid",
            "furniture video", "elia", "ar app",
        ],
    },
    "project-goldie": {
        "file": "business-consulting.md",
        "triggers": [
            "goldie group", "goldie", "email triage", "kenny",
            "david rothschild", "sal macias", "nashville",
        ],
    },
    "project-habitat": {
        "file": "architecture-design.md",
        "triggers": [
            "habitat homeostasis", "habitat", "climate analysis",
            "passive design", "isaac humble", "epw", "psychrometric",
        ],
    },
    "project-tax": {
        "file": "accounting-tax.md",
        "triggers": [
            "my taxes", "form 5471", "feie", "foreign earned income",
            "schedule c", "ges llc", "global edge strategies",
            "wfoe", "chengdu entity", "my tax", "crypto custodial",
        ],
    },
}


def classify(message: str) -> RouteResult:
    """Classify a user message into domain(s) and complexity tier."""
    msg_lower = message.lower()
    words = set(re.findall(r'\b\w+\b', msg_lower))

    # Score each domain by trigger matches
    scores = {}
    for domain, info in DOMAIN_REGISTRY.items():
        score = 0
        for trigger in info["triggers"]:
            trigger_words = trigger.lower().split()
            if len(trigger_words) == 1:
                if trigger_words[0] in words:
                    score += 1
            else:
                if trigger in msg_lower:
                    score += 2  # multi-word matches score higher
        if score > 0:
            scores[domain] = score

    # Sort by score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    if not ranked:
        primary = "business-consulting"  # default fallback
    else:
        primary = ranked[0][0]

    supporting = [d for d, _ in ranked[1:3] if scores.get(d, 0) > 0]

    # Classify tier
    tier = _classify_tier(message)

    return RouteResult(
        primary_domain=primary,
        supporting_domains=supporting,
        tier=tier,
        domain_file=DOMAIN_REGISTRY[primary]["file"],
    )


def _classify_tier(message: str) -> int:
    """Determine complexity tier (1, 2, or 3)."""
    msg_lower = message.lower().strip()
    word_count = len(msg_lower.split())

    # Tier 1 signals: short, question-form
    tier1_patterns = [
        r"^(what|how|when|why|where|who|which|explain|define|tell me)\b",
        r"\?$",
    ]
    if word_count < 20 and any(re.search(p, msg_lower) for p in tier1_patterns):
        return 1

    # Tier 3 signals: complex multi-deliverable
    tier3_keywords = [
        "comprehensive", "complete", "full strategy", "entire", "end-to-end",
        "multi-part", "build a system", "design a platform", "create a plan",
        "from scratch", "everything about",
    ]
    if any(kw in msg_lower for kw in tier3_keywords) or word_count > 80:
        return 3

    # Default: Tier 2
    return 2


def get_domain_prompt_path(domain: str, prompts_dir: str) -> Optional[str]:
    """Get the full file path for a domain's prompt file."""
    if domain in DOMAIN_REGISTRY:
        return f"{prompts_dir}/domains/{DOMAIN_REGISTRY[domain]['file']}"
    return None

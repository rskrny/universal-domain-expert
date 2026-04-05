"""
Project registry. Maps real project folders to dashboard configuration.

All folder access is READ-ONLY. No files in project folders are ever modified.
PII-sensitive projects are flagged for text scrubbing during indexing.
"""

import os
from pathlib import Path

# Base path for all project folders. Uses PROJECTS_BASE env var if set,
# otherwise falls back to ~/Desktop for portability across machines.
DESKTOP = Path(os.environ.get("PROJECTS_BASE", Path.home() / "Desktop"))
GES = DESKTOP / "Global Edge Strategies Chengdu Huanqiao"

PROJECT_REGISTRY = {
    "the-flip-side": {
        "name": "The Flip Side",
        "path": str(DESKTOP / "The Flip Side"),
        "description": "US-China podcast and media brand. Episodes, social content, Lark automation.",
        "category": "Media",
        "agent": "flipside",
        "agent_schedule": "weekly",  # Monday morning
        "lark_chat_id": "oc_9ab63146985ea87abe6718c9ea304822",
        "include_patterns": ["*.md", "*.txt", "*.py", "*.ts", "*.json"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", ".env", "*.jpg", "*.png",
            "*.pdf", "*.docx", "*.zip", "*.srt", "*.mp4", "*.mp3",
            ".gstack/*", "node_modules/*",
        ],
        "pii_scrub": False,
    },
    "bloodline": {
        "name": "Bloodline Charters",
        "path": str(GES / "clients" / "bloodline"),
        "description": "Charter booking site. Next.js + Supabase on Railway.",
        "category": "SaaS",
        "agent": "bloodline",
        "agent_schedule": "daily",  # 7:04 AM CST
        "production_url": "https://fishingbloodline.com",
        "include_patterns": ["*.md", "*.txt", "*.py"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", ".env", "node_modules/*", ".next/*",
            "*.jpg", "*.webp", "*.png", "*.html", "client-template/*",
        ],
        "pii_scrub": False,
    },
    "shopmyroom-vids": {
        "name": "ShopMyRoom Videos",
        "path": str(DESKTOP / "automateshortvidssmr"),
        "description": "Automated short-form video pipeline for ShopMyRoom furniture AR app.",
        "category": "Content",
        "agent": None,
        "agent_schedule": None,
        "include_patterns": ["*.md", "*.txt", "*.py", "*.json"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", ".env",
            "*.mp4", "*.mp3", "*.wav", "*.png", "*.jpg", "*.webp",
            "outputs/*",
        ],
        "pii_scrub": False,
    },
    "goldie-group": {
        "name": "Goldie Group",
        "path": str(GES / "clients" / "goldie-group"),
        "description": "AI email triage MVP consulting. Phase 1: $12K. Nashville client.",
        "category": "Consulting",
        "agent": None,
        "agent_schedule": None,
        "include_patterns": ["*.md", "*.txt", "*.py"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", ".env", "*.pdf", "*.svg",
        ],
        "pii_scrub": False,
    },
    "habitat-homeostasis": {
        "name": "Habitat Homeostasis",
        "path": str(DESKTOP / "Isaac Habitat Homeostasis"),
        "description": "Climate-responsive building design consulting. Automated report pipeline.",
        "category": "Consulting",
        "agent": None,
        "agent_schedule": None,
        "include_patterns": ["*.md", "*.py"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", "*.pdf", "*.png",
            "*.epw", "*.wea", "*.stat", "*.rain", "*.pvsyst",
            "*.ddy", "*.clm", "*.zip", "*.pages",
        ],
        "pii_scrub": False,
    },
    "tax-finance": {
        "name": "Tax Finance Crypto",
        "path": str(DESKTOP / "Tax Finance Crypto"),
        "description": "Personal tax, finance, and crypto documentation. GES LLC + WFOE.",
        "category": "Finance",
        "agent": None,
        "agent_schedule": None,
        "include_patterns": ["*.md", "*.txt"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", ".env",
            "*.csv", "*.pdf", "*.xlsm", "*.png", "*.jpg", "*.zip",
            "Taxdocs/2024*",  # Old year raw docs
        ],
        "pii_scrub": True,  # Scrub SSN, EIN, account numbers before indexing
    },
    "pepper-coo": {
        "name": "Pepper COO",
        "path": str(DESKTOP / "Pepper COO"),
        "description": "OpenClaw Telegram bot for Pepper's arcade. Hostinger VPS.",
        "category": "SaaS",
        "agent": None,
        "agent_schedule": None,
        "include_patterns": ["*.md", "*.txt", "*.py", "*.json"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", ".env", "node_modules/*",
            "*.jpg", "*.png", "*.mp4",
        ],
        "pii_scrub": False,
    },
    "ai-beginner-course": {
        "name": "AI Beginner Course",
        "path": str(DESKTOP / "AI Beginner Course"),
        "description": "AI for the Rest of Us. Course curriculum and content development.",
        "category": "Content",
        "agent": None,
        "agent_schedule": None,
        "include_patterns": ["*.md", "*.txt", "*.py"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", ".env",
            "*.mp4", "*.mp3", "*.png", "*.jpg",
        ],
        "pii_scrub": False,
    },
    "smr-aws": {
        "name": "SMR AWS Projections",
        "path": str(DESKTOP / "SMR AWS or Hardware projections"),
        "description": "Cloud vs hardware cost optimizer for ShopMyRoom AI pipelines.",
        "category": "Finance",
        "agent": None,
        "agent_schedule": None,
        "include_patterns": ["*.md", "*.txt", "*.py", "*.json"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", ".env",
        ],
        "pii_scrub": False,
    },
    "ges-hub": {
        "name": "Global Edge Strategies",
        "path": str(GES),
        "description": "GES business hub. GTM strategy, pricing, outreach, LinkedIn, knowledge base.",
        "category": "Business",
        "agent": None,
        "agent_schedule": None,
        "include_patterns": ["*.md", "*.txt"],
        "exclude_patterns": [
            ".git/*", "__pycache__/*", ".env", "node_modules/*", ".next/*",
            "clients/*",  # Clients indexed separately
            "gesedge/src/*", "gesedge/node_modules/*",
            "*.jpg", "*.png", "*.svg", "*.pdf", "*.docx", "*.xlsx",
        ],
        "pii_scrub": False,
    },
}


def get_project(key: str) -> dict:
    """Get a project config by key."""
    return PROJECT_REGISTRY.get(key)


def get_all_projects() -> dict:
    """Get all project configs."""
    return PROJECT_REGISTRY


def get_scheduled_projects() -> list[tuple[str, dict]]:
    """Get projects that have scheduled agents."""
    return [(k, v) for k, v in PROJECT_REGISTRY.items() if v["agent_schedule"]]


def get_indexable_projects() -> list[tuple[str, dict]]:
    """Get all projects that should be indexed."""
    return [(k, v) for k, v in PROJECT_REGISTRY.items() if Path(v["path"]).exists()]

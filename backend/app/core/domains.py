"""Canonical MVP domains and legacy topic -> domain mapping.

The MVP exposes exactly three learning domains. Older seed data uses topics
such as ``daily-life`` or ``academic``; those remain stored in ``topic`` for
backwards compatibility but are grouped into the General English domain.
"""
from __future__ import annotations

MVP_DOMAIN_ORDER = ("general", "technology", "business")

DOMAINS: dict[str, dict] = {
    "general": {
        "slug": "general",
        "name": "General English",
        "name_vi": "Tiếng Anh tổng quát",
        "description": "Từ vựng tiếng Anh giao tiếp và đời sống hằng ngày.",
        "order": 1,
    },
    "technology": {
        "slug": "technology",
        "name": "IT / Technology",
        "name_vi": "Công nghệ thông tin",
        "description": "Từ vựng công nghệ, lập trình và sản phẩm số.",
        "order": 2,
    },
    "business": {
        "slug": "business",
        "name": "Business English",
        "name_vi": "Tiếng Anh thương mại",
        "description": "Từ vựng kinh doanh, văn phòng và thương mại.",
        "order": 3,
    },
}

# Legacy topics that are not a separate MVP domain fall back to General.
TOPIC_TO_DOMAIN: dict[str, str] = {
    "general": "general",
    "technology": "technology",
    "tech": "technology",
    "it": "technology",
    "business": "business",
    "academic": "general",
    "science": "general",
    "daily-life": "general",
    "daily life": "general",
    "daily_life": "general",
    "travel": "general",
}


def normalize_domain(value: str | None) -> str:
    """Return a canonical MVP domain for a topic/domain value."""
    if not value:
        return "general"
    key = str(value).strip().lower()
    if key in DOMAINS:
        return key
    return TOPIC_TO_DOMAIN.get(key, "general")


def domain_for_topic(topic: str | None) -> str:
    return normalize_domain(topic)


def domain_doc(slug: str) -> dict:
    data = DOMAINS[normalize_domain(slug)]
    return {
        "_id": data["slug"],
        "slug": data["slug"],
        "name": data["name"],
        "name_vi": data["name_vi"],
        "description": data["description"],
        "order": data["order"],
        "active": True,
    }

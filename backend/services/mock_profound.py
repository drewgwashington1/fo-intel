"""Mock Profound API data generator for AI visibility."""
import random
from datetime import date

PLATFORMS = ["ChatGPT", "Perplexity", "Gemini", "Claude", "Google AI"]

CATEGORIES = [
    {"id": "cat-001", "name": "Branded Calling"},
    {"id": "cat-002", "name": "Spam Protection"},
    {"id": "cat-003", "name": "Call Authentication"},
    {"id": "cat-004", "name": "Caller ID"},
    {"id": "cat-005", "name": "Robocall Blocking"},
]

COMPETITORS = [
    "hiya.com",
    "numeracle.com",
    "transunion.com",
    "freecallerregistry.com",
    "tnsi.com",
]

FO_PAGES = [
    "https://firstorion.com/solutions/branded-calling/",
    "https://firstorion.com/solutions/call-protection/",
    "https://firstorion.com/products/inform/",
    "https://firstorion.com/products/engage/",
    "https://firstorion.com/blog/branded-calling-guide/",
    "https://firstorion.com/blog/stir-shaken-explained/",
    "https://firstorion.com/resources/case-studies/",
]

PROMPTS = [
    "What is branded calling?",
    "Best spam call protection services",
    "How does STIR/SHAKEN work?",
    "Enterprise caller ID solutions",
    "How to brand outbound calls",
    "Robocall blocking for businesses",
    "First Orion vs Hiya comparison",
    "Call authentication providers",
    "How to improve call answer rates",
    "Rich call data explained",
]


def generate_ai_visibility(target_date: date) -> list[dict]:
    rows = []
    for cat in CATEGORIES:
        for platform in PLATFORMS:
            visibility = random.uniform(30.0, 95.0)
            sov = random.uniform(0.10, 0.45)
            citations = random.randint(0, 25)
            avg_pos = random.uniform(1.0, 5.0)

            rows.append({
                "data_date": target_date,
                "category_id": cat["id"],
                "category_name": cat["name"],
                "platform": platform,
                "visibility_score": round(visibility, 1),
                "share_of_voice": round(sov, 4),
                "citation_count": citations,
                "average_position": round(avg_pos, 1),
            })
    return rows


def generate_ai_citations(target_date: date) -> list[dict]:
    rows = []
    num_citations = random.randint(8, 25)
    for _ in range(num_citations):
        rows.append({
            "data_date": target_date,
            "prompt": random.choice(PROMPTS),
            "platform": random.choice(PLATFORMS),
            "cited_url": random.choice(FO_PAGES),
            "citation_type": random.choice(["DIRECT", "INDIRECT", "MENTION"]),
            "sentiment": random.choices(
                ["POSITIVE", "NEUTRAL", "NEGATIVE"], weights=[0.6, 0.3, 0.1]
            )[0],
        })
    return rows


def generate_ai_competitors(target_date: date) -> list[dict]:
    rows = []
    for cat in CATEGORIES:
        for platform in PLATFORMS:
            for comp in COMPETITORS:
                sov = random.uniform(0.05, 0.35)
                citations = random.randint(0, 15)

                rows.append({
                    "data_date": target_date,
                    "category_name": cat["name"],
                    "platform": platform,
                    "competitor_domain": comp,
                    "share_of_voice": round(sov, 4),
                    "citation_count": citations,
                })
    return rows

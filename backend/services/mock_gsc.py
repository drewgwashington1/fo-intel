"""Mock Google Search Console data generator."""
import random
from datetime import date, timedelta

SITE_URL = "https://firstorion.com/"

QUERIES = [
    "first orion", "branded calling", "branded call display", "spam call protection",
    "call authentication", "stir shaken", "caller id verification", "robocall blocking",
    "call labeling", "phone number reputation", "branded calling solution",
    "call display branding", "enterprise caller id", "spam call filter",
    "call trust", "call verification service", "first orion inform",
    "first orion engage", "rich call data", "call branding platform",
    "caller name display", "phone spam protection", "business caller id",
    "call center caller id", "outbound call branding",
]

PAGES = [
    "/", "/solutions/branded-calling/", "/solutions/call-protection/",
    "/products/inform/", "/products/engage/", "/products/protect/",
    "/blog/branded-calling-guide/", "/blog/stir-shaken-explained/",
    "/blog/robocall-statistics-2026/", "/resources/case-studies/",
    "/resources/whitepapers/", "/about/", "/contact/",
    "/blog/call-authentication-101/", "/blog/caller-id-best-practices/",
]

COUNTRIES = ["US", "CA", "GB", "AU", "IN"]
DEVICES = ["DESKTOP", "MOBILE", "TABLET"]
DEVICE_WEIGHTS = [0.30, 0.60, 0.10]


def generate_gsc_data(target_date: date) -> list[dict]:
    rows = []
    day_of_week = target_date.weekday()
    is_weekend = day_of_week >= 5
    base_multiplier = 0.55 if is_weekend else 1.0
    base_multiplier *= random.uniform(0.85, 1.15)

    num_rows = random.randint(80, 150)
    for _ in range(num_rows):
        query = random.choice(QUERIES)
        page = random.choice(PAGES)
        country = random.choices(COUNTRIES, weights=[0.70, 0.12, 0.08, 0.05, 0.05])[0]
        device = random.choices(DEVICES, weights=DEVICE_WEIGHTS)[0]

        is_branded = "first orion" in query.lower()
        if is_branded:
            position = random.uniform(1.0, 3.0)
            impressions = int(random.randint(50, 300) * base_multiplier)
        else:
            position = random.uniform(3.0, 45.0)
            impressions = int(random.randint(10, 200) * base_multiplier)

        position_ctr_base = max(0.01, 0.35 - (position - 1) * 0.03)
        ctr = min(1.0, max(0.001, position_ctr_base * random.uniform(0.6, 1.4)))
        clicks = max(0, int(impressions * ctr))

        rows.append({
            "data_date": target_date,
            "site_url": SITE_URL,
            "query": query,
            "page": page,
            "country": country,
            "device": device,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": round(ctr, 4),
            "position": round(position, 1),
        })

    return rows

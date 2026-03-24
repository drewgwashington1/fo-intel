"""Mock Google Ads Transparency Center data generator."""
import random
import uuid
from datetime import date, timedelta

COMPETITORS = {
    "hiya.com": "Hiya Inc.",
    "numeracle.com": "Numeracle",
    "transunion.com": "TransUnion",
    "freecallerregistry.com": "Free Caller Registry",
    "tnsi.com": "Transaction Network Services",
}

HEADLINES = {
    "hiya.com": [
        "Protect Your Calls with Hiya", "Hiya — Branded Caller ID",
        "Stop Spam Calls | Hiya", "Hiya Connect for Enterprise",
        "Know Who's Calling | Hiya App",
    ],
    "numeracle.com": [
        "Numeracle Entity Identity Management", "Fix Your Caller ID — Numeracle",
        "Call Labeling Solutions | Numeracle", "Numeracle — Trusted Call Display",
        "Enterprise Calling Identity | Numeracle",
    ],
    "transunion.com": [
        "TruContact Branded Calling", "TransUnion Caller ID Solutions",
        "Stop Call Spoofing | TransUnion", "Branded Communication — TransUnion",
        "Call Authentication | TruContact",
    ],
    "freecallerregistry.com": [
        "Register Your Caller ID Free", "Free Caller Registry — Verify Your Number",
        "Protect Your Business Calls", "Caller Registration Service",
    ],
    "tnsi.com": [
        "TNS Call Guardian", "Enterprise Call Protection | TNS",
        "Robocall Mitigation — TNS", "TNS Communications Market Intelligence",
        "Call Analytics Platform | TNS",
    ],
}

DESCRIPTIONS = [
    "Protect your brand and increase answer rates with our enterprise solution.",
    "Trusted by carriers nationwide. Get started today.",
    "Reduce spam labels and improve outbound call performance.",
    "The industry's most comprehensive call identity platform.",
    "See why leading enterprises choose our call branding solution.",
    "Improve contact rates by up to 300% with branded calling.",
]

PLATFORMS_POOL = ["Search", "YouTube", "Display"]
REGIONS_POOL = ["United States", "Canada", "United Kingdom", "Australia"]


def generate_competitor_ads(target_date: date) -> list[dict]:
    rows = []

    for domain, advertiser in COMPETITORS.items():
        num_ads = random.randint(3, 10)
        headlines = HEADLINES.get(domain, ["Ad Headline"])

        for _ in range(num_ads):
            first_shown = target_date - timedelta(days=random.randint(1, 120))
            is_active = random.random() < 0.7
            last_shown = None if is_active else target_date - timedelta(days=random.randint(1, 14))
            days_running = (target_date - first_shown).days

            ad_format = random.choices(
                ["TEXT", "IMAGE", "VIDEO"], weights=[0.6, 0.3, 0.1]
            )[0]

            num_platforms = random.randint(1, 3)
            platforms = random.sample(PLATFORMS_POOL, num_platforms)
            num_regions = random.randint(1, 3)
            regions = random.sample(REGIONS_POOL, num_regions)

            rows.append({
                "ad_id": f"ad-{uuid.uuid4().hex[:12]}",
                "scraped_date": target_date,
                "competitor_domain": domain,
                "advertiser_name": advertiser,
                "ad_format": ad_format,
                "headline": random.choice(headlines),
                "description": random.choice(DESCRIPTIONS),
                "destination_url": f"https://{domain}/",
                "platforms": platforms,
                "regions": regions,
                "first_shown_date": first_shown,
                "last_shown_date": last_shown,
                "days_running": days_running,
                "is_active": is_active,
                "image_url": None,
            })

    return rows

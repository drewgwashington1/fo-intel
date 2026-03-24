"""Mock Google Ads data generator."""
import random
from datetime import date

CAMPAIGNS = [
    {"id": 100001, "name": "Brand - Exact", "ad_groups": [
        {"id": 200001, "name": "First Orion Brand"},
        {"id": 200002, "name": "FO Products"},
    ]},
    {"id": 100002, "name": "Non-Brand - Caller ID", "ad_groups": [
        {"id": 200003, "name": "Branded Calling"},
        {"id": 200004, "name": "Caller ID Solutions"},
    ]},
    {"id": 100003, "name": "Non-Brand - Spam Protection", "ad_groups": [
        {"id": 200005, "name": "Robocall Blocking"},
        {"id": 200006, "name": "Spam Call Filter"},
    ]},
    {"id": 100004, "name": "Competitor - Conquesting", "ad_groups": [
        {"id": 200007, "name": "vs Hiya"},
        {"id": 200008, "name": "vs Numeracle"},
    ]},
    {"id": 100005, "name": "Retargeting - Site Visitors", "ad_groups": [
        {"id": 200009, "name": "All Visitors"},
        {"id": 200010, "name": "Demo Page Visitors"},
    ]},
]

SEARCH_TERMS_POOL = [
    "branded calling solution", "caller id branding", "first orion pricing",
    "robocall blocking enterprise", "stir shaken compliance", "call labeling service",
    "spam call protection for business", "outbound caller id", "rich call data provider",
    "branded calling vs spam label", "call authentication platform", "hiya vs first orion",
    "numeracle alternative", "caller name id enterprise", "phone number reputation management",
    "call center caller id display", "mobile caller id branding", "t-mobile branded calling",
    "att call protect enterprise", "verizon call filter business",
]


def generate_paid_data(target_date: date) -> list[dict]:
    rows = []
    is_weekend = target_date.weekday() >= 5
    base_mult = 0.6 if is_weekend else 1.0

    for campaign in CAMPAIGNS:
        for ag in campaign["ad_groups"]:
            impressions = int(random.randint(200, 2000) * base_mult)
            avg_cpc = random.uniform(1.5, 8.0) * 1_000_000
            ctr = random.uniform(0.02, 0.12)
            clicks = max(1, int(impressions * ctr))
            cost = int(clicks * avg_cpc)
            conversions = round(clicks * random.uniform(0.02, 0.15), 1)
            imp_share = random.uniform(0.40, 0.95)
            lost_budget = random.uniform(0.0, 0.25)
            lost_rank = random.uniform(0.0, 0.30)

            rows.append({
                "data_date": target_date,
                "campaign_id": campaign["id"],
                "campaign_name": campaign["name"],
                "ad_group_id": ag["id"],
                "ad_group_name": ag["name"],
                "impressions": impressions,
                "clicks": clicks,
                "cost_micros": cost,
                "avg_cpc_micros": int(avg_cpc),
                "conversions": conversions,
                "impression_share": round(imp_share, 4),
                "lost_is_budget": round(lost_budget, 4),
                "lost_is_rank": round(lost_rank, 4),
            })

    return rows


def generate_search_terms_data(target_date: date) -> list[dict]:
    rows = []
    num_terms = random.randint(15, 30)
    terms = random.sample(SEARCH_TERMS_POOL, min(num_terms, len(SEARCH_TERMS_POOL)))

    for term in terms:
        campaign = random.choice(CAMPAIGNS)
        impressions = random.randint(5, 150)
        ctr = random.uniform(0.01, 0.10)
        clicks = max(0, int(impressions * ctr))
        avg_cpc = random.uniform(1.5, 8.0) * 1_000_000
        cost = int(clicks * avg_cpc)
        conversions = round(clicks * random.uniform(0.0, 0.12), 1)

        rows.append({
            "data_date": target_date,
            "campaign_id": campaign["id"],
            "search_term": term,
            "match_type": random.choice(["BROAD", "PHRASE", "EXACT"]),
            "impressions": impressions,
            "clicks": clicks,
            "cost_micros": cost,
            "conversions": conversions,
        })

    return rows

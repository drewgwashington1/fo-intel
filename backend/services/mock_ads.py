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

AD_CREATIVES = [
    {
        "ad_id": 300001, "ad_type": "RESPONSIVE_SEARCH_AD",
        "headline_1": "Branded Calling Solutions | First Orion",
        "headline_2": "Increase Answer Rates by 48%",
        "headline_3": "Trusted by Top Carriers",
        "description_1": "Display your business name & logo on outbound calls. Boost answer rates and build customer trust with branded calling.",
        "description_2": "First Orion powers branded calling for T-Mobile, AT&T and more. Get a demo today.",
        "final_url": "https://firstorion.com/branded-calling/",
    },
    {
        "ad_id": 300002, "ad_type": "RESPONSIVE_SEARCH_AD",
        "headline_1": "Stop Robocall Labels on Your Calls",
        "headline_2": "Call Authentication Platform",
        "headline_3": "STIR/SHAKEN Compliant",
        "description_1": "Prevent your business calls from being labeled as spam. Enterprise call authentication and number reputation management.",
        "description_2": "Join 500+ enterprises protecting their outbound call reputation with First Orion.",
        "final_url": "https://firstorion.com/call-authentication/",
    },
    {
        "ad_id": 300003, "ad_type": "RESPONSIVE_SEARCH_AD",
        "headline_1": "Enterprise Caller ID Branding",
        "headline_2": "Rich Call Data Provider",
        "headline_3": "Free Assessment Available",
        "description_1": "Display company name, logo & call reason on customer phones. Works across all major US carriers.",
        "description_2": "See how your calls appear today with a free call display assessment from First Orion.",
        "final_url": "https://firstorion.com/products/inform/",
    },
    {
        "ad_id": 300004, "ad_type": "RESPONSIVE_SEARCH_AD",
        "headline_1": "Better Than Hiya for Enterprise",
        "headline_2": "Direct Carrier Partnerships",
        "headline_3": "Request a Comparison",
        "description_1": "First Orion has direct carrier integrations that Hiya can't match. See the difference in call display reach.",
        "description_2": "Compare First Orion vs Hiya — carrier reach, call display coverage, and enterprise features.",
        "final_url": "https://firstorion.com/compare/",
    },
    {
        "ad_id": 300005, "ad_type": "RESPONSIVE_SEARCH_AD",
        "headline_1": "Missed Calls = Lost Revenue",
        "headline_2": "Improve Contact Rates Now",
        "headline_3": "See ROI in 30 Days",
        "description_1": "70% of consumers ignore calls from unknown numbers. Branded calling shows your name so customers answer.",
        "description_2": "Enterprise clients see 30-48% lift in answer rates within the first month. Schedule a demo.",
        "final_url": "https://firstorion.com/demo/",
    },
    {
        "ad_id": 300006, "ad_type": "RESPONSIVE_SEARCH_AD",
        "headline_1": "Call Labeling Prevention",
        "headline_2": "Protect Your Phone Numbers",
        "headline_3": "Number Reputation Dashboard",
        "description_1": "Monitor and protect your business phone numbers from spam labels across all carriers and apps.",
        "description_2": "Real-time number reputation monitoring. Know when your calls are being mislabeled.",
        "final_url": "https://firstorion.com/products/protect/",
    },
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


def generate_ad_creative_data(target_date: date) -> list:
    """Generate mock ad creative performance data."""
    rows = []
    is_weekend = target_date.weekday() >= 5
    base_mult = 0.6 if is_weekend else 1.0

    for creative in AD_CREATIVES:
        campaign = random.choice(CAMPAIGNS)
        ag = random.choice(campaign["ad_groups"])

        impressions = int(random.randint(100, 1200) * base_mult)
        ctr = random.uniform(0.02, 0.14)
        clicks = max(1, int(impressions * ctr))
        avg_cpc = random.uniform(1.5, 9.0) * 1_000_000
        cost = int(clicks * avg_cpc)
        conversions = round(clicks * random.uniform(0.02, 0.18), 1)
        conv_value = round(conversions * random.uniform(25, 150), 2)

        rows.append({
            "data_date": target_date,
            "campaign_id": campaign["id"],
            "campaign_name": campaign["name"],
            "ad_group_id": ag["id"],
            "ad_group_name": ag["name"],
            "ad_id": creative["ad_id"],
            "ad_type": creative["ad_type"],
            "campaign_type": "SEARCH",
            "headline_1": creative["headline_1"],
            "headline_2": creative["headline_2"],
            "headline_3": creative["headline_3"],
            "description_1": creative["description_1"],
            "description_2": creative["description_2"],
            "final_url": creative["final_url"],
            "image_url": None,
            "impressions": impressions,
            "clicks": clicks,
            "cost_micros": cost,
            "conversions": conversions,
            "conversion_value": conv_value,
            "ctr": round(ctr, 4),
            "avg_cpc_micros": int(avg_cpc),
        })

    return rows

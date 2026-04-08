"""Keyword Planner API service — search volume, CPC, competition, and keyword ideas.

Uses the Google Ads KeywordPlanIdeaService to fetch keyword metrics and suggestions.
Basic access returns volume ranges; Standard access returns exact volumes.
"""
import logging
from typing import List

from config import app_settings
from services.google_ads import _get_client

logger = logging.getLogger(__name__)

# US geo target and English language constants
_GEO_TARGET_US = "geoTargetConstants/2840"
_LANGUAGE_EN = "languageConstants/1000"

# Competition enum mapping
_COMPETITION_MAP = {
    0: "UNSPECIFIED",
    1: "UNKNOWN",
    2: "LOW",
    3: "MEDIUM",
    4: "HIGH",
}


def fetch_keyword_metrics(keywords: List[str]) -> List[dict]:
    """Fetch historical metrics for a list of keywords.

    Returns list of dicts with:
        keyword, avg_monthly_searches, competition, competition_index,
        low_cpc_micros, high_cpc_micros
    """
    if not keywords:
        return []

    client = _get_client()
    customer_id = app_settings.GOOGLE_ADS_CUSTOMER_ID
    service = client.get_service("KeywordPlanIdeaService")

    all_results = []

    # Process in batches of 2000 (API limit per request)
    batch_size = 2000
    for i in range(0, len(keywords), batch_size):
        batch = keywords[i:i + batch_size]
        try:
            request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
            request.customer_id = customer_id
            request.keywords.extend(batch)
            request.language = _LANGUAGE_EN
            request.geo_target_constants.append(_GEO_TARGET_US)

            response = service.generate_keyword_historical_metrics(request=request)

            for result in response.results:
                metrics = result.keyword_metrics
                competition_val = metrics.competition if metrics.competition else 0
                # Handle proto-plus enum
                if hasattr(competition_val, 'value'):
                    competition_val = competition_val.value
                elif hasattr(competition_val, 'name'):
                    competition_val = competition_val

                competition_str = _COMPETITION_MAP.get(int(competition_val), "UNKNOWN") if isinstance(competition_val, (int, float)) else str(competition_val)

                all_results.append({
                    "keyword": result.text,
                    "avg_monthly_searches": metrics.avg_monthly_searches or 0,
                    "competition": competition_str,
                    "competition_index": metrics.competition_index or 0,
                    "low_cpc_micros": metrics.low_top_of_page_bid_micros or 0,
                    "high_cpc_micros": metrics.high_top_of_page_bid_micros or 0,
                })

        except Exception as e:
            logger.error(f"Keyword metrics fetch failed for batch starting at {i}: {e}")

    return all_results


def fetch_keyword_ideas(seed_keywords: List[str], limit: int = 50) -> List[dict]:
    """Generate keyword ideas from seed keywords.

    Returns list of dicts with:
        keyword, avg_monthly_searches, competition, competition_index,
        low_cpc_micros, high_cpc_micros
    """
    if not seed_keywords:
        return []

    client = _get_client()
    customer_id = app_settings.GOOGLE_ADS_CUSTOMER_ID
    service = client.get_service("KeywordPlanIdeaService")

    try:
        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = customer_id
        request.language = _LANGUAGE_EN
        request.geo_target_constants.append(_GEO_TARGET_US)
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        request.keyword_seed.keywords.extend(seed_keywords[:20])  # API limit: 20 seeds

        response = service.generate_keyword_ideas(request=request)

        results = []
        for idea in response.results:
            metrics = idea.keyword_idea_metrics
            competition_val = metrics.competition if metrics.competition else 0
            if hasattr(competition_val, 'value'):
                competition_val = competition_val.value
            elif hasattr(competition_val, 'name'):
                competition_val = competition_val

            competition_str = _COMPETITION_MAP.get(int(competition_val), "UNKNOWN") if isinstance(competition_val, (int, float)) else str(competition_val)

            results.append({
                "keyword": idea.text,
                "avg_monthly_searches": metrics.avg_monthly_searches or 0,
                "competition": competition_str,
                "competition_index": metrics.competition_index or 0,
                "low_cpc_micros": metrics.low_top_of_page_bid_micros or 0,
                "high_cpc_micros": metrics.high_top_of_page_bid_micros or 0,
            })

        # Sort by volume descending, return top N
        results.sort(key=lambda x: x["avg_monthly_searches"], reverse=True)
        return results[:limit]

    except Exception as e:
        logger.error(f"Keyword ideas fetch failed: {e}")
        return []

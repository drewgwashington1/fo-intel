"""Real Google Ads data fetcher.

Uses the Google Ads API to pull campaign performance and search term data.
Returns data in the same shape as mock_ads so the ingest router stays clean.
"""
import logging
from datetime import date
from typing import List

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from config import app_settings

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> GoogleAdsClient:
    global _client
    if _client is None:
        _client = GoogleAdsClient.load_from_dict({
            "developer_token": app_settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": app_settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": app_settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": app_settings.GOOGLE_ADS_REFRESH_TOKEN,
            "login_customer_id": app_settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
            "use_proto_plus": True,
        })
    return _client


def fetch_paid_data(target_date: date) -> List[dict]:
    """Fetch campaign performance for a single day.

    Returns list of dicts matching the PaidPerformance model fields.
    """
    client = _get_client()
    customer_id = app_settings.GOOGLE_ADS_CUSTOMER_ID

    ga_service = client.get_service("GoogleAdsService")

    date_str = target_date.strftime("%Y-%m-%d")

    # Query at campaign level (IS metrics only available here)
    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.average_cpc,
            metrics.conversions,
            metrics.search_impression_share,
            metrics.search_budget_lost_impression_share,
            metrics.search_rank_lost_impression_share
        FROM campaign
        WHERE segments.date = '{date_str}'
          AND campaign.status = 'ENABLED'
          AND metrics.impressions > 0
    """

    rows = []
    try:
        response = ga_service.search(customer_id=customer_id, query=query)

        for row in response:
            campaign = row.campaign
            metrics = row.metrics

            is_share = metrics.search_impression_share or 0.0
            lost_budget = metrics.search_budget_lost_impression_share or 0.0
            lost_rank = metrics.search_rank_lost_impression_share or 0.0

            rows.append({
                "data_date": target_date,
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "ad_group_id": 0,
                "ad_group_name": "",
                "impressions": metrics.impressions,
                "clicks": metrics.clicks,
                "cost_micros": metrics.cost_micros,
                "avg_cpc_micros": metrics.average_cpc,
                "conversions": metrics.conversions,
                "impression_share": is_share / 100.0 if is_share > 1 else is_share,
                "lost_is_budget": lost_budget / 100.0 if lost_budget > 1 else lost_budget,
                "lost_is_rank": lost_rank / 100.0 if lost_rank > 1 else lost_rank,
            })

    except GoogleAdsException as ex:
        logger.error(f"Google Ads API error: {ex.failure.errors[0].message}")
        for error in ex.failure.errors:
            logger.error(f"  Error: {error.message}")
    except Exception as e:
        logger.error(f"Google Ads fetch failed for {target_date}: {e}")

    return rows


def fetch_search_terms_data(target_date: date) -> List[dict]:
    """Fetch search terms report for a single day.

    Returns list of dicts matching the SearchTerm model fields.
    """
    client = _get_client()
    customer_id = app_settings.GOOGLE_ADS_CUSTOMER_ID

    ga_service = client.get_service("GoogleAdsService")

    date_str = target_date.strftime("%Y-%m-%d")

    query = f"""
        SELECT
            campaign.id,
            search_term_view.search_term,
            segments.search_term_match_type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM search_term_view
        WHERE segments.date = '{date_str}'
          AND metrics.impressions > 0
    """

    rows = []
    try:
        response = ga_service.search(customer_id=customer_id, query=query)

        for row in response:
            # Map match type enum to string
            match_type_value = row.segments.search_term_match_type
            match_map = {
                2: "EXACT",
                3: "PHRASE",
                4: "BROAD",
                6: "BROAD",  # NEAR_EXACT
                7: "BROAD",  # NEAR_PHRASE
            }
            match_type = match_map.get(match_type_value, "BROAD")

            rows.append({
                "data_date": target_date,
                "campaign_id": row.campaign.id,
                "search_term": row.search_term_view.search_term,
                "match_type": match_type,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost_micros": row.metrics.cost_micros,
                "conversions": row.metrics.conversions,
            })

    except GoogleAdsException as ex:
        logger.error(f"Google Ads search terms error: {ex.failure.errors[0].message}")
    except Exception as e:
        logger.error(f"Google Ads search terms fetch failed for {target_date}: {e}")

    return rows

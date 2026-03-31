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


def fetch_ad_creative_data(target_date: date) -> List[dict]:
    """Fetch ad-level creative performance for a single day.

    Covers three campaign types:
      - Search (RSA via ad_group_ad)
      - Demand Gen (multi-asset via ad_group_ad)
      - Performance Max (asset groups via asset_group_asset)
    """
    client = _get_client()
    customer_id = app_settings.GOOGLE_ADS_CUSTOMER_ID
    ga_service = client.get_service("GoogleAdsService")
    date_str = target_date.strftime("%Y-%m-%d")

    rows = []

    # ── Search + Demand Gen (both live in ad_group_ad) ─────────
    ad_query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.advertising_channel_type,
            ad_group.id,
            ad_group.name,
            ad_group_ad.ad.id,
            ad_group_ad.ad.type,
            ad_group_ad.ad.responsive_search_ad.headlines,
            ad_group_ad.ad.responsive_search_ad.descriptions,
            ad_group_ad.ad.final_urls,
            ad_group_ad.ad.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.ctr,
            metrics.average_cpc
        FROM ad_group_ad
        WHERE segments.date = '{date_str}'
          AND ad_group_ad.status = 'ENABLED'
          AND metrics.impressions > 0
    """

    try:
        response = ga_service.search(customer_id=customer_id, query=ad_query)

        for row in response:
            ad = row.ad_group_ad.ad

            # Map channel type to campaign type string
            channel_type = row.campaign.advertising_channel_type
            channel_map = {
                2: "SEARCH",
                3: "DISPLAY",
                6: "SHOPPING",
                9: "DEMAND_GEN",
                10: "DEMAND_GEN",
                11: "PERFORMANCE_MAX",
                13: "DEMAND_GEN",
            }
            campaign_type = channel_map.get(channel_type, "OTHER")
            # Also detect by campaign name or ad type if enum mapping misses
            cname_lower = row.campaign.name.lower()
            if "demand gen" in cname_lower or "demandgen" in cname_lower:
                campaign_type = "DEMAND_GEN"
            elif "pmax" in cname_lower or "performance max" in cname_lower:
                campaign_type = "PERFORMANCE_MAX"
            elif "DEMAND_GEN" in ad_type_raw:
                campaign_type = "DEMAND_GEN"

            # Extract headlines/descriptions — works for RSA and DemandGen
            headlines = []
            descriptions = []
            image_url = None

            if ad.responsive_search_ad:
                headlines = [h.text for h in ad.responsive_search_ad.headlines[:3]]
                descriptions = [d.text for d in ad.responsive_search_ad.descriptions[:2]]

            # Fallback: use ad.name as headline if no RSA fields
            if not headlines and ad.name:
                headlines = [ad.name]

            final_url = ad.final_urls[0] if ad.final_urls else ""

            ad_type_raw = str(ad.type_)
            # Handle both int enums and string enums
            ad_type_map = {
                "2": "EXPANDED_TEXT_AD",
                "3": "RESPONSIVE_SEARCH_AD",
                "15": "RESPONSIVE_SEARCH_AD",
            }
            # Clean up "AdType.DEMAND_GEN_..." style strings
            if "DEMAND_GEN" in ad_type_raw:
                ad_type = ad_type_raw.replace("AdType.", "")
            elif "RESPONSIVE_SEARCH" in ad_type_raw:
                ad_type = "RESPONSIVE_SEARCH_AD"
            else:
                ad_type = ad_type_map.get(ad_type_raw, ad_type_raw.replace("AdType.", ""))

            rows.append({
                "data_date": target_date,
                "campaign_id": row.campaign.id,
                "campaign_name": row.campaign.name,
                "ad_group_id": row.ad_group.id,
                "ad_group_name": row.ad_group.name,
                "ad_id": ad.id,
                "ad_type": ad_type,
                "campaign_type": campaign_type,
                "headline_1": headlines[0] if len(headlines) > 0 else "",
                "headline_2": headlines[1] if len(headlines) > 1 else "",
                "headline_3": headlines[2] if len(headlines) > 2 else "",
                "description_1": descriptions[0] if len(descriptions) > 0 else "",
                "description_2": descriptions[1] if len(descriptions) > 1 else "",
                "final_url": final_url,
                "image_url": image_url,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost_micros": row.metrics.cost_micros,
                "conversions": row.metrics.conversions,
                "conversion_value": row.metrics.conversions_value or 0.0,
                "ctr": row.metrics.ctr or 0.0,
                "avg_cpc_micros": row.metrics.average_cpc or 0,
            })

    except GoogleAdsException as ex:
        logger.error(f"Google Ads ad_group_ad error: {ex.failure.errors[0].message}")
    except Exception as e:
        logger.error(f"Google Ads ad_group_ad fetch failed for {target_date}: {e}")

    # ── Performance Max (asset groups) ─────────────────────────
    pmax_query = f"""
        SELECT
            campaign.id,
            campaign.name,
            asset_group.id,
            asset_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM asset_group
        WHERE segments.date = '{date_str}'
          AND asset_group.status = 'ENABLED'
          AND campaign.advertising_channel_type = 'PERFORMANCE_MAX'
          AND metrics.impressions > 0
    """

    try:
        response = ga_service.search(customer_id=customer_id, query=pmax_query)

        for row in response:
            imp = row.metrics.impressions
            clicks = row.metrics.clicks
            ctr = clicks / imp if imp > 0 else 0.0
            avg_cpc = row.metrics.cost_micros // clicks if clicks > 0 else 0

            rows.append({
                "data_date": target_date,
                "campaign_id": row.campaign.id,
                "campaign_name": row.campaign.name,
                "ad_group_id": row.asset_group.id,
                "ad_group_name": row.asset_group.name,
                "ad_id": row.asset_group.id,
                "ad_type": "PERFORMANCE_MAX_ASSET_GROUP",
                "campaign_type": "PERFORMANCE_MAX",
                "headline_1": row.asset_group.name,
                "headline_2": "",
                "headline_3": "",
                "description_1": "",
                "description_2": "",
                "final_url": "",
                "image_url": None,
                "impressions": imp,
                "clicks": clicks,
                "cost_micros": row.metrics.cost_micros,
                "conversions": row.metrics.conversions,
                "conversion_value": row.metrics.conversions_value or 0.0,
                "ctr": round(ctr, 4),
                "avg_cpc_micros": avg_cpc,
            })

    except GoogleAdsException as ex:
        logger.error(f"Google Ads PMax error: {ex.failure.errors[0].message}")
    except Exception as e:
        logger.error(f"Google Ads PMax fetch failed for {target_date}: {e}")

    return rows

"""Serper.dev SERP API — discover competitor paid ads on our keywords.

Credits are one-time (2,500 total). This service:
- Only queries keywords not seen in the last SERPER_REFRESH_DAYS (default 90)
- Caps each sweep at SERPER_MAX_KEYWORDS_PER_SWEEP (default 200)
- Logs every credit spent to serper_credit_log
- Caches raw results in serp_cache
"""
import json
import logging
from datetime import date, timedelta
from typing import Optional
from urllib.parse import urlparse

import requests
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from config import app_settings
from models.db import SerpCache, PaidKeywordObservation, OrganicSerpResult, SerperCreditLog

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"


def _get_top_gsc_keywords(db: Session, limit: int) -> list[str]:
    """Pull top keywords by impressions from organic_performance."""
    from models.db import OrganicPerformance

    rows = (
        db.query(
            OrganicPerformance.query,
            sqlfunc.sum(OrganicPerformance.impressions).label("total_imp"),
        )
        .group_by(OrganicPerformance.query)
        .order_by(sqlfunc.sum(OrganicPerformance.impressions).desc())
        .limit(limit)
        .all()
    )
    return [r.query for r in rows]


def _keywords_needing_refresh(db: Session, keywords: list[str]) -> list[str]:
    """Filter to keywords not queried within SERPER_REFRESH_DAYS."""
    cutoff = date.today() - timedelta(days=app_settings.SERPER_REFRESH_DAYS)

    recent = (
        db.query(SerpCache.keyword)
        .filter(
            SerpCache.keyword.in_(keywords),
            SerpCache.queried_date >= cutoff,
        )
        .all()
    )
    recently_queried = {r.keyword for r in recent}
    return [kw for kw in keywords if kw not in recently_queried]


def _credits_used_total(db: Session) -> int:
    """Total Serper credits consumed all-time."""
    result = db.query(sqlfunc.sum(SerperCreditLog.credits_used)).scalar()
    return result or 0


def _query_serper(keyword: str) -> Optional[dict]:
    """Make a single Serper API call."""
    if not app_settings.SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set, skipping")
        return None

    headers = {
        "X-API-KEY": app_settings.SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q": keyword,
        "gl": "us",
        "hl": "en",
        "num": 10,
    }

    try:
        resp = requests.post(SERPER_URL, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Serper API error for '{keyword}': {e}")
        return None


def _extract_paid_ads(keyword: str, serp_data: dict, today: date) -> list[dict]:
    """Extract paid ad observations from Serper response."""
    observations = []
    ads = serp_data.get("ads", [])

    for i, ad in enumerate(ads):
        link = ad.get("link", "")
        domain = ""
        if link:
            parsed = urlparse(link)
            domain = parsed.netloc.replace("www.", "")

        observations.append({
            "observed_date": today,
            "keyword": keyword,
            "advertiser_domain": domain,
            "ad_position": i + 1,
            "ad_title": ad.get("title", ""),
            "ad_description": ad.get("snippet", ""),
            "ad_display_url": ad.get("displayLink", ad.get("displayed_link", "")),
            "ad_destination_url": link,
        })

    return observations


def _extract_organic_results(keyword: str, serp_data: dict, today: date) -> list[dict]:
    """Extract organic ranking results from Serper response."""
    results = []
    organic = serp_data.get("organic", [])

    for item in organic:
        link = item.get("link", "")
        domain = ""
        if link:
            parsed = urlparse(link)
            domain = parsed.netloc.replace("www.", "")

        if domain:
            results.append({
                "observed_date": today,
                "keyword": keyword,
                "domain": domain,
                "position": item.get("position", 0),
                "title": item.get("title", ""),
                "url": link,
            })

    return results


def backfill_organic_from_cache(db: Session) -> dict:
    """Extract organic results from existing serp_cache entries.
    Call once to populate organic_serp_results from already-cached SERP data.
    """
    from sqlalchemy import text
    rows = db.execute(text(
        "SELECT keyword, queried_date, result_json FROM serp_cache WHERE result_json IS NOT NULL"
    )).fetchall()

    total = 0
    for keyword, queried_date, result_json in rows:
        try:
            serp_data = json.loads(result_json)
        except (json.JSONDecodeError, TypeError):
            continue
        organic = _extract_organic_results(keyword, serp_data, queried_date)
        for org in organic:
            db.add(OrganicSerpResult(**org))
            total += 1

    db.commit()
    return {"backfilled": total}


def run_serper_sweep(db: Session) -> dict:
    """Run a keyword sweep using Serper API.

    Returns summary of credits used and observations found.
    """
    total_credits_used = _credits_used_total(db)
    remaining = 2500 - total_credits_used

    if remaining <= 0:
        return {
            "status": "no_credits",
            "message": "All 2,500 Serper credits have been used",
            "credits_remaining": 0,
        }

    # Get top keywords from GSC data
    max_kw = min(app_settings.SERPER_MAX_KEYWORDS_PER_SWEEP, remaining)
    top_keywords = _get_top_gsc_keywords(db, limit=max_kw * 2)

    if not top_keywords:
        return {
            "status": "no_keywords",
            "message": "No GSC keywords found. Run GSC ingest first.",
        }

    # Filter to those needing refresh
    keywords_to_query = _keywords_needing_refresh(db, top_keywords)[:max_kw]

    if not keywords_to_query:
        return {
            "status": "all_cached",
            "message": f"All top keywords were queried within the last {app_settings.SERPER_REFRESH_DAYS} days",
            "credits_remaining": remaining,
        }

    today = date.today()
    credits_spent = 0
    total_ads_found = 0
    observations = []

    for keyword in keywords_to_query:
        serp_data = _query_serper(keyword)
        if serp_data is None:
            continue

        credits_spent += 1

        # Cache the raw result
        db.add(SerpCache(
            keyword=keyword,
            queried_date=today,
            result_json=json.dumps(serp_data),
            credits_used=1,
        ))

        # Extract paid ad observations
        ads = _extract_paid_ads(keyword, serp_data, today)
        for ad_dict in ads:
            db.add(PaidKeywordObservation(**ad_dict))
            total_ads_found += 1

        observations.extend(ads)

        # Extract organic results
        organic = _extract_organic_results(keyword, serp_data, today)
        for org in organic:
            db.add(OrganicSerpResult(**org))

    # Log credit usage
    db.add(SerperCreditLog(
        action="keyword_sweep",
        credits_used=credits_spent,
        keywords_queried=len(keywords_to_query),
        notes=f"Queried {credits_spent} keywords, found {total_ads_found} paid ads",
    ))

    db.commit()

    return {
        "status": "completed",
        "credits_spent": credits_spent,
        "credits_remaining": remaining - credits_spent,
        "keywords_queried": credits_spent,
        "paid_ads_found": total_ads_found,
        "unique_advertisers": len({o["advertiser_domain"] for o in observations if o["advertiser_domain"]}),
    }

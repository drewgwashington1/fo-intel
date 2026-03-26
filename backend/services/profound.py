"""Real Profound API service — AI visibility, citations, and competitor data.

Pulls from Profound's REST API and returns data matching the DB model shapes
so the ingest router stays clean.
"""
import logging
from datetime import date, timedelta
from typing import List

import requests

from config import app_settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.tryprofound.com"


def _headers():
    return {
        "X-API-Key": app_settings.PROFOUND_API_KEY,
        "Content-Type": "application/json",
    }


def _post(endpoint: str, body: dict) -> dict:
    """Make a POST request to Profound API."""
    resp = requests.post(
        f"{API_BASE}{endpoint}",
        headers=_headers(),
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_ai_visibility(target_date: date) -> List[dict]:
    """Fetch AI visibility scores by platform for a single day.

    Returns list of dicts matching the AIVisibility model.
    """
    start_str = target_date.isoformat()
    end_str = (target_date + timedelta(days=1)).isoformat()
    category_id = app_settings.PROFOUND_CATEGORY_ID

    try:
        result = _post("/v1/reports/visibility", {
            "category_id": category_id,
            "start_date": start_str,
            "end_date": end_str,
            "metrics": ["visibility_score", "share_of_voice"],
            "dimensions": ["asset_name", "model"],
            "filters": [
                {"field": "asset_name", "operator": "is", "value": "First Orion"}
            ],
        })

        rows = []
        for item in result.get("data", []):
            metrics = item.get("metrics", [0, 0])
            dims = item.get("dimensions", ["", ""])
            asset_name = dims[0] if len(dims) > 0 else ""
            platform = dims[1] if len(dims) > 1 else ""
            sov = metrics[0] if len(metrics) > 0 else 0
            vis = metrics[1] if len(metrics) > 1 else 0

            rows.append({
                "data_date": target_date,
                "category_id": category_id,
                "category_name": "Technical Services",
                "platform": platform,
                "visibility_score": round(vis * 100, 1) if vis <= 1 else round(vis, 1),
                "share_of_voice": round(sov, 4),
                "citation_count": 0,
                "average_position": 0.0,
            })

        return rows

    except Exception as e:
        logger.error(f"Profound visibility fetch failed for {target_date}: {e}")
        return []


def fetch_ai_citations(target_date: date) -> List[dict]:
    """Fetch citation data for a single day.

    Returns list of dicts matching the AICitation model.
    """
    start_str = target_date.isoformat()
    end_str = (target_date + timedelta(days=1)).isoformat()
    category_id = app_settings.PROFOUND_CATEGORY_ID

    try:
        result = _post("/v1/reports/citations", {
            "category_id": category_id,
            "start_date": start_str,
            "end_date": end_str,
            "metrics": ["count"],
            "dimensions": ["hostname"],
            "pagination": {"limit": 50},
        })

        rows = []
        for item in result.get("data", []):
            metrics = item.get("metrics", [0])
            dims = item.get("dimensions", [""])
            hostname = dims[0] if len(dims) > 0 else ""
            count = metrics[0] if len(metrics) > 0 else 0

            # Only include firstorion.com citations
            if count > 0 and "firstorion" in hostname:
                for _ in range(min(count, 20)):
                    rows.append({
                        "data_date": target_date,
                        "prompt": "",
                        "platform": "",
                        "cited_url": f"https://{hostname}/",
                        "citation_type": "DIRECT",
                        "sentiment": "POSITIVE",
                    })

        return rows

    except Exception as e:
        logger.error(f"Profound citations fetch failed for {target_date}: {e}")
        return []


def fetch_ai_competitors(target_date: date) -> List[dict]:
    """Fetch competitor visibility data for a single day.

    Returns list of dicts matching the AICompetitor model.
    """
    start_str = target_date.isoformat()
    end_str = (target_date + timedelta(days=1)).isoformat()
    category_id = app_settings.PROFOUND_CATEGORY_ID

    competitor_domains = [d.strip() for d in app_settings.COMPETITOR_DOMAINS.split(",")]

    try:
        # Get visibility for all assets (companies) across all models
        result = _post("/v1/reports/visibility", {
            "category_id": category_id,
            "start_date": start_str,
            "end_date": end_str,
            "metrics": ["visibility_score", "share_of_voice"],
            "dimensions": ["asset_name", "model"],
        })

        rows = []
        for item in result.get("data", []):
            metrics = item.get("metrics", [0, 0])
            dims = item.get("dimensions", ["", ""])
            asset_name = dims[0] if len(dims) > 0 else ""
            platform = dims[1] if len(dims) > 1 else ""
            sov = metrics[0] if len(metrics) > 0 else 0

            # Skip First Orion (that's us, not a competitor)
            if "first orion" in asset_name.lower():
                continue

            # Try to map asset name to domain
            domain = _asset_to_domain(asset_name, competitor_domains)
            if not domain:
                domain = asset_name.lower().replace(" ", "") + ".com"

            rows.append({
                "data_date": target_date,
                "category_name": "Technical Services",
                "platform": platform,
                "competitor_domain": domain,
                "share_of_voice": round(sov, 4),
                "citation_count": 0,
            })

        # Also get citation counts per competitor hostname
        cit_result = _post("/v1/reports/citations", {
            "category_id": category_id,
            "start_date": start_str,
            "end_date": end_str,
            "metrics": ["count"],
            "dimensions": ["hostname"],
            "pagination": {"limit": 50},
        })

        citation_map = {}
        for item in cit_result.get("data", []):
            hostname = item["dimensions"][0] if item.get("dimensions") else ""
            count = item["metrics"][0] if item.get("metrics") else 0
            # Normalize hostname
            hostname = hostname.replace("www.", "")
            if hostname in competitor_domains:
                citation_map[hostname] = citation_map.get(hostname, 0) + count

        # Enrich competitor rows with citation counts
        for row in rows:
            domain = row["competitor_domain"].replace("www.", "")
            row["citation_count"] = citation_map.get(domain, 0)

        return rows

    except Exception as e:
        logger.error(f"Profound competitors fetch failed for {target_date}: {e}")
        return []


def _asset_to_domain(asset_name: str, domains: list) -> str:
    """Try to match an asset name to a known competitor domain."""
    name_lower = asset_name.lower()
    mapping = {
        "hiya": "hiya.com",
        "numeracle": "numeracle.com",
        "transunion": "transunion.com",
        "trans union": "transunion.com",
        "free caller": "freecallerregistry.com",
        "tnsi": "tnsi.com",
        "tns": "tnsi.com",
        "transaction network": "tnsi.com",
    }
    for key, domain in mapping.items():
        if key in name_lower:
            return domain
    return ""

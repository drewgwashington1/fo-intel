"""Methodology Scraper — fetches source documentation every 30 days and flags changes.

Sources:
  - Ahrefs Opportunities Report
  - Ahrefs Low-Hanging Fruit SEO
  - Google Ads API Recommendations
  - Clearscope Striking Distance Keywords

When content changes are detected, they are logged to pending_changes in the
methodology config so a human can review and update thresholds if needed.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "insights_methodology.json"


def _fetch_page_text(url: str, timeout: int = 15) -> str | None:
    """Fetch a URL and return its text content."""
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "FO-Intel-Methodology-Scraper/1.0"
        })
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def _hash_content(content: str) -> str:
    """SHA-256 hash of content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def refresh_methodology() -> dict:
    """Fetch all methodology source pages, compare hashes, flag changes.

    Returns a summary dict with results per source.
    """
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    meta = config["_meta"]
    results = []
    changes_detected = []

    for source in meta["sources"]:
        url = source["url"]
        name = source["name"]
        old_hash = source.get("content_hash")

        content = _fetch_page_text(url)
        if content is None:
            results.append({
                "source": name,
                "url": url,
                "status": "fetch_failed",
                "changed": False,
            })
            continue

        new_hash = _hash_content(content)
        changed = old_hash is not None and new_hash != old_hash
        first_fetch = old_hash is None

        # Update the source record
        source["content_hash"] = new_hash
        source["last_fetched"] = date.today().isoformat()

        if changed:
            change_entry = {
                "date": date.today().isoformat(),
                "source": name,
                "url": url,
                "message": f"Content changed since last fetch. Review source for updated thresholds or methodology.",
                "old_hash": old_hash,
                "new_hash": new_hash,
            }
            changes_detected.append(change_entry)
            logger.info(f"METHODOLOGY CHANGE DETECTED: {name} — {url}")

        results.append({
            "source": name,
            "url": url,
            "status": "first_fetch" if first_fetch else ("changed" if changed else "unchanged"),
            "changed": changed,
            "hash": new_hash,
        })

    # Append new changes to pending_changes (don't overwrite existing ones)
    meta["pending_changes"].extend(changes_detected)
    meta["last_refreshed"] = date.today().isoformat()

    # Write updated config
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    total_changed = sum(1 for r in results if r["changed"])
    total_fetched = sum(1 for r in results if r["status"] != "fetch_failed")

    return {
        "sources_checked": len(results),
        "sources_fetched": total_fetched,
        "changes_detected": total_changed,
        "results": results,
        "pending_review": len(meta["pending_changes"]),
    }


def get_pending_changes() -> list:
    """Return list of pending methodology changes awaiting review."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    return config["_meta"]["pending_changes"]


def dismiss_change(index: int) -> bool:
    """Dismiss a pending change by index after review."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    changes = config["_meta"]["pending_changes"]
    if 0 <= index < len(changes):
        changes.pop(index)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        return True
    return False


def dismiss_all_changes() -> int:
    """Dismiss all pending changes. Returns count dismissed."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    count = len(config["_meta"]["pending_changes"])
    config["_meta"]["pending_changes"] = []

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    return count

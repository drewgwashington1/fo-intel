"""Google Ads Transparency Center scraper — real competitor ad data.

Uses the public Transparency Center RPC endpoints to fetch competitor ad
creatives. No API key needed — this is public data.
"""
import datetime
import hashlib
import json
import logging
from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import app_settings

logger = logging.getLogger(__name__)

HEADERS = {
    "authority": "adstransparency.google.com",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Known advertiser name → ID mappings (discovered via search)
ADVERTISER_SEARCH_NAMES = {
    "hiya.com": "Hiya Inc",
    "numeracle.com": "Numeracle",
    "transunion.com": "TransUnion",
    "freecallerregistry.com": "Free Caller Registry",
    "tnsi.com": "Transaction Network Services",
    "firstorion.com": "First Orion",
}


class TransparencyScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # Initialize cookies
        try:
            self.session.get("https://adstransparency.google.com/", timeout=10)
        except requests.RequestException:
            logger.warning("Could not initialize Transparency Center session")

    def _search_advertiser(self, name: str) -> Optional[dict]:
        """Search for an advertiser and return their ID and name."""
        data = {
            "f.req": json.dumps({"1": name, "2": 10, "3": 10}),
        }
        try:
            resp = self.session.post(
                "https://adstransparency.google.com/anji/_/rpc/SearchService/SearchSuggestions",
                params={"authuser": "0"},
                data=data,
                timeout=15,
            )
            result = resp.json()
            if result and "1" in result:
                suggestions = result["1"]
                if suggestions:
                    first = suggestions[0]
                    # Response is nested: {"1": {"1": name, "2": id, ...}}
                    inner = first.get("1", {})
                    if isinstance(inner, dict):
                        return {
                            "advertiser_name": inner.get("1", name),
                            "advertiser_id": inner.get("2", ""),
                        }
                    else:
                        return {
                            "advertiser_name": name,
                            "advertiser_id": first.get("2", ""),
                        }
        except Exception as e:
            logger.error(f"Advertiser search failed for '{name}': {e}")
        return None

    def _get_creative_ids(self, advertiser_id: str, count: int = 50) -> list[str]:
        """Get creative IDs for an advertiser."""
        data = {
            "f.req": json.dumps({
                "2": min(count, 100),
                "3": {"12": {"1": "", "2": True}, "13": {"1": [advertiser_id]}},
                "7": {"1": 1},
            }),
        }
        try:
            resp = self.session.post(
                "https://adstransparency.google.com/anji/_/rpc/SearchService/SearchCreatives",
                params={"authuser": ""},
                data=data,
                timeout=15,
            )
            result = resp.json()
            creatives = result.get("1", [])
            return [c["2"] for c in creatives if "2" in c]
        except Exception as e:
            logger.error(f"Creative search failed for {advertiser_id}: {e}")
            return []

    @staticmethod
    def _parse_yyyymmdd(val: int) -> Optional[date]:
        """Parse a YYYYMMDD integer into a date."""
        try:
            s = str(val)
            if len(s) == 8:
                return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except (ValueError, TypeError):
            pass
        return None

    def _get_creative_detail(self, advertiser_id: str, creative_id: str) -> Optional[dict]:
        """Get details of a single ad creative."""
        data = {
            "f.req": json.dumps({
                "1": advertiser_id,
                "2": creative_id,
                "5": {"1": 1},
            }),
        }
        try:
            resp = self.session.post(
                "https://adstransparency.google.com/anji/_/rpc/LookupService/GetCreativeById",
                params={"authuser": "0"},
                data=data,
                timeout=15,
            )
            result = resp.json().get("1", {})
            if not result:
                return None

            # Detect actual format from content, not just the "8" field
            content_items = result.get("5", [])
            has_img = False
            has_video = False
            ad_link = ""
            image_url = ""

            if content_items and isinstance(content_items, list):
                first_content = content_items[0]
                html_content = ""
                # Try to get HTML/content from various paths
                if "3" in first_content:
                    html_content = first_content["3"].get("2", "")
                elif "1" in first_content:
                    html_content = first_content["1"].get("4", "")

                if "<img" in html_content:
                    has_img = True
                    soup = BeautifulSoup(html_content, "html.parser")
                    img_tag = soup.find("img")
                    if img_tag:
                        image_url = img_tag.get("src", "")
                elif "googlevideo" in html_content:
                    has_video = True
                    ad_link = html_content

                # Try to extract link for text ads
                if not has_img and not has_video:
                    try:
                        ad_link = html_content.split("'")[1] if "'" in html_content else html_content
                    except (IndexError, TypeError):
                        pass

            if has_video:
                ad_format = "VIDEO"
            elif has_img:
                ad_format = "IMAGE"
            else:
                ad_format = "TEXT"

            # Parse dates from "19" (overall) or "17" (per-region)
            first_shown = None
            last_shown = None

            overall = result.get("19", {})
            if overall:
                first_shown = self._parse_yyyymmdd(overall.get("4"))
                last_shown = self._parse_yyyymmdd(overall.get("5"))

            if not first_shown:
                # Fallback: use Unix timestamp from "4"
                date_info = result.get("4", {})
                if "1" in date_info:
                    try:
                        ts = int(date_info["1"])
                        if ts > 1000000000:  # sanity check
                            first_shown = datetime.datetime.fromtimestamp(ts).date()
                    except (ValueError, OSError):
                        pass

            # Parse headline and description from text ads
            headline = ""
            description = ""
            if ad_format == "TEXT" and ad_link and ad_link.startswith("http"):
                try:
                    ad_resp = self.session.get(ad_link, timeout=10)
                    soup = BeautifulSoup(ad_resp.text, "html.parser")
                    title_el = soup.find("div", {"aria-level": "3"})
                    if title_el:
                        headline = title_el.get_text(strip=True)
                    body_el = soup.find("div", {"data-highlight-id-inside": "36"})
                    if body_el:
                        description = body_el.get_text(strip=True)
                except Exception:
                    pass

            # Get advertiser name from response
            adv_name = ""
            if "22" in result:
                adv_name = result["22"].get("1", "")

            # Parse platforms from region data
            platforms = set()
            for region_entry in result.get("17", []):
                for format_entry in region_entry.get("8", []):
                    fmt_id = format_entry.get("1", 0)
                    fmt_map = {1: "Search", 2: "YouTube", 3: "Display", 4: "Maps", 5: "Shopping"}
                    if fmt_id in fmt_map:
                        platforms.add(fmt_map[fmt_id])

            if not platforms:
                platforms = {"Search"}

            return {
                "creative_id": creative_id,
                "ad_format": ad_format,
                "headline": headline or (adv_name + " Ad" if adv_name else ""),
                "description": description,
                "first_shown_date": first_shown,
                "last_shown_date": last_shown,
                "ad_link": ad_link or image_url,
                "platforms": list(platforms),
                "advertiser_name_from_ad": adv_name,
            }

        except Exception as e:
            logger.debug(f"Creative detail failed for {creative_id}: {e}")
            return None

    def scrape_competitor(self, domain: str, max_ads: int = 30) -> list[dict]:
        """Scrape ads for a competitor domain.

        Returns list of dicts matching the CompetitorAd model shape.
        """
        search_name = ADVERTISER_SEARCH_NAMES.get(domain, domain)
        advertiser = self._search_advertiser(search_name)

        if not advertiser or not advertiser["advertiser_id"]:
            logger.warning(f"No advertiser found for {domain} (searched '{search_name}')")
            return []

        adv_id = advertiser["advertiser_id"]
        adv_name = advertiser["advertiser_name"]
        creative_ids = self._get_creative_ids(adv_id, max_ads)

        if not creative_ids:
            logger.info(f"No creatives found for {domain}")
            return []

        today = date.today()
        ads = []

        for cid in creative_ids:
            detail = self._get_creative_detail(adv_id, cid)
            if not detail:
                continue

            first_shown = detail["first_shown_date"] or today
            last_shown = detail["last_shown_date"]
            days_running = (today - first_shown).days if first_shown else 0

            # Use advertiser name from ad detail if available
            ad_adv_name = detail.get("advertiser_name_from_ad") or adv_name

            ad_id = hashlib.md5(f"{domain}:{cid}".encode()).hexdigest()

            ads.append({
                "ad_id": ad_id,
                "scraped_date": today,
                "competitor_domain": domain,
                "advertiser_name": ad_adv_name,
                "ad_format": detail["ad_format"],
                "headline": detail["headline"] or f"{ad_adv_name} Ad",
                "description": detail["description"] or "",
                "destination_url": detail["ad_link"],
                "platforms": detail["platforms"],
                "regions": ["US"],
                "first_shown_date": first_shown,
                "last_shown_date": last_shown,
                "days_running": max(days_running, 0),
                "is_active": last_shown is None or last_shown >= today - datetime.timedelta(days=7),
            })

        logger.info(f"Scraped {len(ads)} ads for {domain}")
        return ads


def fetch_all_competitor_ads() -> list[dict]:
    """Scrape ads for all configured competitor domains + firstorion.com."""
    domains = [d.strip() for d in app_settings.COMPETITOR_DOMAINS.split(",")]
    domains.append("firstorion.com")

    scraper = TransparencyScraper()
    all_ads = []

    for domain in domains:
        try:
            ads = scraper.scrape_competitor(domain, max_ads=30)
            all_ads.extend(ads)
        except Exception as e:
            logger.error(f"Failed to scrape {domain}: {e}")

    return all_ads

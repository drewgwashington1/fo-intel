"""Real Google Search Console data fetcher.

Uses a service account to pull Search Analytics data from the GSC API.
Returns data in the same shape as mock_gsc.generate_gsc_data() so the
ingest router doesn't need to change.
"""
from datetime import date
from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import app_settings

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

_service = None


def _get_service():
    global _service
    if _service is None:
        creds = service_account.Credentials.from_service_account_file(
            app_settings.GSC_CREDENTIALS_PATH,
            scopes=SCOPES,
        )
        _service = build("searchconsole", "v1", credentials=creds)
    return _service


def fetch_gsc_data(target_date: date) -> list[dict]:
    """Fetch one day of GSC data for the configured site.

    Returns list of dicts matching the OrganicPerformance model fields.
    """
    service = _get_service()

    date_str = target_date.isoformat()

    request_body = {
        "startDate": date_str,
        "endDate": date_str,
        "dimensions": ["query", "page", "country", "device"],
        "rowLimit": 5000,
        "startRow": 0,
    }

    rows = []
    start_row = 0

    while True:
        request_body["startRow"] = start_row

        response = (
            service.searchanalytics()
            .query(siteUrl=app_settings.GSC_SITE_URL, body=request_body)
            .execute()
        )

        api_rows = response.get("rows", [])
        if not api_rows:
            break

        for row in api_rows:
            keys = row["keys"]
            rows.append(
                {
                    "data_date": target_date,
                    "site_url": f"https://firstorion.com/",
                    "query": keys[0],
                    "page": keys[1],
                    "country": keys[2].upper(),
                    "device": keys[3].upper(),
                    "clicks": int(row["clicks"]),
                    "impressions": int(row["impressions"]),
                    "ctr": round(row["ctr"], 4),
                    "position": round(row["position"], 1),
                }
            )

        if len(api_rows) < 5000:
            break
        start_row += 5000

    return rows

"""Google Ads API client.

Provides authenticated client for Keyword Planner and other Google Ads services.
"""
import logging

from google.ads.googleads.client import GoogleAdsClient

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

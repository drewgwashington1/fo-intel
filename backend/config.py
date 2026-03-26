from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://fointel:fointel@127.0.0.1:5434/fo_intel"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    ENVIRONMENT: str = "development"

    # Google Search Console
    GSC_CREDENTIALS_PATH: str = "credentials/gsc-service-account.json"
    GSC_SITE_URL: str = "sc-domain:firstorion.com"
    USE_MOCK_GSC: bool = False

    # Serper (SERP scraping — 2,500 one-time credits)
    SERPER_API_KEY: str = ""
    SERPER_REFRESH_DAYS: int = 90
    SERPER_MAX_KEYWORDS_PER_SWEEP: int = 200

    # Profound API (AI Visibility)
    PROFOUND_API_KEY: str = ""
    PROFOUND_CATEGORY_ID: str = ""
    USE_MOCK_PROFOUND: bool = True

    # Google Ads (for Keyword Planner + future direct Ads connection)
    GOOGLE_ADS_DEVELOPER_TOKEN: str = ""
    GOOGLE_ADS_CLIENT_ID: str = ""
    GOOGLE_ADS_CLIENT_SECRET: str = ""
    GOOGLE_ADS_REFRESH_TOKEN: str = ""
    GOOGLE_ADS_CUSTOMER_ID: str = ""
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = ""
    USE_MOCK_ADS: bool = True

    # Competitor Ads
    USE_MOCK_TRANSPARENCY: bool = False
    COMPETITOR_DOMAINS: str = "hiya.com,numeracle.com,transunion.com,freecallerregistry.com,tnsi.com"

    class Config:
        env_file = ".env"


app_settings = Settings()

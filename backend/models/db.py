from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Date, Boolean, DateTime, ARRAY,
    Text, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base


class OrganicPerformance(Base):
    __tablename__ = "organic_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_date = Column(Date, nullable=False)
    site_url = Column(String)
    query = Column(String)
    page = Column(String)
    country = Column(String)
    device = Column(String)
    clicks = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)
    position = Column(Float, default=0.0)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_organic_date_query", "data_date", "query"),
        Index("ix_organic_date_page", "data_date", "page"),
    )


class CompetitorAd(Base):
    __tablename__ = "competitor_ads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String, unique=True)
    scraped_date = Column(Date, nullable=False)
    competitor_domain = Column(String)
    advertiser_name = Column(String)
    ad_format = Column(String)
    headline = Column(String)
    description = Column(String)
    destination_url = Column(String)
    platforms = Column(ARRAY(String))
    regions = Column(ARRAY(String))
    first_shown_date = Column(Date)
    last_shown_date = Column(Date, nullable=True)
    days_running = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    image_url = Column(String, nullable=True)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_comp_ads_domain", "competitor_domain"),
        Index("ix_comp_ads_scraped", "scraped_date"),
    )


class KeywordList(Base):
    """User-defined keyword lists for filtering.
    list_name = tag (custom grouping like 'product', 'support')
    category  = branded / non-branded (binary classification, separate from tag)
    """
    __tablename__ = "keyword_lists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    list_name = Column(String, nullable=False)  # tag name, e.g. "product"
    term = Column(String, nullable=False)
    category = Column(String, nullable=False, server_default="non-branded")  # "branded" or "non-branded"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_keyword_lists_name", "list_name"),
        Index("ix_keyword_lists_category", "category"),
    )


class KeywordMetrics(Base):
    """Keyword Planner data — search volume, CPC, competition per keyword."""
    __tablename__ = "keyword_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, nullable=False, unique=True)
    avg_monthly_searches = Column(Integer, default=0)
    competition = Column(String)  # LOW, MEDIUM, HIGH
    competition_index = Column(Float, default=0)  # 0-100
    low_cpc_micros = Column(BigInteger, default=0)
    high_cpc_micros = Column(BigInteger, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_kw_metrics_keyword", "keyword"),
        Index("ix_kw_metrics_volume", "avg_monthly_searches"),
    )


class KeywordIdea(Base):
    """Related keyword suggestions from Keyword Planner."""
    __tablename__ = "keyword_ideas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seed_keyword = Column(String, nullable=False)
    suggested_keyword = Column(String, nullable=False)
    avg_monthly_searches = Column(Integer, default=0)
    competition = Column(String)
    competition_index = Column(Float, default=0)
    low_cpc_micros = Column(BigInteger, default=0)
    high_cpc_micros = Column(BigInteger, default=0)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_kw_ideas_seed", "seed_keyword"),
        Index("ix_kw_ideas_suggested", "suggested_keyword"),
    )


class SerpCache(Base):
    """Cache SERP results per keyword to avoid burning Serper credits."""
    __tablename__ = "serp_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, nullable=False)
    queried_date = Column(Date, nullable=False)
    result_json = Column(Text)
    credits_used = Column(Integer, default=1)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_serp_cache_keyword", "keyword"),
        Index("ix_serp_cache_date", "queried_date"),
    )


class PaidKeywordObservation(Base):
    """Competitor paid keyword observations from SERP data."""
    __tablename__ = "paid_keyword_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    observed_date = Column(Date, nullable=False)
    keyword = Column(String, nullable=False)
    advertiser_domain = Column(String, nullable=False)
    ad_position = Column(Integer)
    ad_title = Column(String)
    ad_description = Column(String)
    ad_display_url = Column(String)
    ad_destination_url = Column(String)
    estimated_volume = Column(Integer)
    estimated_cpc = Column(Float)
    competition_level = Column(String)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_paid_kw_obs_keyword", "keyword"),
        Index("ix_paid_kw_obs_domain", "advertiser_domain"),
        Index("ix_paid_kw_obs_date", "observed_date"),
    )


class OrganicSerpResult(Base):
    """Organic SERP results extracted from Serper — who ranks for our keywords."""
    __tablename__ = "organic_serp_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    observed_date = Column(Date, nullable=False)
    keyword = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    position = Column(Integer, nullable=False)
    title = Column(String)
    url = Column(String)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_org_serp_keyword", "keyword"),
        Index("ix_org_serp_domain", "domain"),
        Index("ix_org_serp_date", "observed_date"),
    )


class SerperCreditLog(Base):
    """Track Serper API credit usage."""
    __tablename__ = "serper_credit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String, nullable=False)
    credits_used = Column(Integer, nullable=False)
    keywords_queried = Column(Integer, default=0)
    notes = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TrackedCompetitor(Base):
    """Competitor domains to track across all pipelines."""
    __tablename__ = "tracked_competitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String, nullable=False, unique=True)
    display_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KeywordQueryMap(Base):
    """Pre-computed mapping of keyword lists to matching organic queries."""
    __tablename__ = "keyword_query_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_list_name = Column(String, nullable=False)
    query = Column(String, nullable=False)
    matched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_kqm_list_name", "keyword_list_name"),
        Index("ix_kqm_list_query", "keyword_list_name", "query", unique=True),
    )


class SummaryCache(Base):
    """Pre-computed dashboard endpoint responses."""
    __tablename__ = "summary_cache"

    cache_key = Column(String, primary_key=True)
    response_json = Column(JSONB, nullable=False)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())
    stale_after = Column(DateTime(timezone=True), nullable=False)


class PipelineStatus(Base):
    """Track when each data pipeline last ran."""
    __tablename__ = "pipeline_status"

    pipeline_name = Column(String, primary_key=True)
    last_run_at = Column(DateTime(timezone=True), server_default=func.now())
    rows_processed = Column(Integer, default=0)


class AppUser(Base):
    """Application users for login."""
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

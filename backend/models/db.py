from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Date, Boolean, DateTime, ARRAY,
    Index,
)
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


class PaidPerformance(Base):
    __tablename__ = "paid_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_date = Column(Date, nullable=False)
    campaign_id = Column(BigInteger)
    campaign_name = Column(String)
    ad_group_id = Column(BigInteger)
    ad_group_name = Column(String)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost_micros = Column(BigInteger, default=0)
    avg_cpc_micros = Column(BigInteger, default=0)
    conversions = Column(Float, default=0.0)
    impression_share = Column(Float, default=0.0)
    lost_is_budget = Column(Float, default=0.0)
    lost_is_rank = Column(Float, default=0.0)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_paid_date_campaign", "data_date", "campaign_id"),
    )


class SearchTerm(Base):
    __tablename__ = "search_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_date = Column(Date, nullable=False)
    campaign_id = Column(BigInteger)
    search_term = Column(String)
    match_type = Column(String)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost_micros = Column(BigInteger, default=0)
    conversions = Column(Float, default=0.0)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_search_terms_date", "data_date"),
    )


class AIVisibility(Base):
    __tablename__ = "ai_visibility"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_date = Column(Date, nullable=False)
    category_id = Column(String)
    category_name = Column(String)
    platform = Column(String)
    visibility_score = Column(Float, default=0.0)
    share_of_voice = Column(Float, default=0.0)
    citation_count = Column(Integer, default=0)
    average_position = Column(Float, default=0.0)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_ai_vis_date_platform", "data_date", "platform"),
    )


class AICitation(Base):
    __tablename__ = "ai_citations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_date = Column(Date, nullable=False)
    prompt = Column(String)
    platform = Column(String)
    cited_url = Column(String)
    citation_type = Column(String)
    sentiment = Column(String)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_ai_citations_date", "data_date"),
    )


class AICompetitor(Base):
    __tablename__ = "ai_competitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_date = Column(Date, nullable=False)
    category_name = Column(String)
    platform = Column(String)
    competitor_domain = Column(String)
    share_of_voice = Column(Float, default=0.0)
    citation_count = Column(Integer, default=0)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_ai_comp_date", "data_date", "competitor_domain"),
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

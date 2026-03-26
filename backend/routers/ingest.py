"""Ingest pipeline triggers — real + mock data for all sources."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from config import app_settings
from database import get_db
from models.db import (
    OrganicPerformance, PaidPerformance, SearchTerm,
    AIVisibility, AICitation, AICompetitor, CompetitorAd,
)
from services.mock_gsc import generate_gsc_data
from services.gsc import fetch_gsc_data
from services.mock_ads import generate_paid_data, generate_search_terms_data
from services.google_ads import fetch_paid_data, fetch_search_terms_data
from services.mock_profound import (
    generate_ai_visibility, generate_ai_citations, generate_ai_competitors,
)
from services.profound import (
    fetch_ai_visibility, fetch_ai_citations, fetch_ai_competitors,
)
from services.mock_transparency import generate_competitor_ads
from services.transparency import fetch_all_competitor_ads
from services.serper import run_serper_sweep

router = APIRouter()


def _dates_with_data(db: Session, table_name: str, days: int) -> set[date]:
    today = date.today()
    start = today - timedelta(days=days)
    result = db.execute(
        text(f"SELECT DISTINCT data_date FROM {table_name} WHERE data_date >= :start"),
        {"start": start},
    )
    return {row[0] for row in result}


@router.post("/gsc")
def ingest_gsc(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    today = date.today()
    existing = _dates_with_data(db, "organic_performance", days)
    inserted = 0
    source = "mock" if app_settings.USE_MOCK_GSC else "gsc_api"

    for i in range(days):
        target = today - timedelta(days=i + 1)
        if target in existing:
            continue

        if app_settings.USE_MOCK_GSC:
            rows = generate_gsc_data(target)
        else:
            rows = fetch_gsc_data(target)

        for r in rows:
            db.add(OrganicPerformance(**r))
        inserted += len(rows)

    db.commit()
    return {"pipeline": "gsc", "source": source, "days": days, "rows_inserted": inserted}


@router.post("/ads")
def ingest_ads(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    today = date.today()
    existing_paid = _dates_with_data(db, "paid_performance", days)
    existing_terms = _dates_with_data(db, "search_terms", days)
    inserted = 0
    source = "mock" if app_settings.USE_MOCK_ADS else "google_ads_api"

    for i in range(days):
        target = today - timedelta(days=i + 1)
        if target not in existing_paid:
            if app_settings.USE_MOCK_ADS:
                rows = generate_paid_data(target)
            else:
                rows = fetch_paid_data(target)
            for r in rows:
                db.add(PaidPerformance(**r))
            inserted += len(rows)
        if target not in existing_terms:
            if app_settings.USE_MOCK_ADS:
                rows = generate_search_terms_data(target)
            else:
                rows = fetch_search_terms_data(target)
            for r in rows:
                db.add(SearchTerm(**r))
            inserted += len(rows)

    db.commit()
    return {"pipeline": "ads", "source": source, "days": days, "rows_inserted": inserted}


@router.post("/profound")
def ingest_profound(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    today = date.today()
    existing_vis = _dates_with_data(db, "ai_visibility", days)
    inserted = 0
    source = "mock" if app_settings.USE_MOCK_PROFOUND else "profound_api"

    for i in range(days):
        target = today - timedelta(days=i + 1)
        if target in existing_vis:
            continue

        if app_settings.USE_MOCK_PROFOUND:
            vis_rows = generate_ai_visibility(target)
            cit_rows = generate_ai_citations(target)
            comp_rows = generate_ai_competitors(target)
        else:
            vis_rows = fetch_ai_visibility(target)
            cit_rows = fetch_ai_citations(target)
            comp_rows = fetch_ai_competitors(target)

        for r in vis_rows:
            db.add(AIVisibility(**r))
        for r in cit_rows:
            db.add(AICitation(**r))
        for r in comp_rows:
            db.add(AICompetitor(**r))
        inserted += 1

    db.commit()
    return {"pipeline": "profound", "source": source, "days_processed": inserted}


@router.post("/transparency")
def ingest_transparency(db: Session = Depends(get_db)):
    """Scrape competitor ads from Google Ads Transparency Center.

    Uses real scraper when USE_MOCK_TRANSPARENCY=false, otherwise mock data.
    Upserts by ad_id to avoid duplicates.
    """
    today = date.today()

    if app_settings.USE_MOCK_TRANSPARENCY:
        rows = generate_competitor_ads(today)
        source = "mock"
    else:
        rows = fetch_all_competitor_ads()
        source = "transparency_center"

    inserted = 0
    updated = 0
    for r in rows:
        # Upsert: check if ad_id already exists
        existing = db.query(CompetitorAd).filter(CompetitorAd.ad_id == r["ad_id"]).first()
        if existing:
            # Update fields that may have changed
            existing.days_running = r.get("days_running", existing.days_running)
            existing.is_active = r.get("is_active", existing.is_active)
            existing.last_shown_date = r.get("last_shown_date", existing.last_shown_date)
            existing.scraped_date = today
            updated += 1
        else:
            db.add(CompetitorAd(**r))
            inserted += 1

    db.commit()
    return {
        "pipeline": "transparency",
        "source": source,
        "ads_inserted": inserted,
        "ads_updated": updated,
        "total_scraped": len(rows),
    }


@router.post("/serper-sweep")
def ingest_serper_sweep(db: Session = Depends(get_db)):
    """Run a Serper SERP sweep to discover competitor paid keywords.

    Only queries keywords not seen in the last 90 days (configurable).
    Uses one-time Serper credits conservatively.
    """
    result = run_serper_sweep(db)
    return {"pipeline": "serper_sweep", **result}

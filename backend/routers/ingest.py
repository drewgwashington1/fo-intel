"""Ingest pipeline triggers — generate mock data for all 4 sources."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from models.db import (
    OrganicPerformance, PaidPerformance, SearchTerm,
    AIVisibility, AICitation, AICompetitor, CompetitorAd,
)
from services.mock_gsc import generate_gsc_data
from services.mock_ads import generate_paid_data, generate_search_terms_data
from services.mock_profound import (
    generate_ai_visibility, generate_ai_citations, generate_ai_competitors,
)
from services.mock_transparency import generate_competitor_ads

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

    for i in range(days):
        target = today - timedelta(days=i + 1)
        if target in existing:
            continue
        rows = generate_gsc_data(target)
        for r in rows:
            db.add(OrganicPerformance(**r))
        inserted += len(rows)

    db.commit()
    return {"pipeline": "gsc", "days": days, "rows_inserted": inserted}


@router.post("/ads")
def ingest_ads(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    today = date.today()
    existing_paid = _dates_with_data(db, "paid_performance", days)
    existing_terms = _dates_with_data(db, "search_terms", days)
    inserted = 0

    for i in range(days):
        target = today - timedelta(days=i + 1)
        if target not in existing_paid:
            rows = generate_paid_data(target)
            for r in rows:
                db.add(PaidPerformance(**r))
            inserted += len(rows)
        if target not in existing_terms:
            rows = generate_search_terms_data(target)
            for r in rows:
                db.add(SearchTerm(**r))
            inserted += len(rows)

    db.commit()
    return {"pipeline": "ads", "days": days, "rows_inserted": inserted}


@router.post("/profound")
def ingest_profound(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    today = date.today()
    existing_vis = _dates_with_data(db, "ai_visibility", days)
    inserted = 0

    for i in range(days):
        target = today - timedelta(days=i + 1)
        if target in existing_vis:
            continue
        for r in generate_ai_visibility(target):
            db.add(AIVisibility(**r))
        for r in generate_ai_citations(target):
            db.add(AICitation(**r))
        for r in generate_ai_competitors(target):
            db.add(AICompetitor(**r))
        inserted += 1

    db.commit()
    return {"pipeline": "profound", "days_processed": inserted}


@router.post("/transparency")
def ingest_transparency(db: Session = Depends(get_db)):
    today = date.today()
    rows = generate_competitor_ads(today)
    for r in rows:
        db.add(CompetitorAd(**r))
    db.commit()
    return {"pipeline": "transparency", "ads_inserted": len(rows)}

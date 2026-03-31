"""Dashboard API endpoints — all reads come from summary_cache."""
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

import csv
import io

from database import get_db, get_db_session
from models.db import KeywordList, TrackedCompetitor
from services.summaries import (
    get_cached, rebuild_keyword_map, rebuild_summaries, invalidate_scope,
    build_organic_overview, build_organic_timeline, build_organic_top_queries,
    build_organic_position_dist, build_organic_movements, build_organic_top_pages,
    build_organic_devices, build_organic_countries,
    build_paid_overview, build_paid_campaigns, build_paid_search_terms,
    build_paid_timeline, build_paid_is_loss, build_paid_pages, build_paid_ads, build_paid_ad_formats,
    build_ai_overview, build_ai_platforms, build_ai_competitors, build_ai_sov_comparison,
    build_ai_top_cited, build_ai_timeline,
    build_competitors_overview, build_competitors_by_domain, build_competitors_longest_running,
    build_competitors_new_this_week, build_competitors_formats,
    build_creatives_overview, build_creatives_performance, build_creatives_timeline,
    build_creatives_by_campaign, build_creatives_top_headlines,
)

router = APIRouter()


def _cached_or_build(db, cache_key, builder, *args):
    """Read from cache, or build live as fallback."""
    cached = get_cached(db, cache_key)
    if cached is not None:
        return cached
    return builder(db, *args)


# ── Keyword List Management (mutations — no caching) ─────────────

@router.get("/keyword-tags")
def get_keyword_tags(db=Depends(get_db)):
    """List all keyword tag names with term counts."""
    rows = db.execute(text(
        "SELECT list_name, COUNT(*) AS term_count FROM keyword_lists GROUP BY list_name ORDER BY list_name"
    )).mappings().all()
    return [dict(r) for r in rows]


@router.delete("/keyword-tags/{tag_name}")
def delete_keyword_tag(tag_name: str, background_tasks: BackgroundTasks = None, db=Depends(get_db)):
    """Delete an entire keyword tag and all its terms."""
    db.execute(text("DELETE FROM keyword_lists WHERE list_name = :name"), {"name": tag_name})
    db.execute(text("DELETE FROM keyword_query_map WHERE keyword_list_name = :name"), {"name": tag_name})
    db.commit()
    if background_tasks:
        background_tasks.add_task(lambda: None)  # summaries still valid, just fewer tags
    return {"status": "deleted", "tag": tag_name}


# ── Competitor Management ─────────────────────────────────────────

@router.get("/tracked-competitors")
def get_tracked_competitors(db=Depends(get_db)):
    rows = db.execute(text(
        "SELECT id, domain, display_name, created_at FROM tracked_competitors ORDER BY domain"
    )).mappings().all()
    if not rows:
        # Seed from config on first call
        from config import app_settings
        for domain in app_settings.COMPETITOR_DOMAINS.split(","):
            domain = domain.strip()
            if domain:
                db.add(TrackedCompetitor(domain=domain, display_name=domain))
        db.commit()
        rows = db.execute(text(
            "SELECT id, domain, display_name, created_at FROM tracked_competitors ORDER BY domain"
        )).mappings().all()
    return [dict(r) for r in rows]


@router.post("/tracked-competitors")
def add_tracked_competitor(domain: str = Query(...), display_name: str = Query(None), db=Depends(get_db)):
    domain = domain.strip().lower()
    existing = db.execute(text(
        "SELECT id FROM tracked_competitors WHERE domain = :d"
    ), {"d": domain}).first()
    if existing:
        return {"status": "exists", "domain": domain}
    db.add(TrackedCompetitor(domain=domain, display_name=display_name or domain))
    db.commit()
    return {"status": "added", "domain": domain}


@router.delete("/tracked-competitors")
def remove_tracked_competitor(domain: str = Query(...), db=Depends(get_db)):
    domain = domain.strip().lower()
    db.execute(text("DELETE FROM tracked_competitors WHERE domain = :d"), {"d": domain})
    db.commit()
    return {"status": "removed", "domain": domain}


# ── Keyword List Management ──────────────────────────────────────

@router.get("/keyword-lists/{list_name}")
def get_keyword_list(list_name: str, db=Depends(get_db)):
    rows = db.execute(text(
        "SELECT id, term, created_at FROM keyword_lists WHERE list_name = :name ORDER BY term"
    ), {"name": list_name}).mappings().all()
    return [dict(r) for r in rows]


def _rebuild_organic_after_keyword_change(list_name: str):
    """Background task: rebuild keyword map + organic summaries."""
    db = get_db_session()
    try:
        rebuild_keyword_map(db, list_name)
        rebuild_summaries(db, "organic")
    finally:
        db.close()


@router.post("/keyword-lists/{list_name}")
def add_keyword_term(list_name: str, term: str = Query(...), background_tasks: BackgroundTasks = None, db=Depends(get_db)):
    term = term.strip().lower()
    existing = db.execute(text(
        "SELECT id FROM keyword_lists WHERE list_name = :name AND term = :term"
    ), {"name": list_name, "term": term}).first()
    if existing:
        return {"status": "exists", "term": term}
    db.add(KeywordList(list_name=list_name, term=term))
    db.commit()
    if background_tasks:
        background_tasks.add_task(_rebuild_organic_after_keyword_change, list_name)
    return {"status": "added", "term": term, "refresh": "computing"}


@router.post("/keyword-lists/{list_name}/bulk")
def add_keyword_terms_bulk(list_name: str, terms: list[str], background_tasks: BackgroundTasks = None, db=Depends(get_db)):
    added = []
    skipped = []
    for raw in terms:
        term = raw.strip().lower()
        if not term:
            continue
        existing = db.execute(text(
            "SELECT id FROM keyword_lists WHERE list_name = :name AND term = :term"
        ), {"name": list_name, "term": term}).first()
        if existing:
            skipped.append(term)
        else:
            db.add(KeywordList(list_name=list_name, term=term))
            added.append(term)
    db.commit()
    if background_tasks and added:
        background_tasks.add_task(_rebuild_organic_after_keyword_change, list_name)
    return {"added": added, "skipped": skipped, "added_count": len(added), "skipped_count": len(skipped)}


@router.delete("/keyword-lists/{list_name}")
def remove_keyword_term(list_name: str, term: str = Query(...), background_tasks: BackgroundTasks = None, db=Depends(get_db)):
    term = term.strip().lower()
    db.execute(text(
        "DELETE FROM keyword_lists WHERE list_name = :name AND term = :term"
    ), {"name": list_name, "term": term})
    db.commit()
    if background_tasks:
        background_tasks.add_task(_rebuild_organic_after_keyword_change, list_name)
    return {"status": "removed", "term": term}


# ── CSV export helpers ───────────────────────────────────────────

def _period(days: int) -> date:
    return date.today() - timedelta(days=days)


def _csv_response(rows: list[dict], filename: str):
    if not rows:
        return StreamingResponse(io.StringIO(""), media_type="text/csv")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Organic Performance ─────────────────────────────────────────

@router.get("/organic/overview")
def organic_overview(days: int = Query(30), brand: str = Query(None), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_overview:{days}:{brand or 'all'}", build_organic_overview, days, brand)


@router.get("/organic/timeline")
def organic_timeline(days: int = Query(90), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_timeline:{days}", build_organic_timeline, days)


@router.get("/organic/position-distribution")
def organic_position_dist(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_position_dist:{days}", build_organic_position_dist, days)


@router.get("/organic/movements")
def organic_movements(days: int = Query(7), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_movements:{days}", build_organic_movements, days)


@router.get("/organic/top-queries")
def organic_top_queries(days: int = Query(30), limit: int = Query(25), brand: str = Query(None), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_top_queries:{days}:{brand or 'all'}:{limit}", build_organic_top_queries, days, brand, limit)


@router.get("/organic/top-pages")
def organic_top_pages(days: int = Query(30), limit: int = Query(20), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_top_pages:{days}:{limit}", build_organic_top_pages, days, limit)


@router.get("/organic/devices")
def organic_devices(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_devices:{days}", build_organic_devices, days)


@router.get("/organic/countries")
def organic_countries(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_countries:{days}", build_organic_countries, days)


@router.get("/organic/export")
def organic_export(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT query, page, device, country,
               SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               CASE WHEN SUM(impressions) > 0
                    THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr,
               CASE WHEN SUM(impressions) > 0
                    THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1) ELSE 0 END AS avg_position
        FROM organic_performance WHERE data_date >= :start
        GROUP BY query, page, device, country ORDER BY clicks DESC
    """), {"start": start}).mappings().all()
    return _csv_response([dict(r) for r in rows], f"organic_export_{days}d.csv")


# ── Paid Performance ─────────────────────────────────────────────

@router.get("/paid/overview")
def paid_overview(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"paid_overview:{days}", build_paid_overview, days)


@router.get("/paid/campaigns")
def paid_campaigns(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"paid_campaigns:{days}", build_paid_campaigns, days)


@router.get("/paid/search-terms")
def paid_search_terms(days: int = Query(30), limit: int = Query(25), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"paid_search_terms:{days}:{limit}", build_paid_search_terms, days, limit)


@router.get("/paid/ads")
def paid_ads(db: Session = Depends(get_db)):
    return _cached_or_build(db, "paid_ads", build_paid_ads)


@router.get("/paid/timeline")
def paid_timeline(days: int = Query(90), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"paid_timeline:{days}", build_paid_timeline, days)


@router.get("/paid/is-loss")
def paid_is_loss(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"paid_is_loss:{days}", build_paid_is_loss, days)


@router.get("/paid/pages")
def paid_pages(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"paid_pages:{days}", build_paid_pages, days)


@router.get("/paid/ad-formats")
def paid_ad_formats(db: Session = Depends(get_db)):
    return _cached_or_build(db, "paid_ad_formats", build_paid_ad_formats)


@router.get("/paid/export")
def paid_export(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT data_date, campaign_name, ad_group_name, impressions, clicks,
               cost_micros / 1000000.0 AS spend, conversions, impression_share, lost_is_budget, lost_is_rank
        FROM paid_performance WHERE data_date >= :start ORDER BY data_date DESC
    """), {"start": start}).mappings().all()
    return _csv_response([dict(r) for r in rows], f"paid_export_{days}d.csv")


# ── AI Visibility ────────────────────────────────────────────────

@router.get("/ai/overview")
def ai_overview(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"ai_overview:{days}", build_ai_overview, days)


@router.get("/ai/platforms")
def ai_platforms(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"ai_platforms:{days}", build_ai_platforms, days)


@router.get("/ai/competitors")
def ai_competitors(days: int = Query(30), limit: int = Query(15), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"ai_competitors:{days}:{limit}", build_ai_competitors, days, limit)


@router.get("/ai/sov-comparison")
def ai_sov_comparison(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"ai_sov_comparison:{days}", build_ai_sov_comparison, days)


@router.get("/ai/top-cited")
def ai_top_cited(days: int = Query(30), limit: int = Query(10), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"ai_top_cited:{days}:{limit}", build_ai_top_cited, days, limit)


@router.get("/ai/timeline")
def ai_timeline(days: int = Query(60), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"ai_timeline:{days}", build_ai_timeline, days)


@router.get("/ai/citation-timeline")
def ai_citation_timeline(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT data_date, COUNT(*) AS citations,
               SUM(CASE WHEN citation_type = 'DIRECT' THEN 1 ELSE 0 END) AS direct,
               SUM(CASE WHEN citation_type = 'INDIRECT' THEN 1 ELSE 0 END) AS indirect,
               SUM(CASE WHEN citation_type = 'MENTION' THEN 1 ELSE 0 END) AS mention
        FROM ai_citations WHERE data_date >= :start
        GROUP BY data_date ORDER BY data_date
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/ai/topics")
def ai_topics(days: int = Query(30)):
    from config import app_settings
    import requests as req
    start = _period(days).isoformat()
    end = date.today().isoformat()
    try:
        resp = req.post(
            "https://api.tryprofound.com/v1/reports/visibility",
            headers={"X-API-Key": app_settings.PROFOUND_API_KEY, "Content-Type": "application/json"},
            json={
                "category_id": app_settings.PROFOUND_CATEGORY_ID,
                "start_date": start, "end_date": end,
                "metrics": ["visibility_score", "share_of_voice"],
                "dimensions": ["topic"],
                "filters": [{"field": "asset_name", "operator": "is", "value": "First Orion"}],
                "pagination": {"limit": 30},
            },
            timeout=15,
        )
        resp.raise_for_status()
        return [
            {"topic": item["dimensions"][0],
             "visibility": round(item["metrics"][1] * 100, 1) if item["metrics"][1] <= 1 else round(item["metrics"][1], 1),
             "sov": round(item["metrics"][0] * 100, 1)}
            for item in resp.json().get("data", [])
        ]
    except Exception:
        return []


@router.get("/ai/prompts")
def ai_prompts(days: int = Query(30)):
    from config import app_settings
    import requests as req
    start = _period(days).isoformat()
    end = date.today().isoformat()
    try:
        resp = req.post(
            "https://api.tryprofound.com/v1/reports/visibility",
            headers={"X-API-Key": app_settings.PROFOUND_API_KEY, "Content-Type": "application/json"},
            json={
                "category_id": app_settings.PROFOUND_CATEGORY_ID,
                "start_date": start, "end_date": end,
                "metrics": ["visibility_score", "share_of_voice"],
                "dimensions": ["prompt"],
                "filters": [{"field": "asset_name", "operator": "is", "value": "First Orion"}],
                "pagination": {"limit": 30},
            },
            timeout=15,
        )
        resp.raise_for_status()
        return [
            {"prompt": item["dimensions"][0],
             "visibility": round(item["metrics"][1] * 100, 1) if item["metrics"][1] <= 1 else round(item["metrics"][1], 1),
             "sov": round(item["metrics"][0] * 100, 1)}
            for item in resp.json().get("data", [])
        ]
    except Exception:
        return []


@router.get("/ai/cited-urls")
def ai_cited_urls(days: int = Query(30)):
    from config import app_settings
    import requests as req
    start = _period(days).isoformat()
    end = date.today().isoformat()
    try:
        resp = req.post(
            "https://api.tryprofound.com/v1/reports/citations",
            headers={"X-API-Key": app_settings.PROFOUND_API_KEY, "Content-Type": "application/json"},
            json={
                "category_id": app_settings.PROFOUND_CATEGORY_ID,
                "start_date": start, "end_date": end,
                "metrics": ["count"],
                "dimensions": ["url"],
                "pagination": {"limit": 30},
            },
            timeout=15,
        )
        resp.raise_for_status()
        return [
            {"url": item["dimensions"][0], "citations": item["metrics"][0]}
            for item in resp.json().get("data", [])
        ]
    except Exception:
        return []


# ── Competitor Ads ───────────────────────────────────────────────

@router.get("/competitors/overview")
def competitors_overview(db: Session = Depends(get_db)):
    return _cached_or_build(db, "competitors_overview", build_competitors_overview)


@router.get("/competitors/by-domain")
def competitors_by_domain(db: Session = Depends(get_db)):
    return _cached_or_build(db, "competitors_by_domain", build_competitors_by_domain)


@router.get("/competitors/longest-running")
def competitors_longest_running(limit: int = Query(20), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"competitors_longest_running:{limit}", build_competitors_longest_running, limit)


@router.get("/competitors/new-this-week")
def competitors_new_this_week(db: Session = Depends(get_db)):
    return _cached_or_build(db, "competitors_new_this_week", build_competitors_new_this_week)


@router.get("/competitors/formats")
def competitors_formats(db: Session = Depends(get_db)):
    return _cached_or_build(db, "competitors_formats", build_competitors_formats)


# ── Creatives ────────────────────────────────────────────────────

@router.get("/creatives/overview")
def creatives_overview(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"creatives_overview:{days}", build_creatives_overview, days)


@router.get("/creatives/performance")
def creatives_performance(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"creatives_performance:{days}", build_creatives_performance, days)


@router.get("/creatives/timeline")
def creatives_timeline(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"creatives_timeline:{days}", build_creatives_timeline, days)


@router.get("/creatives/by-campaign")
def creatives_by_campaign(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"creatives_by_campaign:{days}", build_creatives_by_campaign, days)


@router.get("/creatives/top-headlines")
def creatives_top_headlines(days: int = Query(30), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"creatives_top_headlines:{days}", build_creatives_top_headlines, days)


# ── Insights (reads from summary_cache) ──────────────────────────

@router.get("/insights")
def get_insights(days: int = Query(30), db: Session = Depends(get_db)):
    key = f"insights:{days}"
    cached = get_cached(db, key)
    if cached is not None:
        return cached
    # Fallback: compute live via insights module
    from routers.insights import _compute_insights
    return _compute_insights(days, db)

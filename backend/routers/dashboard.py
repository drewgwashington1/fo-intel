"""Dashboard API endpoints — all reads come from summary_cache."""
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

import csv
import io

from database import get_db, get_db_session
from models.db import KeywordList, TrackedCompetitor
from services.summaries import (
    get_cached, rebuild_keyword_map, rebuild_category_map, rebuild_summaries, invalidate_scope,
    build_organic_overview, build_organic_timeline, build_organic_top_queries,
    build_organic_position_dist, build_organic_movements, build_organic_top_pages,
    build_organic_devices, build_organic_countries, build_organic_competitors,
    build_competitors_overview, build_competitors_by_domain, build_competitors_longest_running,
    build_competitors_new_this_week, build_competitors_formats,
)

router = APIRouter()


def _cached_or_build(db, cache_key, builder, *args):
    """Read from cache, or build live as fallback."""
    cached = get_cached(db, cache_key)
    if cached is not None:
        return cached
    return builder(db, *args)


# ── Pipeline Status ───────────────────────────────────────────────

@router.get("/pipeline-status")
def pipeline_status(db=Depends(get_db)):
    """Return last run time for all pipelines."""
    rows = db.execute(text(
        "SELECT pipeline_name, last_run_at, rows_processed FROM pipeline_status ORDER BY pipeline_name"
    )).mappings().all()
    return [dict(r) for r in rows]


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
        background_tasks.add_task(_rebuild_branded_map)
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
        "SELECT id, term, category, created_at FROM keyword_lists WHERE list_name = :name ORDER BY term"
    ), {"name": list_name}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/keywords/all")
def get_all_keywords(db=Depends(get_db)):
    """Return every keyword with its tag and category."""
    rows = db.execute(text(
        "SELECT id, list_name, term, category, created_at FROM keyword_lists ORDER BY term"
    )).mappings().all()
    return [dict(r) for r in rows]


def _rebuild_organic_after_keyword_change(list_name: str):
    """Background task: rebuild keyword map for tag + both categories + organic summaries."""
    db = get_db_session()
    try:
        rebuild_keyword_map(db, list_name)
        rebuild_category_map(db, "branded")
        rebuild_category_map(db, "non-branded")
        rebuild_summaries(db, "organic")
    finally:
        db.close()


def _rebuild_branded_map():
    """Background task: rebuild the branded/non-branded category maps + organic summaries."""
    db = get_db_session()
    try:
        rebuild_category_map(db, "branded")
        rebuild_category_map(db, "non-branded")
        rebuild_summaries(db, "organic")
    finally:
        db.close()


@router.post("/keyword-lists/{list_name}")
def add_keyword_term(
    list_name: str,
    term: str = Query(...),
    category: str = Query("non-branded"),
    background_tasks: BackgroundTasks = None,
    db=Depends(get_db),
):
    term = term.strip().lower()
    category = category.strip().lower()
    if category not in ("branded", "non-branded"):
        category = "non-branded"
    existing = db.execute(text(
        "SELECT id FROM keyword_lists WHERE list_name = :name AND term = :term"
    ), {"name": list_name, "term": term}).first()
    if existing:
        return {"status": "exists", "term": term}
    db.add(KeywordList(list_name=list_name, term=term, category=category))
    db.commit()
    if background_tasks:
        background_tasks.add_task(_rebuild_organic_after_keyword_change, list_name)
    return {"status": "added", "term": term, "category": category, "refresh": "computing"}


@router.post("/keyword-lists/{list_name}/bulk")
def add_keyword_terms_bulk(
    list_name: str,
    terms: list[str] = Body(...),
    category: str = Query("non-branded"),
    background_tasks: BackgroundTasks = None,
    db=Depends(get_db),
):
    category = category.strip().lower()
    if category not in ("branded", "non-branded"):
        category = "non-branded"
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
            db.add(KeywordList(list_name=list_name, term=term, category=category))
            added.append(term)
    db.commit()
    if background_tasks and added:
        background_tasks.add_task(_rebuild_organic_after_keyword_change, list_name)
    return {"added": added, "skipped": skipped, "added_count": len(added), "skipped_count": len(skipped)}


@router.patch("/keywords/{keyword_id}/category")
def update_keyword_category(
    keyword_id: int,
    category: str = Query(...),
    background_tasks: BackgroundTasks = None,
    db=Depends(get_db),
):
    """Change a keyword's branded/non-branded category."""
    category = category.strip().lower()
    if category not in ("branded", "non-branded"):
        return {"error": "category must be 'branded' or 'non-branded'"}
    db.execute(text(
        "UPDATE keyword_lists SET category = :cat WHERE id = :id"
    ), {"cat": category, "id": keyword_id})
    db.commit()
    if background_tasks:
        background_tasks.add_task(_rebuild_branded_map)
    return {"status": "updated", "id": keyword_id, "category": category}


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
def organic_overview(days: int = Query(30), brand: str = Query(None), tag: str = Query(None), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_overview:{days}:{brand or 'all'}:{tag or 'all'}", build_organic_overview, days, brand, tag)


@router.get("/organic/timeline")
def organic_timeline(days: int = Query(90), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_timeline:{days}", build_organic_timeline, days)


@router.get("/organic/position-distribution")
def organic_position_dist(days: int = Query(30), brand: str = Query(None), tag: str = Query(None), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_position_dist:{days}:{brand or 'all'}:{tag or 'all'}", build_organic_position_dist, days, brand, tag)


@router.get("/organic/movements")
def organic_movements(days: int = Query(7), brand: str = Query(None), tag: str = Query(None), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_movements:{days}:{brand or 'all'}:{tag or 'all'}", build_organic_movements, days, brand, tag)


@router.get("/organic/top-queries")
def organic_top_queries(days: int = Query(30), limit: int = Query(25), brand: str = Query(None), tag: str = Query(None), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_top_queries:{days}:{brand or 'all'}:{limit}:{tag or 'all'}", build_organic_top_queries, days, brand, limit, tag)


@router.get("/organic/top-pages")
def organic_top_pages(days: int = Query(30), limit: int = Query(20), brand: str = Query(None), tag: str = Query(None), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_top_pages:{days}:{limit}:{brand or 'all'}:{tag or 'all'}", build_organic_top_pages, days, limit, brand, tag)


@router.get("/organic/devices")
def organic_devices(days: int = Query(30), brand: str = Query(None), tag: str = Query(None), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_devices:{days}:{brand or 'all'}:{tag or 'all'}", build_organic_devices, days, brand, tag)


@router.get("/organic/countries")
def organic_countries(days: int = Query(30), brand: str = Query(None), tag: str = Query(None), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_countries:{days}:{brand or 'all'}:{tag or 'all'}", build_organic_countries, days, brand, tag)


@router.get("/organic/competitors")
def organic_competitors_data(days: int = Query(90), db: Session = Depends(get_db)):
    return _cached_or_build(db, f"organic_competitors:{days}", build_organic_competitors, days)


@router.get("/organic/competitors/backfill")
def organic_competitors_backfill(db: Session = Depends(get_db)):
    """One-time backfill: extract organic results from existing serp_cache."""
    from services.serper import backfill_organic_from_cache
    result = backfill_organic_from_cache(db)
    return result


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


# ── Keywords Explorer ────────────────────────────────────────────

@router.get("/keywords/overview")
def keywords_overview(days: int = Query(30), db: Session = Depends(get_db)):
    """Summary stats for keyword metrics."""
    start = _period(days)
    row = db.execute(text("""
        SELECT COUNT(DISTINCT km.keyword) AS total_keywords,
               ROUND(AVG(km.avg_monthly_searches)) AS avg_volume,
               COUNT(DISTINCT km.keyword) FILTER (WHERE km.competition = 'HIGH') AS high_competition,
               COUNT(DISTINCT km.keyword) FILTER (WHERE km.competition = 'LOW') AS low_competition,
               ROUND(AVG(km.high_cpc_micros / 1000000.0)::numeric, 2) AS avg_cpc
        FROM keyword_metrics km
        INNER JOIN (
            SELECT DISTINCT query FROM organic_performance
            WHERE data_date >= :start
              AND LENGTH(query) >= 3
              AND query !~ '^[0-9\\s\\-\\(\\)\\+\\.]+$'
        ) op ON km.keyword = op.query
        WHERE km.avg_monthly_searches > 0
    """), {"start": start}).mappings().first()
    return dict(row) if row else {}


@router.get("/keywords/list")
def keywords_list(
    days: int = Query(30),
    limit: int = Query(100),
    sort: str = Query("volume"),
    brand: str = Query(None),
    tag: str = Query(None),
    db: Session = Depends(get_db),
):
    """Keyword list with volume, competition, CPC, and GSC performance."""
    start = _period(days)

    # Build optional brand/tag filter
    brand_filter = ""
    if brand and brand != "all":
        if brand == "branded":
            brand_filter = "AND op.query IN (SELECT LOWER(term) FROM keyword_lists WHERE category = 'branded')"
        elif brand == "non-branded":
            brand_filter = "AND op.query NOT IN (SELECT LOWER(term) FROM keyword_lists WHERE category = 'branded')"

    tag_filter = ""
    if tag and tag != "all":
        tag_filter = f"AND op.query IN (SELECT LOWER(kqm.query) FROM keyword_query_map kqm WHERE kqm.keyword_list_name = '{tag}')"

    sort_col = {
        "volume": "COALESCE(km.avg_monthly_searches, 0) DESC",
        "clicks": "clicks DESC",
        "impressions": "impressions DESC",
        "position": "avg_position ASC",
        "cpc": "COALESCE(km.high_cpc_micros, 0) DESC",
        "competition": "COALESCE(km.competition_index, 0) DESC",
    }.get(sort, "COALESCE(km.avg_monthly_searches, 0) DESC")

    rows = db.execute(text(f"""
        SELECT op.query AS keyword,
               COALESCE(km.avg_monthly_searches, 0) AS volume,
               km.competition,
               COALESCE(km.competition_index, 0) AS competition_index,
               ROUND(COALESCE(km.low_cpc_micros, 0) / 1000000.0, 2) AS low_cpc,
               ROUND(COALESCE(km.high_cpc_micros, 0) / 1000000.0, 2) AS high_cpc,
               SUM(op.clicks) AS clicks,
               SUM(op.impressions) AS impressions,
               CASE WHEN SUM(op.impressions) > 0
                    THEN ROUND(SUM(op.clicks)::numeric / SUM(op.impressions), 4) ELSE 0 END AS ctr,
               CASE WHEN SUM(op.impressions) > 0
                    THEN ROUND((SUM(op.position * op.impressions) / SUM(op.impressions))::numeric, 0) ELSE 0 END AS avg_position,
               (ARRAY_AGG(op.page ORDER BY op.clicks DESC))[1] AS top_page
        FROM organic_performance op
        LEFT JOIN keyword_metrics km ON km.keyword = op.query
        WHERE op.data_date >= :start
          AND LENGTH(op.query) >= 3
          AND op.query !~ '^[0-9\\s\\-\\(\\)\\+\\.]+$'
          AND op.query !~ '^\\d{{7,}}$'
          {brand_filter} {tag_filter}
        GROUP BY op.query, km.avg_monthly_searches, km.competition, km.competition_index,
                 km.low_cpc_micros, km.high_cpc_micros
        HAVING COALESCE(km.avg_monthly_searches, 0) > 0 OR SUM(op.impressions) >= 10
        ORDER BY {sort_col}
        LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/keywords/ideas")
def keywords_ideas(seeds: str = Query(""), limit: int = Query(50), db: Session = Depends(get_db)):
    """Get keyword ideas from Keyword Planner based on seed keywords.

    Seeds can be comma-separated. If empty, uses top 5 GSC keywords by clicks.
    """
    from services.keyword_planner import fetch_keyword_ideas
    from models.db import KeywordIdea

    if seeds:
        seed_list = [s.strip() for s in seeds.split(",") if s.strip()]
    else:
        # Use high-volume non-branded keywords as seeds
        rows = db.execute(text("""
            SELECT km.keyword
            FROM keyword_metrics km
            INNER JOIN (
                SELECT DISTINCT query FROM organic_performance
                WHERE data_date >= CURRENT_DATE - INTERVAL '30 days'
                  AND query IS NOT NULL AND query != ''
            ) op ON km.keyword = op.query
            WHERE km.avg_monthly_searches > 0
              AND LOWER(km.keyword) NOT IN (
                  SELECT LOWER(term) FROM keyword_lists WHERE category = 'branded'
              )
            ORDER BY km.avg_monthly_searches DESC
            LIMIT 10
        """)).all()
        seed_list = [r[0] for r in rows]

    if not seed_list:
        return []

    # Check cache first (ideas fetched in last 7 days)
    cached = db.execute(text("""
        SELECT suggested_keyword AS keyword, avg_monthly_searches AS volume,
               competition, competition_index,
               ROUND(low_cpc_micros / 1000000.0, 2) AS low_cpc,
               ROUND(high_cpc_micros / 1000000.0, 2) AS high_cpc,
               seed_keyword
        FROM keyword_ideas
        WHERE seed_keyword IN :seeds
          AND fetched_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
        ORDER BY avg_monthly_searches DESC LIMIT :lim
    """), {"seeds": tuple(seed_list), "lim": limit}).mappings().all()

    if cached:
        return [dict(r) for r in cached]

    # Fetch fresh from API
    ideas = fetch_keyword_ideas(seed_list, limit)

    # Cache results
    for idea in ideas:
        db.add(KeywordIdea(
            seed_keyword=seed_list[0],
            suggested_keyword=idea["keyword"],
            avg_monthly_searches=idea["avg_monthly_searches"],
            competition=idea["competition"],
            competition_index=idea["competition_index"],
            low_cpc_micros=idea["low_cpc_micros"],
            high_cpc_micros=idea["high_cpc_micros"],
        ))
    db.commit()

    return [{
        "keyword": i["keyword"],
        "volume": i["avg_monthly_searches"],
        "competition": i["competition"],
        "competition_index": i["competition_index"],
        "low_cpc": round(i["low_cpc_micros"] / 1_000_000, 2),
        "high_cpc": round(i["high_cpc_micros"] / 1_000_000, 2),
        "seed_keyword": seed_list[0],
    } for i in ideas]


@router.get("/keywords/gaps")
def keywords_gaps(days: int = Query(90), limit: int = Query(50), db: Session = Depends(get_db)):
    """Content gaps: keywords competitors rank for but FO doesn't.

    Uses Serper organic_serp_results (competitor rankings) vs GSC (FO rankings).
    Enriched with Keyword Planner volume/CPC when available.
    """
    start = _period(days)
    rows = db.execute(text("""
        SELECT osr.keyword,
               COUNT(DISTINCT osr.domain) AS competitor_count,
               MIN(osr.position) AS best_competitor_position,
               ARRAY_AGG(DISTINCT osr.domain ORDER BY osr.domain) AS competitor_domains,
               COALESCE(km.avg_monthly_searches, 0) AS volume,
               km.competition,
               ROUND(COALESCE(km.high_cpc_micros, 0) / 1000000.0, 2) AS cpc
        FROM organic_serp_results osr
        LEFT JOIN keyword_metrics km ON km.keyword = osr.keyword
        WHERE osr.observed_date >= :start
          AND osr.domain != 'firstorion.com'
          AND osr.keyword NOT IN (
              SELECT DISTINCT query FROM organic_performance
              WHERE data_date >= :start
          )
          AND LOWER(osr.keyword) NOT IN (
              SELECT LOWER(term) FROM keyword_lists WHERE category = 'branded'
          )
        GROUP BY osr.keyword, km.avg_monthly_searches, km.competition, km.high_cpc_micros
        HAVING COUNT(DISTINCT osr.domain) >= 1
        ORDER BY COALESCE(km.avg_monthly_searches, 0) DESC, COUNT(DISTINCT osr.domain) DESC
        LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


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

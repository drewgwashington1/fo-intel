"""Dashboard API endpoints for all 4 data views."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

import csv
import io

from database import get_db

router = APIRouter()


def _period(days: int) -> date:
    return date.today() - timedelta(days=days)


def _prev_period(days: int) -> tuple[date, date]:
    """Return (start, end) for the previous equivalent period."""
    end = _period(days)
    start = end - timedelta(days=days)
    return start, end


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


# ── Organic Performance ──────────────────────────────────────────────

@router.get("/organic/overview")
def organic_overview(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    prev_start, prev_end = _prev_period(days)

    current = db.execute(text("""
        SELECT
            COALESCE(SUM(clicks), 0) AS total_clicks,
            COALESCE(SUM(impressions), 0) AS total_impressions,
            CASE WHEN SUM(impressions) > 0
                 THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4)
                 ELSE 0 END AS avg_ctr,
            CASE WHEN SUM(impressions) > 0
                 THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1)
                 ELSE 0 END AS avg_position,
            COUNT(DISTINCT query) AS unique_queries,
            COUNT(DISTINCT page) AS unique_pages
        FROM organic_performance WHERE data_date >= :start
    """), {"start": start}).mappings().first()

    previous = db.execute(text("""
        SELECT
            COALESCE(SUM(clicks), 0) AS total_clicks,
            COALESCE(SUM(impressions), 0) AS total_impressions,
            CASE WHEN SUM(impressions) > 0
                 THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4)
                 ELSE 0 END AS avg_ctr,
            CASE WHEN SUM(impressions) > 0
                 THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1)
                 ELSE 0 END AS avg_position
        FROM organic_performance WHERE data_date >= :prev_start AND data_date < :prev_end
    """), {"prev_start": prev_start, "prev_end": prev_end}).mappings().first()

    result = dict(current)
    result["prev_clicks"] = previous["total_clicks"]
    result["prev_impressions"] = previous["total_impressions"]
    result["prev_ctr"] = float(previous["avg_ctr"])
    result["prev_position"] = float(previous["avg_position"])
    return result


@router.get("/organic/timeline")
def organic_timeline(days: int = Query(90), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT data_date, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               CASE WHEN SUM(impressions) > 0
                    THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4)
                    ELSE 0 END AS ctr,
               CASE WHEN SUM(impressions) > 0
                    THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1)
                    ELSE 0 END AS avg_position
        FROM organic_performance WHERE data_date >= :start
        GROUP BY data_date ORDER BY data_date
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/organic/position-distribution")
def organic_position_distribution(days: int = Query(30), db: Session = Depends(get_db)):
    """Bucket keywords by position range (like Ahrefs position distribution)."""
    start = _period(days)
    rows = db.execute(text("""
        SELECT
            data_date,
            COUNT(*) FILTER (WHERE position >= 1 AND position <= 3) AS pos_1_3,
            COUNT(*) FILTER (WHERE position > 3 AND position <= 10) AS pos_4_10,
            COUNT(*) FILTER (WHERE position > 10 AND position <= 20) AS pos_11_20,
            COUNT(*) FILTER (WHERE position > 20 AND position <= 50) AS pos_21_50,
            COUNT(*) FILTER (WHERE position > 50) AS pos_51_plus
        FROM organic_performance WHERE data_date >= :start
        GROUP BY data_date ORDER BY data_date
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/organic/movements")
def organic_movements(days: int = Query(7), db: Session = Depends(get_db)):
    """Track new, lost, improved, and declined keywords vs previous period."""
    current_start = _period(days)
    prev_start, prev_end = _prev_period(days)

    rows = db.execute(text("""
        WITH current_period AS (
            SELECT query, page,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 1) AS avg_pos,
                   SUM(clicks) AS clicks, SUM(impressions) AS impressions
            FROM organic_performance WHERE data_date >= :current_start
            GROUP BY query, page
        ),
        prev_period AS (
            SELECT query, page,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 1) AS avg_pos,
                   SUM(clicks) AS clicks
            FROM organic_performance WHERE data_date >= :prev_start AND data_date < :prev_end
            GROUP BY query, page
        )
        SELECT
            c.query, c.page,
            c.avg_pos AS current_position,
            p.avg_pos AS prev_position,
            c.clicks,
            c.impressions,
            CASE
                WHEN p.query IS NULL THEN 'new'
                WHEN c.avg_pos < p.avg_pos THEN 'improved'
                WHEN c.avg_pos > p.avg_pos THEN 'declined'
                ELSE 'unchanged'
            END AS movement,
            COALESCE(p.avg_pos - c.avg_pos, 0) AS position_change
        FROM current_period c
        LEFT JOIN prev_period p ON c.query = p.query AND c.page = p.page

        UNION ALL

        SELECT p.query, p.page, NULL, p.avg_pos, 0, 0, 'lost', 0
        FROM prev_period p
        LEFT JOIN current_period c ON p.query = c.query AND p.page = c.page
        WHERE c.query IS NULL

        ORDER BY clicks DESC
        LIMIT 50
    """), {"current_start": current_start, "prev_start": prev_start, "prev_end": prev_end}).mappings().all()

    result = {"new": [], "lost": [], "improved": [], "declined": [], "unchanged": []}
    for r in rows:
        d = dict(r)
        result[d["movement"]].append(d)

    return {
        "summary": {
            "new": len(result["new"]),
            "lost": len(result["lost"]),
            "improved": len(result["improved"]),
            "declined": len(result["declined"]),
        },
        "details": result,
    }


@router.get("/organic/top-queries")
def organic_top_queries(days: int = Query(30), limit: int = Query(25), db: Session = Depends(get_db)):
    start = _period(days)
    prev_start, prev_end = _prev_period(days)

    rows = db.execute(text("""
        WITH current_q AS (
            SELECT query, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
                   ROUND(SUM(clicks)::numeric / NULLIF(SUM(impressions), 0), 4) AS ctr,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 1) AS avg_position
            FROM organic_performance WHERE data_date >= :start
            GROUP BY query
        ),
        prev_q AS (
            SELECT query, SUM(clicks) AS clicks,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 1) AS avg_position
            FROM organic_performance WHERE data_date >= :prev_start AND data_date < :prev_end
            GROUP BY query
        )
        SELECT c.query, c.clicks, c.impressions, c.ctr, c.avg_position,
               COALESCE(p.clicks, 0) AS prev_clicks,
               p.avg_position AS prev_position
        FROM current_q c
        LEFT JOIN prev_q p ON c.query = p.query
        ORDER BY c.clicks DESC LIMIT :lim
    """), {"start": start, "prev_start": prev_start, "prev_end": prev_end, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/organic/top-pages")
def organic_top_pages(days: int = Query(30), limit: int = Query(20), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT page, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 1) AS avg_position,
               COUNT(DISTINCT query) AS keywords,
               ROUND(SUM(clicks)::numeric / NULLIF(SUM(impressions), 0), 4) AS ctr
        FROM organic_performance WHERE data_date >= :start
        GROUP BY page ORDER BY clicks DESC LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/organic/devices")
def organic_devices(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT device, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               ROUND(SUM(clicks)::numeric / NULLIF(SUM(impressions), 0), 4) AS ctr
        FROM organic_performance WHERE data_date >= :start
        GROUP BY device ORDER BY clicks DESC
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/organic/countries")
def organic_countries(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT country, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               ROUND(SUM(clicks)::numeric / NULLIF(SUM(impressions), 0), 4) AS ctr,
               ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 1) AS avg_position
        FROM organic_performance WHERE data_date >= :start
        GROUP BY country ORDER BY clicks DESC
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/organic/export")
def organic_export(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT query, page, device, country, SUM(clicks) AS clicks,
               SUM(impressions) AS impressions,
               ROUND(SUM(clicks)::numeric / NULLIF(SUM(impressions), 0), 4) AS ctr,
               ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 1) AS avg_position
        FROM organic_performance WHERE data_date >= :start
        GROUP BY query, page, device, country ORDER BY clicks DESC
    """), {"start": start}).mappings().all()
    return _csv_response([dict(r) for r in rows], "organic_performance.csv")


# ── Paid Performance (Google Ads API + Transparency Center) ──────────
# Data sources:
#   - paid_performance / search_terms (Google Ads API) → spend, CPC, IS, campaigns
#   - competitor_ads (Transparency Center) → ad creatives for firstorion.com

@router.get("/paid/overview")
def paid_overview(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    prev_start, prev_end = _prev_period(days)

    current = db.execute(text("""
        SELECT
            COALESCE(SUM(cost_micros), 0) / 1000000.0 AS total_spend,
            COALESCE(AVG(impression_share), 0) AS avg_impression_share,
            CASE WHEN SUM(clicks) > 0
                 THEN SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0
                 ELSE 0 END AS avg_cpc,
            COALESCE(SUM(clicks), 0) AS total_clicks,
            COALESCE(SUM(impressions), 0) AS total_impressions,
            COALESCE(SUM(conversions), 0) AS total_conversions,
            COALESCE(AVG(lost_is_budget), 0) AS avg_lost_budget,
            COALESCE(AVG(lost_is_rank), 0) AS avg_lost_rank
        FROM paid_performance WHERE data_date >= :start
    """), {"start": start}).mappings().first()

    previous = db.execute(text("""
        SELECT
            COALESCE(SUM(cost_micros), 0) / 1000000.0 AS total_spend,
            COALESCE(AVG(impression_share), 0) AS avg_impression_share,
            CASE WHEN SUM(clicks) > 0
                 THEN SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0
                 ELSE 0 END AS avg_cpc,
            COALESCE(SUM(clicks), 0) AS total_clicks,
            COALESCE(SUM(conversions), 0) AS total_conversions
        FROM paid_performance WHERE data_date >= :prev_start AND data_date < :prev_end
    """), {"prev_start": prev_start, "prev_end": prev_end}).mappings().first()

    # Also include Transparency Center ad count
    tc = db.execute(text("""
        SELECT COUNT(*) AS total_ads,
               COUNT(*) FILTER (WHERE is_active) AS active_ads
        FROM competitor_ads WHERE competitor_domain = 'firstorion.com'
    """)).mappings().first()

    result = dict(current)
    result["prev_spend"] = float(previous["total_spend"])
    result["prev_clicks"] = previous["total_clicks"]
    result["prev_cpc"] = float(previous["avg_cpc"])
    result["prev_conversions"] = float(previous["total_conversions"])
    result["prev_impression_share"] = float(previous["avg_impression_share"])
    result["tc_total_ads"] = tc["total_ads"]
    result["tc_active_ads"] = tc["active_ads"]
    return result


@router.get("/paid/campaigns")
def paid_campaigns(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT campaign_name,
               SUM(cost_micros) / 1000000.0 AS spend,
               SUM(clicks) AS clicks,
               SUM(impressions) AS impressions,
               SUM(conversions) AS conversions,
               CASE WHEN SUM(clicks) > 0
                    THEN ROUND(SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0, 2)
                    ELSE 0 END AS cpc,
               AVG(impression_share) AS avg_is,
               AVG(lost_is_budget) AS avg_lost_budget,
               AVG(lost_is_rank) AS avg_lost_rank
        FROM paid_performance WHERE data_date >= :start
        GROUP BY campaign_name ORDER BY spend DESC
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/paid/search-terms")
def paid_search_terms(days: int = Query(30), limit: int = Query(25), db: Session = Depends(get_db)):
    """Search terms enriched with organic position data from GSC."""
    start = _period(days)
    rows = db.execute(text("""
        SELECT
            st.search_term,
            st.match_type,
            SUM(st.clicks) AS clicks,
            SUM(st.cost_micros) / 1000000.0 AS cost,
            SUM(st.impressions) AS volume,
            SUM(st.conversions) AS conversions,
            CASE WHEN SUM(st.clicks) > 0
                 THEN ROUND(SUM(st.cost_micros)::numeric / SUM(st.clicks) / 1000000.0, 2)
                 ELSE 0 END AS cpc,
            org.organic_traffic,
            org.organic_position,
            org.top_url
        FROM search_terms st
        LEFT JOIN LATERAL (
            SELECT
                SUM(op.clicks) AS organic_traffic,
                ROUND(AVG(op.position)::numeric, 1) AS organic_position,
                (ARRAY_AGG(op.page ORDER BY op.clicks DESC))[1] AS top_url
            FROM organic_performance op
            WHERE op.query = st.search_term
              AND op.data_date >= :start
        ) org ON true
        WHERE st.data_date >= :start
        GROUP BY st.search_term, st.match_type, org.organic_traffic, org.organic_position, org.top_url
        ORDER BY SUM(st.clicks) DESC
        LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/paid/ads")
def paid_ads(db: Session = Depends(get_db)):
    """First Orion's own ads from Transparency Center."""
    rows = db.execute(text("""
        SELECT ad_id, ad_format, headline, description, destination_url,
               platforms, regions, first_shown_date, last_shown_date,
               days_running, is_active, advertiser_name, image_url
        FROM competitor_ads
        WHERE competitor_domain = 'firstorion.com'
        ORDER BY days_running DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/paid/timeline")
def paid_timeline(days: int = Query(90), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT data_date, SUM(cost_micros) / 1000000.0 AS spend,
               SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               AVG(impression_share) AS avg_is,
               SUM(conversions) AS conversions
        FROM paid_performance WHERE data_date >= :start
        GROUP BY data_date ORDER BY data_date
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/paid/is-loss")
def paid_is_loss(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT campaign_name,
               ROUND(AVG(impression_share)::numeric * 100, 1) AS is_pct,
               ROUND(AVG(lost_is_budget)::numeric * 100, 1) AS lost_budget_pct,
               ROUND(AVG(lost_is_rank)::numeric * 100, 1) AS lost_rank_pct,
               SUM(cost_micros) / 1000000.0 AS total_spend
        FROM paid_performance WHERE data_date >= :start
        GROUP BY campaign_name ORDER BY lost_rank_pct DESC
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/paid/pages")
def paid_pages(days: int = Query(30), db: Session = Depends(get_db)):
    """Landing pages receiving paid traffic, cross-referenced with organic data."""
    start = _period(days)
    rows = db.execute(text("""
        SELECT
            op.page AS url,
            COUNT(DISTINCT st.search_term) AS ads_keywords,
            SUM(op.clicks) AS organic_traffic,
            SUM(op.impressions) AS impressions,
            ROUND(AVG(op.ctr)::numeric, 4) AS ctr,
            ROUND(AVG(op.position)::numeric, 1) AS avg_position,
            COUNT(DISTINCT op.query) AS total_keywords
        FROM organic_performance op
        INNER JOIN search_terms st ON op.query = st.search_term
        WHERE op.data_date >= :start AND st.data_date >= :start
        GROUP BY op.page
        ORDER BY organic_traffic DESC
        LIMIT 30
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/paid/ad-formats")
def paid_ad_formats(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT ad_format, COUNT(*) AS count,
               COUNT(*) FILTER (WHERE is_active) AS active_count
        FROM competitor_ads
        WHERE competitor_domain = 'firstorion.com'
        GROUP BY ad_format ORDER BY count DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/paid/export")
def paid_export(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT data_date, campaign_name, ad_group_name, impressions, clicks,
               cost_micros / 1000000.0 AS cost, avg_cpc_micros / 1000000.0 AS avg_cpc,
               conversions, impression_share, lost_is_budget, lost_is_rank
        FROM paid_performance WHERE data_date >= :start ORDER BY data_date DESC
    """), {"start": start}).mappings().all()
    return _csv_response([dict(r) for r in rows], "paid_performance.csv")


# ── AI Visibility ────────────────────────────────────────────────────

@router.get("/ai/overview")
def ai_overview(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    prev_start, prev_end = _prev_period(days)

    current = db.execute(text("""
        SELECT
            COALESCE(ROUND(AVG(visibility_score)::numeric, 1), 0) AS avg_visibility,
            COALESCE(ROUND(AVG(share_of_voice)::numeric, 4), 0) AS avg_sov,
            COALESCE(SUM(citation_count), 0) AS total_citations
        FROM ai_visibility WHERE data_date >= :start
    """), {"start": start}).mappings().first()

    previous = db.execute(text("""
        SELECT
            COALESCE(ROUND(AVG(visibility_score)::numeric, 1), 0) AS avg_visibility,
            COALESCE(ROUND(AVG(share_of_voice)::numeric, 4), 0) AS avg_sov,
            COALESCE(SUM(citation_count), 0) AS total_citations
        FROM ai_visibility WHERE data_date >= :prev_start AND data_date < :prev_end
    """), {"prev_start": prev_start, "prev_end": prev_end}).mappings().first()

    citations_count = db.execute(text("""
        SELECT COUNT(*) AS cnt FROM ai_citations WHERE data_date >= :start
    """), {"start": start}).mappings().first()

    result = dict(current)
    result["total_citation_records"] = citations_count["cnt"]
    result["prev_visibility"] = float(previous["avg_visibility"])
    result["prev_sov"] = float(previous["avg_sov"])
    result["prev_citations"] = previous["total_citations"]
    return result


@router.get("/ai/platforms")
def ai_platforms(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT platform,
               ROUND(AVG(visibility_score)::numeric, 1) AS avg_visibility,
               ROUND(AVG(share_of_voice)::numeric, 4) AS avg_sov,
               SUM(citation_count) AS citations
        FROM ai_visibility WHERE data_date >= :start
        GROUP BY platform ORDER BY avg_visibility DESC
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/ai/competitors")
def ai_competitors(days: int = Query(30), limit: int = Query(15), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT competitor_domain,
               ROUND(AVG(share_of_voice)::numeric, 4) AS avg_sov,
               SUM(citation_count) AS citations
        FROM ai_competitors WHERE data_date >= :start
        GROUP BY competitor_domain ORDER BY avg_sov DESC
        LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/ai/sov-comparison")
def ai_sov_comparison(days: int = Query(30), db: Session = Depends(get_db)):
    start = _period(days)
    fo_rows = db.execute(text("""
        SELECT category_name,
               ROUND(AVG(share_of_voice)::numeric, 4) AS fo_sov
        FROM ai_visibility WHERE data_date >= :start
        GROUP BY category_name
    """), {"start": start}).mappings().all()

    # Only include top 10 competitors by SOV to avoid overwhelming the chart
    comp_rows = db.execute(text("""
        SELECT category_name, competitor_domain,
               ROUND(AVG(share_of_voice)::numeric, 4) AS comp_sov
        FROM ai_competitors
        WHERE data_date >= :start
          AND competitor_domain IN (
            SELECT competitor_domain
            FROM ai_competitors
            WHERE data_date >= :start
            GROUP BY competitor_domain
            ORDER BY AVG(share_of_voice) DESC
            LIMIT 10
          )
        GROUP BY category_name, competitor_domain
    """), {"start": start}).mappings().all()

    return {"fo": [dict(r) for r in fo_rows], "competitors": [dict(r) for r in comp_rows]}


@router.get("/ai/top-cited")
def ai_top_cited(days: int = Query(30), limit: int = Query(10), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT cited_url, COUNT(*) AS citation_count,
               SUM(CASE WHEN sentiment = 'POSITIVE' THEN 1 ELSE 0 END) AS positive,
               SUM(CASE WHEN sentiment = 'NEUTRAL' THEN 1 ELSE 0 END) AS neutral,
               SUM(CASE WHEN sentiment = 'NEGATIVE' THEN 1 ELSE 0 END) AS negative,
               ROUND(SUM(CASE WHEN sentiment = 'POSITIVE' THEN 1 ELSE 0 END)::numeric
                     / COUNT(*) * 100, 0) AS positive_pct
        FROM ai_citations WHERE data_date >= :start
        GROUP BY cited_url ORDER BY citation_count DESC LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/ai/timeline")
def ai_timeline(days: int = Query(60), db: Session = Depends(get_db)):
    start = _period(days)
    rows = db.execute(text("""
        SELECT data_date, platform,
               ROUND(AVG(visibility_score)::numeric, 1) AS visibility,
               ROUND(AVG(share_of_voice)::numeric, 4) AS sov
        FROM ai_visibility WHERE data_date >= :start
        GROUP BY data_date, platform ORDER BY data_date
    """), {"start": start}).mappings().all()
    return [dict(r) for r in rows]


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
    """Top AI topics where First Orion appears — from Profound API."""
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
                "start_date": start,
                "end_date": end,
                "metrics": ["visibility_score", "share_of_voice"],
                "dimensions": ["topic"],
                "filters": [{"field": "asset_name", "operator": "is", "value": "First Orion"}],
                "pagination": {"limit": 30},
            },
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        return [
            {
                "topic": item["dimensions"][0],
                "visibility": round(item["metrics"][1] * 100, 1) if item["metrics"][1] <= 1 else round(item["metrics"][1], 1),
                "sov": round(item["metrics"][0] * 100, 1),
            }
            for item in result.get("data", [])
        ]
    except Exception:
        return []


@router.get("/ai/prompts")
def ai_prompts(days: int = Query(30)):
    """Top AI prompts where First Orion is mentioned — from Profound API."""
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
                "start_date": start,
                "end_date": end,
                "metrics": ["visibility_score", "share_of_voice"],
                "dimensions": ["prompt"],
                "filters": [{"field": "asset_name", "operator": "is", "value": "First Orion"}],
                "pagination": {"limit": 30},
            },
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        return [
            {
                "prompt": item["dimensions"][0],
                "visibility": round(item["metrics"][1] * 100, 1) if item["metrics"][1] <= 1 else round(item["metrics"][1], 1),
                "sov": round(item["metrics"][0] * 100, 1),
            }
            for item in result.get("data", [])
        ]
    except Exception:
        return []


@router.get("/ai/cited-urls")
def ai_cited_urls(days: int = Query(30)):
    """Top cited URLs across all domains — from Profound API."""
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
                "start_date": start,
                "end_date": end,
                "metrics": ["count"],
                "dimensions": ["url"],
                "pagination": {"limit": 30},
            },
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        return [
            {
                "url": item["dimensions"][0],
                "citations": item["metrics"][0],
            }
            for item in result.get("data", [])
        ]
    except Exception:
        return []


# ── Competitor Ads ───────────────────────────────────────────────────

@router.get("/competitors/overview")
def competitors_overview(db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE is_active) AS active_ads,
            COUNT(*) AS total_ads,
            MAX(days_running) FILTER (WHERE is_active) AS longest_running,
            COUNT(*) FILTER (WHERE first_shown_date >= CURRENT_DATE - INTERVAL '7 days') AS new_this_week,
            COUNT(DISTINCT competitor_domain) AS competitors_tracked,
            ROUND(AVG(days_running) FILTER (WHERE is_active)::numeric, 0) AS avg_days_running
        FROM competitor_ads
    """)).mappings().first()
    return dict(row)


@router.get("/competitors/by-domain")
def competitors_by_domain(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT competitor_domain, advertiser_name,
               COUNT(*) FILTER (WHERE is_active) AS active_ads,
               COUNT(*) AS total_ads,
               MAX(days_running) AS max_days_running,
               ROUND(AVG(days_running) FILTER (WHERE is_active)::numeric, 0) AS avg_days_running,
               COUNT(DISTINCT ad_format) AS format_count
        FROM competitor_ads
        GROUP BY competitor_domain, advertiser_name ORDER BY active_ads DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/competitors/longest-running")
def competitors_longest_running(limit: int = Query(20), db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT competitor_domain, advertiser_name, headline, description,
               ad_format, days_running, first_shown_date, destination_url, platforms
        FROM competitor_ads
        WHERE is_active = TRUE
        ORDER BY days_running DESC LIMIT :lim
    """), {"lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/competitors/new-this-week")
def competitors_new_this_week(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT competitor_domain, advertiser_name, headline, description,
               ad_format, first_shown_date, destination_url, platforms, days_running
        FROM competitor_ads
        WHERE first_shown_date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY first_shown_date DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/competitors/formats")
def competitors_formats(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT ad_format, COUNT(*) AS count,
               COUNT(*) FILTER (WHERE is_active) AS active_count
        FROM competitor_ads
        GROUP BY ad_format ORDER BY count DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/competitors/platform-distribution")
def competitors_platform_dist(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT competitor_domain, unnest(platforms) AS platform, COUNT(*) AS count
        FROM competitor_ads WHERE is_active = TRUE
        GROUP BY competitor_domain, platform
        ORDER BY competitor_domain, count DESC
    """)).mappings().all()
    return [dict(r) for r in rows]

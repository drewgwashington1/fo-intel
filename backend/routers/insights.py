"""Insights engine — surfaces content opportunities across all data sources.

Every insight answers: "What specific content should FO create, expand, or refresh?"
No SEO tactics. No vague generalizations. Content opportunities only.

Categories: organic (4)
Paid and AI visibility removed — out of scope.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import text

router = APIRouter()


def _period(days: int) -> date:
    return date.today() - timedelta(days=days)


def _prev_period(days: int) -> tuple[date, date]:
    end = _period(days)
    start = end - timedelta(days=days)
    return start, end


def _strip_domain(url: str) -> str:
    if not url:
        return url
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.path or "/"


# Org name variations to always exclude — the app should know these automatically
_ORG_TERMS = [
    'first orion', 'firstorion', 'first-orion', 'first_orion',
    'orion api', 'orion login', 'orion portal',
    'fo shield', 'fo intel', 'foshield',
    'inform authenticated', 'branded communication',
]

# Internal/non-website URLs to exclude from page-based insights
_EXCLUDED_URL_PATTERNS = [
    'portal.firstorion.com',
    'api.firstorion.com',
    'admin.firstorion.com',
    'staging.firstorion.com',
    'dev.firstorion.com',
    'localhost',
]


def _branded_exclusion(col: str = "query") -> str:
    """SQL fragment to exclude branded keywords.
    Combines: hardcoded org name variations + user-defined keywords with category='branded'.
    """
    org_clauses = " AND ".join([f"LOWER({col}) NOT LIKE '%{t}%'" for t in _ORG_TERMS])
    return (
        f"AND {org_clauses} "
        f"AND LOWER({col}) NOT IN (SELECT LOWER(kl.term) FROM keyword_lists kl WHERE kl.category = 'branded')"
    )


def _url_exclusion(col: str = "page") -> str:
    """SQL fragment to exclude internal/non-website URLs."""
    clauses = " AND ".join([f"{col} NOT LIKE '%{u}%'" for u in _EXCLUDED_URL_PATTERNS])
    return f"AND {clauses}"


# ── Main computation ─────────────────────────────────────────────

def _compute_insights(days: int, db: Session):
    start = _period(days)
    prev_start, prev_end = _prev_period(days)
    bf = _branded_exclusion()
    insights = []

    # ═══════════════════════════════════════════════════════════════
    # ORGANIC — 4 types, all content-focused
    # ═══════════════════════════════════════════════════════════════

    # ── 1. Content to Create (positions 4-15, high impressions) ──
    rows = db.execute(text(f"""
        WITH keyword_stats AS (
            SELECT query,
                   (ARRAY_AGG(page ORDER BY clicks DESC))[1] AS top_page,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(impressions) AS impressions, SUM(clicks) AS clicks
            FROM organic_performance WHERE data_date >= :start {bf}
            GROUP BY query
        )
        SELECT * FROM keyword_stats
        WHERE avg_position BETWEEN 4 AND 15 AND impressions >= 100
        ORDER BY impressions DESC LIMIT 20
    """), {"start": start}).mappings().all()

    for r in rows:
        pos = int(r["avg_position"])
        insights.append({
            "id": f"content_create_{len(insights)}",
            "type": "content_to_create",
            "category": "organic",
            "priority": "high" if r["impressions"] >= 500 else "medium" if r["impressions"] >= 200 else "low",
            "title": f'Create content about: "{r["query"]}"',
            "description": f'Position {pos}, {r["impressions"]:,} monthly impressions, {r["clicks"]:,} clicks.',
            "metric": {"position": pos, "impressions": r["impressions"], "clicks": r["clicks"]},
            "action": f'Create dedicated content about "{r["query"]}". Currently ranking position {pos} with {r["impressions"]:,} impressions — dedicated content could push to page 1.',
            "affected_entity": r["query"],
            "source": "GSC organic data",
        })

    # ── 2. Striking Distance (positions 11-20) ──────────────────
    rows = db.execute(text(f"""
        WITH keyword_stats AS (
            SELECT query,
                   (ARRAY_AGG(page ORDER BY clicks DESC))[1] AS top_page,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(impressions) AS impressions, SUM(clicks) AS clicks
            FROM organic_performance WHERE data_date >= :start {bf}
            GROUP BY query
        )
        SELECT * FROM keyword_stats
        WHERE avg_position BETWEEN 11 AND 20 AND impressions >= 100
        ORDER BY impressions DESC LIMIT 15
    """), {"start": start}).mappings().all()

    for r in rows:
        pos = int(r["avg_position"])
        insights.append({
            "id": f"striking_{len(insights)}",
            "type": "striking_distance",
            "category": "organic",
            "priority": "medium" if r["impressions"] >= 300 else "low",
            "title": f'Expand content about: "{r["query"]}"',
            "description": f'Position {pos} (page 2), {r["impressions"]:,} impressions. Expanding existing content could move this to page 1.',
            "metric": {"position": pos, "impressions": r["impressions"], "clicks": r["clicks"]},
            "action": f'Expand or create content about "{r["query"]}" — currently position {pos} with {r["clicks"]:,} clicks. Dedicated content could capture significantly more traffic.',
            "affected_entity": r["query"],
            "source": "GSC organic data",
        })

    # ── 3. Content to Refresh (dropped 5+ positions) ────────────
    rows = db.execute(text(f"""
        WITH current_q AS (
            SELECT query,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(clicks) AS clicks, SUM(impressions) AS impressions
            FROM organic_performance WHERE data_date >= :start {bf}
            GROUP BY query HAVING SUM(impressions) >= 50
        ),
        prev_q AS (
            SELECT query,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(clicks) AS clicks
            FROM organic_performance WHERE data_date >= :prev_start AND data_date < :prev_end {bf}
            GROUP BY query HAVING SUM(impressions) >= 50
        )
        SELECT c.query, c.avg_position AS current_pos, p.avg_position AS prev_pos,
               c.clicks, c.impressions,
               (c.avg_position - p.avg_position) AS position_change,
               CASE WHEN p.clicks > 0 THEN ROUND(((c.clicks - p.clicks)::numeric / p.clicks) * 100, 1) ELSE 0 END AS click_change_pct
        FROM current_q c INNER JOIN prev_q p ON c.query = p.query
        WHERE c.avg_position - p.avg_position >= 5
        ORDER BY c.impressions DESC LIMIT 15
    """), {"start": start, "prev_start": prev_start, "prev_end": prev_end}).mappings().all()

    for r in rows:
        drop = int(r["position_change"])
        insights.append({
            "id": f"refresh_{len(insights)}",
            "type": "content_to_refresh",
            "category": "organic",
            "priority": "high" if drop >= 10 else "medium",
            "title": f'Refresh content about: "{r["query"]}"',
            "description": f'Dropped {drop} positions (was #{int(r["prev_pos"])}, now #{int(r["current_pos"])}). {r["impressions"]:,} impressions.',
            "metric": {"position_change": drop, "current_position": int(r["current_pos"]), "impressions": r["impressions"]},
            "action": f'Refresh content about "{r["query"]}" — dropped {drop} positions over the last {days} days. Update or expand the content to regain ranking.',
            "affected_entity": r["query"],
            "source": "GSC organic data",
        })

    # ── 4. Content Gap (competitors bid, FO has no organic) ─────
    try:
        rows = db.execute(text(f"""
            SELECT pko.keyword, COUNT(DISTINCT pko.advertiser_domain) AS competitor_count,
                   ROUND(AVG(pko.estimated_cpc)::numeric, 2) AS avg_cpc,
                   MAX(pko.estimated_volume) AS volume
            FROM paid_keyword_observations pko
            WHERE pko.advertiser_domain != 'firstorion.com'
              AND pko.keyword NOT IN (
                  SELECT DISTINCT query FROM organic_performance WHERE data_date >= :start
              )
              {_branded_exclusion('pko.keyword')}
            GROUP BY pko.keyword
            HAVING COUNT(DISTINCT pko.advertiser_domain) >= 2
            ORDER BY MAX(pko.estimated_volume) DESC NULLS LAST LIMIT 15
        """), {"start": start}).mappings().all()

        for r in rows:
            insights.append({
                "id": f"gap_{len(insights)}",
                "type": "content_gap",
                "category": "organic",
                "priority": "high" if r["competitor_count"] >= 3 else "medium",
                "title": f'Build content around: "{r["keyword"]}"',
                "description": f'{r["competitor_count"]} competitors actively advertising. FO has no organic presence for this term.',
                "metric": {"competitors": r["competitor_count"], "est_volume": r["volume"], "avg_cpc": float(r["avg_cpc"] or 0)},
                "action": f'Build content around "{r["keyword"]}" — {r["competitor_count"]} competitors are paying to advertise on this term, but FO has zero organic visibility.',
                "affected_entity": r["keyword"],
                "source": "SERP competitor data",
            })
    except Exception:
        pass  # paid_keyword_observations may be empty

    # ═══════════════════════════════════════════════════════════════
    # Sort and summarize
    # ═══════════════════════════════════════════════════════════════

    priority_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda i: (priority_order.get(i["priority"], 3), i["category"]))

    summary = {
        "total": len(insights),
        "high": sum(1 for i in insights if i["priority"] == "high"),
        "medium": sum(1 for i in insights if i["priority"] == "medium"),
        "low": sum(1 for i in insights if i["priority"] == "low"),
        "by_category": {},
    }
    for cat in ["organic"]:
        summary["by_category"][cat] = sum(1 for i in insights if i["category"] == cat)

    result = {"summary": summary, "insights": insights}
    # Cache the result
    from services.summaries import set_cached
    set_cached(db, f"insights:{days}", result)
    return result

"""Insights engine — surfaces content opportunities across all data sources.

Every insight answers: "What specific content should FO create, expand, or refresh?"
No SEO tactics. No vague generalizations. Content opportunities only.

Categories: organic (4), paid (3), ai_visibility (3)
Competitor and cross-channel removed — data visible in Paid > Competitor Ads tab.
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


def _branded_exclusion_st() -> str:
    """Same but for search_terms table (column is search_term, not query)."""
    return _branded_exclusion("search_term")


def _url_exclusion(col: str = "page") -> str:
    """SQL fragment to exclude internal/non-website URLs."""
    clauses = " AND ".join([f"{col} NOT LIKE '%{u}%'" for u in _EXCLUDED_URL_PATTERNS])
    return f"AND {clauses}"


# ── Main computation ─────────────────────────────────────────────

def _compute_insights(days: int, db: Session):
    start = _period(days)
    prev_start, prev_end = _prev_period(days)
    bf = _branded_exclusion()
    bf_st = _branded_exclusion_st()
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
    # PAID — 3 types, opportunity-focused
    # ═══════════════════════════════════════════════════════════════

    # ── 5. Top Converting Search Terms ──────────────────────────
    # Surface which search terms actually drive conversions — content topic signals
    rows = db.execute(text(f"""
        SELECT search_term, SUM(clicks) AS clicks, SUM(conversions) AS conversions,
               SUM(impressions) AS impressions,
               CASE WHEN SUM(clicks) > 0
                    THEN ROUND(SUM(conversions)::numeric / SUM(clicks) * 100, 1)
                    ELSE 0 END AS conv_rate,
               CASE WHEN SUM(conversions) > 0
                    THEN ROUND((SUM(cost_micros) / 1000000.0 / SUM(conversions))::numeric, 2)
                    ELSE 0 END AS cost_per_conv
        FROM search_terms WHERE data_date >= :start {bf_st}
        GROUP BY search_term
        HAVING SUM(conversions) > 0
        ORDER BY SUM(conversions) DESC LIMIT 10
    """), {"start": start}).mappings().all()

    for r in rows:
        conv = float(r["conversions"])
        rate = float(r["conv_rate"])
        insights.append({
            "id": f"converting_{len(insights)}",
            "type": "top_converting",
            "category": "paid",
            "priority": "high" if conv >= 5 else "medium" if conv >= 2 else "low",
            "title": f'Top converter: "{r["search_term"]}"',
            "description": f'{conv:.0f} conversions at {rate}% conversion rate ({r["clicks"]:,} clicks).',
            "metric": {"conversions": conv, "conv_rate": rate, "clicks": r["clicks"], "cost_per_conversion": float(r["cost_per_conv"])},
            "action": f'"{r["search_term"]}" converts at {rate}% — this topic resonates. Build organic content around this theme to capture traffic without ad spend.',
            "affected_entity": r["search_term"],
            "source": "Google Ads search terms",
        })

    # ── 6. High-Traffic Zero-Conversion Terms ───────────────────
    # Terms getting clicks but no conversions — content mismatch or negative keyword candidates
    rows = db.execute(text(f"""
        SELECT search_term, SUM(clicks) AS clicks,
               SUM(cost_micros) / 1000000.0 AS cost,
               SUM(impressions) AS impressions
        FROM search_terms WHERE data_date >= :start {bf_st}
        GROUP BY search_term
        HAVING SUM(conversions) = 0 AND SUM(clicks) >= 10
        ORDER BY SUM(clicks) DESC LIMIT 10
    """), {"start": start}).mappings().all()

    for r in rows:
        insights.append({
            "id": f"nonconv_{len(insights)}",
            "type": "zero_conversion",
            "category": "paid",
            "priority": "medium" if r["clicks"] >= 25 else "low",
            "title": f'No conversions: "{r["search_term"]}" ({r["clicks"]:,} clicks)',
            "description": f'{r["clicks"]:,} clicks, {r["impressions"]:,} impressions, $0 return. Landing page may not match search intent.',
            "metric": {"clicks": r["clicks"], "cost": float(r["cost"]), "impressions": r["impressions"]},
            "action": f'"{r["search_term"]}" gets traffic but no conversions. Check if the landing page matches search intent, or add as a negative keyword to save budget.',
            "affected_entity": r["search_term"],
            "source": "Google Ads search terms",
        })

    # ── 7. Campaign Efficiency Comparison ───────────────────────
    # Compare conversion rates across campaigns to find underperformers
    rows = db.execute(text("""
        SELECT campaign_name,
               SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               SUM(conversions) AS conversions,
               CASE WHEN SUM(clicks) > 0
                    THEN ROUND(SUM(conversions)::numeric / SUM(clicks) * 100, 1)
                    ELSE 0 END AS conv_rate,
               CASE WHEN SUM(clicks) > 0
                    THEN ROUND(SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0, 2)
                    ELSE 0 END AS cpc
        FROM paid_performance WHERE data_date >= :start
        GROUP BY campaign_name
        HAVING SUM(clicks) >= 20
        ORDER BY SUM(conversions)::numeric / NULLIF(SUM(clicks), 0) ASC LIMIT 5
    """), {"start": start}).mappings().all()

    # Get overall avg conversion rate for comparison
    avg_cr = db.execute(text("""
        SELECT CASE WHEN SUM(clicks) > 0
                    THEN ROUND(SUM(conversions)::numeric / SUM(clicks) * 100, 1) ELSE 0 END AS avg_rate
        FROM paid_performance WHERE data_date >= :start
    """), {"start": start}).scalar() or 0

    for r in rows:
        rate = float(r["conv_rate"])
        if rate < float(avg_cr) * 0.5 and r["clicks"] >= 20:
            insights.append({
                "id": f"campaign_eff_{len(insights)}",
                "type": "campaign_efficiency",
                "category": "paid",
                "priority": "medium",
                "title": f'Low conversion rate: "{r["campaign_name"]}"',
                "description": f'{rate}% conversion rate vs {avg_cr}% account average. {r["clicks"]:,} clicks, {float(r["conversions"]):.0f} conversions.',
                "metric": {"conv_rate": rate, "avg_conv_rate": float(avg_cr), "clicks": r["clicks"], "cpc": float(r["cpc"])},
                "action": f'"{r["campaign_name"]}" converts at {rate}% vs your {avg_cr}% average. Review ad copy and landing page alignment, or reallocate budget to higher-converting campaigns.',
                "affected_entity": r["campaign_name"],
                "source": "Google Ads data",
            })

    # ═══════════════════════════════════════════════════════════════
    # AI VISIBILITY — 3 types, content-focused
    # ═══════════════════════════════════════════════════════════════

    # ── 8. Platform Content Gap ─────────────────────────────────
    try:
        current_platforms = db.execute(text("""
            SELECT platform, ROUND(AVG(visibility_score)::numeric, 1) AS visibility,
                   ROUND(AVG(share_of_voice)::numeric, 4) AS sov
            FROM ai_visibility WHERE data_date >= :start
            GROUP BY platform
        """), {"start": start}).mappings().all()

        if current_platforms:
            avg_vis = sum(float(p["visibility"]) for p in current_platforms) / len(current_platforms)
            for p in current_platforms:
                vis = float(p["visibility"])
                if vis < avg_vis * 0.7 and avg_vis > 0:
                    gap_pct = round((1 - vis / avg_vis) * 100, 1)
                    insights.append({
                        "id": f"platform_gap_{len(insights)}",
                        "type": "platform_content_gap",
                        "category": "ai_visibility",
                        "priority": "high" if gap_pct >= 50 else "medium",
                        "title": f'Low visibility on {p["platform"]}',
                        "description": f'Visibility {vis}% vs {avg_vis:.1f}% average across platforms. SOV: {float(p["sov"])*100:.1f}%.',
                        "metric": {"platform": p["platform"], "visibility": vis, "avg_visibility": avg_vis, "sov": float(p["sov"])},
                        "action": f'Create content optimized for {p["platform"]} — visibility is {gap_pct}% below your cross-platform average. Research what content format {p["platform"]} favors.',
                        "affected_entity": p["platform"],
                        "source": "Profound AI data",
                    })
    except Exception:
        pass

    # ── 9. Citation Opportunity (good organic rank, no AI citation)
    uf = _url_exclusion("op.page")
    try:
        rows = db.execute(text(f"""
            SELECT op.page,
                   ROUND((SUM(op.position * op.impressions) / NULLIF(SUM(op.impressions), 0))::numeric, 0) AS avg_position,
                   SUM(op.clicks) AS clicks
            FROM organic_performance op
            WHERE op.data_date >= :start {uf}
            GROUP BY op.page
            HAVING ROUND((SUM(op.position * op.impressions) / NULLIF(SUM(op.impressions), 0))::numeric, 0) <= 10
               AND SUM(op.clicks) >= 20
               AND op.page NOT IN (SELECT DISTINCT cited_url FROM ai_citations WHERE data_date >= :start)
            ORDER BY SUM(op.clicks) DESC LIMIT 10
        """), {"start": start}).mappings().all()

        for r in rows:
            insights.append({
                "id": f"citation_{len(insights)}",
                "type": "citation_opportunity",
                "category": "ai_visibility",
                "priority": "medium",
                "title": f'Citation opportunity: {_strip_domain(r["page"])}',
                "description": f'Ranks #{int(r["avg_position"])} organically with {r["clicks"]:,} clicks but has zero AI citations.',
                "metric": {"position": int(r["avg_position"]), "clicks": r["clicks"]},
                "action": f'Page "{_strip_domain(r["page"])}" ranks well organically but isn\'t cited by AI engines. Add structured Q&A content, clear factual statements, and data that AI can extract.',
                "affected_entity": r["page"],
                "source": "GSC + Profound data",
            })
    except Exception:
        pass

    # ── 10. AI Content Gap (competitors cited, FO not) ──────────
    try:
        rows = db.execute(text("""
            SELECT ac.category_name,
                   ROUND(AVG(ac.share_of_voice)::numeric, 4) AS comp_sov,
                   COUNT(DISTINCT ac.competitor_domain) AS comp_count
            FROM ai_competitors ac
            WHERE ac.data_date >= :start
              AND ac.category_name NOT IN (
                  SELECT DISTINCT category_name FROM ai_visibility
                  WHERE data_date >= :start AND share_of_voice > 0.05
              )
            GROUP BY ac.category_name
            HAVING AVG(ac.share_of_voice) > 0.03
            ORDER BY AVG(ac.share_of_voice) DESC LIMIT 10
        """), {"start": start}).mappings().all()

        for r in rows:
            insights.append({
                "id": f"ai_gap_{len(insights)}",
                "type": "ai_content_gap",
                "category": "ai_visibility",
                "priority": "high" if float(r["comp_sov"]) > 0.08 else "medium",
                "title": f'AI content gap: "{r["category_name"]}"',
                "description": f'{r["comp_count"]} competitors have AI visibility in this category. FO has little to no presence.',
                "metric": {"category": r["category_name"], "competitor_sov": float(r["comp_sov"]), "competitors": r["comp_count"]},
                "action": f'Create content about "{r["category_name"]}" — {r["comp_count"]} competitors are cited by AI engines in this category but FO is not.',
                "affected_entity": r["category_name"],
                "source": "Profound AI data",
            })
    except Exception:
        pass

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
    for cat in ["organic", "paid", "ai_visibility"]:
        summary["by_category"][cat] = sum(1 for i in insights if i["category"] == cat)

    result = {"summary": summary, "insights": insights}
    # Cache the result
    from services.summaries import set_cached
    set_cached(db, f"insights:{days}", result)
    return result

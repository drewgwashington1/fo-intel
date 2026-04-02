"""Pre-compute and cache dashboard responses in summary_cache table.

Core principle: never query raw tables at request time.
All dashboard GET endpoints read from summary_cache with a single indexed lookup.
This module handles building and refreshing those cached responses.
"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db_session

logger = logging.getLogger(__name__)

SUMMARY_TTL_HOURS = 24  # Summaries are fresh for 24 hours
PIPELINE_STALE_DAYS = 14  # Pipeline data is stale after 14 days

# All period variants we pre-compute for
PERIODS = [7, 30, 90, 365]
BRAND_VARIANTS = [None, "branded", "non-branded"]


def _now():
    return datetime.now(timezone.utc)


def _stale_after():
    return _now() + timedelta(hours=SUMMARY_TTL_HOURS)


# ── Cache read/write ─────────────────────────────────────────────

def get_cached(db: Session, cache_key: str):
    """Read from summary_cache. Returns response_json or None if missing/stale."""
    row = db.execute(text(
        "SELECT response_json, stale_after FROM summary_cache WHERE cache_key = :key"
    ), {"key": cache_key}).first()
    if row and row.stale_after and row.stale_after > _now():
        return row.response_json
    return None


def set_cached(db: Session, cache_key: str, response):
    """Upsert into summary_cache."""
    db.execute(text("""
        INSERT INTO summary_cache (cache_key, response_json, computed_at, stale_after)
        VALUES (:key, cast(:val as jsonb), :now, :stale)
        ON CONFLICT (cache_key) DO UPDATE
        SET response_json = cast(EXCLUDED.response_json as jsonb),
            computed_at = EXCLUDED.computed_at,
            stale_after = EXCLUDED.stale_after
    """), {
        "key": cache_key,
        "val": __import__("json").dumps(response, default=str),
        "now": _now(),
        "stale": _stale_after(),
    })
    db.commit()


def invalidate_scope(db: Session, scope: str):
    """Delete cached entries matching a scope prefix (e.g. 'organic', 'paid', 'all')."""
    if scope == "all":
        db.execute(text("DELETE FROM summary_cache"))
    else:
        db.execute(text("DELETE FROM summary_cache WHERE cache_key LIKE :prefix"), {"prefix": f"{scope}%"})
    db.commit()


# ── Keyword Query Map ────────────────────────────────────────────

def rebuild_keyword_map(db: Session, list_name: str):
    """Re-compute keyword_query_map for a specific keyword list (tag name).
    Runs ILIKE once against distinct queries, not per-request.
    """
    logger.info(f"Rebuilding keyword_query_map for list: {list_name}")

    # Get terms for this list
    terms = db.execute(text(
        "SELECT term FROM keyword_lists WHERE list_name = :name"
    ), {"name": list_name}).fetchall()

    # Clear old mappings
    db.execute(text(
        "DELETE FROM keyword_query_map WHERE keyword_list_name = :name"
    ), {"name": list_name})

    if not terms:
        db.commit()
        return 0

    # Build ILIKE ANY array for batch matching against distinct queries
    term_patterns = [f"%{t[0]}%" for t in terms]
    db.execute(text("""
        INSERT INTO keyword_query_map (keyword_list_name, query, matched_at)
        SELECT :name, q.query, now()
        FROM (SELECT DISTINCT query FROM organic_performance) q
        WHERE q.query ILIKE ANY(:patterns)
        ON CONFLICT (keyword_list_name, query) DO NOTHING
    """), {"name": list_name, "patterns": term_patterns})
    db.commit()

    count = db.execute(text(
        "SELECT COUNT(*) FROM keyword_query_map WHERE keyword_list_name = :name"
    ), {"name": list_name}).scalar()
    logger.info(f"keyword_query_map for '{list_name}': {count} queries matched")
    return count


def rebuild_category_map(db: Session, category: str):
    """Re-compute keyword_query_map for a category (branded / non-branded).
    Aggregates all terms with that category across all tags.
    """
    logger.info(f"Rebuilding keyword_query_map for category: {category}")

    terms = db.execute(text(
        "SELECT term FROM keyword_lists WHERE category = :cat"
    ), {"cat": category}).fetchall()

    # Use category name as the keyword_list_name in the map
    db.execute(text(
        "DELETE FROM keyword_query_map WHERE keyword_list_name = :cat"
    ), {"cat": category})

    if not terms:
        db.commit()
        return 0

    term_patterns = [f"%{t[0]}%" for t in terms]
    db.execute(text("""
        INSERT INTO keyword_query_map (keyword_list_name, query, matched_at)
        SELECT :cat, q.query, now()
        FROM (SELECT DISTINCT query FROM organic_performance) q
        WHERE q.query ILIKE ANY(:patterns)
        ON CONFLICT (keyword_list_name, query) DO NOTHING
    """), {"cat": category, "patterns": term_patterns})
    db.commit()

    count = db.execute(text(
        "SELECT COUNT(*) FROM keyword_query_map WHERE keyword_list_name = :cat"
    ), {"cat": category}).scalar()
    logger.info(f"keyword_query_map for category '{category}': {count} queries matched")
    return count


def rebuild_all_keyword_maps(db: Session):
    """Rebuild keyword_query_map for all tag names AND both categories."""
    lists = db.execute(text(
        "SELECT DISTINCT list_name FROM keyword_lists"
    )).fetchall()
    for row in lists:
        rebuild_keyword_map(db, row[0])
    # Also rebuild category-level maps
    rebuild_category_map(db, "branded")
    rebuild_category_map(db, "non-branded")


# ── Keyword-filtered query helper ────────────────────────────────

def _brand_filter_empty_check(db: Session, brand: str) -> str:
    """Returns SQL WHERE fragment to filter organic queries by keyword category.
    Uses keyword_query_map (fast) if available, otherwise falls back to
    a direct subquery against keyword_lists (always current, never stale).
    Returns 'AND 1=0' if no keywords exist for this category.
    """
    if brand is None or brand == "all":
        return ""
    count = db.execute(text(
        "SELECT COUNT(*) FROM keyword_lists WHERE category = :cat"
    ), {"cat": brand}).scalar()
    if not count:
        return "AND 1=0"
    # Use keyword_query_map if it has entries for this category
    map_count = db.execute(text(
        "SELECT COUNT(*) FROM keyword_query_map WHERE keyword_list_name = :name"
    ), {"name": brand}).scalar()
    if map_count:
        return (
            f"AND query IN (SELECT query FROM keyword_query_map "
            f"WHERE keyword_list_name = '{brand}')"
        )
    # Map not built yet — fall back to direct ILIKE against keyword_lists
    # This is slower but always works immediately after adding keywords
    return (
        f"AND EXISTS (SELECT 1 FROM keyword_lists kl "
        f"WHERE kl.category = '{brand}' AND query ILIKE '%' || kl.term || '%')"
    )


def _tag_filter(db: Session, tag: str) -> str:
    """Return SQL WHERE fragment to filter by keyword tag (list_name).
    Uses keyword_query_map when available, falls back to direct ILIKE.
    """
    if not tag or tag == "all":
        return ""
    count = db.execute(text(
        "SELECT COUNT(*) FROM keyword_lists WHERE list_name = :name"
    ), {"name": tag}).scalar()
    if not count:
        return "AND 1=0"
    map_count = db.execute(text(
        "SELECT COUNT(*) FROM keyword_query_map WHERE keyword_list_name = :name"
    ), {"name": tag}).scalar()
    if map_count:
        return (
            f"AND query IN (SELECT query FROM keyword_query_map "
            f"WHERE keyword_list_name = '{tag}')"
        )
    return (
        f"AND EXISTS (SELECT 1 FROM keyword_lists kl "
        f"WHERE kl.list_name = '{tag}' AND query ILIKE '%' || kl.term || '%')"
    )


def _combined_filter(db: Session, brand: str, tag: str) -> str:
    """Combine brand (category) and tag filters."""
    return _brand_filter_empty_check(db, brand) + " " + _tag_filter(db, tag)


# ── Summary Builders ─────────────────────────────────────────────
# Each function computes one endpoint's response from raw tables
# and stores it in summary_cache.

def _period(days: int):
    from datetime import date
    return date.today() - timedelta(days=days)


def _prev_period(days: int):
    from datetime import date
    end = _period(days)
    start = end - timedelta(days=days)
    return start, end


def build_organic_overview(db: Session, days: int, brand: str, tag: str = None):
    key = f"organic_overview:{days}:{brand or 'all'}:{tag or 'all'}"
    start = _period(days)
    prev_start, prev_end = _prev_period(days)
    bf = _combined_filter(db, brand, tag)

    current = db.execute(text(f"""
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
        FROM organic_performance WHERE data_date >= :start {bf}
    """), {"start": start}).mappings().first()

    previous = db.execute(text(f"""
        SELECT
            COALESCE(SUM(clicks), 0) AS total_clicks,
            COALESCE(SUM(impressions), 0) AS total_impressions,
            CASE WHEN SUM(impressions) > 0
                 THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4)
                 ELSE 0 END AS avg_ctr,
            CASE WHEN SUM(impressions) > 0
                 THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1)
                 ELSE 0 END AS avg_position
        FROM organic_performance WHERE data_date >= :prev_start AND data_date < :prev_end {bf}
    """), {"prev_start": prev_start, "prev_end": prev_end}).mappings().first()

    result = dict(current)
    result["prev_clicks"] = previous["total_clicks"]
    result["prev_impressions"] = previous["total_impressions"]
    result["prev_ctr"] = float(previous["avg_ctr"])
    result["prev_position"] = float(previous["avg_position"])
    set_cached(db, key, result)
    return result


def build_organic_timeline(db: Session, days: int):
    key = f"organic_timeline:{days}"
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
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_organic_top_queries(db: Session, days: int, brand: str, limit: int = 25, tag: str = None):
    key = f"organic_top_queries:{days}:{brand or 'all'}:{limit}:{tag or 'all'}"
    start = _period(days)
    prev_start, prev_end = _prev_period(days)
    bf = _combined_filter(db, brand, tag)

    rows = db.execute(text(f"""
        WITH current_q AS (
            SELECT query,
                   (ARRAY_AGG(page ORDER BY clicks DESC))[1] AS top_page,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                   CASE WHEN SUM(impressions) > 0
                        THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr
            FROM organic_performance WHERE data_date >= :start {bf}
            GROUP BY query
        ),
        prev_q AS (
            SELECT query,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(clicks) AS clicks
            FROM organic_performance WHERE data_date >= :prev_start AND data_date < :prev_end {bf}
            GROUP BY query
        )
        SELECT c.query, c.top_page, c.avg_position, c.impressions, c.clicks, c.ctr,
               p.clicks AS prev_clicks, p.avg_position AS prev_position
        FROM current_q c LEFT JOIN prev_q p ON c.query = p.query
        ORDER BY c.clicks DESC LIMIT :lim
    """), {"start": start, "prev_start": prev_start, "prev_end": prev_end, "lim": limit}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_organic_position_dist(db: Session, days: int, brand: str = None, tag: str = None):
    key = f"organic_position_dist:{days}:{brand or 'all'}:{tag or 'all'}"
    start = _period(days)
    bf = _combined_filter(db, brand, tag)
    rows = db.execute(text(f"""
        SELECT data_date,
               COUNT(*) FILTER (WHERE position <= 3) AS pos_1_3,
               COUNT(*) FILTER (WHERE position > 3 AND position <= 10) AS pos_4_10,
               COUNT(*) FILTER (WHERE position > 10 AND position <= 20) AS pos_11_20,
               COUNT(*) FILTER (WHERE position > 20 AND position <= 50) AS pos_21_50,
               COUNT(*) FILTER (WHERE position > 50) AS pos_51_plus
        FROM organic_performance WHERE data_date >= :start {bf}
        GROUP BY data_date ORDER BY data_date
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_organic_movements(db: Session, days: int, brand: str = None, tag: str = None):
    key = f"organic_movements:{days}:{brand or 'all'}:{tag or 'all'}"
    start = _period(days)
    prev_start, prev_end = _prev_period(days)
    bf = _combined_filter(db, brand, tag)

    rows = db.execute(text(f"""
        WITH current_period AS (
            SELECT query,
                   (ARRAY_AGG(page ORDER BY clicks DESC))[1] AS page,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(clicks) AS clicks
            FROM organic_performance WHERE data_date >= :start {bf}
            GROUP BY query
        ),
        prev_period AS (
            SELECT query,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(clicks) AS clicks
            FROM organic_performance WHERE data_date >= :prev_start AND data_date < :prev_end {bf}
            GROUP BY query
        ),
        combined AS (
            SELECT c.query, c.page, c.avg_position AS current_pos, p.avg_position AS prev_pos,
                   c.clicks AS current_clicks,
                   CASE
                     WHEN p.query IS NULL THEN 'new'
                     WHEN c.avg_position < p.avg_position THEN 'improved'
                     WHEN c.avg_position > p.avg_position THEN 'declined'
                     ELSE 'unchanged'
                   END AS movement
            FROM current_period c LEFT JOIN prev_period p ON c.query = p.query
            UNION ALL
            SELECT p.query, NULL, NULL, p.avg_position, p.clicks, 'lost'
            FROM prev_period p LEFT JOIN current_period c ON p.query = c.query
            WHERE c.query IS NULL
        )
        SELECT movement, query, page, current_pos, prev_pos, current_clicks
        FROM combined WHERE movement != 'unchanged'
        ORDER BY current_clicks DESC NULLS LAST LIMIT 50
    """), {"start": start, "prev_start": prev_start, "prev_end": prev_end}).mappings().all()

    details = {"new": [], "lost": [], "improved": [], "declined": []}
    counts = {"new": 0, "lost": 0, "improved": 0, "declined": 0}
    seen = set()
    for r in rows:
        q = r["query"]
        m = r["movement"]
        dedup_key = f"{m}:{q}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        counts[m] = counts.get(m, 0) + 1
        details.setdefault(m, []).append(dict(r))

    result = {"summary": counts, "details": details}
    set_cached(db, key, result)
    return result


def build_organic_top_pages(db: Session, days: int, limit: int = 20, brand: str = None, tag: str = None):
    key = f"organic_top_pages:{days}:{limit}:{brand or 'all'}:{tag or 'all'}"
    start = _period(days)
    bf = _combined_filter(db, brand, tag)
    rows = db.execute(text(f"""
        SELECT page, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               CASE WHEN SUM(impressions) > 0
                    THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1) ELSE 0 END AS avg_position,
               COUNT(DISTINCT query) AS keywords,
               CASE WHEN SUM(impressions) > 0
                    THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr
        FROM organic_performance WHERE data_date >= :start {bf}
        GROUP BY page ORDER BY clicks DESC LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_organic_devices(db: Session, days: int, brand: str = None, tag: str = None):
    key = f"organic_devices:{days}:{brand or 'all'}:{tag or 'all'}"
    start = _period(days)
    bf = _combined_filter(db, brand, tag)
    rows = db.execute(text(f"""
        SELECT device, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               CASE WHEN SUM(impressions) > 0
                    THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr
        FROM organic_performance WHERE data_date >= :start {bf}
        GROUP BY device ORDER BY clicks DESC
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_organic_countries(db: Session, days: int, brand: str = None, tag: str = None):
    key = f"organic_countries:{days}:{brand or 'all'}:{tag or 'all'}"
    start = _period(days)
    bf = _combined_filter(db, brand, tag)
    rows = db.execute(text(f"""
        SELECT country, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               CASE WHEN SUM(impressions) > 0
                    THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr,
               CASE WHEN SUM(impressions) > 0
                    THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1) ELSE 0 END AS avg_position
        FROM organic_performance WHERE data_date >= :start {bf}
        GROUP BY country ORDER BY clicks DESC
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


# ── Organic Competitors (from SERP data) ────────────────────────

def build_organic_competitors(db: Session, days: int = 90):
    """Build competitor overlap analysis from organic_serp_results.
    Shows which domains compete for the same keywords we rank for.
    """
    key = f"organic_competitors:{days}"

    # Check if organic_serp_results table has data
    try:
        has_data = db.execute(text(
            "SELECT 1 FROM organic_serp_results LIMIT 1"
        )).first()
    except Exception:
        return []

    if not has_data:
        return []

    start = _period(days)

    # Get our keyword count for overlap %
    our_keywords = db.execute(text("""
        SELECT COUNT(DISTINCT query) FROM organic_performance WHERE data_date >= :start
    """), {"start": start}).scalar() or 1

    # Competitor domains ranked by keyword overlap with our queries
    # Only show tracked competitors
    tracked = db.execute(text(
        "SELECT domain FROM tracked_competitors"
    )).fetchall()
    tracked_domains = [r[0] for r in tracked]

    if not tracked_domains:
        set_cached(db, key, [])
        return []

    rows = db.execute(text("""
        WITH our_queries AS (
            SELECT DISTINCT query FROM organic_performance WHERE data_date >= :start
        ),
        competitor_rankings AS (
            SELECT osr.domain,
                   osr.keyword,
                   MIN(osr.position) AS best_position
            FROM organic_serp_results osr
            JOIN our_queries oq ON LOWER(osr.keyword) = LOWER(oq.query)
            WHERE osr.observed_date >= :start
              AND osr.domain = ANY(:domains)
            GROUP BY osr.domain, osr.keyword
        ),
        fo_on_shared AS (
            SELECT cr.domain AS competitor_domain,
                   cr.keyword,
                   MIN(op.position) AS fo_position
            FROM competitor_rankings cr
            JOIN organic_performance op ON LOWER(op.query) = LOWER(cr.keyword)
            WHERE op.data_date >= :start
            GROUP BY cr.domain, cr.keyword
        )
        SELECT cr.domain,
               COUNT(DISTINCT cr.keyword) AS common_keywords,
               ROUND(AVG(cr.best_position)::numeric, 1) AS avg_position,
               ROUND(AVG(fs.fo_position)::numeric, 1) AS fo_avg_position,
               COUNT(DISTINCT cr.keyword) FILTER (WHERE cr.best_position <= 3) AS top3,
               COUNT(DISTINCT cr.keyword) FILTER (WHERE cr.best_position <= 10) AS top10,
               COUNT(DISTINCT cr.keyword) FILTER (WHERE cr.best_position < fs.fo_position) AS competitor_wins,
               COUNT(DISTINCT cr.keyword) FILTER (WHERE cr.best_position >= fs.fo_position) AS fo_wins
        FROM competitor_rankings cr
        LEFT JOIN fo_on_shared fs ON fs.competitor_domain = cr.domain AND LOWER(fs.keyword) = LOWER(cr.keyword)
        GROUP BY cr.domain
        ORDER BY common_keywords DESC
    """), {"start": start, "domains": tracked_domains}).mappings().all()

    found = {r["domain"] for r in rows}
    result = []
    for r in rows:
        d = dict(r)
        d["avg_position"] = float(d["avg_position"] or 0)
        d["fo_avg_position"] = float(d["fo_avg_position"] or 0)
        d["common_keywords"] = int(d["common_keywords"])
        d["top3"] = int(d["top3"])
        d["top10"] = int(d["top10"])
        d["competitor_wins"] = int(d["competitor_wins"] or 0)
        d["fo_wins"] = int(d["fo_wins"] or 0)
        result.append(d)

    # Include tracked competitors with no SERP data yet (show as 0)
    for domain in tracked_domains:
        if domain not in found:
            result.append({
                "domain": domain,
                "common_keywords": 0,
                "avg_position": 0,
                "fo_avg_position": 0,
                "top3": 0,
                "top10": 0,
                "competitor_wins": 0,
                "fo_wins": 0,
            })

    set_cached(db, key, result)
    return result


# ── Paid builders ────────────────────────────────────────────────

def build_paid_overview(db: Session, days: int):
    key = f"paid_overview:{days}"
    start = _period(days)
    prev_start, prev_end = _prev_period(days)

    current = db.execute(text("""
        SELECT COALESCE(SUM(cost_micros), 0) / 1000000.0 AS total_spend,
               COALESCE(AVG(impression_share), 0) AS avg_impression_share,
               CASE WHEN SUM(clicks) > 0 THEN SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0 ELSE 0 END AS avg_cpc,
               COALESCE(SUM(clicks), 0) AS total_clicks,
               COALESCE(SUM(impressions), 0) AS total_impressions,
               COALESCE(SUM(conversions), 0) AS total_conversions,
               COALESCE(AVG(lost_is_budget), 0) AS avg_lost_budget,
               COALESCE(AVG(lost_is_rank), 0) AS avg_lost_rank
        FROM paid_performance WHERE data_date >= :start
    """), {"start": start}).mappings().first()

    previous = db.execute(text("""
        SELECT COALESCE(SUM(cost_micros), 0) / 1000000.0 AS total_spend,
               COALESCE(AVG(impression_share), 0) AS avg_impression_share,
               CASE WHEN SUM(clicks) > 0 THEN SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0 ELSE 0 END AS avg_cpc,
               COALESCE(SUM(clicks), 0) AS total_clicks,
               COALESCE(SUM(impressions), 0) AS total_impressions,
               COALESCE(SUM(conversions), 0) AS total_conversions
        FROM paid_performance WHERE data_date >= :prev_start AND data_date < :prev_end
    """), {"prev_start": prev_start, "prev_end": prev_end}).mappings().first()

    tc = db.execute(text("""
        SELECT COUNT(*) AS total_ads, COUNT(*) FILTER (WHERE is_active) AS active_ads
        FROM competitor_ads WHERE competitor_domain = 'firstorion.com'
    """)).mappings().first()

    result = dict(current)
    result["prev_spend"] = float(previous["total_spend"])
    result["prev_clicks"] = previous["total_clicks"]
    result["prev_impressions"] = previous["total_impressions"]
    result["prev_cpc"] = float(previous["avg_cpc"])
    result["prev_conversions"] = float(previous["total_conversions"])
    result["prev_impression_share"] = float(previous["avg_impression_share"])
    result["tc_total_ads"] = tc["total_ads"]
    result["tc_active_ads"] = tc["active_ads"]
    set_cached(db, key, result)
    return result


def build_paid_campaigns(db: Session, days: int):
    key = f"paid_campaigns:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT campaign_name, SUM(cost_micros) / 1000000.0 AS spend,
               SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               SUM(conversions) AS conversions,
               CASE WHEN SUM(clicks) > 0 THEN ROUND(SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0, 2) ELSE 0 END AS cpc,
               AVG(impression_share) AS avg_is,
               AVG(lost_is_budget) AS avg_lost_budget,
               AVG(lost_is_rank) AS avg_lost_rank
        FROM paid_performance WHERE data_date >= :start
        GROUP BY campaign_name ORDER BY spend DESC
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_paid_search_terms(db: Session, days: int, limit: int = 25):
    key = f"paid_search_terms:{days}:{limit}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT st.search_term, st.match_type,
               SUM(st.clicks) AS clicks, SUM(st.cost_micros) / 1000000.0 AS cost,
               SUM(st.impressions) AS volume, SUM(st.conversions) AS conversions,
               CASE WHEN SUM(st.clicks) > 0
                    THEN ROUND(SUM(st.cost_micros)::numeric / SUM(st.clicks) / 1000000.0, 2)
                    ELSE 0 END AS cpc,
               org.organic_traffic, org.organic_position, org.top_url
        FROM search_terms st
        LEFT JOIN LATERAL (
            SELECT SUM(op.clicks) AS organic_traffic,
                   ROUND((SUM(op.position * op.impressions) / NULLIF(SUM(op.impressions), 0))::numeric, 1) AS organic_position,
                   (ARRAY_AGG(op.page ORDER BY op.clicks DESC))[1] AS top_url
            FROM organic_performance op
            WHERE op.query = st.search_term AND op.data_date >= :start
        ) org ON true
        WHERE st.data_date >= :start
        GROUP BY st.search_term, st.match_type, org.organic_traffic, org.organic_position, org.top_url
        ORDER BY clicks DESC LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_paid_timeline(db: Session, days: int):
    key = f"paid_timeline:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT data_date, SUM(cost_micros) / 1000000.0 AS spend,
               SUM(clicks) AS clicks, SUM(impressions) AS impressions,
               AVG(impression_share) AS avg_is, SUM(conversions) AS conversions
        FROM paid_performance WHERE data_date >= :start
        GROUP BY data_date ORDER BY data_date
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_paid_is_loss(db: Session, days: int):
    key = f"paid_is_loss:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT campaign_name,
               ROUND(AVG(impression_share)::numeric * 100, 1) AS is_pct,
               ROUND(AVG(lost_is_budget)::numeric * 100, 1) AS lost_budget_pct,
               ROUND(AVG(lost_is_rank)::numeric * 100, 1) AS lost_rank_pct,
               SUM(cost_micros) / 1000000.0 AS total_spend
        FROM paid_performance WHERE data_date >= :start
        GROUP BY campaign_name ORDER BY total_spend DESC
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_paid_pages(db: Session, days: int):
    key = f"paid_pages:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT op.page AS url,
               COUNT(DISTINCT st.search_term) AS ads_keywords,
               SUM(op.clicks) AS organic_traffic,
               SUM(op.impressions) AS impressions,
               CASE WHEN SUM(op.impressions) > 0
                    THEN ROUND(SUM(op.clicks)::numeric / SUM(op.impressions), 4) ELSE 0 END AS ctr,
               CASE WHEN SUM(op.impressions) > 0
                    THEN ROUND((SUM(op.position * op.impressions) / SUM(op.impressions))::numeric, 1) ELSE 0 END AS avg_position,
               COUNT(DISTINCT op.query) AS total_keywords
        FROM organic_performance op
        INNER JOIN search_terms st ON op.query = st.search_term
        WHERE op.data_date >= :start AND st.data_date >= :start
        GROUP BY op.page ORDER BY organic_traffic DESC LIMIT 50
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_paid_ads(db: Session):
    key = "paid_ads"
    rows = db.execute(text("""
        SELECT ad_id, ad_format, headline, description, destination_url, platforms, regions,
               first_shown_date, last_shown_date, days_running, is_active, advertiser_name, image_url
        FROM competitor_ads WHERE competitor_domain = 'firstorion.com'
        ORDER BY days_running DESC
    """)).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_paid_ad_formats(db: Session):
    key = "paid_ad_formats"
    rows = db.execute(text("""
        SELECT ad_format, COUNT(*) AS count,
               COUNT(*) FILTER (WHERE is_active) AS active_count
        FROM competitor_ads WHERE competitor_domain = 'firstorion.com'
        GROUP BY ad_format ORDER BY count DESC
    """)).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


# ── AI builders ──────────────────────────────────────────────────

def build_ai_overview(db: Session, days: int):
    key = f"ai_overview:{days}"
    start = _period(days)
    prev_start, prev_end = _prev_period(days)

    current = db.execute(text("""
        SELECT ROUND(AVG(visibility_score)::numeric, 1) AS avg_visibility,
               ROUND(AVG(share_of_voice)::numeric, 4) AS avg_sov,
               COALESCE(SUM(citation_count), 0) AS total_citations
        FROM ai_visibility WHERE data_date >= :start
    """), {"start": start}).mappings().first()

    previous = db.execute(text("""
        SELECT ROUND(AVG(visibility_score)::numeric, 1) AS avg_visibility,
               ROUND(AVG(share_of_voice)::numeric, 4) AS avg_sov,
               COALESCE(SUM(citation_count), 0) AS total_citations
        FROM ai_visibility WHERE data_date >= :prev_start AND data_date < :prev_end
    """), {"prev_start": prev_start, "prev_end": prev_end}).mappings().first()

    citation_count = db.execute(text(
        "SELECT COUNT(*) FROM ai_citations WHERE data_date >= :start"
    ), {"start": start}).scalar() or 0

    prev_citation_count = db.execute(text(
        "SELECT COUNT(*) FROM ai_citations WHERE data_date >= :prev_start AND data_date < :prev_end"
    ), {"prev_start": prev_start, "prev_end": prev_end}).scalar() or 0

    result = {
        "avg_visibility": float(current["avg_visibility"] or 0),
        "avg_sov": float(current["avg_sov"] or 0),
        "total_citations": citation_count,
        "prev_visibility": float(previous["avg_visibility"] or 0),
        "prev_sov": float(previous["avg_sov"] or 0),
        "prev_citations": prev_citation_count,
    }
    set_cached(db, key, result)
    return result


def build_ai_platforms(db: Session, days: int):
    key = f"ai_platforms:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT av.platform, ROUND(AVG(av.visibility_score)::numeric, 1) AS avg_visibility,
               ROUND(AVG(av.share_of_voice)::numeric, 4) AS avg_sov,
               COALESCE(c.citations, 0) AS citations
        FROM ai_visibility av
        LEFT JOIN (
            SELECT platform, COUNT(*) AS citations
            FROM ai_citations WHERE data_date >= :start
            GROUP BY platform
        ) c ON c.platform = av.platform
        WHERE av.data_date >= :start
        GROUP BY av.platform, c.citations ORDER BY avg_visibility DESC
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_ai_competitors(db: Session, days: int, limit: int = 15):
    key = f"ai_competitors:{days}:{limit}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT competitor_domain, ROUND(AVG(share_of_voice)::numeric, 4) AS avg_sov,
               COALESCE(SUM(citation_count), 0) AS citations
        FROM ai_competitors WHERE data_date >= :start
        GROUP BY competitor_domain ORDER BY avg_sov DESC LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_ai_sov_comparison(db: Session, days: int):
    key = f"ai_sov_comparison:{days}"
    start = _period(days)

    fo_rows = db.execute(text("""
        SELECT category_name, ROUND(AVG(share_of_voice)::numeric, 4) AS fo_sov
        FROM ai_visibility WHERE data_date >= :start
        GROUP BY category_name ORDER BY fo_sov DESC
    """), {"start": start}).mappings().all()

    comp_rows = db.execute(text("""
        SELECT category_name, competitor_domain, ROUND(AVG(share_of_voice)::numeric, 4) AS comp_sov
        FROM ai_competitors WHERE data_date >= :start
        AND competitor_domain IN (
            SELECT competitor_domain FROM ai_competitors WHERE data_date >= :start
            GROUP BY competitor_domain ORDER BY AVG(share_of_voice) DESC LIMIT 10
        )
        GROUP BY category_name, competitor_domain
    """), {"start": start}).mappings().all()

    result = {"fo": [dict(r) for r in fo_rows], "competitors": [dict(r) for r in comp_rows]}
    set_cached(db, key, result)
    return result


def build_ai_top_cited(db: Session, days: int, limit: int = 10):
    key = f"ai_top_cited:{days}:{limit}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT cited_url, COUNT(*) AS citation_count,
               COUNT(*) FILTER (WHERE sentiment = 'positive') AS positive,
               COUNT(*) FILTER (WHERE sentiment = 'neutral') AS neutral,
               COUNT(*) FILTER (WHERE sentiment = 'negative') AS negative,
               ROUND(COUNT(*) FILTER (WHERE sentiment = 'positive')::numeric / NULLIF(COUNT(*), 0), 2) AS positive_pct
        FROM ai_citations WHERE data_date >= :start
        GROUP BY cited_url ORDER BY citation_count DESC LIMIT :lim
    """), {"start": start, "lim": limit}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_ai_timeline(db: Session, days: int):
    key = f"ai_timeline:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT data_date, platform,
               ROUND(AVG(visibility_score)::numeric, 1) AS visibility,
               ROUND(AVG(share_of_voice)::numeric, 4) AS sov
        FROM ai_visibility WHERE data_date >= :start
        GROUP BY data_date, platform ORDER BY data_date
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


# ── Competitor builders ──────────────────────────────────────────

def build_competitors_overview(db: Session):
    key = "competitors_overview"
    row = db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE is_active) AS active_ads,
               COUNT(*) AS total_ads,
               MAX(days_running) AS longest_running,
               COUNT(*) FILTER (WHERE first_shown_date >= CURRENT_DATE - INTERVAL '7 days') AS new_this_week,
               COUNT(DISTINCT competitor_domain) AS competitors_tracked,
               ROUND(AVG(days_running)::numeric) AS avg_days_running
        FROM competitor_ads
    """)).mappings().first()
    result = dict(row)
    set_cached(db, key, result)
    return result


def build_competitors_by_domain(db: Session):
    key = "competitors_by_domain"
    rows = db.execute(text("""
        SELECT competitor_domain, advertiser_name,
               COUNT(*) FILTER (WHERE is_active) AS active_ads,
               COUNT(*) AS total_ads,
               MAX(days_running) AS max_days_running,
               ROUND(AVG(days_running)::numeric) AS avg_days_running,
               COUNT(DISTINCT ad_format) AS format_count
        FROM competitor_ads GROUP BY competitor_domain, advertiser_name
        ORDER BY active_ads DESC
    """)).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_competitors_longest_running(db: Session, limit: int = 20):
    key = f"competitors_longest_running:{limit}"
    rows = db.execute(text("""
        SELECT competitor_domain, advertiser_name, headline, description, ad_format,
               days_running, first_shown_date, destination_url, platforms
        FROM competitor_ads WHERE is_active
        ORDER BY days_running DESC LIMIT :lim
    """), {"lim": limit}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_competitors_new_this_week(db: Session):
    key = "competitors_new_this_week"
    rows = db.execute(text("""
        SELECT competitor_domain, advertiser_name, headline, description, ad_format,
               first_shown_date, destination_url, platforms, days_running
        FROM competitor_ads WHERE first_shown_date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY first_shown_date DESC
    """)).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_competitors_formats(db: Session):
    key = "competitors_formats"
    rows = db.execute(text("""
        SELECT ad_format, COUNT(*) AS count,
               COUNT(*) FILTER (WHERE is_active) AS active_count
        FROM competitor_ads GROUP BY ad_format ORDER BY count DESC
    """)).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


# ── Creatives builders ───────────────────────────────────────────

def build_creatives_overview(db: Session, days: int):
    key = f"creatives_overview:{days}"
    start = _period(days)
    prev_start, prev_end = _prev_period(days)

    current = db.execute(text("""
        SELECT COUNT(DISTINCT ad_id) AS total_creatives,
               COALESCE(SUM(impressions), 0) AS total_impressions,
               COALESCE(SUM(clicks), 0) AS total_clicks,
               CASE WHEN SUM(impressions) > 0 THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS avg_ctr,
               COALESCE(SUM(cost_micros), 0) / 1000000.0 AS total_spend,
               COALESCE(SUM(conversions), 0) AS total_conversions,
               CASE WHEN SUM(clicks) > 0 THEN ROUND(SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0, 2) ELSE 0 END AS avg_cpc,
               CASE WHEN SUM(clicks) > 0 THEN ROUND(SUM(conversions)::numeric / SUM(clicks), 4) ELSE 0 END AS conv_rate
        FROM ad_creative_performance WHERE data_date >= :start
    """), {"start": start}).mappings().first()

    previous = db.execute(text("""
        SELECT COALESCE(SUM(clicks), 0) AS prev_clicks,
               CASE WHEN SUM(impressions) > 0 THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS prev_ctr,
               COALESCE(SUM(conversions), 0) AS prev_conversions,
               COALESCE(SUM(cost_micros), 0) / 1000000.0 AS prev_spend
        FROM ad_creative_performance WHERE data_date >= :prev_start AND data_date < :prev_end
    """), {"prev_start": prev_start, "prev_end": prev_end}).mappings().first()

    result = {**dict(current), **dict(previous)}
    set_cached(db, key, result)
    return result


def build_creatives_performance(db: Session, days: int):
    key = f"creatives_performance:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT ad_id, MAX(ad_type) AS ad_type, MAX(campaign_type) AS campaign_type,
               MAX(headline_1) AS headline_1, MAX(headline_2) AS headline_2, MAX(headline_3) AS headline_3,
               MAX(description_1) AS description_1, MAX(description_2) AS description_2,
               MAX(final_url) AS final_url, MAX(campaign_name) AS campaign_name, MAX(ad_group_name) AS ad_group_name,
               SUM(impressions) AS impressions, SUM(clicks) AS clicks,
               CASE WHEN SUM(impressions) > 0 THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr,
               SUM(cost_micros) / 1000000.0 AS cost,
               CASE WHEN SUM(clicks) > 0 THEN ROUND(SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0, 2) ELSE 0 END AS cpc,
               SUM(conversions) AS conversions,
               CASE WHEN SUM(clicks) > 0 THEN ROUND(SUM(conversions)::numeric / SUM(clicks), 4) ELSE 0 END AS conv_rate,
               SUM(conversion_value) AS conv_value,
               COUNT(DISTINCT data_date) AS days_active
        FROM ad_creative_performance WHERE data_date >= :start
        GROUP BY ad_id ORDER BY clicks DESC
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_creatives_timeline(db: Session, days: int):
    key = f"creatives_timeline:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT data_date, SUM(impressions) AS impressions, SUM(clicks) AS clicks,
               CASE WHEN SUM(impressions) > 0 THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr,
               SUM(cost_micros) / 1000000.0 AS spend, SUM(conversions) AS conversions
        FROM ad_creative_performance WHERE data_date >= :start
        GROUP BY data_date ORDER BY data_date
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_creatives_by_campaign(db: Session, days: int):
    key = f"creatives_by_campaign:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT campaign_name, COUNT(DISTINCT ad_id) AS creatives,
               SUM(impressions) AS impressions, SUM(clicks) AS clicks,
               CASE WHEN SUM(impressions) > 0 THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr,
               SUM(cost_micros) / 1000000.0 AS cost, SUM(conversions) AS conversions,
               CASE WHEN SUM(clicks) > 0 THEN ROUND(SUM(conversions)::numeric / SUM(clicks), 4) ELSE 0 END AS conv_rate
        FROM ad_creative_performance WHERE data_date >= :start
        GROUP BY campaign_name ORDER BY clicks DESC
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_creatives_top_headlines(db: Session, days: int):
    key = f"creatives_top_headlines:{days}"
    start = _period(days)
    rows = db.execute(text("""
        SELECT headline_1, SUM(impressions) AS impressions, SUM(clicks) AS clicks,
               CASE WHEN SUM(impressions) > 0 THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr,
               SUM(conversions) AS conversions,
               CASE WHEN SUM(clicks) > 0 THEN ROUND(SUM(conversions)::numeric / SUM(clicks), 4) ELSE 0 END AS conv_rate,
               COUNT(DISTINCT ad_id) AS used_in_ads
        FROM ad_creative_performance WHERE data_date >= :start AND headline_1 IS NOT NULL
        GROUP BY headline_1 ORDER BY clicks DESC LIMIT 20
    """), {"start": start}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


# ── Master rebuild ───────────────────────────────────────────────

def rebuild_summaries(db: Session, scope: str = "all"):
    """Rebuild all cached summaries for a given scope."""
    logger.info(f"Rebuilding summaries: scope={scope}")

    if scope in ("all", "organic"):
        for days in PERIODS:
            build_organic_timeline(db, days)
            build_organic_position_dist(db, days)
            build_organic_movements(db, days)
            build_organic_top_pages(db, days)
            build_organic_devices(db, days)
            build_organic_countries(db, days)
            for brand in BRAND_VARIANTS:
                build_organic_overview(db, days, brand)
                build_organic_top_queries(db, days, brand)

    if scope in ("all", "paid"):
        for days in PERIODS:
            build_paid_overview(db, days)
            build_paid_campaigns(db, days)
            build_paid_search_terms(db, days)
            build_paid_timeline(db, days)
            build_paid_is_loss(db, days)
            build_paid_pages(db, days)
        build_paid_ads(db)
        build_paid_ad_formats(db)

    if scope in ("all", "ai"):
        for days in PERIODS:
            build_ai_overview(db, days)
            build_ai_platforms(db, days)
            build_ai_competitors(db, days)
            build_ai_sov_comparison(db, days)
            build_ai_top_cited(db, days)
            build_ai_timeline(db, days)

    if scope in ("all", "competitors"):
        build_competitors_overview(db)
        build_competitors_by_domain(db)
        build_competitors_longest_running(db)
        build_competitors_new_this_week(db)
        build_competitors_formats(db)

    if scope in ("all", "creatives"):
        for days in PERIODS:
            build_creatives_overview(db, days)
            build_creatives_performance(db, days)
            build_creatives_timeline(db, days)
            build_creatives_by_campaign(db, days)
            build_creatives_top_headlines(db, days)

    logger.info(f"Summary rebuild complete: scope={scope}")


def update_pipeline_status(db: Session, pipeline_name: str, rows_processed: int = 0):
    """Record that a pipeline just ran."""
    db.execute(text("""
        INSERT INTO pipeline_status (pipeline_name, last_run_at, rows_processed)
        VALUES (:name, :now, :rows)
        ON CONFLICT (pipeline_name) DO UPDATE
        SET last_run_at = EXCLUDED.last_run_at, rows_processed = EXCLUDED.rows_processed
    """), {"name": pipeline_name, "now": _now(), "rows": rows_processed})
    db.commit()


def get_stale_pipelines(db: Session) -> list[str]:
    """Return pipeline names that haven't run within the freshness window."""
    threshold = _now() - timedelta(days=PIPELINE_STALE_DAYS)
    all_pipelines = ["gsc", "ads", "creatives", "profound", "transparency"]

    rows = db.execute(text(
        "SELECT pipeline_name, last_run_at FROM pipeline_status"
    )).mappings().all()
    status = {r["pipeline_name"]: r["last_run_at"] for r in rows}

    stale = []
    for p in all_pipelines:
        if p not in status or status[p] < threshold:
            stale.append(p)
    return stale

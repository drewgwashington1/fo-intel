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
    For branded terms, also generates no-space variants to catch
    concatenated forms (e.g. "first orion" also matches "firstorion").
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

    # Build patterns including no-space variants for multi-word terms
    term_patterns = []
    for t in terms:
        term = t[0]
        term_patterns.append(f"%{term}%")
        # Add no-space variant for multi-word terms (e.g. "first orion" → "firstorion")
        no_space = term.replace(" ", "")
        if no_space != term:
            term_patterns.append(f"%{no_space}%")

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

    - branded: include only queries matching branded terms
    - non-branded: EXCLUDE queries matching branded terms (the complement)

    Uses keyword_query_map (fast) if available, otherwise falls back to
    a direct subquery against keyword_lists (always current, never stale).
    """
    if brand is None or brand == "all":
        return ""

    if brand == "non-branded":
        # Non-branded = everything NOT matching branded terms
        # Always exclude core brand fragments regardless of keyword_lists
        core_brand_exclusion = (
            "AND LOWER(query) NOT LIKE '%orion%' "
            "AND LOWER(query) NOT LIKE '%firstorion%' "
            "AND LOWER(query) NOT LIKE '%first orion%'"
        )
        branded_count = db.execute(text(
            "SELECT COUNT(*) FROM keyword_lists WHERE category = 'branded'"
        )).scalar()
        if not branded_count:
            return core_brand_exclusion
        map_count = db.execute(text(
            "SELECT COUNT(*) FROM keyword_query_map WHERE keyword_list_name = 'branded'"
        )).scalar()
        if map_count:
            return (
                "AND query NOT IN (SELECT query FROM keyword_query_map "
                "WHERE keyword_list_name = 'branded') "
                + core_brand_exclusion
            )
        return (
            "AND NOT EXISTS (SELECT 1 FROM keyword_lists kl "
            "WHERE kl.category = 'branded' AND query ILIKE '%' || kl.term || '%') "
            + core_brand_exclusion
        )

    # brand == "branded"
    count = db.execute(text(
        "SELECT COUNT(*) FROM keyword_lists WHERE category = 'branded'"
    )).scalar()
    if not count:
        return "AND 1=0"
    map_count = db.execute(text(
        "SELECT COUNT(*) FROM keyword_query_map WHERE keyword_list_name = 'branded'"
    )).scalar()
    if map_count:
        return (
            "AND query IN (SELECT query FROM keyword_query_map "
            "WHERE keyword_list_name = 'branded')"
        )
    return (
        "AND EXISTS (SELECT 1 FROM keyword_lists kl "
        "WHERE kl.category = 'branded' AND query ILIKE '%' || kl.term || '%')"
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
    prev_start = _period(days * 2)
    bf = _combined_filter(db, brand, tag)
    rows = db.execute(text(f"""
        WITH current AS (
            SELECT page, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
                   CASE WHEN SUM(impressions) > 0
                        THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1) ELSE 0 END AS avg_position,
                   COUNT(DISTINCT query) AS keywords,
                   CASE WHEN SUM(impressions) > 0
                        THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr
            FROM organic_performance WHERE data_date >= :start {bf}
            GROUP BY page
        ),
        previous AS (
            SELECT page, SUM(clicks) AS prev_clicks, SUM(impressions) AS prev_impressions,
                   CASE WHEN SUM(impressions) > 0
                        THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1) ELSE 0 END AS prev_position
            FROM organic_performance WHERE data_date >= :prev_start AND data_date < :start {bf}
            GROUP BY page
        )
        SELECT c.page, c.clicks, c.impressions, c.avg_position, c.keywords, c.ctr,
               p.prev_clicks, p.prev_impressions, p.prev_position
        FROM current c
        LEFT JOIN previous p ON c.page = p.page
        ORDER BY c.clicks DESC
        LIMIT :lim
    """), {"start": start, "prev_start": prev_start, "lim": limit}).mappings().all()
    result = [dict(r) for r in rows]
    set_cached(db, key, result)
    return result


def build_page_keywords(db: Session, page: str, days: int = 30, brand: str = None, tag: str = None):
    """Return keywords driving traffic to a specific page with current + prev period data."""
    start = _period(days)
    prev_start = _period(days * 2)
    bf = _combined_filter(db, brand, tag)
    rows = db.execute(text(f"""
        WITH current AS (
            SELECT query, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
                   CASE WHEN SUM(impressions) > 0
                        THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1) ELSE 0 END AS avg_position,
                   CASE WHEN SUM(impressions) > 0
                        THEN ROUND(SUM(clicks)::numeric / SUM(impressions), 4) ELSE 0 END AS ctr
            FROM organic_performance
            WHERE data_date >= :start AND page = :page {bf}
            GROUP BY query
        ),
        previous AS (
            SELECT query, SUM(clicks) AS prev_clicks,
                   CASE WHEN SUM(impressions) > 0
                        THEN ROUND((SUM(position * impressions) / SUM(impressions))::numeric, 1) ELSE 0 END AS prev_position
            FROM organic_performance
            WHERE data_date >= :prev_start AND data_date < :start AND page = :page {bf}
            GROUP BY query
        )
        SELECT c.query AS keyword, c.clicks, c.impressions, c.avg_position, c.ctr,
               p.prev_clicks, p.prev_position
        FROM current c
        LEFT JOIN previous p ON c.query = p.query
        ORDER BY c.clicks DESC
        LIMIT 50
    """), {"start": start, "prev_start": prev_start, "page": page}).mappings().all()

    return [
        {
            "keyword": r["keyword"],
            "clicks": int(r["clicks"] or 0),
            "impressions": int(r["impressions"] or 0),
            "position": int(round(float(r["avg_position"] or 0))),
            "ctr": float(r["ctr"] or 0),
            "prev_clicks": int(r["prev_clicks"] or 0) if r["prev_clicks"] is not None else None,
            "prev_position": int(round(float(r["prev_position"] or 0))) if r["prev_position"] is not None else None,
        }
        for r in rows
    ]


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


def build_organic_competitor_keywords(db: Session, domain: str, days: int = 90):
    """Return per-keyword breakdown for a specific competitor.
    Each row: keyword, your position, their position, who wins.
    """
    start = _period(days)

    rows = db.execute(text("""
        WITH our_queries AS (
            SELECT DISTINCT query FROM organic_performance WHERE data_date >= :start
        ),
        competitor_rankings AS (
            SELECT osr.keyword,
                   MIN(osr.position) AS their_position
            FROM organic_serp_results osr
            JOIN our_queries oq ON LOWER(osr.keyword) = LOWER(oq.query)
            WHERE osr.observed_date >= :start
              AND osr.domain = :domain
            GROUP BY osr.keyword
        ),
        fo_positions AS (
            SELECT cr.keyword,
                   cr.their_position,
                   ROUND(AVG(op.position)::numeric, 1) AS your_position,
                   SUM(op.clicks) AS clicks,
                   SUM(op.impressions) AS impressions
            FROM competitor_rankings cr
            JOIN organic_performance op ON LOWER(op.query) = LOWER(cr.keyword)
            WHERE op.data_date >= :start
            GROUP BY cr.keyword, cr.their_position
        )
        SELECT fp.keyword,
               fp.your_position,
               fp.their_position,
               fp.clicks,
               fp.impressions,
               CASE WHEN fp.your_position <= fp.their_position THEN 'you' ELSE 'them' END AS winner
        FROM fo_positions fp
        ORDER BY fp.clicks DESC NULLS LAST, fp.impressions DESC NULLS LAST
        LIMIT 100
    """), {"start": start, "domain": domain}).mappings().all()

    return [
        {
            "keyword": r["keyword"],
            "your_position": int(round(float(r["your_position"] or 0))),
            "their_position": int(r["their_position"] or 0),
            "clicks": int(r["clicks"] or 0),
            "impressions": int(r["impressions"] or 0),
            "winner": r["winner"],
        }
        for r in rows
    ]


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

    if scope in ("all", "competitors"):
        build_competitors_overview(db)
        build_competitors_by_domain(db)
        build_competitors_longest_running(db)
        build_competitors_new_this_week(db)
        build_competitors_formats(db)

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
    all_pipelines = ["gsc", "transparency", "keyword_planner"]

    rows = db.execute(text(
        "SELECT pipeline_name, last_run_at FROM pipeline_status"
    )).mappings().all()
    status = {r["pipeline_name"]: r["last_run_at"] for r in rows}

    stale = []
    for p in all_pipelines:
        if p not in status or status[p] < threshold:
            stale.append(p)
    return stale

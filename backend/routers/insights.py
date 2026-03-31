"""Insights & Opportunities engine — cross-references all data sources.

Methodology sourced from:
  - Ahrefs Opportunities Report (position ranges, opportunity types)
  - Google Ads API Recommendations (budget, bid, keyword triggers)
  - Clearscope (striking distance definition)
All thresholds read from config/insights_methodology.json.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db

router = APIRouter()

CONFIG_PATH = Path(__file__).parent.parent / "config" / "insights_methodology.json"

COMPETITORS = [
    "hiya.com", "numeracle.com", "transunion.com",
    "freecallerregistry.com", "tnsi.com",
]


def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _period(days: int) -> date:
    return date.today() - timedelta(days=days)


def _prev_period(days: int) -> tuple[date, date]:
    end = _period(days)
    start = end - timedelta(days=days)
    return start, end


def _priority(rules: dict, value: float, key: str) -> str:
    """Determine priority from config rules. Checks high threshold first."""
    if value >= rules["high"][key]:
        return "high"
    if value >= rules["medium"][key]:
        return "medium"
    return "low"


def _strip_domain(url: str) -> str:
    """Strip domain from URL, returning just the path. e.g. 'https://firstorion.com/branded-calling/' -> '/branded-calling/'"""
    if not url:
        return url
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.path or "/"


# ── Computation function (called by summaries or as fallback) ────

def _compute_insights(days: int, db: Session):
    cfg = _load_config()
    start = _period(days)
    prev_start, prev_end = _prev_period(days)
    insights = []

    # ── 1. Organic: Low-Hanging Fruit (Ahrefs: positions 4-15) ──

    lhf = cfg["organic"]["low_hanging_fruit"]
    rows = db.execute(text("""
        WITH keyword_stats AS (
            SELECT query,
                   (ARRAY_AGG(page ORDER BY clicks DESC))[1] AS top_page,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(impressions) AS impressions, SUM(clicks) AS clicks
            FROM organic_performance WHERE data_date >= :start
            GROUP BY query
        )
        SELECT * FROM keyword_stats
        WHERE avg_position BETWEEN :pos_min AND :pos_max AND impressions >= :min_imp
        ORDER BY impressions DESC LIMIT 20
    """), {"start": start, "pos_min": lhf["position_min"], "pos_max": lhf["position_max"], "min_imp": lhf["min_impressions"]}).mappings().all()

    for r in rows:
        pos = int(r["avg_position"])
        on_page_1 = pos <= 10
        page_label = f'on page 1 (#{pos})' if on_page_1 else f'on page 2 (#{pos})'
        insights.append({
            "id": f"organic_lhf_{len(insights)}",
            "type": "low_hanging_fruit",
            "category": "organic",
            "priority": _priority(lhf["priority"], r["impressions"], "min_impressions"),
            "title": f'"{r["query"]}" — {page_label}, {r["impressions"]:,} searches, {r["clicks"]:,} clicks',
            "description": f'Ranking page: {_strip_domain(r["top_page"])}' if r.get("top_page") else '',
            "metric": {"position": int(r["avg_position"]), "times shown": r["impressions"], "clicks": r["clicks"]},
            "action": f'Search this term in Google. Compare FO\'s result against what ranks above it. Check if the ranking page ({_strip_domain(r["top_page"])}) covers this topic thoroughly.' if r.get("top_page") else 'Search this term in Google and compare FO\'s result against competitors.',
            "affected_entity": r["query"],
            "source": lhf["source"],
        })

    # ── 2. Organic: Low CTR (Ahrefs methodology) ──────────────

    lctr = cfg["organic"]["low_ctr"]
    rows = db.execute(text("""
        WITH top_queries AS (
            SELECT query,
                   (ARRAY_AGG(page ORDER BY clicks DESC))[1] AS top_page,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_position,
                   SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                   ROUND(SUM(clicks)::numeric / NULLIF(SUM(impressions), 0), 4) AS ctr
            FROM organic_performance WHERE data_date >= :start
            GROUP BY query
            HAVING ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 1) <= :pos_max
               AND SUM(impressions) >= :min_imp
        ),
        avg_ctr AS (SELECT AVG(ctr) AS benchmark FROM top_queries)
        SELECT t.*, a.benchmark FROM top_queries t, avg_ctr a
        WHERE t.ctr < a.benchmark * :threshold
        ORDER BY t.impressions DESC LIMIT 15
    """), {"start": start, "pos_max": lctr["position_max"], "min_imp": lctr["min_impressions"], "threshold": lctr["ctr_threshold_multiplier"]}).mappings().all()

    for r in rows:
        ctr_pct = float(r["ctr"]) * 100
        benchmark_pct = float(r["benchmark"]) * 100
        insights.append({
            "id": f"organic_low_ctr_{len(insights)}",
            "type": "low_ctr",
            "category": "organic",
            "priority": "high" if float(r["avg_position"]) <= lctr["priority"]["high"]["max_position"] else "medium",
            "title": f'"{r["query"]}" — position {int(r["avg_position"])}, click rate {ctr_pct:.1f}% (avg {benchmark_pct:.1f}%)',
            "description": f'Ranking page: {_strip_domain(r["top_page"])}. People see this result but click it less than other results at this position.' if r.get("top_page") else f'People see this result but click it less than other results at this position.',
            "metric": {"position": int(r["avg_position"]), "click rate": float(r["ctr"]), "average click rate": float(r["benchmark"]), "times shown": r["impressions"], "clicks": r["clicks"]},
            "action": f'Google this term and look at FO\'s listing. Compare the title and description against the results above and below. Rewrite the page title or meta description if they don\'t clearly answer what the searcher is looking for.',
            "affected_entity": r["query"],
            "source": lctr["source"],
        })

    # ── 3. Organic: Declining Keywords (Ahrefs: Content with Declining Traffic) ──

    dk = cfg["organic"]["declining_keywords"]
    rows = db.execute(text("""
        WITH current_period AS (
            SELECT query,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_pos,
                   SUM(clicks) AS clicks, SUM(impressions) AS impressions
            FROM organic_performance WHERE data_date >= :current_start
            GROUP BY query
        ),
        prev_period AS (
            SELECT query,
                   ROUND((SUM(position * impressions) / NULLIF(SUM(impressions), 0))::numeric, 0) AS avg_pos
            FROM organic_performance WHERE data_date >= :prev_start AND data_date < :prev_end
            GROUP BY query
        )
        SELECT c.query, c.avg_pos AS current_pos, p.avg_pos AS prev_pos,
               ROUND((c.avg_pos - p.avg_pos)::numeric, 1) AS position_drop, c.clicks, c.impressions
        FROM current_period c
        JOIN prev_period p ON c.query = p.query
        WHERE c.avg_pos - p.avg_pos >= :min_drop
        ORDER BY c.clicks DESC LIMIT 15
    """), {"current_start": start, "prev_start": prev_start, "prev_end": prev_end, "min_drop": dk["min_position_drop"]}).mappings().all()

    for r in rows:
        insights.append({
            "id": f"organic_declining_{len(insights)}",
            "type": "declining_keywords",
            "category": "organic",
            "priority": _priority(dk["priority"], r["clicks"], "min_clicks"),
            "title": f'"{r["query"]}" dropped from #{int(r["prev_pos"])} to #{int(r["current_pos"])}',
            "description": f'Lost {int(r["position_drop"])} positions since last period. Still getting {r["clicks"]:,} clicks.',
            "metric": {"current position": int(r["current_pos"]), "previous position": int(r["prev_pos"]), "positions lost": int(r["position_drop"]), "clicks": r["clicks"]},
            "action": f'Google this term and look at what now ranks above FO. Check if the FO page content is outdated, if a competitor published something new, or if there are technical issues (slow load time, broken links).',
            "affected_entity": r["query"],
            "source": dk["source"],
        })

    # ── 4. Organic: Content Gap (Ahrefs methodology) ──────────

    cg = cfg["organic"]["content_gap"]
    rows = db.execute(text("""
        SELECT DISTINCT pko.keyword, pko.estimated_volume, pko.estimated_cpc,
               COUNT(DISTINCT pko.advertiser_domain) AS competitor_count,
               ARRAY_AGG(DISTINCT pko.advertiser_domain) AS competitors
        FROM paid_keyword_observations pko
        WHERE pko.advertiser_domain = ANY(:competitors)
          AND pko.observed_date >= :start
          AND NOT EXISTS (
              SELECT 1 FROM organic_performance op
              WHERE op.query = pko.keyword AND op.data_date >= :start
          )
        GROUP BY pko.keyword, pko.estimated_volume, pko.estimated_cpc
        ORDER BY pko.estimated_volume DESC NULLS LAST LIMIT 15
    """), {"start": start, "competitors": COMPETITORS}).mappings().all()

    for r in rows:
        vol = r["estimated_volume"] or 0
        insights.append({
            "id": f"organic_gap_{len(insights)}",
            "type": "content_gap",
            "category": "organic",
            "priority": _priority(cg["priority"], r["competitor_count"], "min_competitor_count"),
            "title": f'"{r["keyword"]}" — {r["competitor_count"]} competitors active, FO missing',
            "description": f'Competitors targeting this: {", ".join(r["competitors"])}. FO has no content ranking for it.',
            "metric": {"competitor count": r["competitor_count"], "competitors": r["competitors"]},
            "action": f'Check if this keyword is relevant to FO. If yes, identify which existing page could target it or whether new content is needed. Look at what the competitors\' ranking pages cover.',
            "affected_entity": r["keyword"],
            "source": cg["source"],
        })

    # ── 5. Paid: Organic/Paid Overlap ─────────────────────────

    opo = cfg["paid"]["organic_paid_overlap"]
    rows = db.execute(text("""
        SELECT st.search_term,
               SUM(st.cost_micros) / 1000000.0 AS paid_cost,
               SUM(st.clicks) AS paid_clicks,
               org.avg_position, org.organic_clicks
        FROM search_terms st
        JOIN LATERAL (
            SELECT ROUND(AVG(position)::numeric, 0) AS avg_position,
                   SUM(clicks) AS organic_clicks
            FROM organic_performance
            WHERE query = st.search_term AND data_date >= :start
        ) org ON true
        WHERE st.data_date >= :start AND org.avg_position <= :max_pos AND org.avg_position > 0
        GROUP BY st.search_term, org.avg_position, org.organic_clicks
        HAVING SUM(st.cost_micros) > 0
        ORDER BY SUM(st.cost_micros) DESC LIMIT 15
    """), {"start": start, "max_pos": opo["max_organic_position"]}).mappings().all()

    for r in rows:
        cost = float(r["paid_cost"])
        insights.append({
            "id": f"paid_overlap_{len(insights)}",
            "type": "organic_paid_overlap",
            "category": "paid",
            "priority": _priority(opo["priority"], cost, "min_cost"),
            "title": f'"{r["search_term"]}" — already ranking #{int(r["avg_position"])} organically, also running paid ads',
            "description": f'FO ranks #{int(r["avg_position"])} in organic results with {r["organic_clicks"]:,} clicks, and is also running paid ads for this term.',
            "metric": {"paid clicks": r["paid_clicks"], "organic position": int(r["avg_position"]), "organic clicks": r["organic_clicks"]},
            "action": f'Test pausing or lowering the bid on this term for 2 weeks. Monitor if organic clicks absorb the paid traffic. If they do, reallocate the budget to keywords where FO has no organic ranking.',
            "affected_entity": r["search_term"],
            "source": opo["source"],
        })

    # ── 6. Paid: Budget Limited (Google Ads: CAMPAIGN_BUDGET) ─

    bl = cfg["paid"]["budget_limited"]
    rl = cfg["paid"]["rank_limited"]
    rows = db.execute(text("""
        SELECT campaign_name,
               ROUND(AVG(impression_share)::numeric, 4) AS avg_is,
               ROUND(AVG(lost_is_budget)::numeric, 4) AS lost_budget,
               ROUND(AVG(lost_is_rank)::numeric, 4) AS lost_rank,
               SUM(conversions) AS conversions,
               SUM(cost_micros) / 1000000.0 AS spend
        FROM paid_performance WHERE data_date >= :start
        GROUP BY campaign_name
        HAVING AVG(lost_is_budget) > :budget_thresh OR AVG(lost_is_rank) > :rank_thresh
        ORDER BY AVG(lost_is_budget) + AVG(lost_is_rank) DESC
    """), {"start": start, "budget_thresh": bl["lost_is_budget_threshold"], "rank_thresh": rl["lost_is_rank_threshold"]}).mappings().all()

    for r in rows:
        lost_b = float(r["lost_budget"]) * 100
        lost_r = float(r["lost_rank"]) * 100
        total_lost = lost_b + lost_r
        insights.append({
            "id": f"paid_is_{len(insights)}",
            "type": "impression_share_loss",
            "category": "paid",
            "priority": _priority(bl["priority"], total_lost, "min_total_lost_pct"),
            "title": f'"{r["campaign_name"]}" — ads not showing {total_lost:.0f}% of the time',
            "description": f'Ads are missing {lost_b:.1f}% of searches due to budget and {lost_r:.1f}% due to ad rank. {float(r["conversions"]):.0f} conversions this period.',
            "metric": {"impression share": float(r["avg_is"]), "lost to budget": float(r["lost_budget"]), "lost to rank": float(r["lost_rank"]), "conversions": float(r["conversions"])},
            "action": f'For the {lost_b:.0f}% lost to budget: increase this campaign\'s daily budget in Google Ads. For the {lost_r:.0f}% lost to rank: review Quality Score in Google Ads — check ad relevance, landing page experience, and expected click rate.',
            "affected_entity": r["campaign_name"],
            "source": bl["source"],
        })

    # ── 7. Paid: High CPC (Google Ads bid thresholds) ─────────

    hcpc = cfg["paid"]["high_cpc"]
    rows = db.execute(text("""
        SELECT search_term,
               ROUND(SUM(cost_micros)::numeric / NULLIF(SUM(clicks), 0) / 1000000.0, 2) AS cpc,
               SUM(clicks) AS clicks, SUM(cost_micros) / 1000000.0 AS total_cost,
               SUM(conversions) AS conversions
        FROM search_terms WHERE data_date >= :start
        GROUP BY search_term
        HAVING SUM(clicks) > 0 AND SUM(cost_micros)::numeric / SUM(clicks) / 1000000.0 > :threshold
        ORDER BY SUM(cost_micros) DESC LIMIT 15
    """), {"start": start, "threshold": hcpc["cpc_threshold"]}).mappings().all()

    for r in rows:
        cpc = float(r["cpc"])
        insights.append({
            "id": f"paid_cpc_{len(insights)}",
            "type": "high_cpc",
            "category": "paid",
            "priority": _priority(hcpc["priority"], cpc, "min_cpc"),
            "title": f'"{r["search_term"]}" — high cost per click (${cpc:.2f})',
            "description": f'{r["clicks"]:,} clicks, {float(r["conversions"]):.0f} conversions this period.',
            "metric": {"cost per click": cpc, "clicks": r["clicks"], "conversions": float(r["conversions"])},
            "action": f'This keyword costs ${cpc:.2f} per click. If it\'s converting well ({float(r["conversions"]):.0f} conversions), keep it but optimize the landing page to improve Quality Score. If conversions are low, add it as a negative keyword or lower the bid.',
            "affected_entity": r["search_term"],
            "source": hcpc["source"],
        })

    # ── 8. Paid: Competitor Gap (Google Ads KEYWORD + Ahrefs Content Gap) ──

    pcg = cfg["paid"]["competitor_gap"]
    rows = db.execute(text("""
        SELECT pko.keyword, pko.estimated_volume, pko.estimated_cpc,
               COUNT(DISTINCT pko.advertiser_domain) AS competitor_count,
               ARRAY_AGG(DISTINCT pko.advertiser_domain) AS competitors
        FROM paid_keyword_observations pko
        WHERE pko.advertiser_domain = ANY(:competitors)
          AND pko.observed_date >= :start
          AND NOT EXISTS (
              SELECT 1 FROM search_terms st WHERE st.search_term = pko.keyword AND st.data_date >= :start
          )
        GROUP BY pko.keyword, pko.estimated_volume, pko.estimated_cpc
        ORDER BY COUNT(DISTINCT pko.advertiser_domain) DESC, pko.estimated_volume DESC NULLS LAST
        LIMIT 15
    """), {"start": start, "competitors": COMPETITORS}).mappings().all()

    for r in rows:
        vol = r["estimated_volume"] or 0
        insights.append({
            "id": f"paid_gap_{len(insights)}",
            "type": "competitor_paid_gap",
            "category": "paid",
            "priority": _priority(pcg["priority"], r["competitor_count"], "min_competitor_count"),
            "title": f'"{r["keyword"]}" — {r["competitor_count"]} competitors running ads, FO is not',
            "description": f'Running ads: {", ".join(r["competitors"])}.',
            "metric": {"competitor count": r["competitor_count"], "competitors": r["competitors"]},
            "action": f'Google this keyword to see what competitors are promoting. If relevant to FO, add it to an existing campaign as a new ad group with a small test budget.',
            "affected_entity": r["keyword"],
            "source": pcg["source"],
        })

    # ── 9. AI: Platform Gap ───────────────────────────────────

    pg = cfg["ai_visibility"]["platform_gap"]
    rows = db.execute(text("""
        WITH platform_scores AS (
            SELECT platform, ROUND(AVG(visibility_score)::numeric, 1) AS avg_vis,
                   ROUND(AVG(share_of_voice)::numeric, 4) AS avg_sov
            FROM ai_visibility WHERE data_date >= :start
            GROUP BY platform
        ),
        overall AS (SELECT AVG(avg_vis) AS benchmark FROM platform_scores)
        SELECT p.*, o.benchmark
        FROM platform_scores p, overall o
        WHERE p.avg_vis < o.benchmark * :threshold
        ORDER BY p.avg_vis ASC
    """), {"start": start, "threshold": pg["gap_threshold_multiplier"]}).mappings().all()

    for r in rows:
        gap = float(r["benchmark"]) - float(r["avg_vis"])
        insights.append({
            "id": f"ai_gap_{len(insights)}",
            "type": "platform_gap",
            "category": "ai_visibility",
            "priority": _priority(pg["priority"], gap, "min_gap_points"),
            "title": f'Low visibility on {r["platform"]}',
            "description": f'{r["platform"]}: {r["avg_vis"]}% visibility vs {float(r["benchmark"]):.1f}% average across all AI platforms.',
            "metric": {"platform": r["platform"], "visibility": float(r["avg_vis"]), "average visibility": float(r["benchmark"])},
            "action": f'Check what content competitors have that {r["platform"]} is citing. Look at the format (Q&A, comparison, data-driven) and structure FO content similarly for this platform.',
            "affected_entity": r["platform"],
            "source": pg["source"],
        })

    # ── 10. AI: Competitor Overtaking ─────────────────────────

    co = cfg["ai_visibility"]["competitor_overtaking"]
    rows = db.execute(text("""
        WITH fo_current AS (
            SELECT ROUND(AVG(share_of_voice)::numeric, 4) AS sov FROM ai_visibility WHERE data_date >= :current_start
        ),
        fo_prev AS (
            SELECT ROUND(AVG(share_of_voice)::numeric, 4) AS sov FROM ai_visibility WHERE data_date >= :prev_start AND data_date < :prev_end
        ),
        comp_current AS (
            SELECT competitor_domain, ROUND(AVG(share_of_voice)::numeric, 4) AS sov
            FROM ai_competitors WHERE data_date >= :current_start GROUP BY competitor_domain
        ),
        comp_prev AS (
            SELECT competitor_domain, ROUND(AVG(share_of_voice)::numeric, 4) AS sov
            FROM ai_competitors WHERE data_date >= :prev_start AND data_date < :prev_end GROUP BY competitor_domain
        )
        SELECT cc.competitor_domain, cc.sov AS current_sov, cp.sov AS prev_sov,
               fc.sov AS fo_current_sov, fp.sov AS fo_prev_sov
        FROM comp_current cc
        JOIN comp_prev cp ON cc.competitor_domain = cp.competitor_domain
        CROSS JOIN fo_current fc CROSS JOIN fo_prev fp
        WHERE cc.sov > cp.sov AND fc.sov < fp.sov
        ORDER BY cc.sov - cp.sov DESC LIMIT :max_results
    """), {"current_start": start, "prev_start": prev_start, "prev_end": prev_end, "max_results": co["max_results"]}).mappings().all()

    for r in rows:
        comp_gain = (float(r["current_sov"]) - float(r["prev_sov"])) * 100
        fo_loss = (float(r["fo_prev_sov"]) - float(r["fo_current_sov"])) * 100
        insights.append({
            "id": f"ai_overtake_{len(insights)}",
            "type": "competitor_overtaking",
            "category": "ai_visibility",
            "priority": _priority(co["priority"], comp_gain, "min_sov_gain_pp"),
            "title": f'{r["competitor_domain"]} gaining ground in AI results',
            "description": f'{r["competitor_domain"]} share: {float(r["prev_sov"]) * 100:.1f}% → {float(r["current_sov"]) * 100:.1f}%. FO share: {float(r["fo_prev_sov"]) * 100:.1f}% → {float(r["fo_current_sov"]) * 100:.1f}%.',
            "metric": {"competitor": r["competitor_domain"], "competitor current share": float(r["current_sov"]), "competitor previous share": float(r["prev_sov"]), "fo current share": float(r["fo_current_sov"]), "fo previous share": float(r["fo_prev_sov"])},
            "action": f'Visit {r["competitor_domain"]} and look at their recent content (blog posts, whitepapers, product pages). Identify what they published that AI engines are picking up and whether FO has equivalent or better content.',
            "affected_entity": r["competitor_domain"],
            "source": co["source"],
        })

    # ── 11. AI: Uncited Content ───────────────────────────────

    uc = cfg["ai_visibility"]["uncited_content"]
    rows = db.execute(text("""
        SELECT op.page, ROUND(AVG(op.position)::numeric, 0) AS avg_position, SUM(op.clicks) AS clicks
        FROM organic_performance op
        WHERE op.data_date >= :start
        GROUP BY op.page
        HAVING AVG(op.position) <= :max_pos AND SUM(op.clicks) >= :min_clicks
           AND NOT EXISTS (
               SELECT 1 FROM ai_citations ac WHERE ac.cited_url = op.page AND ac.data_date >= :start
           )
        ORDER BY SUM(op.clicks) DESC LIMIT 10
    """), {"start": start, "max_pos": uc["max_organic_position"], "min_clicks": uc["min_clicks"]}).mappings().all()

    for r in rows:
        path = _strip_domain(r["page"])
        insights.append({
            "id": f"ai_uncited_{len(insights)}",
            "type": "uncited_content",
            "category": "ai_visibility",
            "priority": _priority(uc["priority"], r["clicks"], "min_clicks"),
            "title": f'{path} ranks well in search but AI engines don\'t reference it',
            "description": f'Position {int(r["avg_position"])} in Google with {r["clicks"]:,} clicks, but no AI engines cite this page.',
            "metric": {"page": path, "position": int(r["avg_position"]), "clicks": r["clicks"]},
            "action": f'This page gets traffic from Google but AI engines skip it. Add clear factual statements, structured Q&A sections, and schema markup so AI engines can extract and cite the content.',
            "affected_entity": r["page"],
            "source": uc["source"],
        })

    # ── 12. AI: Negative Sentiment ────────────────────────────

    rows = db.execute(text("""
        SELECT cited_url, prompt, platform, citation_type, data_date
        FROM ai_citations
        WHERE sentiment = 'NEGATIVE' AND data_date >= :start
        ORDER BY data_date DESC LIMIT 10
    """), {"start": start}).mappings().all()

    for r in rows:
        prompt_text = r["prompt"][:100] if r.get("prompt") else None
        insights.append({
            "id": f"ai_neg_{len(insights)}",
            "type": "negative_sentiment",
            "category": "ai_visibility",
            "priority": "high",
            "title": f'Negative mention on {r["platform"]}',
            "description": (f'Prompt: "{prompt_text}"' if prompt_text else f'Negative {r["citation_type"]} citation on {r["platform"]}, {r["data_date"]}.'),
            "metric": {"platform": r["platform"], "citation type": r["citation_type"], "date": str(r["data_date"])},
            "action": f'Read the page at {_strip_domain(r["cited_url"])} and identify what might have triggered the negative reference. Update outdated information or add clarifying content.',
            "affected_entity": r["cited_url"],
            "source": cfg["ai_visibility"]["negative_sentiment"]["source"],
        })

    # ── 13. Competitor: New Campaigns ─────────────────────────

    nc = cfg["competitor"]["new_campaigns"]
    rows = db.execute(text("""
        SELECT competitor_domain, COUNT(*) AS new_ads,
               (ARRAY_AGG(headline ORDER BY first_shown_date DESC))[1:3] AS sample_headlines
        FROM competitor_ads
        WHERE first_shown_date >= CURRENT_DATE - INTERVAL ':lookback days'
          AND competitor_domain != 'firstorion.com'
        GROUP BY competitor_domain
        ORDER BY new_ads DESC
    """.replace(":lookback", str(nc["lookback_days"]))), {}).mappings().all()

    for r in rows:
        insights.append({
            "id": f"comp_new_{len(insights)}",
            "type": "new_campaigns",
            "category": "competitor",
            "priority": _priority(nc["priority"], r["new_ads"], "min_new_ads"),
            "title": f'{r["competitor_domain"]} launched {r["new_ads"]} new ads',
            "description": (f'Sample: "{r["sample_headlines"][0]}"' if r["sample_headlines"] else f'{r["new_ads"]} new creatives detected.'),
            "metric": {"competitor": r["competitor_domain"], "new ads": r["new_ads"], "headlines": r["sample_headlines"]},
            "action": f'Review their ad copy and landing pages. Look for new messaging angles, product launches, or competitive claims that FO should respond to.',
            "affected_entity": r["competitor_domain"],
            "source": nc["source"],
        })

    # ── 14. Competitor: Long-Running Ads ──────────────────────

    lra = cfg["competitor"]["long_running_ads"]
    rows = db.execute(text("""
        SELECT competitor_domain, headline, description, days_running, ad_format, destination_url
        FROM competitor_ads
        WHERE is_active AND days_running >= :min_days AND competitor_domain != 'firstorion.com'
        ORDER BY days_running DESC LIMIT 15
    """), {"min_days": lra["min_days_running"]}).mappings().all()

    for r in rows:
        insights.append({
            "id": f"comp_long_{len(insights)}",
            "type": "long_running_ads",
            "category": "competitor",
            "priority": _priority(lra["priority"], r["days_running"], "min_days"),
            "title": f'{r["competitor_domain"]} — ad running {r["days_running"]} days',
            "description": (f'"{(r["headline"] or "")[:80]}"' if r.get("headline") else f'{r["ad_format"]} ad, {r["days_running"]} days active.'),
            "metric": {"competitor": r["competitor_domain"], "days running": r["days_running"], "format": r["ad_format"]},
            "action": f'This ad has run for {r["days_running"]} days — study the headline, call-to-action, and landing page ({r["destination_url"] or "N/A"}). Test similar angles in FO campaigns.',
            "affected_entity": r["competitor_domain"],
            "source": lra["source"],
        })

    # ── 15. Competitor: Keyword Overlap ───────────────────────

    ko = cfg["competitor"]["keyword_overlap"]
    rows = db.execute(text("""
        SELECT keyword, COUNT(DISTINCT advertiser_domain) AS advertiser_count,
               ARRAY_AGG(DISTINCT advertiser_domain) AS advertisers,
               MAX(estimated_volume) AS est_volume, MAX(estimated_cpc) AS est_cpc
        FROM paid_keyword_observations
        WHERE advertiser_domain = ANY(:competitors)
          AND observed_date >= :start
        GROUP BY keyword
        HAVING COUNT(DISTINCT advertiser_domain) >= :min_adv
        ORDER BY COUNT(DISTINCT advertiser_domain) DESC, MAX(estimated_volume) DESC NULLS LAST
        LIMIT 15
    """), {"start": start, "competitors": COMPETITORS, "min_adv": ko["min_advertisers"]}).mappings().all()

    for r in rows:
        insights.append({
            "id": f"comp_overlap_{len(insights)}",
            "type": "keyword_overlap",
            "category": "competitor",
            "priority": _priority(ko["priority"], r["advertiser_count"], "min_advertisers"),
            "title": f'"{r["keyword"]}" — {r["advertiser_count"]} competitors advertising',
            "description": f'Competitors: {", ".join(r["advertisers"])}.',
            "metric": {"keyword": r["keyword"], "competitor count": r["advertiser_count"], "competitors": r["advertisers"]},
            "action": f'When {r["advertiser_count"]} competitors all bid on a keyword, it validates demand. Google this term, check if FO should be competing, and test a small ad group if so.',
            "affected_entity": r["keyword"],
            "source": ko["source"],
        })

    # ── 16. Cross-Channel: AI cited but poor organic ──────────

    awo = cfg["cross_channel"]["ai_without_organic"]
    rows = db.execute(text("""
        SELECT ac.cited_url, COUNT(*) AS citation_count,
               org.avg_position, org.clicks
        FROM ai_citations ac
        LEFT JOIN LATERAL (
            SELECT ROUND(AVG(position)::numeric, 0) AS avg_position, SUM(clicks) AS clicks
            FROM organic_performance WHERE page = ac.cited_url AND data_date >= :start
        ) org ON true
        WHERE ac.data_date >= :start AND ac.cited_url LIKE '%%firstorion.com%%'
          AND (org.avg_position IS NULL OR org.avg_position > :min_pos)
        GROUP BY ac.cited_url, org.avg_position, org.clicks
        ORDER BY COUNT(*) DESC LIMIT 10
    """), {"start": start, "min_pos": awo["min_organic_position_or_missing"]}).mappings().all()

    for r in rows:
        pos_text = f"position {int(r['avg_position'])}" if r["avg_position"] else "not ranking"
        path = _strip_domain(r["cited_url"])
        insights.append({
            "id": f"cross_ai_{len(insights)}",
            "type": "ai_without_organic",
            "category": "cross_channel",
            "priority": _priority(awo["priority"], r["citation_count"], "min_citations"),
            "title": f'{path} — cited by AI but not ranking in search',
            "description": f'{r["citation_count"]} AI citations. Organic: {pos_text}.',
            "metric": {"page": path, "ai citations": r["citation_count"], "organic position": int(r["avg_position"] or 0), "organic clicks": r["clicks"] or 0},
            "action": f'AI engines trust this content enough to cite it. Optimize {path} for search — update the title tag, add relevant keywords, and build internal links to it from other FO pages.',
            "affected_entity": r["cited_url"],
            "source": awo["source"],
        })

    # ── 17. Cross-Channel: Strong organic, no AI ──────────────

    owa = cfg["cross_channel"]["organic_without_ai"]
    rows = db.execute(text("""
        SELECT op.page, SUM(op.clicks) AS organic_clicks,
               ROUND(AVG(op.position)::numeric, 0) AS avg_position
        FROM organic_performance op
        WHERE op.data_date >= :start
        GROUP BY op.page
        HAVING AVG(op.position) <= :max_pos AND SUM(op.clicks) >= :min_clicks
           AND NOT EXISTS (
               SELECT 1 FROM ai_citations ac WHERE ac.cited_url = op.page AND ac.data_date >= :start
           )
        ORDER BY SUM(op.clicks) DESC LIMIT 10
    """), {"start": start, "max_pos": owa["max_organic_position"], "min_clicks": owa["min_organic_clicks"]}).mappings().all()

    for r in rows:
        path = _strip_domain(r["page"])
        insights.append({
            "id": f"cross_org_{len(insights)}",
            "type": "organic_without_ai",
            "category": "cross_channel",
            "priority": _priority(owa["priority"], r["organic_clicks"], "min_clicks"),
            "title": f'{path} — ranks #{int(r["avg_position"])} in search but not cited by AI',
            "description": f'{r["organic_clicks"]:,} clicks from search. No AI engine cites this page.',
            "metric": {"page": path, "clicks": r["organic_clicks"], "position": int(r["avg_position"])},
            "action": f'This page gets {r["organic_clicks"]:,} clicks from search but AI engines ignore it. Add FAQ schema markup, include concise factual definitions, and structure content so AI can extract clean answers.',
            "affected_entity": r["page"],
            "source": owa["source"],
        })

    # ── Sort and summarize ─────────────────────────────────────

    priority_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: priority_order[x["priority"]])

    summary = {
        "total": len(insights),
        "high": sum(1 for i in insights if i["priority"] == "high"),
        "medium": sum(1 for i in insights if i["priority"] == "medium"),
        "low": sum(1 for i in insights if i["priority"] == "low"),
        "by_category": {},
    }
    for cat in ["organic", "paid", "ai_visibility", "competitor", "cross_channel"]:
        summary["by_category"][cat] = sum(1 for i in insights if i["category"] == cat)

    # Include methodology metadata
    summary["methodology_version"] = cfg["_meta"]["version"]
    summary["methodology_refreshed"] = cfg["_meta"]["last_refreshed"]
    summary["pending_changes"] = cfg["_meta"]["pending_changes"]

    result = {"summary": summary, "insights": insights}
    # Cache the result
    from services.summaries import set_cached
    set_cached(db, f"insights:{days}", result)
    return result

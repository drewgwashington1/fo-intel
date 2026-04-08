# FO Intel — Organic Search Intelligence & Competitor Ads Platform

## Quick Start

### 1. Start PostgreSQL
```bash
docker-compose up -d
```
Database runs on `localhost:5434` — db: `fo_intel`, user: `fointel`, password: `fointel`

### 2. Start Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8001
```
API docs at http://localhost:8001/docs

### 3. Start Frontend
```bash
cd frontend
npm install
npm run dev
```
Dashboard at http://localhost:3000

### 4. Run Pipelines
Use the sidebar buttons or curl:
```bash
curl -X POST "http://localhost:8001/api/ingest/gsc?days=30"
curl -X POST "http://localhost:8001/api/ingest/keyword-planner"
curl -X POST "http://localhost:8001/api/ingest/transparency"
curl -X POST "http://localhost:8001/api/ingest/serper-sweep"
```

## Architecture
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** Nuxt 3 + Tailwind CSS + Pinia
- **Database:** PostgreSQL 15 (Docker)
- **Production:** GCP — Cloud Run + Cloud SQL

## What This Replaces
Ahrefs ($129–$249/month) — FO Intel covers organic search, keyword research, content gaps, and competitor ad intelligence at ~$1–5/month on GCP.

## Data Sources (4 pipelines)
| Pipeline | Source | Schedule | What It Covers |
|----------|--------|----------|----------------|
| GSC Organic | Google Search Console API | Daily 3:00 AM CT | Organic impressions, clicks, CTR, position by query + page |
| Keyword Planner | Google Ads Keyword Planner API | Weekly | Search volume, CPC, competition for all tracked keywords |
| Competitor Ads | Google Ads Transparency Center | Weekly Sunday 6:00 AM CT | Competitor ad creatives: copy, format, run duration |
| Serper SERP | Serper.dev API | Every 90 days (limited credits) | Competitor organic rankings, paid ad observations |

## Removed Pipelines (out of scope)
- **Paid Performance** (Google Ads campaign data) — use Google Ads UI directly
- **AI Visibility** (Profound API) — migrated to Databricks via Google Sheets pipeline

## Database Tables
- `organic_performance` — Daily organic search metrics per query/page
- `keyword_metrics` — Keyword Planner data: volume, CPC, competition per keyword
- `keyword_ideas` — Related keyword suggestions from Keyword Planner
- `competitor_ads` — Competitor ad creatives from Transparency Center
- `keyword_lists` — User-defined keyword tags and branded/non-branded classification
- `keyword_query_map` — Pre-computed keyword list to query mappings
- `serp_cache` — Cached Serper SERP results
- `paid_keyword_observations` — Competitor paid keyword data from Serper
- `organic_serp_results` — Competitor organic rankings from Serper
- `serper_credit_log` — Serper credit usage tracking
- `tracked_competitors` — Competitor domains to monitor
- `summary_cache` — Pre-computed dashboard responses
- `pipeline_status` — Pipeline run timestamps

## Dashboard Pages (5)
1. **Insights** — Content opportunities: create, expand, refresh, content gaps
2. **Organic Performance** — clicks, impressions, CTR, position trends, top queries, top pages, device breakdown, organic competitors
3. **Keywords Explorer** — keyword list with volume/CPC/competition + GSC data, keyword ideas from Keyword Planner, content gaps (competitors rank, you don't)
4. **Competitor Ads** — active ad count, longest-running creatives, format distribution, new ads this week, domain filtering
5. **Settings** — pipeline controls, competitor domain management, user management

## Key Files
- `backend/services/gsc.py` — Real GSC API integration
- `backend/services/google_ads.py` — Google Ads API client (for Keyword Planner)
- `backend/services/keyword_planner.py` — Keyword Planner API: volume, CPC, competition, keyword ideas
- `backend/services/transparency.py` — Transparency Center scraper
- `backend/services/serper.py` — Serper SERP sweep (limited credits)
- `backend/routers/dashboard.py` — Dashboard API endpoints
- `backend/routers/ingest.py` — Ingest pipeline triggers
- `backend/routers/insights.py` — Content opportunity engine

## Branding
See `screenshots-branding/` for the branding kit. Apply those colors, typography, and UI patterns to all frontend components.

## Competitors to Track
- hiya.com
- numeracle.com
- transunion.com
- freecallerregistry.com
- tnsi.com (Transaction Network Services)

## Single Tenant
This is an internal tool for First Orion only. No multi-org. Auth via JWT with hardcoded credentials in environment variables.

## Port Allocation
To run alongside FO Shield without conflicts:
- PostgreSQL: `5434` (FO Shield uses `5433`)
- Backend: `8001` (FO Shield uses `8000`)
- Frontend: `3000` or `3001` (check availability)

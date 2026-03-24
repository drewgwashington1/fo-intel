# FO Intel — Competitive & Paid Search Intelligence Platform

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

### 4. Generate Data & Run Pipelines
Use the sidebar buttons or curl:
```bash
curl -X POST "http://localhost:8001/api/ingest/gsc?days=30"
curl -X POST "http://localhost:8001/api/ingest/ads?days=30"
curl -X POST "http://localhost:8001/api/ingest/profound?days=30"
curl -X POST "http://localhost:8001/api/ingest/transparency"
```

## Architecture
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** Nuxt 3 + Tailwind CSS + Pinia
- **Database:** PostgreSQL 15 (Docker)
- **Production target:** GCP — Cloud Run + Cloud SQL + BigQuery + Looker Studio

## What This Replaces
Ahrefs ($129–$249/month) — FO Intel consolidates organic search, paid search, AI visibility, and competitor ad intelligence into one internal platform at ~$1–5/month on GCP.

## Data Sources (4 pipelines)
| Pipeline | Source | Schedule | What It Covers |
|----------|--------|----------|----------------|
| GSC Organic | Google Search Console API | Daily 3:00 AM CT | Organic impressions, clicks, CTR, position by query + page |
| Google Ads | Google Ads API | Daily 3:30 AM CT | Paid performance: spend, CPC, impression share, search terms |
| AI Visibility | Profound API | Daily 4:00 AM CT | AI engine SOV, citations, competitor benchmarks (ChatGPT, Perplexity, Gemini, Claude, Google AI) |
| Competitor Ads | Google Ads Transparency Center | Weekly Sunday 6:00 AM CT | Competitor ad creatives: copy, format, run duration |

## Database Tables (7)
- `organic_performance` — Daily organic search metrics per query/page
- `paid_performance` — Daily paid search metrics per campaign/ad group
- `search_terms` — Actual queries that triggered paid ads
- `ai_visibility` — AI engine visibility scores per category/platform
- `ai_citations` — Which FO pages are cited in AI responses
- `ai_competitors` — Competitor share of voice in AI engines
- `competitor_ads` — Competitor ad creatives from Transparency Center

## Dashboard Pages (4)
1. **Organic Performance** — clicks, impressions, CTR, position trends, top queries, top pages, device breakdown
2. **Paid Performance** — spend, impression share, CPC, campaign breakdown, top search terms, IS loss analysis
3. **AI Visibility** — visibility scores by platform, FO vs competitor SOV, top cited pages, citation trends
4. **Competitor Ads** — active ad count, longest-running creatives, format distribution, new ads this week

## Key Files
- `backend/services/mock_gsc.py` — Mock GSC data generator (swap for real API later)
- `backend/services/mock_ads.py` — Mock Google Ads data generator (swap for real API later)
- `backend/services/mock_profound.py` — Mock Profound data generator (swap for real API later)
- `backend/services/mock_transparency.py` — Mock competitor ad data generator (swap for real API later)
- `backend/routers/dashboard.py` — Dashboard API endpoints
- `backend/routers/ingest.py` — Ingest pipeline triggers

## Branding
See `screenshots-branding/` for the branding kit. Apply those colors, typography, and UI patterns to all frontend components.

## Competitors to Track
- hiya.com
- numeracle.com
- transunion.com
- freecallerregistry.com
- tnsi.com (Transaction Network Services)

## Build Approach
Follow the same pattern as FO Shield (`/Documents/fo-shield`):
1. **Mock data first** — build generators for all 4 data sources with realistic patterns
2. **Backend pipeline** — ingest, store, and serve via FastAPI REST API
3. **Frontend dashboard** — Nuxt 3 + Tailwind, 4 tabbed pages matching the branding kit
4. **Settings page** — pipeline controls, data source config, competitor domain management
5. **Git init** — .gitignore (node_modules, .env, __pycache__, .nuxt, .output), commit early
6. **GCP deployment** — Cloud Run + Cloud SQL + Cloud Scheduler (later)
7. **Real API connections** — swap mock generators for real GSC, Ads, Profound, Transparency APIs (later)

## Single Tenant
This is an internal tool for First Orion only. No multi-org, no auth UI, no user management. Hard-code credentials via environment variables. Same approach as FO Shield.

## Port Allocation
To run alongside FO Shield without conflicts:
- PostgreSQL: `5434` (FO Shield uses `5433`)
- Backend: `8001` (FO Shield uses `8000`)
- Frontend: `3000` or `3001` (check availability)

# FO Intel — Deployment Instructions

## Services

| Service | Cloud Run Name | Image Path |
|---------|---------------|------------|
| Backend API | `fo-intel-api` | `us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/api:latest` |
| Frontend | `fo-intel-frontend` | `us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/frontend:latest` |

## Prerequisites

- Docker Desktop running
- gcloud CLI at `/Users/drewwashington/google-cloud-sdk/bin/gcloud`
- Authenticated to Artifact Registry (run once):
  ```bash
  export PATH="$PATH:/Users/drewwashington/google-cloud-sdk/bin"
  gcloud auth configure-docker us-central1-docker.pkg.dev --quiet
  ```

## Build & Push Images

From the `fo-intel` project root:

### Backend API
```bash
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/api:latest \
  backend/

export PATH="$PATH:/Users/drewwashington/google-cloud-sdk/bin"
docker push us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/api:latest
```

### Frontend
```bash
docker build --platform linux/amd64 \
  --build-arg API_BASE_URL=https://fo-intel-api-665828676800.us-central1.run.app/api \
  -t us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/frontend:latest \
  frontend/

export PATH="$PATH:/Users/drewwashington/google-cloud-sdk/bin"
docker push us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/frontend:latest
```

## Deploy from GCP Console

1. Go to **Cloud Run** in GCP Console
2. Click the service (`fo-intel-api` or `fo-intel-frontend`)
3. Click **Edit & Deploy New Revision**
4. Image should already show `:latest` — just click **Deploy**

## Environment Variables (Backend)

Set these in Cloud Run → Edit & Deploy → Environment variables:
- `DATABASE_URL` = `postgresql://fointel:PASSWORD@CLOUD_SQL_IP:5432/fo_intel`
- `CORS_ORIGINS` = `https://fo-intel-frontend-665828676800.us-central1.run.app`
- `GSC_CREDENTIALS_PATH` = `/app/credentials/gsc-credentials.json`
- `GOOGLE_ADS_DEVELOPER_TOKEN` = (your token)
- `GOOGLE_ADS_CLIENT_ID` = (your client ID)
- `GOOGLE_ADS_CLIENT_SECRET` = (your secret)
- `GOOGLE_ADS_REFRESH_TOKEN` = (your refresh token)
- `GOOGLE_ADS_CUSTOMER_ID` = (your customer ID)
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` = (your login customer ID)
- `SERPER_API_KEY` = (your Serper key)
- `USE_MOCK_GSC` = `false`
- `USE_MOCK_TRANSPARENCY` = `false`

**Removed (no longer needed):**
- `PROFOUND_API_KEY`, `PROFOUND_CATEGORY_ID`, `USE_MOCK_PROFOUND` — AI data moved to Databricks
- `USE_MOCK_ADS` — Paid performance removed

## Production URLs

- **API:** https://fo-intel-api-665828676800.us-central1.run.app
- **Frontend:** https://fo-intel-frontend-665828676800.us-central1.run.app
- **API Docs:** https://fo-intel-api-665828676800.us-central1.run.app/docs

## Post-Deploy Tasks

After deploying a new backend revision, run the data pipelines:

```bash
BASE=https://fo-intel-api-665828676800.us-central1.run.app

# Pull organic data from GSC
curl -X POST "$BASE/api/ingest/gsc?days=30"

# Fetch keyword volume/CPC from Keyword Planner
curl -X POST "$BASE/api/ingest/keyword-planner"

# Scrape competitor ads from Transparency Center
curl -X POST "$BASE/api/ingest/transparency"

# Run SERP sweep for competitor keywords (uses limited Serper credits)
curl -X POST "$BASE/api/ingest/serper-sweep"
```

## GCP Resources

- **Project:** `advance-wavelet-442900-f9`
- **Region:** `us-central1`
- **Artifact Registry:** `us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/`
- **Cloud SQL:** `advance-wavelet-442900-f9:us-central1:fo-intel-db` (PostgreSQL, db: `fo_intel`, user: `fointel`)

## Important Notes

- **ALWAYS** use `--platform linux/amd64` when building (Mac is ARM, Cloud Run is x86)
- Backend image goes to `fo-intel/api` — NOT `fo-intel/backend`
- Frontend needs `--build-arg API_BASE_URL=...` or it defaults to localhost
- Always include `/api` suffix in the frontend API_BASE_URL build arg

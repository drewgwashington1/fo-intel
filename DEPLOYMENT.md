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

## First-Time Cloud Run Setup

If the Cloud Run services don't exist yet, create them:

### Backend API (`fo-intel-api`)
1. Cloud Run → **Create Service**
2. **Container image:** `us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/api:latest`
3. **Service name:** `fo-intel-api`
4. **Region:** `us-central1`
5. **Authentication:** Allow unauthenticated invocations
6. **Container port:** `8080`
7. **Memory:** 512 MiB, **CPU:** 1
8. **Environment variables** (set in the Env vars section):
   - `DATABASE_URL` = `postgresql://fointel:PASSWORD@CLOUD_SQL_IP:5432/fo_intel`
   - `CORS_ORIGINS` = `https://fo-intel-frontend-665828676800.us-central1.run.app`
   - `GSC_CREDENTIALS_PATH` = `/app/credentials/gsc-credentials.json`
   - `GOOGLE_ADS_DEVELOPER_TOKEN` = (your token)
   - `GOOGLE_ADS_CLIENT_ID` = (your client ID)
   - `GOOGLE_ADS_CLIENT_SECRET` = (your secret)
   - `GOOGLE_ADS_REFRESH_TOKEN` = (your refresh token)
   - `GOOGLE_ADS_CUSTOMER_ID` = (your customer ID)
   - `GOOGLE_ADS_LOGIN_CUSTOMER_ID` = (your login customer ID)
   - `PROFOUND_API_KEY` = (your Profound key)
   - `SERPER_API_KEY` = (your Serper key)
   - `USE_MOCK_GSC` = `false`
   - `USE_MOCK_ADS` = `false`
   - `USE_MOCK_PROFOUND` = `false`
   - `USE_MOCK_TRANSPARENCY` = `false`
9. **Cloud SQL connections:** Add `advance-wavelet-442900-f9:us-central1:fo-intel-db`

### Frontend (`fo-intel-frontend`)
1. Cloud Run → **Create Service**
2. **Container image:** `us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/frontend:latest`
3. **Service name:** `fo-intel-frontend`
4. **Region:** `us-central1`
5. **Authentication:** Allow unauthenticated invocations
6. **Container port:** `3000`
7. **Memory:** 256 MiB, **CPU:** 1

## Cloud SQL Setup

If the database doesn't exist yet:

1. Go to **Cloud SQL** → **Create Instance** → **PostgreSQL 15**
2. **Instance ID:** `fo-intel-db`
3. **Region:** `us-central1`
4. **Database name:** `fo_intel`
5. **User:** `fointel`
6. Set a strong password and use it in `DATABASE_URL`

## Production URLs

- **API:** https://fo-intel-api-665828676800.us-central1.run.app
- **Frontend:** https://fo-intel-frontend-665828676800.us-central1.run.app
- **API Docs:** https://fo-intel-api-665828676800.us-central1.run.app/docs
- **Health Check:** https://fo-intel-api-665828676800.us-central1.run.app/api/health

> **Note:** The `665828676800` project number in URLs above is from FO Shield. Your actual URLs will use FO Intel's project number — update these after first deploy.

## GCP Resources

- **Project:** `advance-wavelet-442900-f9`
- **Region:** `us-central1`
- **Artifact Registry:** `us-central1-docker.pkg.dev/advance-wavelet-442900-f9/fo-intel/`
- **Cloud SQL:** `advance-wavelet-442900-f9:us-central1:fo-intel-db` (PostgreSQL, db: `fo_intel`, user: `fointel`)
- **Service Account:** `fo-budgeting-deployer@advance-wavelet-442900-f9.iam.gserviceaccount.com`

## Important Notes

- **ALWAYS** use `--platform linux/amd64` when building (Mac is ARM, Cloud Run is x86)
- Backend image goes to `fo-intel/api` — NOT `fo-intel/backend`
- Frontend needs `--build-arg API_BASE_URL=...` or it defaults to localhost
- The `config/insights_methodology.json` is baked into the backend image — rebuild after methodology updates

## Post-Deploy Tasks

After deploying a new backend revision, run the data pipelines:

```bash
BASE=https://fo-intel-api-665828676800.us-central1.run.app

# Pull organic data from GSC
curl -X POST "$BASE/api/ingest/gsc?days=30"

# Pull paid data from Google Ads
curl -X POST "$BASE/api/ingest/ads?days=30"

# Pull ad creative performance
curl -X POST "$BASE/api/ingest/creatives?days=30"

# Pull AI visibility from Profound
curl -X POST "$BASE/api/ingest/profound?days=30"

# Scrape competitor ads from Transparency Center
curl -X POST "$BASE/api/ingest/transparency"

# Run SERP sweep for competitor keywords
curl -X POST "$BASE/api/ingest/serper-sweep"

# Refresh methodology sources (run monthly)
curl -X POST "$BASE/api/ingest/methodology-refresh"
```

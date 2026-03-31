from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import app_settings
from database import engine, Base
from routers import dashboard, ingest, insights

app = FastAPI(title="FO Intel API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in app_settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["Ingest"])
app.include_router(insights.router, prefix="/api/dashboard", tags=["Insights"])


@app.on_event("startup")
def startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        import logging
        logging.error(f"Database startup failed: {e}")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/debug/db")
def debug_db():
    """Test database connectivity and ensure tables exist."""
    try:
        Base.metadata.create_all(bind=engine)
        from sqlalchemy import text as sa_text
        with engine.connect() as conn:
            tables = conn.execute(sa_text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )).fetchall()
            return {"db": "connected", "tables": [t[0] for t in tables]}
    except Exception as e:
        return {"db": "error", "detail": str(e)}

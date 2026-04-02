import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import app_settings
from database import engine, Base, get_db_session
from routers import auth, dashboard, ingest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FO Intel API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in app_settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["Ingest"])


@app.on_event("startup")
def startup():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
        # Migrate: add category column if missing (existing installs)
        from sqlalchemy import text as _t, inspect as _inspect
        insp = _inspect(engine)
        if "keyword_lists" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("keyword_lists")]
            if "category" not in cols:
                with engine.begin() as conn:
                    conn.execute(_t("ALTER TABLE keyword_lists ADD COLUMN category VARCHAR NOT NULL DEFAULT 'non-branded'"))
                    conn.execute(_t("CREATE INDEX IF NOT EXISTS ix_keyword_lists_category ON keyword_lists (category)"))
                    conn.execute(_t("UPDATE keyword_lists SET category = 'branded' WHERE list_name = 'branded'"))
                logger.info("Migrated keyword_lists: added category column")

        # Seed admin user if app_users table is empty
        from passlib.context import CryptContext
        _pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
        with engine.begin() as conn:
            user_count = conn.execute(_t("SELECT COUNT(*) FROM app_users")).scalar()
            if user_count == 0 and app_settings.ADMIN_EMAIL and app_settings.ADMIN_PASSWORD:
                hashed = _pwd.hash(app_settings.ADMIN_PASSWORD)
                conn.execute(_t(
                    "INSERT INTO app_users (email, password_hash, role) VALUES (:email, :hash, 'admin')"
                ), {"email": app_settings.ADMIN_EMAIL, "hash": hashed})
                logger.info(f"Seeded admin user: {app_settings.ADMIN_EMAIL}")
    except Exception as e:
        logger.error(f"Database startup failed: {e}")
        return

    # Build summaries in background thread so startup doesn't block
    def _initial_build():
        db = get_db_session()
        try:
            from sqlalchemy import text as sa_text
            # Check if summary_cache has any data
            from services.summaries import rebuild_all_keyword_maps, rebuild_summaries, invalidate_scope
            count = db.execute(sa_text("SELECT COUNT(*) FROM summary_cache")).scalar()
            if count == 0:
                logger.info("No cached summaries — building all summaries...")
                rebuild_all_keyword_maps(db)
                rebuild_summaries(db, "all")
            else:
                logger.info(f"Summary cache has {count} entries")
                # Always rebuild keyword maps (category-based maps may be missing)
                rebuild_all_keyword_maps(db)
                # Invalidate organic cache so stale data doesn't persist across deploys
                invalidate_scope(db, "organic")
                rebuild_summaries(db, "organic")

            # Always rebuild insights on startup (logic may have changed between deploys)
            logger.info("Rebuilding insights cache...")
            invalidate_scope(db, "insights")
            from routers.insights import _compute_insights
            try:
                _compute_insights(30, db)
                logger.info("Insights rebuild complete")
            except Exception as e:
                logger.warning(f"Insights rebuild failed: {e}")
        except Exception as e:
            logger.error(f"Initial summary build failed: {e}")
        finally:
            db.close()

    threading.Thread(target=_initial_build, daemon=True).start()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/debug/db")
def debug_db():
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

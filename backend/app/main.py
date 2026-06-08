from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE, create_session_token, verify_password, verify_session_token
from app.config import get_settings
from app.database import SessionLocal, get_session, init_db
from app.models import AdminUser, Asset
from app.seed import seed_defaults
from app.services import dashboard
from app.workers.collector import regenerate_interpretations_for_latest_run, regenerate_news_analyses_for_recent_news, run_collection_once


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    session = SessionLocal()
    try:
        seed_defaults(session, settings)
    finally:
        session.close()
    yield


app = FastAPI(title="Crypto Event Intelligence API", version="0.1.0", lifespan=lifespan)


class LoginRequest(BaseModel):
    username: str
    password: str


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def get_current_admin(session_cookie: str | None, session: Session) -> AdminUser:
    if not session_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = verify_session_token(session_cookie, settings.session_secret)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    user = session.scalar(select(AdminUser).where(AdminUser.username == payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown session user")
    return user


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response, session: Session = Depends(get_session)):
    user = session.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_session_token(user.username, settings.session_secret)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return {"username": user.username}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def me(session: Session = Depends(get_session), crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    user = get_current_admin(crypto_intel_session, session)
    return {"username": user.username}


@app.get("/api/assets")
def list_assets(session: Session = Depends(get_session), crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    get_current_admin(crypto_intel_session, session)
    rows = session.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.group, Asset.rank)).all()
    return [{"symbol": row.symbol, "name": row.name, "group": row.group, "rank": row.rank} for row in rows]


@app.get("/api/market/brief")
def get_market_brief(session: Session = Depends(get_session), crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    get_current_admin(crypto_intel_session, session)
    return dashboard.market_brief(session)


@app.get("/api/market/regime")
def get_market_regime(session: Session = Depends(get_session), crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    get_current_admin(crypto_intel_session, session)
    return dashboard.market_regime(session)


@app.get("/api/assets/{symbol}/overview")
def get_asset_overview(
    symbol: str,
    window: str = "30d",
    session: Session = Depends(get_session),
    crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    get_current_admin(crypto_intel_session, session)
    overview = dashboard.asset_overview(session, symbol, window)
    if not overview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return overview


@app.get("/api/assets/{symbol}/signals")
def get_asset_signals(symbol: str, session: Session = Depends(get_session), crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    get_current_admin(crypto_intel_session, session)
    return dashboard.event_feed(session, symbol=symbol)


@app.get("/api/events")
def get_events(
    symbol: str | None = None,
    signal_type: str | None = None,
    severity: str | None = None,
    include_research: bool = False,
    session: Session = Depends(get_session),
    crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    get_current_admin(crypto_intel_session, session)
    return dashboard.event_feed(session, symbol=symbol, signal_type=signal_type, severity=severity, include_research=include_research)


@app.get("/api/health/sources")
def get_source_health(session: Session = Depends(get_session), crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    get_current_admin(crypto_intel_session, session)
    return dashboard.source_health(session)


@app.post("/api/admin/collection-runs")
def create_collection_run(session: Session = Depends(get_session), crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    get_current_admin(crypto_intel_session, session)
    run = run_collection_once(session, settings, trigger="manual")
    return {"id": run.id, "status": run.status, "message": run.message, "summary": run.raw_summary}


@app.post("/api/admin/interpretations/regenerate")
def regenerate_interpretations(session: Session = Depends(get_session), crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    get_current_admin(crypto_intel_session, session)
    return regenerate_interpretations_for_latest_run(session)


@app.post("/api/admin/news-analyses/regenerate")
def regenerate_news_analyses(session: Session = Depends(get_session), crypto_intel_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    get_current_admin(crypto_intel_session, session)
    return regenerate_news_analyses_for_recent_news(session, settings)

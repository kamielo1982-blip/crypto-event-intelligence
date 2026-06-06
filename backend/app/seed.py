from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import Settings
from app.models import AdminUser, Asset


DEFAULT_ASSETS = [
    {"symbol": "BTC", "name": "Bitcoin", "coingecko_id": "bitcoin", "group": "investable", "rank": 1},
    {"symbol": "ETH", "name": "Ethereum", "coingecko_id": "ethereum", "group": "investable", "rank": 2},
    {"symbol": "BNB", "name": "BNB", "coingecko_id": "binancecoin", "group": "investable", "rank": 3},
    {"symbol": "SOL", "name": "Solana", "coingecko_id": "solana", "group": "investable", "rank": 4},
    {"symbol": "XRP", "name": "XRP", "coingecko_id": "ripple", "group": "investable", "rank": 5},
    {"symbol": "DOGE", "name": "Dogecoin", "coingecko_id": "dogecoin", "group": "investable", "rank": 6},
    {"symbol": "ADA", "name": "Cardano", "coingecko_id": "cardano", "group": "investable", "rank": 7},
    {"symbol": "TRX", "name": "TRON", "coingecko_id": "tron", "group": "investable", "rank": 8},
    {"symbol": "TON", "name": "Toncoin", "coingecko_id": "the-open-network", "group": "investable", "rank": 9},
    {"symbol": "AVAX", "name": "Avalanche", "coingecko_id": "avalanche-2", "group": "investable", "rank": 10},
    {"symbol": "USDT", "name": "Tether", "coingecko_id": "tether", "group": "stablecoin", "rank": 1},
    {"symbol": "USDC", "name": "USDC", "coingecko_id": "usd-coin", "group": "stablecoin", "rank": 2},
]


def seed_assets(session: Session) -> None:
    for item in DEFAULT_ASSETS:
        existing = session.scalar(select(Asset).where(Asset.symbol == item["symbol"]))
        if existing:
            existing.name = item["name"]
            existing.coingecko_id = item["coingecko_id"]
            existing.group = item["group"]
            existing.rank = item["rank"]
            existing.is_active = True
            continue
        session.add(Asset(**item, is_active=True))


def seed_admin(session: Session, settings: Settings) -> None:
    existing = session.scalar(select(AdminUser).where(AdminUser.username == settings.admin_username))
    if existing:
        return
    session.add(AdminUser(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))


def seed_defaults(session: Session, settings: Settings) -> None:
    seed_assets(session)
    seed_admin(session, settings)
    session.commit()

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services.data_quality import is_investor_grade_snapshot


@dataclass(frozen=True)
class SignalDraft:
    signal_type: str
    severity: str
    title: str
    description: str
    value: float | None
    source: str
    evidence: dict


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100


def severity_from_abs_pct(value: float | None, medium: float, high: float) -> str | None:
    if value is None:
        return None
    absolute = abs(value)
    if absolute >= high:
        return "high"
    if absolute >= medium:
        return "medium"
    return None


def build_market_signals(symbol: str, current: dict, previous: dict | None) -> list[SignalDraft]:
    if not previous:
        return []
    signals: list[SignalDraft] = []
    price_delta = pct_change(current.get("price_usd"), previous.get("price_usd"))
    price_severity = severity_from_abs_pct(price_delta, medium=3.0, high=6.0)
    if price_severity:
        direction = "상승" if price_delta and price_delta > 0 else "하락"
        signals.append(
            SignalDraft(
                signal_type="price_move",
                severity=price_severity,
                title=f"{symbol} 가격 {direction}",
                description=f"직전 스냅샷 대비 가격이 {price_delta:.2f}% {direction}했습니다.",
                value=round(price_delta, 4) if price_delta is not None else None,
                source="market_snapshot",
                evidence={"current": current, "previous": previous},
            )
        )

    volume_delta = pct_change(current.get("volume_24h_usd"), previous.get("volume_24h_usd"))
    volume_severity = severity_from_abs_pct(volume_delta, medium=25.0, high=60.0)
    if volume_severity:
        direction = "증가" if volume_delta and volume_delta > 0 else "감소"
        signals.append(
            SignalDraft(
                signal_type="volume_change",
                severity=volume_severity,
                title=f"{symbol} 거래량 {direction}",
                description=f"직전 스냅샷 대비 24h 거래량이 {volume_delta:.2f}% {direction}했습니다.",
                value=round(volume_delta, 4) if volume_delta is not None else None,
                source="market_snapshot",
                evidence={"current": current, "previous": previous},
            )
        )
    return signals


def build_news_signals(symbol: str, related_news: list[dict], observed_at: datetime) -> list[SignalDraft]:
    if len(related_news) < 3:
        return []
    severity = "high" if len(related_news) >= 6 else "medium"
    return [
        SignalDraft(
            signal_type="news_cluster",
            severity=severity,
            title=f"{symbol} 관련 뉴스 집중",
            description=f"최근 수집 구간에서 {symbol} 관련 뉴스가 {len(related_news)}건 감지되었습니다.",
            value=float(len(related_news)),
            source="news_items",
            evidence={
                "observed_at": observed_at.isoformat(),
                "items": [
                    {"title": item.get("title"), "url": item.get("url"), "source": item.get("source")}
                    for item in related_news[:6]
                ],
            },
        )
    ]


def build_onchain_signals(symbol: str, current: dict, previous: dict | None) -> list[SignalDraft]:
    if not previous or not is_investor_grade_snapshot(current.get("availability"), current.get("source")):
        return []
    signals: list[SignalDraft] = []
    for field, label in [("active_addresses", "활성 주소"), ("transaction_count", "거래 수")]:
        delta = pct_change(current.get(field), previous.get(field))
        severity = severity_from_abs_pct(delta, medium=15.0, high=35.0)
        if not severity:
            continue
        direction = "증가" if delta and delta > 0 else "감소"
        signals.append(
            SignalDraft(
                signal_type="onchain_change",
                severity=severity,
                title=f"{symbol} {label} {direction}",
                description=f"직전 스냅샷 대비 {label}가 {delta:.2f}% {direction}했습니다.",
                value=round(delta, 4) if delta is not None else None,
                source="onchain_snapshot",
                evidence={"field": field, "current": current, "previous": previous},
            )
        )
    return signals


def build_supply_signals(symbol: str, current: dict, previous: dict | None) -> list[SignalDraft]:
    if not previous or not is_investor_grade_snapshot(current.get("availability"), current.get("source")):
        return []
    delta = pct_change(current.get("circulating_supply"), previous.get("circulating_supply"))
    severity = severity_from_abs_pct(delta, medium=0.5, high=1.5)
    if not severity:
        return []
    direction = "증가" if delta and delta > 0 else "감소"
    return [
        SignalDraft(
            signal_type="supply_change",
            severity=severity,
            title=f"{symbol} 유통 공급량 {direction}",
            description=f"직전 스냅샷 대비 유통 공급량이 {delta:.2f}% {direction}했습니다.",
            value=round(delta, 4) if delta is not None else None,
            source="supply_snapshot",
            evidence={"current": current, "previous": previous},
        )
    ]

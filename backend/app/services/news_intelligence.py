from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import NewsAnalysis, NewsItem
from app.services.ai_interpreter import contains_disallowed_advice


PROMPT_VERSION = "news-ko-v1"
STANCE_LABELS = {
    "positive_candidate": "잠재적 호재",
    "neutral": "중립",
    "negative_candidate": "잠재적 악재",
    "mixed": "혼재",
    "unavailable": "판단 보류",
}
STANCE_VALUES = set(STANCE_LABELS)
HTML_TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
POSITIVE_RE = re.compile(r"\b(etf|inflow|approval|partnership|adoption|launch|upgrade|rally|surge|record|accumulate|falling exchange balance)\b", re.I)
NEGATIVE_RE = re.compile(r"\b(hack|exploit|lawsuit|ban|outflow|liquidation|selloff|crash|regulatory|probe|fine|security breach)\b", re.I)


@dataclass(frozen=True)
class NewsAnalysisPayload:
    summary_ko: str
    stance: str
    stance_label_ko: str
    stance_confidence: float
    reason_ko: str
    risk_notes: list[str]
    model: str
    analysis_source: str
    raw_output: dict


def parse_news_analysis_payload(payload: str | dict, model: str, analysis_source: str) -> NewsAnalysisPayload:
    data = json.loads(payload) if isinstance(payload, str) else payload
    required = {"summary_ko", "stance", "stance_confidence", "reason_ko"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"missing news analysis keys: {', '.join(sorted(missing))}")

    stance = str(data.get("stance") or "unavailable")
    if stance not in STANCE_VALUES:
        stance = "unavailable"
    generated_text = "\n".join(
        [
            str(data.get("summary_ko") or ""),
            str(data.get("stance_label_ko") or ""),
            str(data.get("reason_ko") or ""),
            "\n".join(str(item) for item in data.get("risk_notes") or []),
        ]
    )
    if contains_disallowed_advice(generated_text):
        raise ValueError("news analysis contains disallowed trading advice language")

    confidence = _clamp_confidence(data.get("stance_confidence"))
    return NewsAnalysisPayload(
        summary_ko=_compact_text(str(data.get("summary_ko") or "한국어 요약을 생성하지 못했습니다."), 420),
        stance=stance,
        stance_label_ko=STANCE_LABELS[stance],
        stance_confidence=confidence,
        reason_ko=_compact_text(str(data.get("reason_ko") or "근거가 충분하지 않아 참고 수준으로만 볼 수 있습니다."), 360),
        risk_notes=[_compact_text(str(item), 180) for item in (data.get("risk_notes") or [])[:3]],
        model=model,
        analysis_source=analysis_source,
        raw_output=data,
    )


def ensure_news_analyses(session: Session, settings: Settings, limit: int = 120) -> dict:
    rows = session.scalars(select(NewsItem).order_by(desc(NewsItem.published_at), desc(NewsItem.created_at)).limit(limit)).all()
    created = 0
    reused = 0
    sources: set[str] = set()
    for item in rows:
        existing = session.scalar(
            select(NewsAnalysis).where(
                NewsAnalysis.news_item_id == item.id,
                NewsAnalysis.language == "ko",
                NewsAnalysis.prompt_version == PROMPT_VERSION,
            )
        )
        if existing:
            reused += 1
            sources.add(existing.analysis_source)
            continue
        payload = analyze_news_item(item, settings)
        session.add(
            NewsAnalysis(
                news_item_id=item.id,
                language="ko",
                summary_ko=payload.summary_ko,
                stance=payload.stance,
                stance_label_ko=payload.stance_label_ko,
                stance_confidence=payload.stance_confidence,
                reason_ko=payload.reason_ko,
                risk_notes=payload.risk_notes,
                model=payload.model,
                prompt_version=PROMPT_VERSION,
                analysis_source=payload.analysis_source,
                generated_at=datetime.now(timezone.utc),
                raw_output=payload.raw_output,
            )
        )
        created += 1
        sources.add(payload.analysis_source)
    session.commit()
    return {"created": created, "reused": reused, "analysis_sources": sorted(sources)}


def regenerate_recent_news_analyses(session: Session, settings: Settings, limit: int = 120) -> dict:
    rows = session.scalars(select(NewsItem).order_by(desc(NewsItem.published_at), desc(NewsItem.created_at)).limit(limit)).all()
    ids = [row.id for row in rows]
    if not ids:
        return {"created": 0, "deleted": 0, "analysis_sources": []}
    existing = session.scalars(
        select(NewsAnalysis).where(
            NewsAnalysis.news_item_id.in_(ids),
            NewsAnalysis.language == "ko",
            NewsAnalysis.prompt_version == PROMPT_VERSION,
        )
    ).all()
    deleted = len(existing)
    for row in existing:
        session.delete(row)
    session.commit()
    result = ensure_news_analyses(session, settings, limit=limit)
    return {"created": result["created"], "deleted": deleted, "analysis_sources": result["analysis_sources"]}


def analyze_news_item(item: NewsItem, settings: Settings) -> NewsAnalysisPayload:
    if settings.openai_api_key and settings.openai_model != "local-heuristic":
        try:
            return _analyze_with_openai(item, settings)
        except Exception:
            return _local_fallback(item)
    return _local_fallback(item)


def _analyze_with_openai(item: NewsItem, settings: Settings) -> NewsAnalysisPayload:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    source = _sanitized_news_input(item)
    prompt = {
        "role": "system",
        "content": (
            "You analyze crypto news for a Korean private dashboard. "
            "Return strict JSON only. Do not provide buy/sell/long/short advice, price targets, or deterministic causality. "
            "Use cautious candidate language."
        ),
    }
    user = {
        "role": "user",
        "content": (
            "다음 뉴스가 해당 코인 가격 변동의 참고 신호가 될 수 있는지 한국어로 요약하고 분류해줘.\n"
            "JSON fields: summary_ko, stance, stance_confidence, reason_ko, risk_notes.\n"
            "stance enum: positive_candidate, neutral, negative_candidate, mixed, unavailable.\n"
            f"news={json.dumps(source, ensure_ascii=False)}"
        ),
    }
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[prompt, user],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    content = response.choices[0].message.content or "{}"
    return parse_news_analysis_payload(content, model=settings.openai_model, analysis_source="openai")


def _local_fallback(item: NewsItem) -> NewsAnalysisPayload:
    source = _sanitized_news_input(item)
    text = f"{source['title']} {source.get('summary') or ''}"
    has_positive = bool(POSITIVE_RE.search(text))
    has_negative = bool(NEGATIVE_RE.search(text))
    if has_positive and has_negative:
        stance = "mixed"
        reason = "긍정적 재료와 부정적 재료가 함께 언급되어 방향성은 혼재된 원인 후보로만 볼 수 있습니다."
    elif has_positive:
        stance = "positive_candidate"
        reason = "ETF, 채택, 업그레이드, 유입 등 긍정 키워드가 포함되어 잠재적 호재 후보로 분류했습니다."
    elif has_negative:
        stance = "negative_candidate"
        reason = "규제, 해킹, 유출, 하락 압력 등 부정 키워드가 포함되어 잠재적 악재 후보로 분류했습니다."
    else:
        stance = "neutral"
        reason = "강한 방향성 키워드가 부족해 중립적인 참고 뉴스로 분류했습니다."
    summary = f"{source['source']} 기사에서 {', '.join(source['related_symbols']) or '관련 코인'} 관련 이슈를 다루며, 가격 변동과 함께 확인할 참고 뉴스 후보입니다."
    payload = {
        "summary_ko": summary,
        "stance": stance,
        "stance_confidence": 0.35 if stance != "neutral" else 0.25,
        "reason_ko": reason,
        "risk_notes": ["로컬 규칙 기반 해석이므로 원문 맥락과 다를 수 있습니다."],
    }
    return parse_news_analysis_payload(payload, model="local-fallback", analysis_source="local_fallback")


def _sanitized_news_input(item: NewsItem) -> dict:
    return {
        "title": _compact_text(_strip_html(item.title), 220),
        "summary": _compact_text(_strip_html(item.summary or ""), 900),
        "source": _compact_text(item.source, 80),
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "related_symbols": list(item.related_symbols or [])[:12],
        "url_domain": urlsplit(item.url or "").netloc.lower(),
    }


def _strip_html(value: str) -> str:
    return SPACE_RE.sub(" ", HTML_TAG_RE.sub(" ", value)).strip()


def _compact_text(value: str, limit: int) -> str:
    normalized = SPACE_RE.sub(" ", value).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."


def _clamp_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    if confidence > 1:
        confidence = confidence / 100
    return max(0.0, min(1.0, confidence))

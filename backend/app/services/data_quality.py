from __future__ import annotations

from typing import Any


RESEARCH_ONLY_MAX_SCORE = 30
INVESTOR_GRADE = "investor_grade"
RESEARCH_ONLY = "research_only"
UNAVAILABLE = "unavailable"


def is_demo_source(source: str | None) -> bool:
    return source == "demo_fallback" or bool(source and source.endswith("_demo"))


def is_investor_grade_snapshot(availability: str | None, source: str | None) -> bool:
    return availability == "complete" and not is_demo_source(source)


def classify_snapshot_quality(availability: str | None, source: str | None) -> dict[str, Any]:
    if availability == "unavailable":
        return {
            "data_quality": UNAVAILABLE,
            "quality_reason": "필수 데이터가 없어 투자 판단용 신호로 사용하지 않습니다.",
            "is_investor_grade": False,
        }
    if not is_investor_grade_snapshot(availability, source):
        return {
            "data_quality": RESEARCH_ONLY,
            "quality_reason": "부분 수집 또는 demo fallback 데이터라 Research-only로 제한합니다.",
            "is_investor_grade": False,
        }
    return {
        "data_quality": INVESTOR_GRADE,
        "quality_reason": "완전한 외부 소스 데이터로 계산된 투자 참고용 신호입니다.",
        "is_investor_grade": True,
    }


def classify_signal_quality(signal_type: str, source: str | None, evidence: dict | None) -> dict[str, Any]:
    evidence = evidence if isinstance(evidence, dict) else {}
    current = evidence.get("current") if isinstance(evidence.get("current"), dict) else {}
    previous = evidence.get("previous") if isinstance(evidence.get("previous"), dict) else {}

    evidence_sources = [
        source,
        current.get("source") if isinstance(current, dict) else None,
        previous.get("source") if isinstance(previous, dict) else None,
    ]
    items = evidence.get("items") if isinstance(evidence.get("items"), list) else []
    for item in items:
        if isinstance(item, dict):
            evidence_sources.append(item.get("source"))
    if any(is_demo_source(item) for item in evidence_sources):
        return {
            "data_quality": RESEARCH_ONLY,
            "quality_reason": "demo fallback 기반 이벤트라 Research-only로만 표시합니다.",
            "is_investor_grade": False,
        }

    if signal_type in {"onchain_change", "supply_change"} or source in {"onchain_snapshot", "supply_snapshot"}:
        availability = current.get("availability") if isinstance(current, dict) else evidence.get("availability")
        snapshot_source = current.get("source") if isinstance(current, dict) else source
        return classify_snapshot_quality(availability, snapshot_source or source)

    return {
        "data_quality": INVESTOR_GRADE,
        "quality_reason": "가격/거래량/뉴스 계열의 기본 투자 참고 신호입니다.",
        "is_investor_grade": True,
    }


def cap_score_for_quality(score: int | float | None, data_quality: str) -> int:
    normalized = int(round(score or 0))
    if data_quality != INVESTOR_GRADE:
        return min(RESEARCH_ONLY_MAX_SCORE, normalized)
    return max(0, min(100, normalized))


def confidence_for_quality(score: int | float, data_quality: str) -> str:
    if data_quality != INVESTOR_GRADE:
        return "low"
    if score >= 75:
        return "high"
    if score >= 40:
        return "medium"
    return "low"

from __future__ import annotations

import json
import re
from dataclasses import dataclass


BANNED_ADVICE_PATTERNS = [
    r"\b(buy|sell|long|short)\b",
    r"매수",
    r"매도",
    r"수익률.*예측",
    r"확정.*원인",
]


@dataclass(frozen=True)
class InterpretationResult:
    summary: str
    candidates: list[dict]
    caveats: list[str]
    confidence: str
    model: str
    raw_output: dict


def contains_disallowed_advice(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in BANNED_ADVICE_PATTERNS)


def parse_interpretation_payload(payload: str | dict) -> dict:
    data = json.loads(payload) if isinstance(payload, str) else payload
    required = {"summary", "candidates", "caveats", "confidence"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"missing interpretation keys: {', '.join(sorted(missing))}")
    generated_text = _generated_language_for_safety_check(data)
    if contains_disallowed_advice(generated_text):
        raise ValueError("interpretation contains disallowed trading advice language")
    confidence = data["confidence"]
    if confidence not in {"low", "medium", "high"}:
        data["confidence"] = "low"
    return data


def _generated_language_for_safety_check(data: dict) -> str:
    parts = [str(data.get("summary", ""))]
    for candidate in data.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        parts.append(str(candidate.get("title", "")))
        parts.append(str(candidate.get("rationale", "")))
    parts.extend(str(caveat) for caveat in data.get("caveats", []))
    return "\n".join(parts)


class LocalHeuristicInterpreter:
    model = "local-heuristic"

    def interpret(self, symbol: str, signals: list[dict], data_quality_caveats: list[str] | None = None) -> InterpretationResult:
        data_quality_caveats = data_quality_caveats or []
        ranked = sorted(signals, key=lambda item: {"high": 3, "medium": 2, "low": 1}.get(item.get("severity"), 0), reverse=True)
        top = ranked[:3]
        if not top:
            payload = {
                "summary": f"{symbol}은 이번 스냅샷에서 강한 구조화 신호가 감지되지 않았습니다.",
                "candidates": [],
                "caveats": data_quality_caveats or ["신호가 없다는 것은 가격 영향 요인이 없다는 뜻은 아닙니다."],
                "confidence": "low",
            }
        else:
            candidates = [
                {
                    "title": item["title"],
                    "rationale": item["description"],
                    "evidence": item.get("evidence", {}),
                    "signal_type": item.get("signal_type"),
                }
                for item in top
            ]
            confidence = "high" if len(top) >= 3 and top[0].get("severity") == "high" else "medium"
            if data_quality_caveats:
                confidence = "medium" if confidence == "high" else "low"
            payload = {
                "summary": f"{symbol}은 이번 스냅샷에서 {len(top)}개의 주요 원인 후보가 감지되었습니다.",
                "candidates": candidates,
                "caveats": data_quality_caveats or ["해석은 원인 후보이며 투자 결정을 대신하지 않습니다."],
                "confidence": confidence,
            }
        parsed = parse_interpretation_payload(payload)
        return InterpretationResult(
            summary=parsed["summary"],
            candidates=parsed["candidates"],
            caveats=parsed["caveats"],
            confidence=parsed["confidence"],
            model=self.model,
            raw_output=parsed,
        )

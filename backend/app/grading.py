"""Completion anchors are server-owned; the model supplies evidence and a bounded adjustment."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

RUBRIC = [
    {"key": "preparation", "label": "仅完成准备", "min": 0, "max": 39, "baseline": 20, "description": "已进入实验或完成环境准备，尚无实质解题尝试。"},
    {"key": "attempt", "label": "已进行实质尝试", "min": 40, "max": 59, "baseline": 50, "description": "有与目标相关的输入或命令，但尚未确认关键步骤有效。"},
    {"key": "progress", "label": "完成关键步骤", "min": 60, "max": 79, "baseline": 70, "description": "已完成参考解法或等价方法的关键步骤，尚未确认最终结果。"},
    {"key": "result", "label": "已有成功结果", "min": 80, "max": 89, "baseline": 85, "description": "操作记录中有明确成功反馈，但 Flag 尚未通过判题。"},
    {"key": "verified", "label": "Flag 判题通过", "min": 90, "max": 100, "baseline": 95, "description": "平台确认本次实验提交的 Flag 正确。"},
]


class ScoreDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    band: Literal["unscored", "preparation", "attempt", "progress", "result", "verified"]
    reason: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(max_length=30)
    adjustment: int = Field(strict=True, ge=-5, le=5)
    adjustment_reason: str = Field(min_length=1, max_length=400)
    adjustment_evidence_ids: list[str] = Field(max_length=30)
    adjustment_basis: Literal["none", "effective_comparison", "targeted_adjustment", "clear_explanation", "unresolved_error"]


def calculate_score(decision, evidence, criteria):
    proposal = ScoreDecision.model_validate(decision).model_dump()
    events = {e["id"]: e for e in evidence.get("events", [])}
    submissions = {s["id"]: s for s in evidence.get("submissions", [])}
    known = events.keys() | submissions.keys()
    if not set(proposal["evidence_ids"] + proposal["adjustment_evidence_ids"]).issubset(known):
        raise ValueError("Unknown scoring citation")
    correct = [key for key, value in submissions.items() if value.get("correct") is True]
    complete = evidence.get("capture_complete") is True and not evidence.get("truncated", False)
    band, reason, refs = proposal["band"], proposal["reason"], proposal["evidence_ids"]
    if correct:
        band, reason, refs = "verified", "你提交的 Flag 已通过平台判题。", correct
    elif band == "verified":
        raise ValueError("Verified band requires a correct submission")
    elif not complete or not events:
        band, reason, refs = "unscored", "本次操作记录不足以确定完成程度，暂不评分。", []
    elif band != "unscored":
        if not set(refs) & events.keys():
            raise ValueError("Completion band requires operation evidence")
        by_key = {c["key"]: c for c in criteria}
        if band in ("attempt", "progress", "result") and not any(
            e.get("type") in ("terminal.submit", "web.submit", "web.change", "ui.change")
            for e in events.values()
        ):
            raise ValueError("Substantial attempt requires recorded input")
        key = "verification" if band == "result" else "method"
        criterion = by_key.get(key, {})
        if band in ("progress", "result") and (
            criterion.get("verdict") not in (("achieved",) if band == "result" else ("achieved", "partial"))
            or not set(criterion.get("evidence_ids", [])) & events.keys()
        ):
            raise ValueError("Completion band lacks corresponding criterion evidence")
    result = {"policy_version": 1, "rubric": RUBRIC, "proposal": proposal,
              "band": band, "reason": reason, "evidence_ids": refs,
              "score": None, "baseline": None, "adjustment": 0,
              "adjustment_reason": "暂不评分。", "adjustment_evidence_ids": [], "status": "unscored"}
    if band == "unscored":
        return result
    anchor = next(row for row in RUBRIC if row["key"] == band)
    delta, basis = proposal["adjustment"], proposal["adjustment_basis"]
    adjustment_refs = set(proposal["adjustment_evidence_ids"]) & events.keys()
    relevant = {"effective_comparison": "strategy", "targeted_adjustment": "strategy",
                "clear_explanation": "understanding", "unresolved_error": "method"}.get(basis)
    supported = any(c["key"] == relevant and set(c.get("evidence_ids", [])) & adjustment_refs
                    and c["verdict"] in (("needs_work",) if delta < 0 else ("achieved", "partial"))
                    for c in criteria)
    allowed = complete and supported and ((delta > 0 and basis != "unresolved_error") or
                                          (delta < 0 and basis == "unresolved_error"))
    if not allowed:
        delta = 0
    score = max(anchor["min"], min(anchor["max"], anchor["baseline"] + delta))
    result.update(status="scored", label=anchor["label"], baseline=anchor["baseline"],
                  score=score, adjustment=score - anchor["baseline"],
                  adjustment_reason=proposal["adjustment_reason"] if delta else "按本次完成程度计基准分，没有另行加减分。",
                  adjustment_evidence_ids=proposal["adjustment_evidence_ids"] if delta else [])
    return result


def published_score(report):
    """Only versioned, finalized grades participate in aggregates."""
    grading = (report or {}).get("scoring") or {}
    score = grading.get("score")
    if grading.get("policy_version") == 1 and grading.get("status") == "scored" and type(score) is int and 0 <= score <= 100:
        return score
    return None

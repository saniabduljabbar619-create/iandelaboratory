# -*- coding: utf-8 -*-
# app/services/sas/tier1/rule_engine.py
"""
SAS Tier 1 Rule Engine — pure logic, no AI API calls.
Predicts a field's likely current value from its historical trend,
and scores confidence based purely on the rules defined in our
confidence scoring model.
"""
from __future__ import annotations

import statistics
from typing import Optional


def predict_field_value(history: list[dict]) -> dict:
    """
    history: list of {"value": float, "date": iso-string}, oldest -> newest.

    Returns:
        {
            "predicted_value": float | None,
            "confidence": int,
            "trend_direction": "rising" | "falling" | "stable" | "unknown",
            "basis": str,
        }
    """
    values = [h["value"] for h in history if h.get("value") is not None]
    count = len(values)

    if count == 0:
        return {
            "predicted_value": None,
            "confidence": 10,
            "trend_direction": "unknown",
            "basis": "No prior history for this field. Manual entry required.",
        }

    if count == 1:
        return {
            "predicted_value": round(values[0], 2),
            "confidence": 55,
            "trend_direction": "stable",
            "basis": f"Based on 1 prior result ({values[0]}).",
        }

    if count == 2:
        avg = sum(values) / 2
        if values[-1] > values[0]:
            direction = "rising"
        elif values[-1] < values[0]:
            direction = "falling"
        else:
            direction = "stable"
        return {
            "predicted_value": round(avg, 2),
            "confidence": 65,
            "trend_direction": direction,
            "basis": f"Based on 2 prior results ({values[0]}, {values[-1]}).",
        }

    # 3 or more — trend-based extrapolation
    recent = values[-3:]
    diffs = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]
    avg_diff = sum(diffs) / len(diffs)
    predicted = recent[-1] + avg_diff

    consistency = statistics.pstdev(diffs) if len(diffs) > 1 else 0
    base_confidence = 90
    if avg_diff != 0 and consistency > abs(avg_diff):
        base_confidence = 80  # erratic trend, less confident

    if avg_diff > 0.01:
        direction = "rising"
    elif avg_diff < -0.01:
        direction = "falling"
    else:
        direction = "stable"
        base_confidence = min(base_confidence + 5, 95)

    confidence = min(max(base_confidence, 80), 95)

    return {
        "predicted_value": round(predicted, 2),
        "confidence": confidence,
        "trend_direction": direction,
        "basis": f"Based on {count} prior results. Trend: {direction} (last 3: {recent}).",
    }


def flag_predicted_value(
    value: Optional[float],
    low: Optional[float],
    high: Optional[float],
) -> str:
    """Applies the same reference range logic as ComputeService, for predicted values."""
    if value is None:
        return "unknown"
    if low is not None and value < float(low):
        return "LOW"
    if high is not None and value > float(high):
        return "HIGH"
    return "NORMAL"
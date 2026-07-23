# -*- coding: utf-8 -*-
# app/services/sas/tier2/response_parser.py
"""
Parses Claude API responses into normalized SAS prediction objects.
Handles partial responses, missing fields, and error states gracefully —
always returns something the UI can render even if Claude partially failed.
"""
from __future__ import annotations

from typing import Any


def parse_prediction_response(
    claude_response: dict,
    tier1_result: dict,
) -> dict:
    """
    Merges Claude's Tier 2 response with the Tier 1 baseline.
    Claude fields win where they exist and have reasonable confidence.
    Tier 1 fields fill in where Claude returned null or low confidence.
    """
    if "error" in claude_response:
        # Claude failed — fall back to Tier 1 entirely
        tier1_result["tier_used"] = 1
        tier1_result["tier2_error"] = claude_response["error"]
        tier1_result["tier2_attempted"] = True
        return tier1_result

    t2_predictions = claude_response.get("predictions", {})
    t2_confidence = claude_response.get("confidence_per_field", {})
    t2_reasoning = claude_response.get("reasoning", {})

    # Start from Tier 1 predictions as base
    merged_predictions = dict(tier1_result.get("predictions", {}))
    merged_confidence = dict(tier1_result.get("confidence_per_field", {}))

    # Claude fields with confidence >= 50 override Tier 1
    for key, value in t2_predictions.items():
        t2_conf = t2_confidence.get(key, 0)
        if value is not None and t2_conf >= 50:
            merged_predictions[key] = value
            merged_confidence[key] = t2_conf

    # Rebuild field details with merged data
    fields = []
    for f in tier1_result.get("fields", []):
        key = f["key"]
        merged_val = merged_predictions.get(key)
        merged_conf = merged_confidence.get(key, f["confidence"])
        reasoning = t2_reasoning.get(key, f["basis"])

        fields.append({
            **f,
            "predicted_value": merged_val,
            "confidence": merged_conf,
            "basis": reasoning,
            "tier_source": "tier2" if key in t2_predictions and t2_predictions[key] is not None else "tier1",
        })

    overall = (
        round(sum(merged_confidence.values()) / len(merged_confidence), 1)
        if merged_confidence else 0
    )

    return {
        **tier1_result,
        "predictions": merged_predictions,
        "confidence_per_field": merged_confidence,
        "overall_confidence": overall,
        "fields": fields,
        "tier_used": 2,
        "tier2_attempted": True,
        "clinical_notes": claude_response.get("clinical_notes"),
        "disease_alerts": claude_response.get("disease_alerts", []),
    }


def parse_query_response(claude_response: dict) -> dict:
    """Normalizes a Claude text query response."""
    if "error" in claude_response:
        return {
            "answer": "SAS was unable to process this query at this time.",
            "key_findings": [],
            "recommendations": [],
            "confidence": 0,
            "caveat": claude_response["error"],
            "tier_used": 1,
        }
    return {**claude_response, "tier_used": 2}
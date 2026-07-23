# -*- coding: utf-8 -*-
# app/services/sas/tier2/claude_client.py
"""
Claude API client for SAS Tier 2.
All calls are structured — Claude is always asked to return
clean JSON so response_parser can extract predictions reliably.
"""
from __future__ import annotations

import json
from typing import Optional

import anthropic

from app.core.config import settings


SAS_SYSTEM_PROMPT = """You are SAS — the Solunex Assistance System, the embedded AI of LabCore 2.0, a professional laboratory information system serving medical laboratories.

Your role:
- Assist medical laboratory scientists with result creation, interpretation, and clinical pattern recognition.
- Analyze patient test histories and predict likely current result values based on temporal trends, disease patterns, and reference range knowledge.
- Format lab results in the structure the user specifies (table, structured, narrative) with professional medical language.
- Answer data analysis questions about the lab's patient population.

Your constraints:
- You are a decision-support tool. You NEVER diagnose. You NEVER prescribe. You suggest; the qualified medical laboratory scientist decides.
- Always attach confidence scores (0-100) to predictions.
- Always state the basis for a prediction clearly and concisely.
- Flag when data is insufficient for confident prediction.
- Use SI units unless otherwise specified.
- Be aware of disease prevalence in West African clinical settings: malaria, typhoid, hepatitis B/C, sickle cell disease, tuberculosis, HIV/AIDS, and anaemia are high-frequency considerations.
- All patient data you receive is anonymized. Never attempt to re-identify patients.

Response format:
- ALWAYS return valid JSON only. No prose, no markdown, no code fences.
- Do not include any text before or after the JSON object.
- Follow the exact schema requested in each task."""


def _get_client() -> Optional[anthropic.Anthropic]:
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key or api_key == "your-anthropic-api-key-here":
        return None
    return anthropic.Anthropic(api_key=api_key)


def call_predict(payload: dict) -> dict:
    """
    Calls Claude for result value prediction.
    Returns parsed JSON prediction or an error dict.
    """
    client = _get_client()
    if not client:
        return {"error": "Anthropic API key not configured.", "tier_used": 1}

    prompt = f"""Given this anonymized patient data and clinical history, predict the most likely values for the current lab test request.

Patient context:
{json.dumps(payload['patient'], indent=2)}

Clinical timeline (most recent first):
{json.dumps(payload['clinical_timeline'], indent=2)}

Current request:
{json.dumps(payload['current_request'], indent=2)}

Return ONLY a JSON object with this exact structure:
{{
  "predictions": {{
    "<field_key>": <predicted_numeric_value_or_null>
  }},
  "confidence_per_field": {{
    "<field_key>": <confidence_0_to_100>
  }},
  "reasoning": {{
    "<field_key>": "<brief clinical reasoning for this prediction>"
  }},
  "clinical_notes": "<overall clinical interpretation in 1-2 sentences>",
  "disease_alerts": ["<any disease patterns SAS detected that the scientist should be aware of>"],
  "overall_confidence": <average_confidence_0_to_100>,
  "tier_used": 2
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SAS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse Claude response: {e}", "tier_used": 2}
    except Exception as e:
        return {"error": str(e), "tier_used": 2}


def call_text_query(payload: dict) -> dict:
    """
    Calls Claude for on-demand text analysis (Mode 5).
    Returns a structured answer.
    """
    client = _get_client()
    if not client:
        return {"error": "Anthropic API key not configured."}

    prompt = f"""Given this anonymized patient clinical history, answer the following question from a medical laboratory scientist.

Patient context:
{json.dumps(payload['patient'], indent=2)}

Clinical timeline:
{json.dumps(payload['clinical_timeline'], indent=2)}

Question: {payload['question']}

Return ONLY a JSON object with this structure:
{{
  "answer": "<clear, professional answer to the question>",
  "key_findings": ["<finding 1>", "<finding 2>"],
  "recommendations": ["<recommendation 1>"],
  "confidence": <0_to_100>,
  "caveat": "<any important limitations or caveats to this analysis>"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SAS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse Claude response: {e}"}
    except Exception as e:
        return {"error": str(e)}


def call_lab_analysis(question: str, context: dict) -> dict:
    """
    Calls Claude for lab-wide analysis questions
    (not patient-specific — used for trend analysis, population queries).
    """
    client = _get_client()
    if not client:
        return {"error": "Anthropic API key not configured."}

    prompt = f"""You are analyzing aggregated, anonymized laboratory data for a medical lab administrator.

Lab context:
{json.dumps(context, indent=2)}

Question: {question}

Return ONLY a JSON object:
{{
  "answer": "<clear answer>",
  "key_findings": ["<finding 1>", "<finding 2>"],
  "recommendations": ["<recommendation 1>"],
  "confidence": <0_to_100>
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SAS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}
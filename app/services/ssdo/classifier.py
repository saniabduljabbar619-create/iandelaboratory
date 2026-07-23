# -*- coding: utf-8 -*-
# app/services/ssdo/classifier.py
"""
SSDO Classifier — Tier 1 intelligence.
Assigns test_category, disease_tags, and severity_flag
to every record that enters the system.
No AI API calls — pure rule-based logic.
"""
from __future__ import annotations
from typing import Optional


# --------------------------------------------------
# TEST CATEGORY MAP
# Maps test type codes to clinical categories
# --------------------------------------------------
TEST_CATEGORY_MAP: dict[str, str] = {
    # Haematology
    "FBC":        "Haematology",
    "CBC":        "Haematology",
    "PCV":        "Haematology",
    "HB":         "Haematology",
    "ESR":        "Haematology",
    "SICKLING":   "Haematology",
    "CLOTTING":   "Haematology",
    "PT":         "Haematology",
    "APTT":       "Haematology",
    "BF":         "Haematology",   # Blood Film

    # Biochemistry
    "LFT":        "Biochemistry",
    "RFT":        "Biochemistry",
    "LIPID":      "Biochemistry",
    "FBS":        "Biochemistry",
    "RBS":        "Biochemistry",
    "HBA1C":      "Biochemistry",
    "ELECTRO":    "Biochemistry",
    "TFT":        "Biochemistry",
    "PSA":        "Biochemistry",
    "CRP":        "Biochemistry",
    "URIC":       "Biochemistry",
    "AMYLASE":    "Biochemistry",
    "LIPASE":     "Biochemistry",

    # Microbiology
    "CS":         "Microbiology",
    "WIDAL":      "Microbiology",
    "URINE_CS":   "Microbiology",
    "AFB":        "Microbiology",
    "GS":         "Microbiology",  # Gram Stain
    "HVS":        "Microbiology",
    "SWAB":       "Microbiology",

    # Serology / Immunology
    "HBSAg":      "Serology",
    "HEPATITIS":  "Serology",
    "HEP_B":      "Serology",
    "HEP_C":      "Serology",
    "HIV":        "Serology",
    "VDRL":       "Serology",
    "TPHA":       "Serology",
    "PREGNANCY":  "Serology",
    "MANTOUX":    "Serology",
    "ASO":        "Serology",
    "RF":         "Serology",

    # Parasitology
    "MAL":        "Parasitology",
    "MALARIA":    "Parasitology",
    "STOOL":      "Parasitology",
    "MCS":        "Parasitology",
    "URINE_MCS":  "Parasitology",

    # Blood Bank
    "BLOOD_GROUP":  "Blood Bank",
    "GENOTYPE":     "Blood Bank",
    "CROSS_MATCH":  "Blood Bank",
    "COOMBS":       "Blood Bank",
}


# --------------------------------------------------
# DISEASE TAG RULES
# Maps (test_code, field_name, flag_direction) → disease_tags
# flag_direction: "HIGH" | "LOW" | "POSITIVE" | "NEGATIVE"
# --------------------------------------------------
DISEASE_TAG_RULES: list[dict] = [
    # Haematology — Anaemia
    {"test": "FBC",      "field": "Hb",          "flag": "LOW",      "tags": ["anemia"]},
    {"test": "FBC",      "field": "HGB",         "flag": "LOW",      "tags": ["anemia"]},
    {"test": "FBC",      "field": "MCV",         "flag": "LOW",      "tags": ["microcytic_anemia"]},
    {"test": "FBC",      "field": "MCH",         "flag": "LOW",      "tags": ["hypochromic_anemia"]},
    {"test": "FBC",      "field": "RBC",         "flag": "LOW",      "tags": ["anemia"]},
    {"test": "PCV",      "field": "PCV",         "flag": "LOW",      "tags": ["anemia"]},

    # Haematology — Infection / Inflammation
    {"test": "FBC",      "field": "WBC",         "flag": "HIGH",     "tags": ["leukocytosis", "infection"]},
    {"test": "FBC",      "field": "WBC",         "flag": "LOW",      "tags": ["leukopenia"]},
    {"test": "FBC",      "field": "Neutrophils", "flag": "HIGH",     "tags": ["bacterial_infection"]},
    {"test": "FBC",      "field": "Lymphocytes", "flag": "HIGH",     "tags": ["viral_infection"]},
    {"test": "FBC",      "field": "Eosinophils", "flag": "HIGH",     "tags": ["parasitic_infection", "allergy"]},
    {"test": "ESR",      "field": "ESR",         "flag": "HIGH",     "tags": ["inflammation", "infection"]},
    {"test": "CRP",      "field": "CRP",         "flag": "HIGH",     "tags": ["inflammation", "infection"]},

    # Haematology — Platelets / Clotting
    {"test": "FBC",      "field": "Platelets",   "flag": "LOW",      "tags": ["thrombocytopenia"]},
    {"test": "FBC",      "field": "Platelets",   "flag": "HIGH",     "tags": ["thrombocytosis"]},

    # Sickle Cell
    {"test": "SICKLING", "field": "Sickling",    "flag": "POSITIVE", "tags": ["sickle_cell"]},
    {"test": "GENOTYPE", "field": "Genotype",    "flag": "SS",       "tags": ["sickle_cell_disease"]},
    {"test": "GENOTYPE", "field": "Genotype",    "flag": "AS",       "tags": ["sickle_cell_trait"]},

    # Biochemistry — Liver
    {"test": "LFT",      "field": "ALT",         "flag": "HIGH",     "tags": ["hepatic_stress"]},
    {"test": "LFT",      "field": "AST",         "flag": "HIGH",     "tags": ["hepatic_stress"]},
    {"test": "LFT",      "field": "ALP",         "flag": "HIGH",     "tags": ["hepatic_stress", "cholestasis"]},
    {"test": "LFT",      "field": "Bilirubin",   "flag": "HIGH",     "tags": ["jaundice", "hepatic_stress"]},
    {"test": "LFT",      "field": "GGT",         "flag": "HIGH",     "tags": ["hepatic_stress"]},

    # Biochemistry — Kidney
    {"test": "RFT",      "field": "Creatinine",  "flag": "HIGH",     "tags": ["renal_impairment"]},
    {"test": "RFT",      "field": "Urea",        "flag": "HIGH",     "tags": ["renal_impairment", "azotemia"]},
    {"test": "RFT",      "field": "GFR",         "flag": "LOW",      "tags": ["renal_impairment"]},

    # Biochemistry — Diabetes
    {"test": "FBS",      "field": "FBS",         "flag": "HIGH",     "tags": ["hyperglycemia", "diabetes"]},
    {"test": "RBS",      "field": "RBS",         "flag": "HIGH",     "tags": ["hyperglycemia", "diabetes"]},
    {"test": "HBA1C",    "field": "HbA1c",       "flag": "HIGH",     "tags": ["diabetes", "poor_glycemic_control"]},

    # Biochemistry — Lipids
    {"test": "LIPID",    "field": "Cholesterol", "flag": "HIGH",     "tags": ["hypercholesterolemia", "cardiovascular_risk"]},
    {"test": "LIPID",    "field": "Triglycerides","flag": "HIGH",    "tags": ["hypertriglyceridemia"]},
    {"test": "LIPID",    "field": "LDL",         "flag": "HIGH",     "tags": ["cardiovascular_risk"]},
    {"test": "LIPID",    "field": "HDL",         "flag": "LOW",      "tags": ["cardiovascular_risk"]},

    # Biochemistry — Thyroid
    {"test": "TFT",      "field": "TSH",         "flag": "HIGH",     "tags": ["hypothyroidism"]},
    {"test": "TFT",      "field": "TSH",         "flag": "LOW",      "tags": ["hyperthyroidism"]},
    {"test": "TFT",      "field": "T4",          "flag": "LOW",      "tags": ["hypothyroidism"]},

    # Parasitology — Malaria
    {"test": "MAL",      "field": "Malaria",     "flag": "POSITIVE", "tags": ["malaria"]},
    {"test": "MALARIA",  "field": "Malaria",     "flag": "POSITIVE", "tags": ["malaria"]},
    {"test": "BF",       "field": "Malaria",     "flag": "POSITIVE", "tags": ["malaria"]},

    # Microbiology — Typhoid
    {"test": "WIDAL",    "field": "H_antigen",   "flag": "HIGH",     "tags": ["typhoid"]},
    {"test": "WIDAL",    "field": "O_antigen",   "flag": "HIGH",     "tags": ["typhoid"]},

    # Microbiology — TB
    {"test": "AFB",      "field": "AFB",         "flag": "POSITIVE", "tags": ["tuberculosis"]},

    # Serology — Hepatitis
    {"test": "HBSAg",    "field": "HBsAg",       "flag": "POSITIVE", "tags": ["hepatitis_b"]},
    {"test": "HEPATITIS","field": "HBsAg",       "flag": "POSITIVE", "tags": ["hepatitis_b"]},
    {"test": "HEP_B",    "field": "HBsAg",       "flag": "POSITIVE", "tags": ["hepatitis_b"]},
    {"test": "HEP_C",    "field": "HCV",         "flag": "POSITIVE", "tags": ["hepatitis_c"]},

    # Serology — HIV
    {"test": "HIV",      "field": "HIV",         "flag": "POSITIVE", "tags": ["hiv"]},
    {"test": "HIV",      "field": "HIV_1_2",     "flag": "POSITIVE", "tags": ["hiv"]},

    # Serology — Syphilis
    {"test": "VDRL",     "field": "VDRL",        "flag": "POSITIVE", "tags": ["syphilis"]},
    {"test": "TPHA",     "field": "TPHA",        "flag": "POSITIVE", "tags": ["syphilis"]},

    # Serology — Pregnancy
    {"test": "PREGNANCY","field": "hCG",         "flag": "POSITIVE", "tags": ["pregnancy"]},
]


# --------------------------------------------------
# SEVERITY SCORING
# --------------------------------------------------
SEVERITY_WEIGHT: dict[str, int] = {
    "CRITICAL_HIGH": 4,
    "CRITICAL_LOW":  4,
    "HIGH":          2,
    "LOW":           2,
    "BORDERLINE":    1,
    "NORMAL":        0,
    "POSITIVE":      2,
}


def classify_test_category(test_code: str) -> str:
    """Returns the clinical category for a given test code."""
    code = (test_code or "").upper().strip()
    return TEST_CATEGORY_MAP.get(code, "General")


def classify_disease_tags(
    test_code: str,
    values: dict,
    flags: dict
) -> list[str]:
    """
    Returns a deduplicated list of disease tags based on
    test code, entered values, and flags.
    """
    code = (test_code or "").upper().strip()
    tags: set[str] = set()

    for rule in DISEASE_TAG_RULES:
        if rule["test"].upper() != code:
            continue

        field = rule["field"]
        expected_flag = rule["flag"].upper()

        # Check against flags dict first
        actual_flag = str(flags.get(field, "")).upper()
        actual_value = str(values.get(field, "")).upper()

        if actual_flag == expected_flag or actual_value == expected_flag:
            tags.update(rule["tags"])

    return sorted(tags)


def classify_severity(flags: dict) -> str:
    """
    Computes overall severity from the flags dictionary.
    Returns: normal | borderline | abnormal | critical | unknown
    """
    if not flags:
        return "unknown"

    max_weight = 0
    for flag_value in flags.values():
        flag_str = str(flag_value).upper().strip()
        weight = SEVERITY_WEIGHT.get(flag_str, 0)
        if weight > max_weight:
            max_weight = weight

    if max_weight >= 4:
        return "critical"
    elif max_weight >= 2:
        return "abnormal"
    elif max_weight >= 1:
        return "borderline"
    elif max_weight == 0 and flags:
        return "normal"
    return "unknown"


# --------------------------------------------------
# FLAG NORMALIZATION
# Handles the real ComputeService output format, which
# is {"Hb": {"state": "L", "low": 12, "high": 16, "value": 8.5}}
# rather than a plain string.
# --------------------------------------------------
STATE_CODE_MAP: dict[str, str] = {
    "L": "LOW",
    "H": "HIGH",
    "N": "NORMAL",
}


def normalize_flags(raw_flags: dict) -> dict:
    """
    Normalizes flags into simple string form regardless of source format.
    Supports both:
      - Simple string flags: {"Hb": "LOW"}
      - Compute-engine field flags: {"Hb": {"state": "L", ...}}
    """
    normalized: dict = {}
    for key, value in (raw_flags or {}).items():
        if isinstance(value, dict):
            state = str(value.get("state", "")).upper()
            normalized[key] = STATE_CODE_MAP.get(state, state or "UNKNOWN")
        else:
            normalized[key] = str(value).upper()
    return normalized


def classify_record(
    test_code: str,
    values: dict,
    flags: dict
) -> dict:
    """
    Master classification function.
    Returns all three classification outputs in one call.
    """
    normalized_flags = normalize_flags(flags)
    return {
        "test_category": classify_test_category(test_code),
        "disease_tags": classify_disease_tags(test_code, values, normalized_flags),
        "severity_flag": classify_severity(normalized_flags),
    }
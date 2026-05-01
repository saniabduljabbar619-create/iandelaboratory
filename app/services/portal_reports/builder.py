def build_bundle_result(result):
    snapshot = result.template_snapshot or {}
    values = result.values or {}
    flags = result.flags or {}

    test_name = result.test_type.name if result.test_type else "Test"

    # ==========================================
    # 1. MULTI-GRID / MULTI-TABLE (NEW FORMAT)
    # ==========================================
    # We check if 'sections' exists in values or snapshot
    sections = values.get("sections") or snapshot.get("sections")
    
    if sections:
        return {
            "type": "table",
            "request": {
                "test_name": test_name
            },
            # This 'uix' key is what your PDF renderer looks for 
            # to handle multiple tables in a loop.
            "uix": {
                "sections": sections
            }
        }

    # ==========================================
    # 2. LEGACY SINGLE GRID / TABLE
    # ==========================================
    cells = values.get("cells")
    if cells:
        return {
            "type": "table",
            "request": {
                "test_name": test_name
            },
            "grid": {
                "cells": cells
            }
        }

    # ==========================================
    # 3. STRUCTURED RESULTS (SINGLE PARAMETERS)
    # ==========================================
    fields = snapshot.get("fields") or []
    rows = []

    for f in fields:
        key = f.get("key")
        label = f.get("label") or key
        unit = f.get("unit") or ""
        value = values.get(key, "")
        flag = flags.get(key) or {}

        low = flag.get("low", "")
        high = flag.get("high", "")
        state = flag.get("state", "")

        ref_range = ""
        if low or high:
            ref_range = f"{low}-{high}"

        rows.append({
            "parameter": label,
            "result": value,
            "unit": unit,
            "ref_range": ref_range,
            "flag": state
        })

    return {
        "type": "structured",
        "request": {
            "test_name": test_name
        },
        "rows": rows
    }

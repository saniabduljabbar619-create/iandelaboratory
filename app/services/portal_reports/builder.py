def build_bundle_result(result):

    snapshot = result.template_snapshot or {}
    values = result.values or {}
    flags = result.flags or {}

    test_name = result.test_type.name if result.test_type else "Test"

    # =========================
    # GRID / TABLE RESULTS
    # =========================
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

    # =========================
    # STRUCTURED RESULTS
    # =========================
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
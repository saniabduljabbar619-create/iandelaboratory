# -*- coding: utf-8 -*-
# app/services/compute_service.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


class ComputeService:
    @staticmethod
    def _iterjs(d: Any, key: str, default=None):
        if isinstance(d, dict):
            return d.get(key, default)
        return default

    @staticmethod
    def _iter_fields(snapshot: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        # 1) Current format: snapshot["fields"]
        fields = snapshot.get("fields")
        if isinstance(fields, list):
            for f in fields:
                if isinstance(f, dict):
                    yield f

        # 2) Common nested format: snapshot["sections"][...]["fields"]
        sections = snapshot.get("sections")
        if isinstance(sections, list):
            for s in sections:
                if not isinstance(s, dict):
                    continue
                s_fields = s.get("fields")
                if isinstance(s_fields, list):
                    for f in s_fields:
                        if isinstance(f, dict):
                            yield f

        # 3) Optional: snapshot["tabs"][...]["sections"][...]["fields"]
        tabs = snapshot.get("tabs")
        if isinstance(tabs, list):
            for t in tabs:
                if not isinstance(t, dict):
                    continue
                t_sections = t.get("sections")
                if isinstance(t_sections, list):
                    for s in t_sections:
                        if not isinstance(s, dict):
                            continue
                        s_fields = s.get("fields")
                        if isinstance(s_fields, list):
                            for f in s_fields:
                                if isinstance(f, dict):
                                    yield f

    @staticmethod
    def _to_float(x: Any) -> Optional[float]:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None

    # -----------------------------
    # TABLE (fields-based) flags
    # -----------------------------
    @staticmethod
    def _compute_flags_for_fields(snapshot: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        for f in ComputeService._iter_fields(snapshot):
            key = f.get("key")
            if not key or key not in values:
                continue

            ref = f.get("ref") or {}
            low = ref.get("low")
            high = ref.get("high")

            v = ComputeService._to_float(values.get(key))
            if v is None:
                continue

            # Normalized to N/L/H for consistency with grid logic
            state = "N"
            if low is not None and v < float(low):
                state = "L"
            if high is not None and v > float(high):
                state = "H"

            out[str(key)] = {
                "state": state,
                "low": low,
                "high": high,
                "value": v,
            }

        return out

    # -----------------------------
    # GRID (schema + cells) flags
    # -----------------------------
    @staticmethod
    def _grid_schema(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        sch = snapshot.get("schema") or {}
        if not sch:
            g = snapshot.get("grid") or {}
            sch = g.get("schema") or {}
        return sch or {}

    @staticmethod
    def _safe_cell(cells: Any, r: int, c: int) -> str:
        if not isinstance(cells, list):
            return ""
        if r < 0 or r >= len(cells):
            return ""
        row = cells[r]
        if not isinstance(row, list):
            return ""
        if c < 0 or c >= len(row):
            return ""
        v = row[c]
        return (str(v).strip() if v is not None else "")

    @staticmethod
    def _compute_flags_for_grid(snapshot: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        sch = ComputeService._grid_schema(snapshot)
        enabled = bool(sch.get("enabled", False))
        if not enabled:
            return {}

        cols_map = (sch.get("columns") or {})
        res_c = cols_map.get("result")
        lo_c = cols_map.get("ref_min")
        hi_c = cols_map.get("ref_max")
        flag_c = cols_map.get("flag")
        param_c = cols_map.get("parameter")
        unit_c = cols_map.get("unit")

        if res_c is None or lo_c is None or hi_c is None or flag_c is None:
            return {}

        header_row = int(sch.get("header_row", 0) or 0)
        cells = values.get("cells")
        if not isinstance(cells, list):
            return {}

        row_flags: List[Dict[str, Any]] = []

        for r in range(header_row + 1, len(cells)):
            res_s = ComputeService._safe_cell(cells, r, int(res_c))
            lo_s = ComputeService._safe_cell(cells, r, int(lo_c))
            hi_s = ComputeService._safe_cell(cells, r, int(hi_c))

            res = ComputeService._to_float(res_s)
            lo = ComputeService._to_float(lo_s)
            hi = ComputeService._to_float(hi_s)

            if res is None or lo is None or hi is None:
                continue

            # 🔥 SYNC: Using "L", "H", "N" to match frontend result_table_editor.py logic
            state = "N"
            if res < lo:
                state = "L"
            elif res > hi:
                state = "H"

            entry: Dict[str, Any] = {
                "row_index": r,
                "state": state,
                "low": lo,
                "high": hi,
                "value": res,
                "flag_col": int(flag_c),
            }

            if param_c is not None:
                entry["parameter"] = ComputeService._safe_cell(cells, r, int(param_c))
            if unit_c is not None:
                entry["unit"] = ComputeService._safe_cell(cells, r, int(unit_c))

            row_flags.append(entry)

        return {
            "enabled": True,
            "header_row": header_row,
            "mode": sch.get("mode") or "minmax",
            "columns": cols_map,
            "rows": row_flags,
        }

    # -----------------------------
    # Public entrypoint
    # -----------------------------
    @staticmethod
    def compute_flags(snapshot: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified compute handler:
        - multi-grid: iterates through sections array
        - grid: handles single schema+cells logic
        - fields: fallback for legacy structured fields
        """
        snapshot = snapshot or {}
        values = values or {}

        kind = str(snapshot.get("kind") or "").strip().lower()

        # 🚀 1. Handle Multi-Grid (New Component Table System)
        if kind == "multi-grid" or "sections" in snapshot:
            sections = snapshot.get("sections") or []
            
            # Values for multi-grid are stored in uix['sections'] or directly in sections
            # We check both to be safe based on the payload structure
            val_sections = values.get("sections") or values.get("uix", {}).get("sections") or []
            
            multi_flags = []
            for i, sec_snap in enumerate(sections):
                # Match values to snapshot by index. If values missing, pass empty dict
                sec_vals = val_sections[i] if i < len(val_sections) else {}
                
                # Recursive call to handle the specific section (grid or field)
                multi_flags.append(ComputeService.compute_flags(sec_snap, sec_vals))
            
            return {
                "kind": "multi-grid",
                "sections": multi_flags
            }

        # 2. Handle Single Grid Snapshot
        if kind == "grid" or isinstance(snapshot.get("grid"), dict):
            grid_flags = ComputeService._compute_flags_for_grid(snapshot, values)
            return {"grid": grid_flags} if grid_flags else {}

        # 3. Backward Compatibility: Field-based (Old format)
        field_flags = ComputeService._compute_flags_for_fields(snapshot, values)
        return field_flags

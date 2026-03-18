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

            state = "normal"
            if low is not None and v < float(low):
                state = "low"
            if high is not None and v > float(high):
                state = "high"

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
        # schema can be at snapshot["schema"] OR snapshot["grid"]["schema"]
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
        """
        Uses schema mapping:
          schema = {
            enabled: bool,
            header_row: int,
            mode: "minmax",
            columns: { result, ref_min, ref_max, flag, parameter?, unit? }
          }
        Reads values["cells"] (2D list of strings).
        Returns a grid flags object; does NOT mutate values.
        """
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

        # must have minimum mapping
        if res_c is None or lo_c is None or hi_c is None or flag_c is None:
            return {}

        header_row = int(sch.get("header_row", 0) or 0)

        cells = values.get("cells")
        if not isinstance(cells, list):
            return {}

        rows_n = len(cells)
        # compute per row (below header)
        row_flags: List[Dict[str, Any]] = []

        for r in range(header_row + 1, rows_n):
            res_s = ComputeService._safe_cell(cells, r, int(res_c))
            lo_s = ComputeService._safe_cell(cells, r, int(lo_c))
            hi_s = ComputeService._safe_cell(cells, r, int(hi_c))

            res = ComputeService._to_float(res_s)
            lo = ComputeService._to_float(lo_s)
            hi = ComputeService._to_float(hi_s)

            if res is None or lo is None or hi is None:
                # skip rows that aren't numeric yet
                continue

            state = "normal"
            if res < lo:
                state = "low"
            elif res > hi:
                state = "high"

            entry: Dict[str, Any] = {
                "row_index": r,
                "state": state,
                "low": lo,
                "high": hi,
                "value": res,
                "flag_col": int(flag_c),
            }

            # Optional metadata
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
        Unified compute:
          - table/structured snapshots (fields-based): returns flags["fields"]
          - grid snapshots (schema+cells): returns flags["grid"]

        This keeps backward compatibility for existing structured callers.
        """
        snapshot = snapshot or {}
        values = values or {}

        kind = str(snapshot.get("kind") or "").strip().lower()

        # If it's a grid editor snapshot
        if kind == "grid" or isinstance(snapshot.get("grid"), dict):
            grid_flags = ComputeService._compute_flags_for_grid(snapshot, values)
            return {"grid": grid_flags} if grid_flags else {}

        # Otherwise treat as "table"/structured fields snapshot
        field_flags = ComputeService._compute_flags_for_fields(snapshot, values)
        return field_flags  # BACKWARD COMPAT: existing code expects {key: {...}}

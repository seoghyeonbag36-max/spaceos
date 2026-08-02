"""Rent heatmap layer backed by posting_inputs R-ONE rents."""
from __future__ import annotations

import math

from app.services import districts, posting_inputs


def _dist_m(a: float, b: float, c: float, d: float) -> float:
    dy = (a - c) * 111000
    dx = (b - d) * 88300
    return math.sqrt(dx * dx + dy * dy)


def _nearest_rent_per_pyeong(cell: dict, units: list[dict]) -> float:
    best = min(
        units,
        key=lambda u: _dist_m(cell["c_lat"], cell["c_lng"], u["lat"], u["lng"]),
    )
    return round(best["rent"] / best["area"], 1)


def rent_heatmap(district_id: str) -> dict | None:
    """Return a rent layer using the exact vacancy heatmap grid.

    R-ONE availability is determined through posting_inputs, the same service used
    by posting cards. Districts without R-ONE rent data are omitted by returning
    None rather than filling cells with zeroes or neighboring values.
    """
    if not posting_inputs.for_district(district_id):
        return None

    vacancy = districts.get_vacancy_heatmap(district_id)
    units = districts.resolved_units(district_id)
    if vacancy is None or units is None:
        return None

    rone_units = [
        u for u in units
        if u.get("area") and (u.get("inputs_source") or {}).get("rent") == "rone"
    ]
    if not rone_units:
        return None

    cells = []
    for cell in vacancy["cells"]:
        rent = _nearest_rent_per_pyeong(cell, rone_units)
        cells.append({
            "i": cell["i"], "j": cell["j"],
            "lat": cell["lat"], "lng": cell["lng"],
            "c_lat": cell["c_lat"], "c_lng": cell["c_lng"],
            "dlat": cell["dlat"], "dlng": cell["dlng"],
            "v": rent,
            "rent_per_pyeong": rent,
        })

    return {
        "district": district_id,
        "rent_source": "rone",
        "unit": "만원/평",
        "cells": cells,
    }

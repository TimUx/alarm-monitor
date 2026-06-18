"""Resolve German federal state (Bundesland) from coordinates for DWD map links."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

Bounds = Tuple[float, float, float, float]  # min_lat, max_lat, min_lon, max_lon


@dataclass(frozen=True)
class DwdRegion:
    """DWD warning map region (may cover one or more Bundesländer)."""

    code: str
    name: str
    bounds: Bounds


# DWD map codes: https://www.dwd.de/DE/wetter/warnungen_aktuell/objekt_einbindung/objekteinbindung_node.html
# Bounds are approximate; smaller regions are listed first for border cases.
DWD_REGIONS: Sequence[DwdRegion] = (
    DwdRegion("bbb", "Berlin", (52.33, 52.68, 13.08, 13.77)),
    DwdRegion("shh", "Hamburg", (53.39, 53.73, 9.73, 10.33)),
    DwdRegion("nib", "Bremen", (53.01, 53.59, 8.48, 8.99)),
    DwdRegion("rps", "Saarland", (49.11, 49.64, 6.35, 7.41)),
    DwdRegion("shh", "Schleswig-Holstein", (53.35, 55.06, 8.40, 11.20)),
    DwdRegion("mvp", "Mecklenburg-Vorpommern", (53.11, 54.69, 10.59, 14.41)),
    DwdRegion("bbb", "Brandenburg", (51.35, 53.55, 11.27, 14.77)),
    DwdRegion("saa", "Sachsen-Anhalt", (50.93, 53.04, 10.56, 13.19)),
    DwdRegion("thu", "Thüringen", (50.20, 51.65, 9.88, 12.65)),
    DwdRegion("sac", "Sachsen", (50.17, 51.68, 11.87, 15.04)),
    DwdRegion("hes", "Hessen", (49.39, 51.66, 7.77, 10.24)),
    DwdRegion("nrw", "Nordrhein-Westfalen", (50.32, 52.53, 5.87, 9.46)),
    DwdRegion("rps", "Rheinland-Pfalz", (48.97, 50.94, 6.11, 8.51)),
    DwdRegion("nib", "Niedersachsen", (51.30, 53.89, 6.65, 11.60)),
    DwdRegion("baw", "Baden-Württemberg", (47.53, 49.79, 7.51, 10.50)),
    DwdRegion("bay", "Bayern", (47.27, 50.56, 8.98, 13.84)),
)

DWD_MAP_URL_TEMPLATE = (
    "https://www.dwd.de/DWD/warnungen/warnapp_gemeinden/json/warnungen_gemeinde_map_{code}.png"
)

WARNING_LEVEL_LABELS = {
    1: "Wetterwarnung",
    2: "Warnung vor markantem Wetter",
    3: "Unwetterwarnung",
    4: "Warnung vor extremem Unwetter",
}

# Official DWD map colors (Warnstufen-Farbskala on regional warning maps).
WARNING_MAP_LEGEND = (
    {"level": 1, "label": "Wetterwarnung", "color": "#fff700"},
    {"level": 2, "label": "Markantes Wetter", "color": "#ff8c00"},
    {"level": 3, "label": "Unwetter", "color": "#e3000f"},
    {"level": 4, "label": "Extremes Unwetter", "color": "#9400d3"},
    {"level": "heat", "label": "Hitze/UV", "color": "#b565d9"},
)


def warning_map_legend() -> List[dict]:
    """Return a copy of the DWD warning map color legend for API/UI use."""
    return [dict(entry) for entry in WARNING_MAP_LEGEND]


def _in_bounds(lat: float, lon: float, bounds: Bounds) -> bool:
    min_lat, max_lat, min_lon, max_lon = bounds
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def resolve_dwd_region(lat: float, lon: float) -> Optional[DwdRegion]:
    """Return the DWD warning map region for the given coordinates."""
    for region in DWD_REGIONS:
        if _in_bounds(lat, lon, region.bounds):
            return region
    return None


def dwd_map_url(region_code: str) -> str:
    """Return the official DWD warning map image URL for a region code."""
    return DWD_MAP_URL_TEMPLATE.format(code=region_code)


__all__ = [
    "DWD_REGIONS",
    "DwdRegion",
    "WARNING_LEVEL_LABELS",
    "WARNING_MAP_LEGEND",
    "dwd_map_url",
    "resolve_dwd_region",
    "warning_map_legend",
]

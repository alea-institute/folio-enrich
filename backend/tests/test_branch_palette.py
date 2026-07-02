"""AC-8 (backend): stable branch-color palette for non-FOLIO branches.

FOLIO's 27 curated branch colors must stay byte-identical (regression guard), while
non-FOLIO branch names get a deterministic, distinct, non-gray color instead of the
old flat gray fallback.
"""

from __future__ import annotations

from app.services.folio.branch_config import BRANCH_CONFIG, get_branch_color
from app.services.ontology.palette import stable_color

_GRAY = "#4a5568"


def test_folio_branch_colors_byte_identical() -> None:
    # Every curated FOLIO branch name must return its exact configured hex.
    for cfg in BRANCH_CONFIG.values():
        assert get_branch_color(cfg["name"]) == cfg["color"]
    assert len(BRANCH_CONFIG) == 27


def test_empty_name_stays_gray() -> None:
    assert get_branch_color("") == _GRAY


def test_canon_branches_get_stable_distinct_nongray_colors() -> None:
    names = ["Sacraments", "Religious Events", "Councils"]
    colors = {name: get_branch_color(name) for name in names}

    # Non-gray: overflow palette, not the flat fallback.
    for name, color in colors.items():
        assert color != _GRAY, f"{name} fell back to gray"
        assert color.startswith("#") and len(color) == 7

    # Distinct across the sample.
    assert len(set(colors.values())) == len(names)

    # Stable across repeated calls / matches the palette function directly.
    for name in names:
        assert get_branch_color(name) == colors[name]
        assert get_branch_color(name) == stable_color(name)


def test_stable_color_is_deterministic() -> None:
    assert stable_color("Sacraments") == stable_color("Sacraments")

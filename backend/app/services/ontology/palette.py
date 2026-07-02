"""AC-8 overflow palette: deterministic stable colors for non-FOLIO branches.

FOLIO's 27 branches have hand-curated colors in ``branch_config.BRANCH_CONFIG``.
Other ontologies (e.g. the Catholic Semantic Canon) auto-derive their branches at
load time and have no curated palette, so ``get_branch_color`` falls back here to
assign each branch a stable, distinct hue.

The mapping is a pure function of the branch name via ``blake2b`` — NOT Python's
builtin ``hash()``, which is salted per-process (``PYTHONHASHSEED``) and would give
a branch a different color on every worker/restart. blake2b makes the color
identical across processes, workers, and restarts.
"""

from __future__ import annotations

import hashlib

# Fixed saturation/lightness keep every overflow color in the same tonal family as
# FOLIO's muted palette (mid saturation, medium-dark) so hues read as siblings, not
# a rainbow. Only the hue varies per branch name.
_SATURATION = 0.60
_LIGHTNESS = 0.42


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL (h in [0,360), s/l in [0,1]) to a ``#rrggbb`` hex string."""
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0.0
    elif h < 120:
        r, g, b = x, c, 0.0
    elif h < 180:
        r, g, b = 0.0, c, x
    elif h < 240:
        r, g, b = 0.0, x, c
    elif h < 300:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    return "#{:02x}{:02x}{:02x}".format(
        round((r + m) * 255), round((g + m) * 255), round((b + m) * 255)
    )


def stable_color(name: str) -> str:
    """Deterministic ``#rrggbb`` for a branch name (stable across processes)."""
    hue = int.from_bytes(hashlib.blake2b(name.encode(), digest_size=2).digest(), "big") % 360
    return _hsl_to_hex(hue, _SATURATION, _LIGHTNESS)

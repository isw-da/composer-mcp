"""Offline test — describe_theme_palette against real deployed themes.

Both fixtures are themes that shipped to customers. They put the named
palette at `content.variables.colors` and carry no `content.colors` key,
so a regression back to the old `content.colors` path makes `colors` null
and this test fails.

Run via:
  .venv/bin/python -m tests.test_theme_palette
"""

import asyncio
import json
import sys
from pathlib import Path

from composer_mcp.tools.themes import describe_theme_palette

FIXTURES = Path(__file__).parent / "fixtures"

# Spot-check values read straight out of the fixture files. If the tool
# starts reading a different path these stop matching.
DEPLOYED = {
    "deployed-theme-b.json": {
        "brandColor": "#084A8A",
        "palettes": ["DefaultSequential"],
    },
    "deployed-theme-a.json": {
        "brandColor": "#E00016",
        "palettes": [
            "ComboSequential",
            "DefaultSequential",
            "KPIBackgroundGradient",
            "KPIBackgroundGradientReverse",
            "KPIMetricGradient",
            "KPIMetricGradientReverse",
        ],
    },
}


class FakeClient:
    """Stands in for ComposerClient — returns one canned theme record."""

    def __init__(self, theme: dict) -> None:
        self._theme = theme

    async def get(self, path: str) -> dict:
        assert path.startswith("/customization/themes/"), path
        return self._theme


async def check(filename: str, expected: dict) -> list[str]:
    raw = json.loads((FIXTURES / filename).read_text())
    theme = {"id": "fixture", "masterThemeId": "modern", **raw}
    failures = []

    # The shape this test exists to pin down.
    if "colors" in theme["content"]:
        failures.append(
            f"{filename}: fixture has content.colors — it is no longer the "
            "deployed shape, so it can't hold this test up"
        )

    out = await describe_theme_palette(FakeClient(theme), "fixture")

    colors = out.get("colors")
    if not colors:
        failures.append(
            f"{filename}: colors is {colors!r} — the tool is reading "
            "content.colors, not content.variables.colors"
        )
    elif colors.get("brandColor") != expected["brandColor"]:
        failures.append(
            f"{filename}: brandColor {colors.get('brandColor')!r}, "
            f"expected {expected['brandColor']!r}"
        )

    if not out.get("charts"):
        failures.append(f"{filename}: charts is empty")

    # Not read by the tool, but the reason THEMES.md's "every theme must
    # include four KPI palettes" is wrong: deployed theme B ships one and is live.
    got = sorted(theme["content"]["variables"]["palettes"])
    if got != sorted(expected["palettes"]):
        failures.append(f"{filename}: palettes {got}, expected {expected['palettes']}")

    return failures


async def main() -> None:
    failures = []
    for filename, expected in DEPLOYED.items():
        failures += await check(filename, expected)
    for f in failures:
        print(f"FAIL  {f}")
    if failures:
        sys.exit(1)
    print(f"ok — {len(DEPLOYED)} deployed themes resolve a named palette")


if __name__ == "__main__":
    asyncio.run(main())

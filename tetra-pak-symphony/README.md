# tetra-pak-modern: proposed `symphony` block, and two customProperties fixes

Built 27 August 2026 from the evidence in `../CHATBOT_THEMING.md`. Nothing here has
been applied to any instance, and Peter Armstrong's bundle files were not modified.

## Files

| File | What it is |
|---|---|
| `build.py` | Derives the block from Tetra Pak's own `variables.colors`, using Otto as the structural reference. Re-runnable. |
| `symphony-block.json` | The block alone, for pasting into `content.symphony`. |
| `tetra-pak-logi-composer-theme.PROPOSED.json` | Full theme: original plus `symphony`, plus the two bug fixes. |
| `validate.py` | 29 adversarial checks. Exits 0. Run it after any edit to the JSON. |
| `preview.py` / `preview.html` | Renders the resolved tokens as a chat panel and before/after pairs for both bugs. Colours are read from the JSON, so the picture cannot drift from the data. |

## What the validator proves

Structural parity with Otto (same five components, the same 16 `chatBot` keys, no
inventions), all 13 `$colors.*` references resolving inside
`symphony.variables.colors` with no leak into the top-level namespace, the light
theme direction rules from the guide, WCAG AA on chat input text, suggestion
chips and sidebar icons, all four timebar background properties resolving to
opaque hex, the picker separated from the widget tile at 2.19:1 with AA text on
it, and no change anywhere outside `symphony` and the two named bugs.

## Colour decisions worth challenging

- **Brand ramp.** `brand.primary.100` to `400` are taken from the theme's own
  `DefaultSequential` palette; `500/600/700` are `brandColor`,
  `intentPrimaryHover`, `intentPrimaryActive`. Only `800/900/950` are derived,
  by darkening `#042D55`.
- **Semantic ramps.** Tailwind bodies kept, as Otto does, with Tetra Pak's own
  danger, warning and success colours dropped into the `400/500/600` stops.
  Only `danger.500` and `warning.500` are referenced by the chatbot.
- **dataSeries.** `01` and `02` are Tetra Pak's brand blue and secondary red;
  `03` to `13` are Otto's vendor spread with its near-blue moved to the end so
  it does not clash with `01`. No documented component reads this group.
- **metaDataPicker.** The brief named `background` only. `color` and
  `secondary` had to move with it: on a panel dark enough to be visible,
  `$colors.text` (`#4A5568`) fails AA at 3.43:1. They now point at
  `$colors.onSurface` and `$colors.primaryVariant`. Otto does the same thing,
  both of its picker text tokens being `#1A1A1A`.
- **Timebar hover.** `#D2DCE7` is `rgba(8,74,138,0.12)` composited over the
  timebar's own `#EDF0F4`, so the intended appearance is preserved and only the
  transparency that breaks the canvas clear is removed.

## Still open, and why

1. **Does Tetra Pak embed the chatbot?** Not answerable from local material.
   `grep -rl "tetra-pak-modern" ~/logi-composer` returns three files, all of
   them theme copies or the guide, and no embed anywhere passes the theme name
   to `createComponent('chat-bot', ...)`. Every chatbot embed in the bundle
   names `otto-partner-connect` or `__platform__`. That is an absence of
   evidence in Peter's bundle, not evidence of absence on their instance.
2. **Is the deployed theme this file?** Unknown. The three local copies are
   byte-identical (md5 `7ce9ac4ab0c0fc6f0d7576c49d53dda6`), dated 6 and 13 May,
   so there is no newer local variant to compare against. Only
   `composer_get_theme` on their instance settles it.
3. **The write.** Theme content writes return 403 from a tenant-admin session
   (`~/composer-mcp/LIMITATIONS.md:27-39`) and the `__platform__` workaround
   does not reach the chat surface, so applying this needs a Symphony global
   admin.

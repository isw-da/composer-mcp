# Chatbot theming: the `symphony` layer

> **How the evidence here works.** The findings below were established against
> two themes that really did ship to customers. Those two files are NOT in this
> repository and never were published: they sit in an internal working copy.
>
> What ships here instead is a pair of synthetic fixtures,
> `tests/fixtures/theme-with-symphony-six-palettes.json` and
> `theme-no-symphony-one-palette.json`, generated from them key for key with
> every concrete colour replaced. Structure is identical, so a citation below
> that points at a path resolves in this repo and means what it says. A claim
> about what a customer actually chose rests on the internal originals, and is
> marked where it appears.



> Absorbed from Peter Armstrong's Logi Composer toolkit on 27 August 2026, source
> `peter-kb/bundle-2026-05-21/logi-composer-toolkit/Styling/logi-composer-theme-guide.md`
> lines 185 to 262, cross-checked against the two deployed customer themes that
> ship beside it (`theme-with-symphony-six-palettes.json`,
> `theme-no-symphony-one-palette.json`).

`THEMES.md` is the schema reference for the whole theme record and gives the
`symphony` section two sentences (`THEMES.md:26`, `THEMES.md:42-44`).
`CHATBOT_EMBED.md:62-69` covers it from the consumption side: pass a custom
theme name to the bot and it only lands if that theme carries a `symphony`
section. This file is the missing middle, the shape of that section, what each
token drives, and which parts of it are load-bearing in themes that actually
shipped.

Both JSON files cited below are single-line minified documents, so evidence is
located by its JSON path rather than by line number.

## The silent failure mode, first

A theme with no `symphony` block is a perfectly valid theme. Composer accepts
it, the dashboard renders in brand, and the embedded Simba Intelligence chatbot
beside it quietly falls back to its own internal defaults
(`logi-composer-theme-guide.md:187`, restated as a rule at `:258`). Nothing
errors. No warning appears in the browser console, in the embed events, or in
any server log. The user sees a branded dashboard with an unbranded bot next to
it, and the only detection method is looking at the screen.

The evidence for this is not hypothetical, and the file is not in this repo.
Deployed theme B, held in the internal working copy, shipped to a customer with
`content` containing exactly `customProperties` and `variables` and no
`symphony` key at all. The synthetic fixture preserves that shape, so the claim
is checkable here too (`theme-no-symphony-one-palette.json`, `content`). Any
chatbot embedded with that theme is running Composer's stock chat colours on a
fully branded dashboard. Whether that was a decision or an oversight is not
recorded anywhere in the bundle; the guide that documents the trap
(`logi-composer-theme-guide.md:187`) sits in the same directory as the theme
that walks into it.

Check before you promise brand coverage: `composer_get_theme` on the target
theme and confirm `content.symphony.components.chatBot` exists. If it does not,
say so before the demo rather than after.

## Where `symphony` sits

Third top-level section inside `content`, a sibling of `variables` and
`customProperties` (`logi-composer-theme-guide.md:185-202`):

```json
"content": {
  "variables": { ... },
  "customProperties": { ... },
  "symphony": {
    "components": { ... },
    "variables": { "colors": { ... } }
  }
}
```

`symphony.variables.colors` is a separate namespace from the top-level
`variables.colors`. You cannot cross-reference between them
(`logi-composer-theme-guide.md:259`). A `$colors.*` reference written inside
`symphony.components` resolves against `symphony.variables.colors` only, so
`$colors.text` (a perfectly good top-level token) is a dangling reference here.

The content-wrapper rule in `THEMES.md:51-73` applies to `symphony` exactly as
it does to the other two sections: outside `content`, the PUT returns 200 and
stores `"content": {}`.

## `symphony.variables.colors`: the 12 token groups

| Group | Keys | Purpose | In Deployed theme A |
|---|---|---|---|
| `background.level0-5` | 6 | Surface layers, lightest to darkest | `#FFFFFF`, `#F8F8F8`, `#F2F2F2`, `#E5E5E5`, `#CCCCCC`, `#AAAAAA` |
| `brand.primary.50-950` | 11 | Brand accent ramp | `#FFF5F6` up to `#3D0004`, `500` = `#E00016` |
| `brand.secondary.300-700` | 5 | Second brand ramp, optional | absent |
| `foreground.level0-5` | 6 | Text and icon layers, darkest to lightest | `#1A1A1A` down to `#BBBBBB` |
| `neutral.400-600` | 3 | Mid greys | `#999999`, `#777777`, `#555555` |
| `slate.50-950` | 11 | Grey ramp, input backgrounds and subtle surfaces | see the bend below |
| `semantic.danger.50-950` | 11 | Red ramp | Tailwind red, `500` = `#EF4646` |
| `semantic.warning.50-950` | 11 | Orange ramp | Tailwind orange, `500` = `#F97316` |
| `semantic.success.50-950` | 11 | Green ramp | Tailwind green, `500` = `#22C55E` |
| `semantic.info.50-950` | 11 | Blue ramp | Tailwind sky, `500` = `#0EA5E9` |
| `dataSeries.01-13` | 13 | Chart series palette for Symphony visuals | 13 distinct hexes |
| `white` | 1 | Alias used by component tokens | `#FFFFFF` |

Group list and intent from `logi-composer-theme-guide.md:208-222`; the Deployed theme A
column is read from `theme-with-symphony-six-palettes.json`,
`content.symphony.variables.colors`.

Light versus dark direction: for a light theme run `background.level0-5` white
to mid grey, put a light surface in `slate.600` (the token the chat input
reads), and keep `inputColor` and `foreground.level0` dark. Reverse all of that
for a dark theme (`logi-composer-theme-guide.md:260`).

## `symphony.components`: the five components

| Component | Properties | Source |
|---|---|---|
| `chatBot` | 16, full table below | `logi-composer-theme-guide.md:227`, `:233-254` |
| `buttons` | `primary`, `secondary`, `accent`, `link`, each with `.default` and `.hover` | `:228` |
| `input` | `background`, `backgroundDisabled`, `border`, `borderActive`, `foreground` | `:229` |
| `actionCard` | `background`, `hoverBackground`, `activeBackground`, `description`, `icon` | `:230` |
| `sidebar` | `background`, `iconColor`, `tabBg`, `tabBgActive`, `tabBgHover`, `activeIndicatorColor`, `headingTabBg`, `menuBorder`, `profileBubble.bg`, `profileBubble.color`, `verticalAccentBg` | `:231` |

Deployed theme A carries all five, with every property in the guide's list present and no
extras (`theme-with-symphony-six-palettes.json`,
`content.symphony.components`). Two shapes are worth noting because they are
not plain colours: `sidebar.tabBg` is the literal string `"transparent"`, and
`sidebar.verticalAccentBg` is a `border-image` value,
`"linear-gradient(to bottom, #E00016 0%, #FF5566 100%) 1"`, trailing `1`
included. Copying that key as a flat hex will not render the accent bar.

## `symphony.components.chatBot`: the 16 properties

Every one is resolved at render time from `symphony.variables.colors` via
`$colors.*` or set as a literal hex, 8-digit hex, `rgba()`, or CSS gradient
(`logi-composer-theme-guide.md:235`). The Deployed theme A column is the deployed value.

| Property | Controls | Deployed theme A value |
|---|---|---|
| `background` | Main chat area background | `$colors.background.level1` |
| `bgGradient` | Welcome screen hero gradient | `linear-gradient(321.91deg, #A0000E 34.29%, #600007 80.96%)` |
| `gradientMask` | Gradient overlay on the welcome screen | `linear-gradient(180deg, #E00016 0%, rgba(224, 0, 22, 0.18) 49.84%, rgba(224, 0, 22, 0) 102.07%)` |
| `assistantMessageBg` | Assistant reply bubble | `#F2F2F2BF` |
| `userMessageBg` | User message bubble | `#FFFFFFBF` |
| `actionsMenuBg` | Context and actions menu panel | `#F2F2F2` |
| `inputBg` | Chat input field background | `$colors.slate.600` |
| `inputColor` | Chat input field text | `$colors.foreground.level0` |
| `suggestionChipBg` | Suggestion chip background | `$colors.brand.primary.500` |
| `suggestionChipHoverBg` | Suggestion chip hover | `$colors.brand.primary.400` |
| `suggestionChipText` | Suggestion chip text | `$colors.white` |
| `workingDots` | Typing and thinking indicator dots | `$colors.brand.primary.300` |
| `errorMessageBg` | Error bubble background | `#F8717133` |
| `errorMessageBorder` | Error bubble border | `$colors.semantic.danger.500` |
| `timeoutMessageBg` | Timeout bubble background | `#FB923C33` |
| `timeoutMessageBorder` | Timeout bubble border | `$colors.semantic.warning.500` |

Property list and purposes: `logi-composer-theme-guide.md:239-254`. Values:
`theme-with-symphony-six-palettes.json`,
`content.symphony.components.chatBot`, verified as exactly these 16 keys with
no additions and no omissions.

Two authoring conventions the guide states and Deployed theme A confirms. Message bubbles
use 8-digit hex so the chat background bleeds through, `BF` being roughly 75
percent opacity (`logi-composer-theme-guide.md:261`). The welcome gradient runs
at 321.91 degrees, a diagonal from bottom left to upper right, and takes two
dark tints of the brand primary (`:262`, `:369`); Deployed theme A uses `brand.primary.700`
and `brand.primary.900` by value rather than by token reference.

## Applying it

Pass the theme ID, or the theme name for a custom theme, as the `theme`
property of `ChatBotConfiguration` (`logi-composer-theme-guide.md:413-417`):

```js
embedManager.createComponent('chat-bot', {
  theme: 'my-theme-id',
  sources: [ '<sourceId>' ],
  config: { apiBaseUrl: '<server>/intelligence', mode: 'auto', timeout: 60 }
});
```

The rest of that config object is in `CHATBOT_EMBED.md`; the theme rule and the
fallback behaviour are at `CHATBOT_EMBED.md:62-69`.

The system `dark` theme ships with a `symphony` section and is the reference
shape to read when you want a known-good example on the instance you are
actually deploying to (`logi-composer-theme-guide.md:422`). Prefer it to the
bundled template: `GET /api/customization/themes` then `composer_get_theme` on
`dark` gives you resolved values from the live instance, whereas the template
gives you `BRAND_*` strings. `modern` is the safe fallback theme name when a
custom theme's `symphony` coverage is unknown (`CHATBOT_EMBED.md:69`).

## What the deployed themes prove that a template cannot

**Which tokens are load-bearing.** Of the 16 `chatBot` properties, 9 resolve
through `$colors.*` and 7 are literals in Deployed theme A. The token references touch only
`background.level1`, `slate.600`, `foreground.level0`, `brand.primary.300/400/500`,
`white`, `semantic.danger.500`, and `semantic.warning.500`. That is 9 values out
of roughly 95 tokens defined in `symphony.variables.colors`. The remaining
groups are defined and unreferenced by any component in the file, `dataSeries`
and `neutral` most obviously. Whether the chatbot consumes `dataSeries`
internally for chart rendering is not documented, and this file does not prove
it. Populating those groups is defensive, so keep them.

**The slate ramp is deliberately broken.** Deployed theme A's `slate` is a normal light-to-dark
ramp from `50` (`#F8F8F8`) to `500` (`#777777`), then reverses: `600` is
`#FFFFFF`, `700` `#F8F8F8`, `800` `#F2F2F2`, `900` `#E5E5E5`, `950` `#CCCCCC`
(`theme-with-symphony-six-palettes.json`,
`content.symphony.variables.colors.slate`). The reason is `chatBot.inputBg`
pointing at `$colors.slate.600`: on a light theme the input has to be white, so
the ramp was bent at that stop rather than the property being given a literal.
Peter's guide hints at this in one clause (`logi-composer-theme-guide.md:260`),
and the deployed file shows the consequence, which is that `slate` in a light
Composer theme is not a monotonic scale and should not be treated as one when
you reuse it for anything else.

**Semantic ramps were left stock.** All four `semantic.*` families in Deployed theme A are
the Tailwind defaults, untouched apart from `danger.500` (`#EF4646` against
Tailwind's `#EF4444`). Only `danger.500` and `warning.500` are referenced by
the chatBot block. Rebranding the semantic ramps is optional work with no
visible effect on the bot unless you also repoint those two properties.

**A key present in production and documented nowhere.** Deployed theme A's
`variables.palettes` carries `ComboSequential` alongside `DefaultSequential`
and the four KPI palettes, and `customProperties.charts.COMBO_CHART.palette`
and `charts.LINE_AND_BARS.palette` both point at it
(`theme-with-symphony-six-palettes.json`, `content.variables.palettes` and
`content.customProperties.charts`). Neither Peter's guide (`:53-54`) nor
`THEMES.md:34-35` mentions it. The lesson is that the palette set is open:
any named palette in `variables.palettes` can be referenced by a
`charts.{TYPE}.palette` value, so palette names are not a fixed vocabulary of
five. This sits outside the `symphony` layer and belongs in `THEMES.md`, noted
here because the evidence turned up in the same file.

**A documented key absent from both deployed themes.**
`brand.secondary.300-700` is in the guide's token table
(`logi-composer-theme-guide.md:212`, marked optional). Deployed theme A's `brand` contains
`primary` only, and Deployed theme B has no `symphony` at all, so no shipped theme
exercises it. Treat it as genuinely optional and expect no component in the
documented five to reference it.

## Two corrections to carry

### The four KPI palettes are not mandatory

Peter's guide states that every Logi Composer theme "must include four KPI
palettes" (`logi-composer-theme-guide.md:268`). Deployed theme B ships
`variables.palettes` containing `DefaultSequential` alone
(`theme-no-symphony-one-palette.json`, `content.variables.palettes`) and
renders in production. The claim is false as written. The four palettes are
needed only when KPI conditional formatting is in play, since that is what
consumes them (`THEMES.md:81-85`). Include all four when you want performance
colouring on KPI tiles, and when reading someone else's theme treat any of them
as legitimately absent.

### Do not copy `customProperties` from the Deployed theme B example

The guide's minimal-theme recipe is to start from
`logi-composer-theme-template.json` and replace the `BRAND_*` placeholders
(`logi-composer-theme-guide.md:358`), and the bundle's own workflow note points
at the Deployed theme B file as the deployed example to copy. `THEMES.md:206-209` forbids
that approach outright: never build a theme by copying `customProperties` from
a template, an example file, or a different instance, because
`customProperties` schemas differ between instances and versions and a
mismatch fails silently as blank grey sidebar panels (`THEMES.md:191-204`).

The Deployed theme B file also carries two of Peter's own documented bugs, verified in
the JSON:

- `customProperties.timebar.backgroundColorHover` and
  `customProperties.timebar.scrubber.backgroundColorHover` are both
  `rgba(8,74,138,0.12)`. That is the semi-transparent value the guide's own
  timebar section says must never be used, because the scrubber canvas then
  fails to clear and period labels double-render
  (`logi-composer-theme-guide.md:104-123`).
- `customProperties.metaDataPicker.background` is `$colors.surface`, which
  resolves to `#fff`, the exact value of `customProperties.widget.background`.
  The guide describes this failure with the default token
  `$colors.backgroundVariant` (`:129`); Deployed theme B is the worse case, picker and
  widget tile identical, so the dimension picker is invisible rather than merely
  low contrast.

Deployed theme A is the corrected counterpart on both counts: opaque `#E0E0E0` and
`#FCEAEC` on the timebar, `#BEBEBE` on the picker
(`theme-with-symphony-six-palettes.json`, `content.customProperties.timebar`
and `.metaDataPicker`). If you must start from a deployed file rather than a
fresh reference pull, start from Deployed theme A, and still follow the reference-theme
workflow in `THEMES.md:206-235`.

## The write path Peter's material never mentions

The guide's happy path is to fill in the `BRAND_*` placeholders and POST to
`/api/customization/themes`, or PUT to update an existing theme ID
(`logi-composer-theme-guide.md:166-176`, `:394-406`). From a tenant-admin
session that path returns `403 Forbidden / Access Denied`, including on themes
the tenant created through the UI (`LIMITATIONS.md:27-39`). Nothing in the
toolkit's theming material records this, so following it as written produces a
finished, correct `symphony` block that cannot be written to the instance.

Three ways out (`LIMITATIONS.md:33-39`):

1. Pass `theme: '__platform__'` to the embed manager and brand the shell with
   your own CSS, per-visual palette settings winning where they matter.
2. Apply branding through host-page CSS reaching into Composer's native DOM,
   canonical override block in `EMBEDDING.md`.
3. Ask a Symphony global admin to apply the theme edits for you.

For the chatbot specifically, option 1 does not help: the bot's chat surface is
themed through `symphony` and nothing else, so an instance where theme writes
403 is an instance where custom chatbot branding requires a global admin. Say
that out loud in scoping rather than discovering it during a build.

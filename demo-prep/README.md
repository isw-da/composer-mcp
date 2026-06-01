# Demo prep: voice-over walkthrough videos

How I turn a demo into a recorded, narrated walkthrough that prospects can
replay, and that I can re-record over with my own voice when I want a polished
final cut.

This is the working pipeline behind the Amplifin governance walkthrough (27
beats, 7 minutes 38 seconds, end-to-end Tell-Show-Tell with annotated SI
screens). It generalises to any deal with very small edits.

## Output

For each demo I produce four artefacts:

1. **Slide deck**, numbered PNGs in `~/Downloads/<deal>-slides/`.
2. **Recording script**, a markdown table and a plain text teleprompter.
3. **Storyboard**, a single-page HTML with thumbnails and narration side by
   side. Designed to scroll alongside the mp4 while reviewing.
4. **Synced mp4**, TTS-narrated walkthrough at 1280x720, 25 fps.

The mp4 is the one I ship to prospects. The storyboard is what I use to
record over the top with my own voice if I want a more personal version.

## Structure: Demo2Win Tell-Show-Tell

Every walkthrough follows the same shape:

- Title slide (limbic open, one sentence on why)
- Visual roadmap, all parts dimmed except the current focus
- Per part:
  - Roadmap (current part highlighted)
  - Tell card (D+A branded, conceptual)
  - Show (SI screen, annotated with a focus highlight)
  - Tell impact (D+A branded, "so you can ...")
- Final roadmap with all parts revealed
- Value close
- Call to action

The roadmap-tell-show-tell rhythm is what keeps the audience oriented and
stops the video drifting into feature walkthroughs.

## File layout

```
demo-prep/
  README.md
  scripts/
    annot.py           # focus()/crop_to() PIL helpers for SI screens
    gtts.py            # Google Cloud TTS wrapper
    build.py           # per-beat ffmpeg + TTS stitcher
    gen_script.py      # produce .md + .txt teleprompter
    gen_storyboard.py  # produce single-page HTML
  examples/
    walk_example.json  # example beat JSON
```

For a real demo I create a per-deal working directory (e.g.
`~/<deal>-build/`) that holds the deal-specific `walk.json`, the raw SI gif
captures, the annotated PNGs, and the rendered D+A cards. The scripts in
`demo-prep/scripts/` are not copied per deal, they are imported from
wherever they live.

## The pipeline

1. **Capture SI screens**. Drive SI in Chrome with the
   `mcp__claude-in-chrome__*` tools and record short clips with the
   `gif_creator` tool. Then extract frames with ffmpeg:

   ```bash
   ffmpeg -y -i capture.gif -vsync 0 frames/f_%02d.png \
     -hide_banner -loglevel error
   ```

   Why gif and not direct PNG? `computer_use.screenshot` only returns inline
   data, gif is the only reliable persist path through the Chrome extension.

2. **Annotate**. For each captured frame, pick the box that holds the thing
   the narration is talking about, then call `annot.focus()`. The helper
   dims everything outside the box, draws a fuchsia border (D+A `#C5267E`),
   pastes a zoomed inset on one side, and labels the focus. The viewer sees
   exactly what the voice is pointing at without having to scan the screen.

   ```python
   from annot import focus
   focus("raw/row_security.png", "annotated/row_filter.png",
         box=(0.43, 0.62, 0.74, 0.79),
         label="Step 4: Branch Region INCLUDE Western Cape",
         zoom=(1.5, "left"))
   ```

3. **Render D+A cards**. For roadmaps, title cards, the six-step pattern
   card, the value close, and so on, use a Chrome headless render against an
   HTML template with Poppins and the D+A palette. The template is in the
   companion `walkthrough/build/scripts/render_da2.py` in the work repo
   (deal-specific, not in this playbook). The base style is in the brand
   section below.

4. **Wire the beats**. One JSON file, list of `{img, label, text}` objects,
   one per slide. `img` is an absolute path so the build can run from
   anywhere. `label` is a short human-readable label for the storyboard.
   `text` is the narration as you want it spoken.

5. **Build the video**. Run `python3 scripts/build.py path/to/walk.json
   en-GB-Chirp3-HD-Charon`. It synthesises TTS per beat, builds a per-beat
   1280x720 letterboxed mp4, concats them, writes
   `~/Downloads/<scene>-synced.mp4`.

6. **Generate script and storyboard**. Run `gen_script.py` and
   `gen_storyboard.py` against the same walk JSON. The script gives you a
   numbered markdown table and a plain text teleprompter. The storyboard
   gives you an HTML page with thumbnails plus narration, perfect for
   reading while you record over the top.

7. **Re-record over**. Open the mp4, mute it, scroll the storyboard, read
   each line into your recorder. Or ship the TTS version as-is.

## Beat JSON

```json
[
  {
    "img": "/abs/path/to/01_title.png",
    "label": "Title - one sentence on why",
    "text": "Narration for this beat, written for the ear. Short sentences. No semicolons. Read it out loud and listen for stumbles."
  },
  {
    "img": "/abs/path/to/02_roadmap.png",
    "label": "Roadmap - agenda",
    "text": "..."
  }
]
```

Notes:

- One JSON beat = one slide = one TTS clip. Per-beat duration is whatever
  the TTS produces plus a 0.7 second tail.
- Keep each beat between 8 and 25 seconds of narration. Longer than that and
  the slide gets boring. Shorter than that and the cut feels jerky.
- Write for the ear. Avoid abbreviations the TTS will mispronounce
  ("WCape" becomes "double-you cape"; spell out as "W-cape" or use the long
  form). Spell numbers out for emphasis ("one hundred and sixteen", not
  "116") if you want them to land.

## Annotation idioms

`annot.py` exposes two functions.

- `focus(src, dst, box, label=None, zoom=None, dim=0.55, border=4)`. Dims
  outside the box, draws a fuchsia border around the box. Optional
  `zoom=(scale, side)` pastes a magnified copy of the box on one side
  (`left`, `right`, `top`, `bottom`). Optional `label` puts a fuchsia pill
  with white text next to the box.
- `crop_to(src, dst, box, label=None, target=(1280,720))`. Crops the source
  to the box, letterboxes onto a slate 1280x720 canvas. For "overview"
  slides where you want the whole region clean rather than a focus
  highlight.

Boxes are `(x1, y1, x2, y2)` in pixels, or relative floats all in `[0, 1]`.
Relative makes the script source-resolution independent, which matters when
the gif extraction sizes drift between captures.

## Voice (TTS)

Google Cloud Text to Speech, voice `en-GB-Chirp3-HD-Charon` (British male,
neutral, presentation-paced). `gtts.py` is a thin wrapper. It reads the
service account from `GCP_SA_PATH` (env var) or
`~/.config/demo-prep/gcp-sa.json` as a fallback.

Speaking rate 0.9 sounds right for a demo. Faster than that and it loses
gravity; slower and it sounds slow.

Voice cloning with ElevenLabs is the next step if you want the synced
version to sound like you instead of Charon. Reuse the same beat JSON, swap
the TTS function in `build.py`.

## Brand: D+A palette

Used in every D+A card and every annotation border.

- Slate `#2E2E2D` (text on light, background on dark)
- White `#FFFFFF`
- Purple `#46217C` (titles, accents)
- Black `#000000`
- Fuchsia `#C5267E` (highlights, focus borders, callouts)

Font: Poppins (400, 500, 600, 700). Code blocks use Roboto Mono.

Card layout: 1280x720, content box at `left:84px; top:64px; right:78px;
bottom:80px`, title at 39px Poppins 600, subtitle at 22px Poppins 500
italic in purple.

## What this is not

- Not a production tool. Each demo customises cards, screens, narration.
  The pipeline assembles, it does not generalise across personas.
- Not a substitute for a recorded human take. The TTS version is good
  enough for early reviews; the final cut should be your voice.
- Not a presentation deck. The output is video, not slides you click through
  live.

## Worked example

The Amplifin governance walkthrough, 27 beats, 7m 38s, was built with this
exact pipeline. The beat JSON, annotation script, and gif captures live in
my work repo (deal-specific, not committed here). The reusable bits, the
scripts in this directory, were extracted from that build.

Pattern summary from that build:

- 14 D+A cards (title, roadmaps, profiles card, six-step pattern card,
  five gate-test chat cards, value close, CTA).
- 10 annotated SI screens (groups list, privileges, users, source canvas,
  fields list, derived field detail, row filter panel, column block panel,
  source permissions, function carve-out).
- One overview frame.
- Charon voice at rate 0.9.

The annotated SI screens were the difference between the first cut (felt
abstract, "what are we looking at?") and the final cut (each frame points
directly at the field, the rule, the panel that the narration is naming).

#!/usr/bin/env python3
"""Single-page HTML storyboard: thumbnail + label + narration per beat.

Usage:
    python3 gen_storyboard.py <walk.json> [out.html]

Writes <out.html> next to walk.json (default
~/Downloads/<scene>-storyboard.html). Expects slides at
~/Downloads/<scene>-slides/ (run gen_script.py first to populate that).

The beat JSON must include `img`, `text`, and optionally `label` and
`section`. Beats with the same `section` value are grouped under one
section heading in the storyboard.
"""
import json, os, sys

walk = os.path.abspath(sys.argv[1])
scene = os.path.splitext(os.path.basename(walk))[0]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser(
    f"~/Downloads/{scene}-storyboard.html"
)
slides_dirname = f"{scene}-slides"

beats = json.load(open(walk))
rows = []
for i, b in enumerate(beats, 1):
    bn = os.path.basename(b["img"]).replace(".png", "")
    fn = f"{i:02d}_{bn}.png"
    rows.append((
        i, fn,
        b.get("label", bn),
        b.get("section", "Walkthrough"),
        b["text"],
    ))

html = ["""<!doctype html><html lang=en><head><meta charset=utf-8>
<title>__SCENE__ - storyboard</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;background:#0d0d0d;color:#e9e8e6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.55}
header{padding:36px 48px 12px;border-bottom:1px solid #2a2a2a}
h1{margin:0 0 6px;font-weight:600;font-size:28px}
header p{margin:0;color:#9a9892;font-size:14px}
.part{padding:24px 48px 8px;border-top:1px solid #1f1f1f}
.part h2{margin:0 0 18px;color:#C5267E;font-weight:600;font-size:20px;letter-spacing:0.3px}
.beat{display:grid;grid-template-columns:380px 1fr;gap:28px;padding:14px 48px 22px;border-bottom:1px solid #1a1a1a}
.beat:last-child{border-bottom:none}
.beat .thumb{position:relative}
.beat img{width:100%;border-radius:8px;border:1px solid #2a2a2a;background:#000}
.beat .num{position:absolute;top:8px;left:8px;background:rgba(0,0,0,0.7);color:#fff;font-weight:600;padding:4px 10px;border-radius:14px;font-size:12px}
.beat .copy{padding-top:2px}
.beat .label{color:#46217C;background:#f5f4f1;display:inline-block;padding:4px 10px;border-radius:12px;font-size:12px;font-weight:600;margin-bottom:10px}
.beat .text{color:#dad9d5;font-size:15.5px}
footer{padding:30px 48px 60px;color:#777572;font-size:12px}
@media print {body{background:#fff;color:#000}.beat img{border-color:#bbb}.beat .label{background:#eee}}
</style></head><body>
<header>
<h1>__SCENE__ - storyboard</h1>
<p>__N__ beats. Play the synced mp4 alongside this page; each block below = one slide.</p>
</header>""".replace("__SCENE__", scene).replace("__N__", str(len(rows)))]

current_section = None
for i, fn, label, section, text in rows:
    if section != current_section:
        html.append(f'<section class=part><h2>{section}</h2></section>')
        current_section = section
    html.append(f'''<div class=beat>
<div class=thumb><img src="{slides_dirname}/{fn}" alt=""><span class=num>#{i:02d}</span></div>
<div class=copy><span class=label>{label}</span><div class=text>{text}</div></div>
</div>''')

html.append('<footer>Edit walk.json, rerun build.py + gen_script.py + gen_storyboard.py.</footer></body></html>')
open(out, "w").write("\n".join(html))
print(f"wrote {out}")

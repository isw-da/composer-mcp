#!/usr/bin/env python3
"""Produce a recording script (md table + txt teleprompter) from a walk.json.

Usage:
    python3 gen_script.py <walk.json> [out_basename]

Writes <out_basename>.md and <out_basename>.txt next to walk.json (or in
~/Downloads/ if you pass an absolute basename like ~/Downloads/myscene-script).

The beat JSON must include `img`, `text`, and optionally `label`.
"""
import json, os, sys, shutil

walk = os.path.abspath(sys.argv[1])
base = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(walk)[0] + "-script"
base = os.path.expanduser(base)

beats = json.load(open(walk))
slides_dir = os.path.expanduser(
    f"~/Downloads/{os.path.basename(os.path.splitext(walk)[0])}-slides"
)
shutil.rmtree(slides_dir, ignore_errors=True)
os.makedirs(slides_dir, exist_ok=True)

rows = []
for i, b in enumerate(beats, 1):
    src = b["img"]
    bn = os.path.basename(src).replace(".png", "")
    label = b.get("label", bn)
    dst = f"{slides_dir}/{i:02d}_{bn}.png"
    shutil.copy(src, dst)
    rows.append((i, f"{i:02d}_{bn}.png", label, b["text"]))

md = [f"# Recording script: {os.path.basename(os.path.splitext(walk)[0])}", ""]
md += [f"Slides are in `{slides_dir}/` (numbered). Read the script line per slide.", ""]
md += ["| # | Slide file | Screen | Script (read this) |", "|---|---|---|---|"]
for i, fn, label, text in rows:
    safe = text.replace("|", "/")
    md.append(f"| {i} | `{fn}` | {label} | {safe} |")
open(base + ".md", "w").write("\n".join(md))

tp = [f"RECORDING SCRIPT: {os.path.basename(os.path.splitext(walk)[0]).upper()}", ""]
for i, fn, label, text in rows:
    tp.append(f"--- SLIDE {i:02d}  ({label})  [{fn}] ---")
    tp.append(text)
    tp.append("")
open(base + ".txt", "w").write("\n".join(tp))

print(f"slides -> {slides_dir}  ({len(rows)} files)")
print(f"script -> {base}.md  and  {base}.txt")

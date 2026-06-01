#!/usr/bin/env python3
"""Per-beat synced mp4 using Google Cloud TTS.

Usage:
    python3 build.py <walk.json> [voice]

Writes ~/Downloads/<scene>-synced.mp4 where <scene> is the basename of walk.json.

Looks for gtts.py alongside this file. Build artefacts (per-beat mp3 and mp4
clips) go into $BUILD_DIR (default: a temp dir alongside the walk.json).
"""
import json, subprocess, sys, os, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gtts

walk = os.path.abspath(sys.argv[1])
voice = sys.argv[2] if len(sys.argv) > 2 else "en-GB-Chirp3-HD-Charon"
scene = os.path.splitext(os.path.basename(walk))[0]

build_dir = os.environ.get("BUILD_DIR") or os.path.join(
    os.path.dirname(walk) or ".", f".{scene}-build"
)
os.makedirs(build_dir, exist_ok=True)

beats = json.load(open(walk))
VF = ("scale=1280:720:force_original_aspect_ratio=decrease,"
      "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x0d0d0d,format=yuv420p,fps=25")
clips = []
for i, b in enumerate(beats):
    aud = os.path.join(build_dir, f"{scene}_g{i}.mp3")
    gtts.synth(b["text"], aud, voice=voice, rate=0.9)
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", aud]).strip()) + 0.7
    clip = os.path.join(build_dir, f"{scene}_gc{i}.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", b["img"],
        "-i", aud, "-t", f"{dur:.3f}", "-vf", VF,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", clip,
    ], check=True)
    clips.append(clip)
    print(f"beat {i}: {dur:.1f}s")

out = os.path.expanduser(f"~/Downloads/{scene}-synced.mp4")
inputs = []
fc = ""
for i, c in enumerate(clips):
    inputs += ["-i", c]
    fc += f"[{i}:v:0][{i}:a:0]"
fc += f"concat=n={len(clips)}:v=1:a=1[v][a]"
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error", *inputs,
    "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
    "-c:a", "aac", "-b:a", "192k", "-ar", "44100", out,
], check=True)
tot = float(subprocess.check_output([
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=nk=1:nw=1", out,
]).strip())
print(f"wrote {out}  ({tot:.1f}s)")

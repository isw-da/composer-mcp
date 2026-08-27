#!/usr/bin/env python3
"""Adversarial checks on the proposed theme. Exit 1 on any failure."""
import json, os, re, sys, hashlib

SRC_DIR = "/Users/aminhasan/logi-composer/peter-kb/bundle-2026-05-21/logi-composer-toolkit/Styling"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(SRC_DIR, "tetra-pak-logi-composer-theme.json")

fails, checks = [], 0
def check(name, ok, detail=""):
    global checks
    checks += 1
    print(("PASS  " if ok else "FAIL  ") + name + ((" | " + detail) if detail else ""))
    if not ok: fails.append(name)

orig = json.load(open(SRC))
otto = json.load(open(os.path.join(SRC_DIR, "otto-partner-connect-theme-fixed.json")))
prop = json.load(open(os.path.join(OUT_DIR, "tetra-pak-logi-composer-theme.PROPOSED.json")))

# 0. source untouched
check("source theme byte-identical to the 6 May / 13 May copies",
      hashlib.md5(open(SRC,'rb').read()).hexdigest() == "7ce9ac4ab0c0fc6f0d7576c49d53dda6")

sym  = prop["content"]["symphony"]
osym = otto["content"]["symphony"]

# 1. structural parity with the only deployed theme that has a symphony block
def paths(o, p=""):
    if isinstance(o, dict):
        out = set()
        for k, v in o.items(): out |= paths(v, p + "." + k)
        return out
    return {p}

check("symphony sits inside content, sibling of variables/customProperties",
      set(prop["content"].keys()) == {"customProperties", "variables", "symphony"})
check("components key set matches Otto exactly",
      set(sym["components"]) == set(osym["components"]),
      "%s" % sorted(sym["components"]))
check("chatBot has exactly the 16 documented properties",
      set(sym["components"]["chatBot"]) == set(osym["components"]["chatBot"]),
      "%d keys" % len(sym["components"]["chatBot"]))
missing = paths(osym["components"]) - paths(sym["components"])
check("no component property Otto has is missing here", not missing, str(sorted(missing)))
check("no component property invented beyond Otto's set",
      not (paths(sym["components"]) - paths(osym["components"])),
      str(sorted(paths(sym["components"]) - paths(osym["components"]))))

# 2. every $colors.* reference resolves inside symphony.variables.colors only
scolors = sym["variables"]["colors"]
tcolors = prop["content"]["variables"]["colors"]
def resolve(ref, tree):
    cur = tree
    for part in ref.split("."):
        if not isinstance(cur, dict) or part not in cur: return None
        cur = cur[part]
    return cur if isinstance(cur, str) else None

refs = set()
def collect(o):
    if isinstance(o, dict):
        for v in o.values(): collect(v)
    elif isinstance(o, str):
        refs.update(re.findall(r"\$colors\.([A-Za-z0-9_.]+)", o))
collect(sym["components"])
unresolved = sorted(r for r in refs if resolve(r, scolors) is None)
check("every $colors.* in symphony.components resolves in symphony.variables.colors",
      not unresolved, "%d refs checked, unresolved: %s" % (len(refs), unresolved))
cross = sorted(r for r in refs if resolve(r, scolors) is None and resolve(r, tcolors) is not None)
check("no reference leaks into the top-level variables namespace", not cross, str(cross))

# 3. every literal colour is a valid hex / rgba / gradient / transparent
HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
bad = []
def literals(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items(): literals(v, p + "." + k)
    elif isinstance(o, str) and not o.startswith("$colors."):
        if o in ("transparent",) or o.startswith("linear-gradient") or o.startswith("rgba"): return
        if not HEX.match(o): bad.append(p + " = " + o)
literals(sym)
check("all literal colours are valid hex / rgba / gradient / transparent", not bad, str(bad))

# 4. light-theme direction rules from the guide
def lum(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    h = h[:6]
    r, g, b = (int(h[i:i+2], 16)/255 for i in (0, 2, 4))
    f = lambda c: c/12.92 if c <= 0.03928 else ((c+0.055)/1.055) ** 2.4
    return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b)
def contrast(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

bglev = [scolors["background"]["level%d" % i] for i in range(6)]
check("background.level0-5 runs light to dark (light theme)",
      all(lum(bglev[i]) > lum(bglev[i+1]) for i in range(5)),
      " > ".join(bglev))
fglev = [scolors["foreground"]["level%d" % i] for i in range(6)]
check("foreground.level0-5 runs dark to light",
      all(lum(fglev[i]) < lum(fglev[i+1]) for i in range(5)), " < ".join(fglev))
check("slate.600 (chatBot.inputBg) is a light surface", lum(scolors["slate"]["600"]) > 0.8,
      scolors["slate"]["600"])
check("foreground.level0 (chatBot.inputColor) is dark", lum(scolors["foreground"]["level0"]) < 0.1,
      scolors["foreground"]["level0"])
ramp = [scolors["brand"]["primary"][k] for k in ["50","100","200","300","400","500","600","700","800","900","950"]]
check("brand.primary.50-950 is monotonic light to dark",
      all(lum(ramp[i]) > lum(ramp[i+1]) for i in range(len(ramp)-1)), " > ".join(ramp))

# 5. chat legibility: input text on input background, chip text on chip
chip_bg   = resolve("brand.primary.500", scolors)
chip_text = resolve("white", scolors)
input_bg  = resolve("slate.600", scolors)
input_fg  = resolve("foreground.level0", scolors)
check("chat input text on input background >= 4.5:1",
      contrast(input_fg, input_bg) >= 4.5, "%.2f:1 (%s on %s)" % (contrast(input_fg, input_bg), input_fg, input_bg))
check("suggestion chip text on chip background >= 4.5:1",
      contrast(chip_text, chip_bg) >= 4.5, "%.2f:1 (%s on %s)" % (contrast(chip_text, chip_bg), chip_text, chip_bg))
chip_hover = resolve("brand.primary.400", scolors)
check("suggestion chip text on chip hover >= 3:1",
      contrast(chip_text, chip_hover) >= 3.0, "%.2f:1" % contrast(chip_text, chip_hover))
check("sidebar icons on sidebar background >= 4.5:1",
      contrast(sym["components"]["sidebar"]["iconColor"], sym["components"]["sidebar"]["background"]) >= 4.5,
      "%.2f:1" % contrast(sym["components"]["sidebar"]["iconColor"], sym["components"]["sidebar"]["background"]))

# 6. bug fix 1: three timebar background properties opaque
tb = prop["content"]["customProperties"]["timebar"]
tb_props = {
    "timebar.backgroundColor": tb["backgroundColor"],
    "timebar.backgroundColorHover": tb["backgroundColorHover"],
    "timebar.scrubber.backgroundColor": tb["scrubber"]["backgroundColor"],
    "timebar.scrubber.backgroundColorHover": tb["scrubber"]["backgroundColorHover"],
}
for name, val in tb_props.items():
    resolved = resolve(val[len("$colors."):], tcolors) if val.startswith("$colors.") else val
    opaque = bool(resolved) and HEX.match(resolved) and len(resolved.lstrip("#")) in (3, 6)
    check("%s resolves to opaque hex" % name, bool(opaque), "%s -> %s" % (val, resolved))
check("timebar hover values changed from the rgba that doubles period labels",
      orig["content"]["customProperties"]["timebar"]["backgroundColorHover"] == "rgba(8,74,138,0.12)"
      and tb["backgroundColorHover"] != "rgba(8,74,138,0.12)")

# 7. bug fix 2: picker visible against widget tiles
picker = prop["content"]["customProperties"]["metaDataPicker"]["background"]
widget = prop["content"]["customProperties"]["widget"]["background"]
widget_r = resolve(widget[len("$colors."):], tcolors) if widget.startswith("$colors.") else widget
check("metaDataPicker.background differs from widget.background", picker.lower() != str(widget_r).lower(),
      "%s vs %s" % (picker, widget_r))
check("picker is noticeably darker than the widget tile (>= 1.5:1)",
      contrast(picker, widget_r) >= 1.5, "%.2f:1" % contrast(picker, widget_r))
ptext = resolve(prop["content"]["customProperties"]["metaDataPicker"]["color"][len("$colors."):], tcolors)
psec  = resolve(prop["content"]["customProperties"]["metaDataPicker"]["secondary"][len("$colors."):], tcolors)
check("picker primary text on picker background >= 4.5:1",
      contrast(ptext, picker) >= 4.5, "%.2f:1 (%s)" % (contrast(ptext, picker), ptext))
check("picker secondary text on picker background >= 4.5:1",
      contrast(psec, picker) >= 4.5, "%.2f:1 (%s)" % (contrast(psec, picker), psec))

# 8. nothing else changed
def diffpaths(a, b, p=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            out += diffpaths(a.get(k), b.get(k), p + "." + k)
    elif a != b:
        out.append(p)
    return out
d = sorted(x for x in diffpaths(orig["content"], prop["content"]) if not x.startswith(".symphony"))
expected = ['.customProperties.metaDataPicker.background', '.customProperties.metaDataPicker.color',
            '.customProperties.metaDataPicker.item.aggrHover',
            '.customProperties.metaDataPicker.item.border', '.customProperties.metaDataPicker.item.hover.bg',
            '.customProperties.metaDataPicker.secondary', '.customProperties.timebar.backgroundColorHover',
            '.customProperties.timebar.scrubber.backgroundColorHover']
check("no change outside symphony and the two named bugs", d == expected, str(d))
check("theme name unchanged", prop["name"] == orig["name"] == "tetra-pak-modern")

print("\n%d checks, %d failed" % (checks, len(fails)))
sys.exit(1 if fails else 0)

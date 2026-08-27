#!/usr/bin/env python3
"""Build the missing symphony block for tetra-pak-modern and fix two customProperties bugs.

Source theme is read-only; output is written beside this script. Nothing here
touches an instance.
"""
import json, os, copy

SRC_DIR = "/Users/aminhasan/logi-composer/peter-kb/bundle-2026-05-21/logi-composer-toolkit/Styling"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

tetra = json.load(open(os.path.join(SRC_DIR, "tetra-pak-logi-composer-theme.json")))
otto = json.load(open(os.path.join(SRC_DIR, "otto-partner-connect-theme-fixed.json")))

# --- Tetra Pak brand tokens, all read from the theme's own variables.colors ---
C = tetra["content"]["variables"]["colors"]
BRAND        = C["brandColor"]          # #084A8A
BRAND_HOVER  = C["intentPrimaryHover"]  # #063B6E
BRAND_ACTIVE = C["intentPrimaryActive"] # #042D55
NAVY         = C["primary"]             # #0D1B2A
NAVY_LIGHT   = C["primaryVariant"]      # #1A2F45
SURFACE      = C["surface"]             # #fff
BG           = C["background"]          # #F5F7FA
BG_VARIANT   = C["backgroundVariant"]   # #EDF0F4
BASE_ACTIVE  = C["intentBaseActive"]    # #DDE3EA
BORDER       = C["border"]              # #CBD5E0
MUTED        = C["muted"]               # #8899A6
TEXT         = C["text"]                # #4A5568
SECONDARY    = C["secondary"]           # #EB2C33
INFO_BG      = C["intentInfoBackground"]# #E8F0F9

# Blue ramp stops that already exist in the theme's DefaultSequential palette.
SEQ = tetra["content"]["variables"]["palettes"]["DefaultSequential"]["9"]
# ['#084A8A','#1F5890','#2E6499','#3A72A6','#4A88B8','#6B9DC5','#9AC0DC','#B0CDDF','#C7DAF0']

def rgb(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def hexs(t):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in t)

def darken(h, f):
    return hexs([v * f for v in rgb(h)])

def flatten(fg, alpha, bg):
    """Opaque equivalent of fg at `alpha` composited over bg."""
    f, b = rgb(fg), rgb(bg)
    return hexs([alpha * f[i] + (1 - alpha) * b[i] for i in range(3)])

def mix(a, b, t):
    ra, rb = rgb(a), rgb(b)
    return hexs([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])

# --- symphony.variables.colors -------------------------------------------------
brand_primary = {
    "50":  INFO_BG,        # #E8F0F9  lightest brand tint in the theme
    "100": SEQ[8],         # #C7DAF0
    "200": SEQ[6],         # #9AC0DC
    "300": SEQ[3],         # #3A72A6 -> replaced below, see note
    "400": SEQ[4],         # #4A88B8
    "500": BRAND,          # #084A8A
    "600": BRAND_HOVER,    # #063B6E
    "700": BRAND_ACTIVE,   # #042D55
    "800": darken(BRAND_ACTIVE, 0.80),
    "900": darken(BRAND_ACTIVE, 0.60),
    "950": darken(BRAND_ACTIVE, 0.45),
}
brand_primary["300"] = SEQ[5]   # #6B9DC5, keeps 300 lighter than 400

symphony_colors = {
    "background": {
        "level0": "#FFFFFF",       # surface
        "level1": BG,              # #F5F7FA
        "level2": BG_VARIANT,      # #EDF0F4
        "level3": BASE_ACTIVE,     # #DDE3EA
        "level4": BORDER,          # #CBD5E0
        "level5": MUTED,           # #8899A6
    },
    "brand": {"primary": brand_primary},
    "foreground": {
        "level0": NAVY,            # #0D1B2A
        "level1": NAVY_LIGHT,      # #1A2F45
        "level2": TEXT,            # #4A5568
        "level3": mix(TEXT, MUTED, 0.5),
        "level4": MUTED,           # #8899A6
        "level5": BORDER,          # #CBD5E0
    },
    "neutral": {
        "400": MUTED,
        "500": mix(TEXT, MUTED, 0.5),
        "600": TEXT,
    },
    # Light theme: normal ramp to 500, then bent at 600 so chatBot.inputBg
    # ($colors.slate.600) is white. Same deliberate bend as Otto.
    "slate": {
        "50": BG, "100": BG_VARIANT, "200": BASE_ACTIVE, "300": BORDER,
        "400": MUTED, "500": TEXT,
        "600": "#FFFFFF", "700": BG, "800": BG_VARIANT, "900": BASE_ACTIVE,
        "950": BORDER,
    },
    "semantic": copy.deepcopy(otto["content"]["symphony"]["variables"]["colors"]["semantic"]),
    "dataSeries": {
        "01": BRAND, "02": SECONDARY, "03": "#26AAC5", "04": "#217C4A",
        "05": "#DF604D", "06": "#A826C5", "07": "#C58B26", "08": "#D8539D",
        "09": "#8645E1", "10": "#5187F9", "11": "#F6BF60", "12": "#1C778A",
        "13": "#2658C5",
    },
    "white": "#FFFFFF",
}

# Tailwind ramps kept (defensive, per CHATBOT_THEMING.md), with the stops Tetra
# Pak actually defines swapped in: hover -> 400, base -> 500, active -> 600.
for fam, base, hover, active in [
    ("danger",  C["intentDanger"],  C["intentDangerHover"],  C["intentDangerActive"]),
    ("warning", C["intentWarning"], C["intentWarningHover"], C["intentWarningActive"]),
    ("success", C["intentSuccess"], C["intentSuccessHover"], C["intentSuccessActive"]),
]:
    symphony_colors["semantic"][fam]["400"] = hover
    symphony_colors["semantic"][fam]["500"] = base
    symphony_colors["semantic"][fam]["600"] = active
symphony_colors["semantic"]["info"]["500"] = C["intentPrimary"]

# --- symphony.components -------------------------------------------------------
DANGER_400  = symphony_colors["semantic"]["danger"]["400"]
WARNING_400 = symphony_colors["semantic"]["warning"]["400"]
br = rgb(BRAND)

components = {
    "actionCard": {
        "activeBackground": BRAND + "99",
        "background": BRAND + "33",
        "description": TEXT,
        "hoverBackground": BRAND + "66",
        "icon": BRAND,
    },
    "buttons": {
        "accent":    {"default": brand_primary["900"], "hover": brand_primary["950"]},
        "link":      {"default": BRAND, "hover": BRAND_HOVER},
        "primary":   {"default": BRAND, "hover": BRAND_HOVER},
        "secondary": {"default": TEXT,  "hover": NAVY_LIGHT},
    },
    "chatBot": {
        "actionsMenuBg": BG_VARIANT,
        "assistantMessageBg": BG_VARIANT + "BF",
        "background": "$colors.background.level1",
        "bgGradient": "linear-gradient(321.91deg, %s 34.29%%, %s 80.96%%)"
                      % (brand_primary["700"], brand_primary["900"]),
        "errorMessageBg": DANGER_400 + "33",
        "errorMessageBorder": "$colors.semantic.danger.500",
        "gradientMask": "linear-gradient(180deg, %s 0%%, rgba(%d, %d, %d, 0.18) 49.84%%, rgba(%d, %d, %d, 0) 102.07%%)"
                        % (BRAND, br[0], br[1], br[2], br[0], br[1], br[2]),
        "inputBg": "$colors.slate.600",
        "inputColor": "$colors.foreground.level0",
        "suggestionChipBg": "$colors.brand.primary.500",
        "suggestionChipHoverBg": "$colors.brand.primary.400",
        "suggestionChipText": "$colors.white",
        "timeoutMessageBg": WARNING_400 + "33",
        "timeoutMessageBorder": "$colors.semantic.warning.500",
        "userMessageBg": "#FFFFFFBF",
        "workingDots": "$colors.brand.primary.300",
    },
    "input": {
        "background": "$colors.background.level0",
        "backgroundDisabled": "$colors.background.level3",
        "border": "$colors.foreground.level5",
        "borderActive": "$colors.brand.primary.300",
        "foreground": "$colors.foreground.level1",
    },
    "sidebar": {
        "activeIndicatorColor": BRAND,
        "background": NAVY,
        "headingTabBg": BRAND,
        "iconColor": "#FFFFFF",
        "menuBorder": BORDER,
        "profileBubble": {"bg": BRAND_ACTIVE, "color": "#FFFFFF"},
        "tabBg": "transparent",
        "tabBgActive": NAVY_LIGHT,
        "tabBgHover": mix(NAVY, NAVY_LIGHT, 0.5),
        "verticalAccentBg": "linear-gradient(to bottom, %s 0%%, %s 100%%) 1"
                            % (BRAND, brand_primary["300"]),
    },
}

symphony = {"components": components, "variables": {"colors": symphony_colors}}

# --- the two customProperties bugs ---------------------------------------------
fixed = copy.deepcopy(tetra)
cp = fixed["content"]["customProperties"]

# 1. timebar: semi-transparent hover values break the scrubber canvas clear.
#    Replace with the opaque equivalent of what was intended, composited over
#    each property's own base colour (both bases are #EDF0F4).
opaque_hover = flatten(BRAND, 0.12, BG_VARIANT)
cp["timebar"]["backgroundColorHover"] = opaque_hover
cp["timebar"]["scrubber"]["backgroundColorHover"] = opaque_hover

# 2. metaDataPicker.background was $colors.surface, identical to widget.background.
picker_bg = mix(BORDER, MUTED, 0.45)
cp["metaDataPicker"]["background"] = picker_bg
cp["metaDataPicker"]["item"]["border"] = darken(picker_bg, 0.90)
cp["metaDataPicker"]["item"]["aggrHover"] = darken(picker_bg, 0.90)
cp["metaDataPicker"]["item"]["hover"]["bg"] = darken(picker_bg, 0.90)
cp["metaDataPicker"]["secondary"] = "$colors.onBackgroundVariant"

fixed["content"]["symphony"] = symphony

json.dump(symphony, open(os.path.join(OUT_DIR, "symphony-block.json"), "w"), indent=2, sort_keys=True)
json.dump(fixed, open(os.path.join(OUT_DIR, "tetra-pak-logi-composer-theme.PROPOSED.json"), "w"), indent=2, sort_keys=True)
print("wrote symphony-block.json and tetra-pak-logi-composer-theme.PROPOSED.json")
print("timebar hover  :", opaque_hover)
print("picker bg      :", picker_bg, "-> items", darken(picker_bg, 0.90))

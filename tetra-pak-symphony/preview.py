#!/usr/bin/env python3
"""Render the proposed tokens as HTML. Every colour is resolved from the JSON."""
import json, os
OUT = os.path.dirname(os.path.abspath(__file__))
prop = json.load(open(os.path.join(OUT, "tetra-pak-logi-composer-theme.PROPOSED.json")))
orig = json.load(open("/Users/aminhasan/logi-composer/peter-kb/bundle-2026-05-21/logi-composer-toolkit/Styling/tetra-pak-logi-composer-theme.json"))

sym = prop["content"]["symphony"]
sc  = sym["variables"]["colors"]
tc  = prop["content"]["variables"]["colors"]

def res(v, tree):
    if isinstance(v, str) and v.startswith("$colors."):
        cur = tree
        for part in v[len("$colors."):].split("."):
            cur = cur[part]
        return cur
    return v

cb = {k: res(v, sc) for k, v in sym["components"]["chatBot"].items()}
sb = {k: res(v, sc) for k, v in sym["components"]["sidebar"].items()}
tb_new = prop["content"]["customProperties"]["timebar"]
tb_old = orig["content"]["customProperties"]["timebar"]
pk_new = {k: res(v, tc) for k, v in prop["content"]["customProperties"]["metaDataPicker"].items() if isinstance(v, str)}
pk_old = {k: res(v, tc) for k, v in orig["content"]["customProperties"]["metaDataPicker"].items() if isinstance(v, str)}
widget_bg = res(prop["content"]["customProperties"]["widget"]["background"], tc)

swatches = "".join(
    '<div class=sw><span style="background:%s"></span><code>%s</code><code class=d>%s</code></div>'
    % (v, k, v) for k, v in sorted(cb.items()) if not v.startswith("linear-gradient"))

html = f"""<!doctype html><meta charset=utf-8><title>tetra-pak-modern symphony proposal</title>
<style>
 body{{font:13px/1.5 "Helvetica Neue",Helvetica,Arial,sans-serif;background:#E9ECF0;color:#0D1B2A;margin:0;padding:24px}}
 h2{{font-size:14px;font-weight:500;margin:28px 0 10px}}
 .row{{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}}
 .card{{background:#fff;border:1px solid #CBD5E0;border-radius:4px;padding:14px}}
 .chat{{width:380px;border-radius:4px;overflow:hidden;border:1px solid #CBD5E0;background:{cb['background']}}}
 .hero{{background:{cb['bgGradient']};height:110px;position:relative}}
 .hero .mask{{position:absolute;inset:0;background:{cb['gradientMask']};opacity:.55}}
 .hero h3{{position:absolute;left:16px;bottom:14px;color:#fff;font-size:15px;font-weight:500;margin:0}}
 .msgs{{padding:14px}}
 .bub{{padding:8px 11px;border-radius:8px;margin-bottom:9px;max-width:82%;border:1px solid rgba(13,27,42,.06)}}
 .assistant{{background:{cb['assistantMessageBg']}}}
 .user{{background:{cb['userMessageBg']};margin-left:auto}}
 .err{{background:{cb['errorMessageBg']};border:1px solid {cb['errorMessageBorder']}}}
 .tmo{{background:{cb['timeoutMessageBg']};border:1px solid {cb['timeoutMessageBorder']}}}
 .chips span{{display:inline-block;background:{cb['suggestionChipBg']};color:{cb['suggestionChipText']};
   padding:5px 10px;border-radius:14px;margin:0 6px 6px 0;font-size:12px}}
 .chips span.hov{{background:{cb['suggestionChipHoverBg']}}}
 .dots i{{display:inline-block;width:7px;height:7px;border-radius:50%;background:{cb['workingDots']};margin-right:4px}}
 .inp{{margin:0 14px 14px;background:{cb['inputBg']};color:{cb['inputColor']};border:1px solid #CBD5E0;
   border-radius:18px;padding:9px 13px}}
 .menu{{background:{cb['actionsMenuBg']};border:1px solid #CBD5E0;border-radius:4px;padding:7px 10px;margin:0 14px 12px;width:150px}}
 .side{{width:190px;background:{sb['background']};border-radius:4px;padding:12px;color:#fff}}
 .side .tab{{padding:7px 9px;border-radius:3px;margin-bottom:4px}}
 .side .active{{background:{sb['tabBgActive']};border-left:3px solid {sb['activeIndicatorColor']}}}
 .side .hover{{background:{sb['tabBgHover']}}}
 .side .head{{background:{sb['headingTabBg']};padding:6px 9px;border-radius:3px;margin-bottom:10px;font-weight:500}}
 .side .bub2{{background:{sb['profileBubble']['bg']};color:{sb['profileBubble']['color']};width:28px;height:28px;
   border-radius:50%;display:flex;align-items:center;justify-content:center;margin-top:12px}}
 .sw{{display:flex;align-items:center;gap:8px;margin-bottom:3px}}
 .sw span{{width:26px;height:16px;border:1px solid #CBD5E0;border-radius:2px;display:inline-block}}
 .sw code{{font:11px Menlo,monospace}} .sw .d{{color:#4A5568}}
 .tbar{{width:300px;height:44px;border:1px solid #CBD5E0;border-radius:3px;display:flex;overflow:hidden}}
 .tbar div{{flex:1;display:flex;align-items:center;justify-content:center;font-size:11px;color:#4A5568}}
 .tile{{background:{widget_bg};border:1px solid #DDE3EA;border-radius:4px;padding:10px;width:150px;height:96px}}
 .lbl{{font-size:11px;color:#4A5568;margin-top:5px}}
</style>
<h2>Chatbot, themed by the proposed <code>symphony</code> block</h2>
<div class=row>
  <div class=chat>
    <div class=hero><div class=mask></div><h3>Ask about your data</h3></div>
    <div class=msgs>
      <div class="bub assistant">Volumes are up 4.2% against last quarter.</div>
      <div class="bub user">Show me packaging lines below target.</div>
      <div class="bub err">Query failed against the source.</div>
      <div class="bub tmo">That took too long and timed out.</div>
      <div class=chips><span>Top 5 plants</span><span class=hov>Yield by line</span></div>
      <div class=dots><i></i><i></i><i></i></div>
    </div>
    <div class=menu>Copy &nbsp; Export &nbsp; Retry</div>
    <div class=inp>Type a question…</div>
  </div>
  <div class=side>
    <div class=head>Analytics</div>
    <div class="tab active">Dashboards</div>
    <div class="tab hover">Sources</div>
    <div class=tab>Settings</div>
    <div class=bub2>TP</div>
  </div>
  <div class=card style="width:260px"><strong>chatBot tokens, resolved</strong><br><br>{swatches}</div>
</div>

<h2>Bug 1 &middot; timebar hover: <code>{tb_old['backgroundColorHover']}</code> to <code>{tb_new['backgroundColorHover']}</code></h2>
<div class=row>
  <div><div class=tbar><div style="background:#EDF0F4">Q3 2026</div>
    <div style="background:{tb_old['backgroundColorHover']}">Q4 2026</div>
    <div style="background:#EDF0F4">Q1 2027</div></div>
    <div class=lbl>before: semi-transparent, canvas fails to clear</div></div>
  <div><div class=tbar><div style="background:#EDF0F4">Q3 2026</div>
    <div style="background:{tb_new['backgroundColorHover']}">Q4 2026</div>
    <div style="background:#EDF0F4">Q1 2027</div></div>
    <div class=lbl>after: opaque {tb_new['backgroundColorHover']}</div></div>
</div>

<h2>Bug 2 &middot; metaDataPicker on a widget tile</h2>
<div class=row>
  <div><div class=tile><div style="background:{pk_old['background']};color:{pk_old['color']};padding:7px;border:1px solid {pk_old['item']['border'] if isinstance(pk_old.get('item'),dict) else '#DDE3EA'}">Dimensions<div style="color:{pk_old['secondary']};font-size:11px">3 fields</div></div></div>
    <div class=lbl>before: picker {pk_old['background']} on tile {widget_bg}</div></div>
  <div><div class=tile><div style="background:{pk_new['background']};color:{pk_new['color']};padding:7px;border:1px solid {prop['content']['customProperties']['metaDataPicker']['item']['border']}">Dimensions<div style="color:{pk_new['secondary']};font-size:11px">3 fields</div></div></div>
    <div class=lbl>after: picker {pk_new['background']}, dark text</div></div>
</div>
"""
open(os.path.join(OUT, "preview.html"), "w").write(html)
print("wrote preview.html")

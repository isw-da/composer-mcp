# Embedding Composer dashboards into a partner app

The Composer Embed Manager (`/embed/embed.js`) renders dashboards as native
DOM, not iframes. That's the whole point: your CSS can reach in, your
keyboard navigation works, your fonts apply, no `X-Frame-Options` games.

> **Embed not behaving as expected?** — see the "Embed manager limits"
> section of `LIMITATIONS.md` first. Theme override beats per-visual
> palette, embed caches visual configs against the push-token session,
> cross-tab filter state doesn't sync, `display: none` produces zero-height
> widgets — these are all known properties of `embed.js`, not bugs in your
> shell.

This doc captures the working pattern (verified end-to-end against UAT for
the Otto Group "Partner Center" demo). The full reference shell lives at
`embed/otto-opc-shell.html.template` in this repo.

## TL;DR — let the MCP do it

If you just want a working config block to paste into the shell:

```
composer_make_embed_config(
  client_id="<from Symphony admin>",
  secret="<from Symphony admin>",
  account="Otto Group",                # literal display name
  username="tenant.viewer",
  dashboard_ids={
    "snapshot":  "7d498e0c-c75c-4089-b851-b88875b89432_69fba5090b70396702ebb36e",
    "campaigns": "7d498e0c-c75c-4089-b851-b88875b89432_69fba50a0b70396702ebb371",
    "brands":    "7d498e0c-c75c-4089-b851-b88875b89432_69fba50a0b70396702ebb374",
  },
  groups=["TechWorld GmbH"],
  theme="__platform__",
)
```

Returns the full `CONFIG = { ... }` block plus a freshly-minted token.
Underscore→plus dashboard-id conversion is automatic.

If you're getting opaque errors at boot, run
`composer_verify_trusted_access_client(client_id, secret, account)` first
— it translates the 500 'can't get authentication' (client not registered)
and 400 'account does not exist' (client out of scope) into readable
diagnostics rather than making you guess.

## The seven-step flow

```
[ parent app ]                      [ Composer ]
      │
      │ 1. POST /api/trusted-access/push/tokens
      │    (Basic auth: clientId:secret of a registered Trusted Access client)
      │    body: {username, account, groups}
      │  ─────────────────────────────────────►
      │  ◄───────────────────────────────────── { access_token, expires_in }
      │
      │ 2. <script src="/discovery/embed/embed.js"></script>
      │    (window.initComposerEmbedManager appears)
      │
      │ 3. const mgr = await initComposerEmbedManager({
      │      getToken: async () => ({access_token, expires_in})
      │    })
      │
      │ 4. const comp = await mgr.createComponent('dashboard', {
      │      dashboardId: '<accountId>+<dashId>',  // NB: + not _
      │      theme: '__platform__',                 // see "theme override" below
      │      header: { visible: false },            // hide Composer chrome
      │      interactivityProfileName: 'interactive',
      │    })
      │
      │ 5. await comp.render(document.getElementById('host'))
      │
      │ 6. (your app code does whatever — tab switching, hover tooltips, ...)
      │
      │ 7. Apply shell CSS to clean up Composer's standalone-view leftovers
      │    (see "Required shell CSS" below)
```

## Required prerequisites

1. A **Trusted Access client** registered on the Composer instance, scoped
   to the target account. Tenant admins cannot register one — needs Symphony
   global admin. Returns `clientId` + `secret`.
2. A **viewer user** that exists in the target account. The push token mints
   a session impersonating that user. Use a generic `tenant.viewer` for
   shared-anonymous patterns, or pass the real partner username for
   personalised forced filters.
3. The **target account display name** verbatim. Spaces and case matter.
   `'Otto Group'`, not `'otto-group'`.
4. The **dashboard id in `+` form**: `<accountId>+<dashId>`. The URL form
   uses `_` separator; rewrite to `+` for the embed manager.

## Theme override behaviour (the silent gotcha)

When `createComponent({theme: '<name>'})` is called, Composer applies the
named theme's `customProperties.charts.*` palette OVER per-visual palette
settings. So if you carefully recoloured `Bar Color` on every UBER_BARS
visual to Otto red, those edits are ignored at render time and the bars
render in the theme's palette (default modern is yellow → teal → blue).

Three ways out:
1. Pass `theme: '__platform__'` (per-visual configs win) and apply branding
   via shell CSS.
2. Get a Symphony global admin to set the right `Bar Color` etc. on the
   custom theme. Tenant admins cannot edit themes via API (403).
3. Don't pass `theme` at all (defaults to `'__platform__'`).

## Required shell CSS

Composer's standalone shell has UI elements that don't make sense in an
embedded context but still claim space. Add these rules to your shell:

```css
/* Composer's main wrapper uses a 2-column CSS Grid where the first column
   is the standalone-view navigation rail (~900px wide). In embed mode it's
   empty but still squashes the dashboard into the right half. Hide it and
   span content full width. The 'html body' prefix is needed because
   Composer's stylesheet loads after the shell <style> and matches at equal
   specificity. */
html body div.zd-main > header.zd-main-header,
html body div.zd-main > header.zd-custom-header,
html body div.zd-main > header.zd-license-banner,
html body div.zd-main > footer.zd-main-footer { display: none !important; }
html body div.zd-main > section.zd-main-section { grid-column: 1 / -1 !important; }

/* Composer paints its embed wrapper with #F7F7F7 by default and the widget
   grid is narrower than the viewport, leaving a grey gutter on the right. */
.logi-embed,
.logi-embed-main { background: white !important; }

/* Optional: repaint the default cyan KPI value text and dark grey KPI tile
   background to your brand colours. The hashed CSS-module class names are
   stable per Composer build. Targeting via class*= is safe within one
   deployment. */
body div[class*="Tqwvz2y"] { background-color: #FFFFFF !important; }
body div[class*="W95yvuc"] { color: #YOUR_BRAND_RED !important; }
```

## Caching gotchas during development

* Python's default `http.server` sends no cache headers, so Chrome
  aggressively caches the shell HTML. `location.reload()` uses the cached
  copy. Solution: use a small wrapper that sends
  `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` on every
  response, and also embed `<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">`
  in the shell `<head>`.
* The Composer embed manager attaches a `beforeunload` handler that
  triggers a "Leave site?" dialog. This can swallow programmatic
  navigation. To force-reload during dev, do
  `window.onbeforeunload = null; location.replace(url + '?n=' + Date.now())`
  or just close and reopen the tab.

## Filter widget rendering

Set the `LIST_FILTER` widget's `dashboardLayout.layout` `params` to at
least `[25, 100]` (25% height, full width). Anything below ~20% squashes
the filter into a strip too short to show options. Use
`dashboards.resize_widgets_by_visual_type(dashboard_id, 'LIST_FILTER',
30, 100)` for a one-shot fix across every dashboard you embed.

## Pivot row rendering when stacked

If you stack multiple dashboard panes via `z-index` swaps and toggle
visibility instead of `display: none`, Composer's pivot tables sometimes
fail to render their row bodies (column headers show but rows are empty).
The fix: dispatch a synthetic `resize` event after each tab switch:

```js
btn.addEventListener('click', () => {
  // ... swap active class ...
  window.dispatchEvent(new Event('resize'));
  setTimeout(() => window.dispatchEvent(new Event('resize')), 60);
});
```

Avoid `display: none` altogether: the embed measures host height once at
render time and locks zero-height widgets if the pane is hidden when the
embed paints. Use `opacity: 0; pointer-events: none; z-index: 1` instead
and `opacity: 1; pointer-events: auto; z-index: 2` for the active pane.

## Custom hover tooltips (the parent-app feature you'd want next)

Composer doesn't ship "explain this widget on hover" out of the box.
Implement it in the shell via event delegation:

```js
document.addEventListener('mouseover', (e) => {
  let el = e.target;
  let hops = 0;
  while (el && hops < 8) {
    if (el.classList && el.classList.contains('widgetBody')) {
      const titleEl = el.querySelector('.widget-title, [class*="WidgetTitle"]') || el;
      const text = (titleEl.textContent || '').trim();
      const hint = lookupHint(text);  // your lookup table
      if (hint) showTip(el, hint);
      return;
    }
    el = el.parentElement; hops++;
  }
}, true);
```

The Otto shell uses a `CONFIG.tooltips` map keyed by widget title with
substring matching (longest key wins). One-line edits to add new tooltip
copy without touching Composer. Reference implementation in
`embed/otto-opc-shell.html.template`.

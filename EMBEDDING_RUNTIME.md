# Embedding runtime: driving an embedded dashboard after it's on screen

`EMBEDDING.md` gets a dashboard rendered. This file covers what happens next:
pushing filters in from the host app, capturing what the user does for your
product-analytics tooling, secondary embeds, interactivity overrides,
intercepting exports, and reading the visible data back out.

For boot, token and shell CSS see EMBEDDING.md. For limits see LIMITATIONS.md.

## Passing filters from the host app into a dashboard

There are three working methods. Try them in this order. The first that the
target dashboard supports is the cleanest; the third always works.

### Method 1: `embedManager.publish()` (preferred)

```js
embedManager.publish("Campaign", {
  type: "selection",
  valueType: "ATTRIBUTE",   // or "TIME" for date ranges
  ranges: [{ operation: 'IN', value: ['New Year Fitness'] }]
});
```

The topic (`"Campaign"`) MUST be a cross-source link label that the dashboard
author configured, not a raw source field name. The label is read from the
dashboard JSON at `fieldLinks[].label`. Publishing to a raw field name (e.g.
`"campaign_name"`) is the silent gotcha: the pub/sub bus accepts the message,
host-side `subscribe` handlers even receive it, but the query engine ignores it
and nothing filters. Confirm the label before you wire it:

```
GET /api/dashboards/{<dashboardId>} → data.fieldLinks[].label
```

Authoring the link (one-off, in the Composer editor): Interactions →
Cross-Source Links → add a link, give it a label, map it to the field and
source, then mute the publish direction on every widget so visuals subscribe
but don't re-publish (otherwise a click feeds back into the filter).

Clear a filter by publishing empty `ranges` (an empty array), not `null`
ranges:

```js
embedManager.publish("Campaign", {
  type: "selection", valueType: "ATTRIBUTE", ranges: []
});
```

Timing: gate every publish on `composer-dashboard-ready`. Publishing before the
dashboard is ready silently no-ops.

```js
document.addEventListener('composer-dashboard-ready', function onReady() {
  document.removeEventListener('composer-dashboard-ready', onReady);
  embedManager.publish("Campaign", payload);
});
```

### Method 2: `window.Zoomdata.publish()` (no fieldLink needed)

Use this when the dashboard has no cross-source link and you can't author one.
It targets visuals directly by widget and field, so it needs no fieldLink.

```js
window.Zoomdata.publish("WidgetName.FieldName", {
  type: "selection",
  valueType: "ATTRIBUTE",
  ranges: [{ operation: 'EQUALS', value: "Aaron Harrison" }]  // scalar, not array
});
```

Three differences from Method 1 that bite if you copy a Method 1 payload:
the channel is `"WidgetName.FieldName"` (WidgetName comes from
`data.widgets[].name`), the operation is `EQUALS` with a scalar value (not `IN`
with an array), and you gate on `composer-dashboard-loaded` (not `-ready`).
Clear by holding visual refs and calling `v.filters.remove('field')`.

### Method 3: WebSocket `START_VIS` injection (universal fallback)

Works regardless of dashboard configuration. The embed library runs every data
query over a WebSocket; each visual sends a `START_VIS` frame carrying a
`filters` array. Intercept `WebSocket.prototype.send`, append your filters to
that array, then call `refreshData()` to re-fire the queries.

```js
let activeFilters = [];                       // current filter state, empty = no filter
const originalSend = WebSocket.prototype.send;

WebSocket.prototype.send = function(data) {
  if (typeof data === 'string' && data.includes('START_VIS') && activeFilters.length) {
    try {
      const msg = JSON.parse(data);
      if (msg.type === 'START_VIS' && msg.sourceId === '<sourceId>') {
        // skip filter-value lookup queries (cid prefixed 'filter_') or they get filtered too
        if (!msg.cid || !msg.cid.startsWith('filter_')) {
          msg.filters = (msg.filters || []).concat(activeFilters);
          data = JSON.stringify(msg);
        }
      }
    } catch (e) { /* pass through unmodified */ }
  }
  // the strict-mode gotcha: see below
  return originalSend.call(this, data);
};

function applyFilter(fieldName, values) {
  activeFilters = (values && values.length)
    ? [{ operation: 'IN', path: { name: fieldName }, value: values }]
    : [];
  dashboardComponent.refreshData();
}
```

Filter object shape: `{ operation: 'IN' | 'NOTIN', path: { name: '<field>' }, value: [...] }`.
The `path` object form (`{ name }`) matches the dashboard's own internal
queries; a bare string also works.

The strict-mode gotcha (this was the root cause of a whole class of "filter is
registered but never applies" failures): forward with
`originalSend.call(this, data)`, never `originalSend.apply(this, arguments)`. In
a `"use strict"` file (which includes every module), a named parameter and its
`arguments[i]` slot are decoupled, so reassigning `data` above does NOT update
`arguments[0]`. With `.apply()` the original, unmodified frame goes on the wire
and your injection is silently dropped. If you're debugging this, inspect the
actual outgoing WS frame in DevTools, not the interceptor's intermediate state;
they diverge for exactly this reason.

Tag each WS connection with the embed id it belongs to at construction time, so
injected filters never leak between embeds that share a source. Without tagging,
the prototype-level interceptor sees every connection on the page.

## Multiple embeds on one page: `targetComponents`

`initComposerEmbedManager` returns a singleton: one embed manager per page no
matter how many times you call it. So a bare `publish()` hits EVERY embedded
dashboard that has a matching fieldLink. On any page with more than one embed
(main plus a modal, main plus a drawer), scope the publish to a single
dashboard by passing `targetComponents` as the third argument:

```js
const dashboard = await embedManager.createComponent('dashboard', opts);
const instanceId = dashboard.componentInstanceId;   // 32-char hex on the returned object

embedManager.publish("Brand", {
  type: "selection",
  valueType: "ATTRIBUTE",
  ranges: [{ operation: 'IN', value: ['<value>'] }]
}, {
  targetComponents: [instanceId]   // only this dashboard, no leakage
});
```

`PublicationOptions` also accepts `publisherId` (so subscribers can ignore their
own messages) and `timestamp` (defaults to `Date.now()`). The common case is a
modal or drawer context-menu action filtering the main dashboard back behind it:
read the main embed's `componentInstanceId`, pass it as the only entry in
`targetComponents`.

## Capturing embed events for product-analytics SDKs

Everything the user does inside an embed is observable via
`addEventListener`. Wire those events straight into Mixpanel, Amplitude,
Segment or PostHog, and attach the host app's account and plan context at
capture time so the event is already segmented when it lands.

```js
function trackEmbed(name, props) {
  analytics.track(name, Object.assign({
    accountId: '<accountId>',
    plan: currentUser.plan,
    dashboardId: '<dashboardId>'
  }, props));
}

dashboard.addEventListener('composer-dashboard-loaded', e =>
  trackEmbed('dashboard_loaded', { dashboard: e.detail.dashboard }));
dashboard.addEventListener('composer-visual-rendered', () =>
  trackEmbed('visual_rendered'));
dashboard.addEventListener('composer-visual-series-clicked', e =>
  trackEmbed('visual_clicked', { point: e.detail }));
dashboard.addEventListener('composer-visual-failed', () =>
  trackEmbed('visual_failed'));
dashboard.addEventListener('composer-dashboard-saved', () =>
  trackEmbed('dashboard_saved'));
```

The event names worth capturing, from the documented set:

- Dashboard: `composer-dashboard-loaded`, `composer-dashboard-ready`,
  `composer-dashboard-saved`, `composer-dashboard-changed`,
  `composer-dashboard-dirty`, `composer-dashboard-pristine`,
  `composer-dashboard-widget-added`, `composer-dashboard-widget-removed`.
- Visual: `composer-visual-loaded`, `composer-visual-rendered`,
  `composer-visual-failed`, `composer-visual-series-clicked`,
  `composer-visual-cell-clicked`, `composer-visual-row-clicked`,
  `composer-visual-context-menu-clicked`.

There's no single "dashboard exported" or "filter applied" event in the SDK; you
synthesise those from the export interception below and from your own
filter-publish call sites. The framing that makes this worth the wiring: a user
active in your app but generating zero embed events is a churn signal the rest
of your telemetry won't catch.

## Secondary embeds (modal, drawer, side panel)

Two defaults matter for any dashboard embedded inside a modal or drawer.

First, set `interactivityProfileName: 'readonly'` and it MUST appear before
`interactivityOverrides` in the config object, or the overrides are silently
ignored (the library reads them in order).

Second, kill the in-iframe time bar with `visualSettings.TIMEBAR_PANEL: false`.
Composer renders the timebar directly into the host-page DOM, not inside the
embed, so it floats above any modal or drawer overlay regardless of z-index.
Suppress it in the embed config, and additionally hide/show the host-DOM
timebar element on open/close:

```js
// on open
hideMainTimebar();
modal.classList.remove('hidden');
// on close
modal.classList.add('hidden');
showMainTimebar();
```

The host-DOM timebar can be located by finding its "Update from/to" button (a
unique anchor present in every Composer timebar), walking up to its container,
and toggling `display: none`.

## interactivityOverrides: the nested schema

`interactivityOverrides` is a NESTED object with two sub-objects, `settings`
(dashboard-level flags) and `visualSettings` (per-visual flags). The
flat-map form, e.g. `{ FILTER: true, EXPORT: false }`, is wrong and will not
take effect. (This is also the shape behind Jira ZP-28728: the Visual Builder
embed breaks when a `sourceId` is passed alongside a flat
`interactivityOverrides`.)

```js
const config = {
  dashboardId: '<dashboardId>',
  originId:    '<dashboardId>',
  theme:       '__platform__',
  interactivityProfileName: 'readonly',     // BEFORE interactivityOverrides
  interactivityOverrides: {
    name: 'interactive',                     // base profile to start from
    type: 'SYSTEM',
    overrideVisualInteractivity: true,       // required for visualSettings to apply
    settings: {
      REFRESH: false, FILTER: false, EXPORT_PNG_PDF: false,
      SAVE: false, SAVE_AS: false, SHARE_DASHBOARD: false,
      COMMENTS: false /* ...etc... */
    },
    visualSettings: {
      TIMEBAR_PANEL: false,                  // the time bar lives here, not in settings
      EXPORT: false, MAXIMIZE: false, ACTIONS: false,
      KEYSET: false, TREND_ACTION: false /* ...etc... */
    }
  },
  header: { visible: false }
};
```

List every flag you care about explicitly. Omitting one lets it inherit
unpredictably from the base profile rather than defaulting to off.

## Context-menu custom actions

Add host-defined actions to the visual click menu via `contextMenu` (also seen
as `menuEventsConfig`):

```js
contextMenu: {
  click: 'openMenu',                 // open on left-click instead of right-click
  customActions: [
    {
      name: 'View details',
      icon: { src: 'data:image/svg+xml;base64,...' },   // base64, not URL-encoded SVG
      action: function (data) {
        const dims    = data.data.group;     // ['Cotton Throw Blanket', 'Home & Living']
        const metrics = data.data.current;   // metric values for the clicked point
        openDetail(dims, metrics);
      }
    }
  ]
}
```

In the callback, `data.data.group` is the ordered array of clicked dimension
values and `data.data.current` (with `.metrics` inside it) holds the metric
values; use `.current`, not `.metric`. Two known traps: the menu renders inside
the embed DOM, so it appears offset 100 to 300px from the click; a MutationObserver
that repositions the menu's absolute parent against the tracked `clientX/Y` fixes
it. And custom-action icons must be base64 data URIs; URL-encoded SVG data URIs
may not render.

## Export interception (brand your exports)

Composer exports are client-side, so you can intercept them and overlay your own
branding (e.g. a partner logo on every PNG and PDF the user downloads).

PNG (Screenshot) export goes through canvas. Override `toDataURL`:

```js
const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function () {
  // draw your logo onto this canvas, then defer to the original
  return origToDataURL.apply(this, arguments);
};
```

PDF export is the silent gotcha. The SDK uses FileSaver.js, so it triggers the
download via `window.saveAs`, NOT an anchor click. Overriding
`HTMLAnchorElement.prototype.click`, `document.createElement('a')`, or a
document-level click listener will NOT catch the PDF. Only overriding
`window.saveAs` works, and because `saveAs` is loaded dynamically you have to
poll for it to appear:

```js
const t = setInterval(function () {
  if (typeof window.saveAs === 'function') {
    clearInterval(t);
    const origSaveAs = window.saveAs;
    window.saveAs = function (blob, name) {
      // re-stamp the PDF blob with the logo, then save
      return origSaveAs.call(this, blob, name);
    };
  }
}, 500);
```

## Reading visible data from an embed: the visual API

Inside a context-menu action callback the object is richer than the docs say.
The real top-level key is `visualApi` (the docs name `visualization`, which does
not appear at the top level). `visualApi.thread.getData()` returns every row the
visual is currently showing, with no separate WebSocket call:

```js
action: function (data) {
  const rows = data.visualApi.thread.getData();
  // [{ group: ['Bluetooth Speaker', 'Electronics'],
  //    current: { count: 262,
  //               metrics: { roas: { calc: 4.31 }, impressions_k: { calc: 614.273 } } } }, ...]
}
```

Two things to know. Metric values come wrapped as `{ calc: <number> }`, never
raw numbers, so read `metric.calc`. And `getData()` returns the cached, already
filtered and aggregated rows; it does not trigger a fresh query, so if the
visual hasn't finished loading the array may be empty. Map `group` to dimension
names via `visualApi.variables` (`Row Attributes` for tables, `Group By` for bar
charts). This replaces the older pattern of firing a `START_VIS` query over the
captured WebSocket to read chart data; use that only where `visualApi` is
unavailable.

## Sources

- EmbedManager class: https://insightsoftware.atlassian.net/wiki/spaces/ZD/pages/15459516960/EmbedManager
- Embed API: https://insightsoftware.atlassian.net/wiki/spaces/DCI/pages/15750987797/Embed+API
- Embed SDK: https://insightsoftware.atlassian.net/wiki/spaces/ZD/pages/15459525583/Embed+SDK
- Embedding Composer/Symphony Using Script: https://insightsoftware.atlassian.net/wiki/spaces/CB/pages/17291477021
- Dashboard/Visual event names spike: https://insightsoftware.atlassian.net/wiki/spaces/CB/pages/17245503782

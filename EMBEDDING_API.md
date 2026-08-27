# Embed API surface: publication options, filter schemas, export interception

Absorbed from Peter Armstrong's toolkit on 27 August 2026, source
`/Users/aminhasan/logi-composer/peter-kb/bundle-2026-05-21/logi-composer-toolkit/docs/Logi-Composer-Symphony-Embedding-Reference.md`,
sections 8 to 13 and section 25. Every citation below is to that file as
`Logi-Composer-Symphony-Embedding-Reference.md:NNN`.

This file carries the API surface that `EMBEDDING_RUNTIME.md` states loosely or
leaves out: the full `PublicationOptions` interface, the tested negative
results, the `initialFilters` type catalogue, and the export interception table.
`EMBEDDING_RUNTIME.md` remains the place for the strict-mode WebSocket gotcha,
the `visualApi.thread.getData()` pattern and the analytics event wiring.
`EMBEDDING.md` covers boot, trusted-access tokens and the `zd-main` shell CSS,
which Peter's reference does not touch.

Punctuation note: Peter's prose uses em dashes throughout. Quotations below keep
his wording and substitute a colon or comma for the dash, because the house gate
rejects em and en dashes.

## Confirmed not working

The most useful part of the source, because it closes off approaches that look
plausible. Reproduced from `Logi-Composer-Symphony-Embedding-Reference.md:643-646`,
under his own heading "Still confirmed not working":

- `dashboardComponent.trigger('EMBED/PUBLISH', ...)`: `trigger is not a function` on `EmbeddedDashboard`
- `initialFilters` with `forTopic`: accepted but does not filter
- Dispatching `CustomEvent('EMBED/PUBLISH')` on `document`: no effect

Carry his caveats with the list. The word "still" is load-bearing: the same
section retracts an earlier claim of his own that `embedManager.publish()` does
not filter dashboard visuals, which he marks "Previously incorrect
documentation" and describes as wrong
(`Logi-Composer-Symphony-Embedding-Reference.md:641`). So the three above are
what survived retesting, not a list assembled once and left alone. The second
entry is the sharpest trap of the three, because `forTopic` is accepted without
error and produces an unfiltered dashboard rather than a failure you can see.

He does not date these three or name the build they were tested against. The
only dated bench result in the section is for Method 2, "Confirmed working
against `showcase.logianalytics.com` on 2026-05-12"
(`Logi-Composer-Symphony-Embedding-Reference.md:745`).

**All three were retested end to end against a running Composer 26.2.0 on
27 August 2026, and all three hold.** They are current fact, not a period piece,
and they are safe to quote. The mechanism behind each, and the working call that
replaces the third, are in "Settled against a live 26.2.1 instance" below and in
[`_run/LIVE-TEST-20260827.md`](_run/LIVE-TEST-20260827.md).

## `PublicationOptions` and `publisherId`

Full signature, `Logi-Composer-Symphony-Embedding-Reference.md:666`:

```typescript
embedManager.publish(topic: string, message: null | SelectionMessage, options?: PublicationOptions): void
```

Note that `message` is typed `null | SelectionMessage`, so a null message is
part of the contract even though the documented way to clear a filter is an
empty `ranges` array (`Logi-Composer-Symphony-Embedding-Reference.md:689`). He
does not say what a null message does. Untested here.

`PublicationOptions`, all properties optional
(`Logi-Composer-Symphony-Embedding-Reference.md:669-674`):

| Property | Type | What it does |
|---|---|---|
| `publisherId` | `string` | Arbitrary string identifying the publisher. Subscribers use it to ignore messages they themselves posted. |
| `targetComponents` | `string[]` | Restricts delivery to specific dashboards. Omitted means the message reaches every embedded dashboard on the page. Each entry is a `componentInstanceId` from `embedManager.createComponent()`. |
| `timestamp` | `number` | Defaults to `Date.now()`. |

When you need a publisher id at all: only when the same page both publishes and
subscribes on one topic. `embedManager.subscribe()` receives everything on the
topic including your own publications
(`Logi-Composer-Symphony-Embedding-Reference.md:953-965`), so a host control
that publishes a selection and also listens for dashboard-originated selections
will re-enter its own handler. Stamp a `publisherId` on the publish, compare it
in the subscriber, and drop the match. Where the host only publishes, or only
subscribes, the field earns nothing. The string is arbitrary and Peter gives no
uniqueness or namespacing rule, so pick something specific to the control rather
than to the page.

`timestamp` is a default-filled field with no documented consumer. Leave it out.

## `targetComponents` worked patterns

`initComposerEmbedManager` returns a singleton, one embed manager per page
however many times you call it, so a bare `publish()` reaches every embedded
dashboard with a matching fieldLink
(`Logi-Composer-Symphony-Embedding-Reference.md:695`).

Pattern one, capture the instance id at creation
(`Logi-Composer-Symphony-Embedding-Reference.md:700-712`). The id is a 32
character hex string on the object `createComponent()` resolves to, example
`"3e4a5f3974977542bc4260c81eed0053"`:

```javascript
var dashboard = await embedManager.createComponent('dashboard', opts);
var instanceId = dashboard.componentInstanceId;

embedManager.publish("Brand", {
  type: "selection",
  valueType: "ATTRIBUTE",
  ranges: [{ operation: 'IN', value: ['SoundMax'] }]
}, {
  targetComponents: [instanceId]
});
```

Pattern two, a modal or drawer context-menu action filtering the main dashboard
behind it (`Logi-Composer-Symphony-Embedding-Reference.md:717-728`). The modal
does not hold the main embed's object, so it reads it back out of a host-app
registry that the boot code populated:

```javascript
var mainDashRef = window._modalAuth.embedRefs['analytics-embed'];
var mainInstanceId = mainDashRef.dashboard.componentInstanceId;

embedManager.publish(fieldLinkLabel, {
  type: 'selection',
  valueType: 'ATTRIBUTE',
  ranges: [{ operation: 'IN', value: [clickedValue] }]
}, {
  targetComponents: [mainInstanceId]
});
```

`window._modalAuth.embedRefs` is his demo harness rather than anything the SDK
provides. The transferable part is the shape: keep a keyed registry of embed
refs at boot so any later context can resolve an instance id by name.

His rule, at `Logi-Composer-Symphony-Embedding-Reference.md:714`: always use
`targetComponents` when filtering from one embed context to another, otherwise
the filter leaks to every dashboard on the page carrying a matching fieldLink.

Timing for the second embed
(`Logi-Composer-Symphony-Embedding-Reference.md:739`): the main embed's
`composer-dashboard-ready` fires on initial load, so for a drawer booted later
the next occurrence of that event belongs to the secondary embed. That is an
ordering assumption rather than a discriminator, and it breaks if a third embed
boots concurrently. Where you can, gate on the drawer's own component object
instead of the document-level event.

## Filtering methods, deltas only

`EMBEDDING_RUNTIME.md` already carries the three methods, the fieldLink-label
rule, the `fieldLinks[].label` lookup, the Zoomdata channel differences and the
`START_VIS` interceptor. What Peter adds on top:

The priority is stated as a table with an explicit "requires" column
(`Logi-Composer-Symphony-Embedding-Reference.md:635-639`): method 1 needs a
named fieldLink on the dashboard, method 2 needs nothing on the dashboard and
targets visuals by name, method 3 needs nothing at all. That is the decision
input. Read the dashboard JSON for `fieldLinks[]` first, and if it is empty and
you cannot author the dashboard, you are on method 2 or 3 whatever you would
prefer.

Subscribe topics are more forgiving than publish topics
(`Logi-Composer-Symphony-Embedding-Reference.md:965`): on the outbound side the
topic matches the raw field name, for example `'category'`, and the label form
`'Category'` also works. Publishing has no such tolerance. Do not infer from a
subscribe that succeeded on a raw field name that a publish on the same string
will filter anything.

Populating host filter dropdowns off the captured socket
(`Logi-Composer-Symphony-Embedding-Reference.md:879-951`): send your own
`START_VIS` frame on the embed's authenticated connection with a `TERMS`
aggregation on the field and a `COUNT` metric, time bounded by
`'+$start_of_data'` to `'+$end_of_data'`. The server answers with about six
messages per query (status, time range, activity, viewport, data, final status),
so match on `msg.cid` and act only on `msg.data` or `msg.error`, ignoring the
rest. The `cid` must start with `'filter_'`, because the interceptor in method 3
skips that prefix; without it your value-lookup query gets the active filters
injected into it and the dropdown only ever offers values already selected.

Related and worth knowing when reading his section 10: the chart-data fetch
pattern uses the `cid` prefix `'chartdata_'`, which is deliberately not
`'filter_'`, so those queries do pick up the injected host filters and the
fetched rows respect the current selection
(`Logi-Composer-Symphony-Embedding-Reference.md:1251`).

## `initialFilters`: the pre-load filter catalogue

Absent from `EMBEDDING_RUNTIME.md`, which starts after render. `initialFilters`
pre-filters a dashboard at boot and is a property of the component config passed
to `createComponent()`.

Envelope, `Logi-Composer-Symphony-Embedding-Reference.md:457-466`:

```javascript
const initialFilters = [
  {
    sourceId: "source-id-string",             // required
    filters: [ /* filter objects */ ],
    timeFilter: { /* time filter object */ },
    applyFiltersStrategy: "overrideSamePath"  // or "replaceExisting"
  }
];
```

One entry per source, so a multi-source dashboard needs one envelope per
`sourceId`. `applyFiltersStrategy`
(`Logi-Composer-Symphony-Embedding-Reference.md:468-471`): `overrideSamePath`
replaces only filters on the same field path and leaves the rest of the saved
filter state alone, `replaceExisting` wipes all existing filters. Choose
`overrideSamePath` when the dashboard author's own filters are part of the
design and `replaceExisting` when the host is the only authority on what the
viewer may see.

Filter types, `Logi-Composer-Symphony-Embedding-Reference.md:475-586`. The
discriminator is `type` and every one of them carries `path`:

| `type` | Shape beyond `path` | Operations |
|---|---|---|
| `ATTRIBUTE` | `values: []` | `IN`, `NOT_IN`, `EQUALS`, `NOT_EQUALS` |
| `COMPARISON` | `value` (number) | `GT`, `GTE`, `LT`, `LTE`, `EQ`, `NE` |
| `RANGE` | `from`, `to` | none |
| `TIME` | `timeWindow` | none |
| `TEXT_SEARCH` | `value` (string) | `CONTAINS`, `STARTS_WITH`, `ENDS_WITH` |
| `WILDCARD` | `value` (pattern, `*`) | none |
| `HIERARCHY` | `values: []` | `IN` |
| `BOOLEAN` | `value` (boolean) | none |
| `KEYSET` | `keys: []` | `IN` |

`path` takes a dotted form for nested fields, his example being
`"product.category"` (`Logi-Composer-Symphony-Embedding-Reference.md:480`).

`timeWindow` has two forms
(`Logi-Composer-Symphony-Embedding-Reference.md:508-533`), absolute with `from`
and `to` as ISO 8601 strings, or relative with
`{ type: "RELATIVE", amount, unit }` where `unit` is one of `MINUTE`, `HOUR`,
`DAY`, `WEEK`, `MONTH`, `YEAR`. The relative form is what you want for an embed
whose default window should follow the viewer rather than the author.

Two schema mismatches to hold in mind, both real rather than typos in his file.
`initialFilters` attribute filters use `values` (plural array) with `path` as a
bare string; the filter objects injected over the WebSocket in method 3 use
`value` and wrap the path as `{ name: 'field' }`
(`Logi-Composer-Symphony-Embedding-Reference.md:790-808`). Copying one shape
into the other silently produces no filtering. And `NOT_IN` here is spelled with
the underscore, against `NOTIN` in the WebSocket form.

The `forTopic` variant of `initialFilters` is in the confirmed-not-working list
above. Pre-filtering at boot works through `sourceId` plus `path`, never through
a pub/sub topic.

## The section 5 `interactivityOverrides` trap

`Logi-Composer-Symphony-Embedding-Reference.md:283-288` documents
`interactivityOverrides` as a flat key to boolean map:

```javascript
interactivityOverrides: {
  FILTER: true,
  EXPORT: true,
  MULTI_SELECTION: false
}
```

That is wrong and his own section 11 says so:
`Logi-Composer-Symphony-Embedding-Reference.md:1360` marks it "schema correction
(previously wrong)" and states the real structure is nested, with `settings` for
dashboard-level controls and `visualSettings` for per-visual controls. The
correction was applied in section 11 and never back-propagated into section 5,
so a reader who reaches for the config reference at section 5.1 and stops there
gets the broken schema with no warning attached to it.

`EMBEDDING_RUNTIME.md:236` already carries the correct nested shape, the
`interactivityProfileName` ordering rule and the `overrideVisualInteractivity`
requirement. Use that. Anyone reading Peter's section 5.1 should be pointed at
his section 11.1 before they copy the block.

One in-slice addition on ordering that `EMBEDDING_RUNTIME.md` lacks: the Stitch
template kit's `components.js` maps `interactivityProfile` in its own config to
`interactivityProfileName` on the embed library, and its `bootSingleEmbed()`
builds `createOpts` with `interactivityProfileName` first and
`interactivityOverrides` after, preserving the required order
(`Logi-Composer-Symphony-Embedding-Reference.md:1563-1574`). If you inherit a
Stitch-derived shell, the ordering discipline is already in the harness and you
should not re-implement it in the page.

## PDF export interception

Section 25. `EMBEDDING_RUNTIME.md` says overriding `window.saveAs` is the only
thing that works and gives the polling loop. Peter's addition is the evidence
for why, plus the blob guard and the PDF rewriting step.

Composer's dashboard PDF export is entirely client-side
(`Logi-Composer-Symphony-Embedding-Reference.md:3195-3200`): the SDK renders to
PDF internally, builds a `Blob` of type `application/pdf`, calls
`URL.createObjectURL(blob)`, then hands off to `window.saveAs(blob, filename)`,
the global from FileSaver.js bundled with the embed SDK.

What does not catch it, and why
(`Logi-Composer-Symphony-Embedding-Reference.md:3204-3212`):

| Approach | Why it fails |
|---|---|
| Override `HTMLAnchorElement.prototype.click` | The SDK uses `saveAs()`, not `.click()` on an anchor |
| Override `Document.prototype.createElement('a')` | FileSaver may cache native `createElement` before your override runs |
| Document-level capture click listener | `saveAs()` creates anchors that are not in the DOM, or uses cached native methods |
| Override `EventTarget.prototype.dispatchEvent` | `saveAs()` bypasses the standard event path |
| Override the `HTMLAnchorElement.prototype.href` setter | The SDK may use `setAttribute` or cached property descriptors |

He states the only reliable interception point is overriding `window.saveAs`
itself (`Logi-Composer-Symphony-Embedding-Reference.md:3212`).

Guard the override so you only touch PDFs and only once your overlay asset has
loaded, and fall back to the original saver on any failure
(`Logi-Composer-Symphony-Embedding-Reference.md:3218-3245`):

```javascript
window.saveAs = function (blob, filename) {
  if (blob instanceof Blob
      && blob.type === 'application/pdf'
      && filename && filename.toLowerCase().indexOf('.pdf') !== -1
      && _logoBytes) {
    addLogoToPdf(blob)
      .then(function (modifiedBlob) { _origSaveAs(modifiedBlob, filename); })
      .catch(function (err) { _origSaveAs(blob, filename); });
    return;
  }
  return _origSaveAs.apply(this, arguments);   // non-PDF passes through
};
```

The `_logoBytes` term in the guard matters: without it a race where the logo has
not loaded yet produces a silently unbranded export rather than an error, and
the `.catch` branch means a malformed PDF still reaches the user unmodified
instead of failing the download.

Installation is idempotent and polled at 500ms because `saveAs` is loaded
dynamically by the embed script and is absent at page load
(`Logi-Composer-Symphony-Embedding-Reference.md:3249-3271`). Clear the interval
once installed, and keep the immediate first attempt before the interval starts
so a late-running page does not wait 500ms for nothing.

Rewriting the blob uses pdf-lib from a CDN
(`Logi-Composer-Symphony-Embedding-Reference.md:3273-3302`):
`PDFDocument.load(await blob.arrayBuffer())`, `embedPng`, then loop
`pdfDoc.getPages()` drawing the image at each page's own size with an explicit
`opacity`, and return `new Blob([await pdfDoc.save()], { type: 'application/pdf' })`.
Scale the logo height from its native aspect ratio rather than fixing both
dimensions. A CDN dependency is a live-network requirement at export time, so
for an air-gapped or CSP-restricted deployment self-host pdf-lib and say so in
the deployment notes.

The two export paths need different hooks
(`Logi-Composer-Symphony-Embedding-Reference.md:3304-3311`): PNG screenshot
export goes canvas `toDataURL()` to `Blob` to anchor click, intercepted at
`HTMLCanvasElement.prototype.toDataURL`; PDF goes `Blob` to `window.saveAs`,
intercepted at `window.saveAs`. He states both overlays coexist on one page
without interfering.

## Context menu CSS defects

In slice (section 10) and absent from both of Amin's files, which cover the
positioning offset and the base64 icon rule but not these two.

Clipping (`Logi-Composer-Symphony-Embedding-Reference.md:1314-1328`): the SDK
renders the context menu inside the embed's own DOM tree, under
`SECTION.zd-main-section`, rather than in a portal at `document.body`, so any
ancestor with `overflow: hidden` or `overflow: auto` cuts the menu off. Fix with
`.logi-embed.logi-embed-main { overflow: visible !important; }`, combined with
the positioning fix from his section 10.5.

Item styling (`Logi-Composer-Symphony-Embedding-Reference.md:1330-1352`):
standard menu items get `align-items: center`, `padding: 0 16px` and
`min-height: 40px`, while custom items added through `customActions` default to
`align-items: flex-start`, `padding: 0 7px` and `min-height: 0`, which is why a
custom action looks wrong next to a built-in one. Match them on the
`[data-testid^="context-menu-custom"]` selector and constrain the icon to 16 by
16 with `object-fit: contain`.

## ZoomdataSDK direct queries

Section 12, in slice, absent from both of Amin's files. Query a source without
rendering a visual, for a custom chart or a data extract.

`ZoomdataSDK.createClient({ credentials, application: { secure, host, port, path } })`
where `path` is the context path, `/discovery` in his example, and `credentials`
is the object your existing `getToken()` already returns
(`Logi-Composer-Symphony-Embedding-Reference.md:1586-1600`). So this reuses the
trusted-access plumbing in `EMBEDDING.md` with no second auth path.

The query config takes `sourceId`, a `fields` array where each entry is either a
grouping field with `limit` and `sort` or a metric with `func`, a `filters`
array in the same `ATTRIBUTE` shape as `initialFilters`, a `time` object with
`timeField`, `from` and `to`, and a top-level `limit`
(`Logi-Composer-Symphony-Embedding-Reference.md:1602-1626`).
`client.createQuery(config)` then `query.run()`, which takes a callback or
returns a promise (`Logi-Composer-Symphony-Embedding-Reference.md:1628-1647`).

Results come back as `{ data: [{ group: [...], current: { count, metrics } }] }`
(`Logi-Composer-Symphony-Embedding-Reference.md:1649-1676`). Metrics are keyed
by field name and wrapped by aggregation, `revenue: { sum: 250000 }`, matching
the `{ calc: n }` wrapping that `EMBEDDING_RUNTIME.md` documents for
`visualApi.thread.getData()`. Read the aggregation key, never the object.

Prefer `visualApi.thread.getData()` when you want what a visual is already
showing, since it costs no query. Reach for ZoomdataSDK when you need data no
visual on the page is rendering.

## Settled against a live 26.2.1 instance, 27 August 2026

The three items above were retested against the embed SDK served by a running Simba
Intelligence 26.2.1 install with Composer as its `discovery` subchart, fetched from
`/discovery/embed/embed.js` (44,422 bytes). Full method in
`/Users/aminhasan/simba-intel-lab/CONFIRMED-NOT-WORKING-VERDICT.md`.

**All three confirmed.** Peter's list holds. What follows is the mechanism, which his entry
did not carry, and which turns two of the three into a working call.

`trigger` occurs zero times in the SDK. The publish API is `publish(topic, message, options)`
and it lives on the **EmbedManager**, not on a dashboard component, so the working form is
`embedManager.publish(...)`. Reaching for the component was the error.

`forTopic` occurs zero times. `initialFilters` is real (11 occurrences, assigned in the
component constructor beside `interactivityProfileName` and `interactivityOverrides`), but
JavaScript accepts an unknown key without complaint, so the property is silently dropped.

The event dispatched is named `EMBED/CUSTOM_EVENT`, not `EMBED/PUBLISH`. The SDK's whole
dispatcher is:

```js
const L = (e, t) => {
  const i = new CustomEvent("EMBED/CUSTOM_EVENT", {detail: {type: e, data: t}, bubbles: true});
  document.dispatchEvent(i)
};
```

with `publish(e,t,i){ L("EMBED/PUBLISH", {topic:e, message:t, options:i}) }`. So
`EMBED/PUBLISH` is the inner `detail.type`, never an event name. The equivalent that should
work from outside the SDK, derived from the source rather than guessed:

```js
document.dispatchEvent(new CustomEvent("EMBED/CUSTOM_EVENT", {
  detail: { type: "EMBED/PUBLISH", data: { topic, message, options } },
  bubbles: true
}));
```

`document.addEventListener` and `postMessage` both occur zero times in this file; the only
listeners bound are `composer-dashboard-loaded`, `composer-visual-builder-loaded` and
`discovery-report-loaded`.

### Runtime confirmation, 27 August 2026

The paragraph above ended by flagging one thing as unproven: that the
`EMBED/CUSTOM_EVENT` form filters a live dashboard end to end, for want of a
dashboard, a source and a browser. All three were built on a `kimi` rig running
Composer 26.2.0 and the whole list was re-run through the real SDK. Method and raw
results: [`_run/LIVE-TEST-20260827.md`](_run/LIVE-TEST-20260827.md).

**The static reading was right on every point, and the open item is now closed.**

* `comp.trigger` is `undefined` at runtime and calling it throws
  `trigger is not a function`, matching Peter's wording exactly.
* `initialFilters` with `forTopic` is stored verbatim on the component and produces
  SQL with no predicate on the mapped field. Accepted, stored, ignored.
* `CustomEvent('EMBED/PUBLISH')` on `document` fires no query at all.
* **The derived `EMBED/CUSTOM_EVENT` form works.** Dispatching it with
  `detail.type = "EMBED/PUBLISH"` put
  `and "ds"."full_site_name" = 'Karratha Gorge Iron Ore Mine'` into the generated
  SQL 1.2 seconds later. The form written above from source reading, unproven at the
  time, is correct as written.

Verdicts were read from the SQL the query engine logged, not from the rendered
chart, and each negative is gated by a positive control in the same session:
`embedManager.publish("Site", ...)` on the same dashboard and topic did produce a
`full_site_name` predicate. So the fieldLink, the topic label and the embed session
were all sound, and the three negatives failed on their own merits rather than on a
misconfigured harness.

One practical note the SDK does not advertise: the `embed.js` script tag must carry
`data-name="composer-embed-manager"`. The manager locates its own tag to derive the
server path, and without it `initComposerEmbedManager` throws
`Cannot read properties of null (reading 'groups')`.

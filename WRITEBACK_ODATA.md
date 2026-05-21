# Write-back and the OData API

Two runtime data features that pair together. Write-back lets an embedded app
edit the rows behind an upload-backed source. The OData API lets third-party BI
tools read any governed source out as a live feed. Both run under the session's
security, both are documented here from working demo code.

## Write-back to upload-backed sources

When a source is built on a file upload (CSV/TSV/JSON), you can replace, append
to, or clear that upload's data at runtime from the embedded app. The use case is
an editable parameter table: a targets table, a budget table, a what-if input set
that drives the dashboard, edited in your UI and written straight back.

### The endpoints

| Method | Path | Effect |
|---|---|---|
| `PUT` | `/discovery/api/uploads/{uploadId}/data` | Replace all rows. |
| `POST` | `/discovery/api/uploads/{uploadId}/data` | Append rows. |
| `DELETE` | `/discovery/api/uploads/{uploadId}/data` | Clear all rows. |

There is NO GET. `GET .../data` returns 405. The endpoint is write-only by
design (the `data` field is `writeOnly`). To read current values back, use OData,
see "reading current values" below. This is the first silent gotcha: people
reach for GET, get a 405, and assume the upload is broken.

### The uploadId is not the sourceId

They are always different values. The uploadId addresses the upload directly; the
sourceId addresses the source built on top of it. An upload joined into a larger
multi-entity source has no standalone source id of its own. Get the uploadId from
`GET /api/uploads` or the source editor's API Endpoints dialog. Get the sourceId
from the dashboard's widget (`GET /api/dashboards/{id}` then a widget's
`sourceId`).

### The multipart shape

The write is `multipart/form-data`, not JSON. Three fields:

| Field | Value |
|---|---|
| `fileData` | a `Blob` of the CSV text, `type: 'text/csv'` |
| `delimiter` | the delimiter, e.g. `,` |
| `includesHeader` | `true` if the first row is a header |

```js
async function putUploadCsv(server, uploadId, csvString, token, basicCreds) {
  const form = new FormData();
  form.append('fileData', new Blob([csvString], { type: 'text/csv' }), 'data.csv');
  form.append('delimiter', ',');
  form.append('includesHeader', 'true');

  // Bearer token preferred (no plaintext password needed)
  let res = await fetch(`${server}/discovery/api/uploads/${uploadId}/data`, {
    method: 'PUT',
    headers: { Authorization: 'Bearer ' + token },
    body: form,
  });

  // Basic auth fallback
  if (!res.ok && basicCreds) {
    const basic = 'Basic ' + btoa(`${basicCreds.username}:${basicCreds.password}`);
    res = await fetch(`${server}/discovery/api/uploads/${uploadId}/data`, {
      method: 'PUT',
      headers: { Authorization: basic },
      body: form,
    });
  }

  if (!res.ok) throw new Error('PUT ' + res.status + ': ' + await res.text());
}
```

Prefer the Bearer token (the DataDiscoveryToken the embed already holds); it
needs no plaintext password. Fall back to Basic only if the Bearer write is
rejected.

Build the CSV with CRLF line endings and quote any value containing a comma,
quote, or newline.

### Cache rows in memory, then refresh

There is no GET and no row-level update. You replace the whole table each write,
so you must hold the current rows yourself:

1. On first edit, read the current rows once via OData (below) and cache them.
2. Apply the user's edit to the cached array.
3. PUT the full rebuilt CSV.
4. Update the in-memory cache. Never re-read on later edits.
5. Call `dashboard.refreshData()` on every embedded dashboard so the visuals
   repaint with the new values.

```js
function refreshAllEmbeds(embedRefs) {
  Object.values(embedRefs || {}).forEach((ref) => {
    if (ref.dashboard && typeof ref.dashboard.refreshData === 'function') {
      ref.dashboard.refreshData();
    }
  });
}
```

### Reading current values via OData

Because the upload's own `GET .../data` is 405, read current values through the
source's OData endpoint. Use `$apply=groupby((fields))` to get one row per
distinct combination, so you pull just the N parameter rows rather than the full
joined time-series:

```js
async function readUploadRows(server, sourceId, fields, token) {
  const url = `${server}/discovery/api/sources/odata/s_${sourceId}`
    + `?$apply=groupby((${fields.join(',')}))`;
  const res = await fetch(url, { headers: { Authorization: 'Bearer ' + token } });
  if (!res.ok) throw new Error('OData failed: ' + res.status);
  return (await res.json()).value;  // array of named-key row objects
}
```

One more gotcha: a joined source may suffix field names that collide across
entities (e.g. `id` becomes `id_1`). Check the OData response keys and use the
actual suffixed names in the `groupby` list.

## The OData API for third-party BI

Every governed source is exposable as an OData v4 feed, the format Excel, Power
BI, and Python read natively. Same source, same security, no second pipeline.

### The endpoint

```
https://<server>/api/sources/odata/s_<sourceId>
```

From the browser the path is `/discovery/api/sources/odata/`. The entity-set name
is `s_` followed by the sourceId (`s_<sourceId>`). The service root
(`GET /discovery/api/sources/odata/`) lists every source the session can reach as
an entity set.

### `$metadata` auto-populates clients

`GET .../s_<sourceId>/$metadata` returns a standard OData schema document: field
names, types, relationships. This is what Excel (Data, Get Data, From OData Feed)
and Power BI read to build the field list with zero client-side configuration.

### Supported query options

`$select`, `$filter`, `$orderby`, `$top`, `$skip`, and `$apply`.

```
/discovery/api/sources/odata/s_<sourceId>
  ?$select=account_name,revenue,region
  &$filter=region eq 'EMEA'
  &$orderby=revenue desc
  &$top=20
```

Pages are 10,000 rows. Use `$skip` to paginate; Power BI does this for you.

### Security is enforced on every request

You must authenticate to get even the `$metadata` document. Row-level security
and column security fire on every single request, so a consumer sees exactly what
their identity is entitled to and nothing more. Switch to a user scoped to one
region and the other regions' rows simply are not in the response. The consumer
never sees the filter; it just works.

### Read-only

The OData feed is read-only. Writes go through the Upload API above, a separate
governed flow. There is no OData write path.

### Consumers

Excel and Power BI connect directly via the OData feed. Fivetran, Airbyte, and
dbt all support OData as a source, so you can schedule syncs from a governed Logi
source into a warehouse without rebuilding the model or its security.

## The CORS rule worth knowing

| Path prefix | CORS from the browser |
|---|---|
| `/discovery/api` | safe, use this for all browser-side fetches |
| `/zoomdata/api` | not safe, never call it from browser JavaScript |

So both the upload write and the OData read must go through `/discovery/api`.
Reaching for the bare `/api` or a `/zoomdata/api` path from the browser fails the
CORS preflight with no useful error.

## Sources

* Upload write-back (PUT replace, POST append, DELETE clear; multipart shape;
  uploadId vs sourceId; Bearer-then-Basic auth; cache-and-refresh) is reproduced
  from the demo write-back example and the worked targets-popup implementation.
* The OData endpoint, `s_<sourceId>` entity-set naming, `$metadata`
  auto-population, supported query options, 10,000-row pages, per-request RLS and
  column security, and read-only behaviour are reproduced from the OData demo
  script. The 405-on-GET upload behaviour and the `$apply=groupby` read pattern
  are verified empirically in that same demo material.

# Safety notes for composer-mcp

This file exists because on 2026-05-07 I (Claude, driving composer-mcp via
Amin's session) wiped Amin Hasan's admin roles in UAT Logi Symphony by
calling endpoints I shouldn't have. Recovery required Leo Carlin to manually
re-add Amin as a Global Administrator.

This document is the permanent learning artefact. Read it before working
with any user-mutation code in this repo.

## What happened

While debugging an "embed dashboards aren't loading" symptom in the Otto
Partner Center demo shell, I called:

1. `PUT /api/users/{aminId}` with a payload that omitted Amin's existing
   role memberships in Visual Data Discovery. The endpoint behaves as
   POST-overwrite (silently strips unset fields), so this cleared the
   33 admin roles he had in VDD.

2. `POST /api/trusted-access/push/tokens` with `{username: "amin.hasan",
   roles: [...]}` against Amin's own username. This created/refreshed
   a TA_PUSH-origin shadow record for amin.hasan in VDD with empty
   roles + empty groups, which the discovery API then preferred over
   the MDR-sourced record. Net effect: every subsequent /api/user call
   resolved to the empty ghost.

3. Repeated the push-token call with various role overrides as
   "workarounds", each one re-stamping the empty record.

The MDR side (Symphony admin home) continued to show Amin as Global
Administrator + System Administrators member, but the VDD side
(/discovery) saw zero roles. Amin couldn't reach /discovery/admin.html
nor `/managed/Admin/Accounts` after a session refresh; admin-only API
endpoints returned 403; the Connections menu disappeared from the UI
even when navigating directly.

## The two warnings I should have heeded

### Glyn McKenna's June 2025 email

Glyn explicitly wrote (forwarded to Amin by Peter Armstrong on this
same day, before I made the mistake):

> "I don't recommend using this endpoint when working with Logi Symphony
> Embedding and SSO... [the push token request] is also a POST [...] If you
> do not include all group memberships, custom attributes, or tenants etc
> in the request body, those parts will be treated as being set to nothing
> and will be cleared for the user. Using this request can also lead to
> the system becoming out of sync, as the changes are not automatically
> carried over to the MDR metadata repository."

I read this email *before* running the offending calls. I rationalised
"but I'm just minting a token, the body is small" and ignored the warning.

### The repo's own existing notes

`accounts.py` already documented PUT-replace semantics in docstrings
("PUT REPLACES — fetch the existing list... before calling, otherwise
you'll evict everyone except the users you pass"). Same shape of risk.
I should have generalised that lesson to push tokens.

## Hard rules now enforced in code

### `tokens.py`

- `mint_push_token` calls `_running_session_username()` first and
  raises `SelfMutationBlocked` if the target username equals the
  running session's user. Bypassable only with explicit
  `allow_self=True`, which forces the caller to acknowledge the risk
  in code review.
- The `roles` parameter has been **removed**. The Composer server
  silently ignores it on issuance, but it participates in the
  POST-overwrite that wipes the user record. There is no clean way
  to use it.
- Module docstring leads with the danger.

### `client.py` (added in v0.5.1, after Trevor's bootstrap-admin recovery)

- `_enforce_guards()` runs on every request. Two hard rules:
  1. **MDR endpoints are blocked.** Any path starting with `/managed`
     raises `MdrEndpointBlocked`. composer-mcp is VDD-only by policy.
     If you need MDR, do it manually outside this codebase with an
     explicit one-shot session — never via automation.
  2. **Self-mutation by user id is blocked.** PUT/PATCH/DELETE on
     `/api/users/{me}` raises `SelfUserMutationBlocked`. This is the
     direct write path that complements the push-token guard in
     `tokens.py`.
- The running user's id is fetched once via GET /api/user on first
  request and cached on the client instance.

### Anywhere else with PUT-replace or POST-overwrite semantics

- `accounts.py` `add_users_to_account` / `add_admins_to_account`:
  docstrings already warn "PUT REPLACES". Keep that warning.
- Any new helper that mutates user records must follow the
  read-modify-write pattern: fetch the full record, apply the diff
  in memory, send the full record back. No partial bodies.

## How to provision users inside Logi Symphony

Per Glyn: use **MDR's long-form Logon** at
`POST /managed/API/Logon` with `accountProperties` populated. MDR is
the source of truth; it pushes to VDD automatically with the full
payload, so nothing gets stripped. Example body in Glyn's email,
saved at `/Users/aminhasan/composer-mcp/agents/` if needed.

Do not provision Symphony users via VDD push tokens. Do not "fix"
broken user records via VDD push tokens. There is no shortcut here.

## Recovery procedure (if this happens again)

1. The damaged user must contact a Symphony global admin (someone other
   than themselves) who still has working credentials.
2. The global admin opens `/managed/Admin/Accounts`, finds the user,
   re-adds the System Administrators group (and Tenant Administrators
   for any tenants they should have admin in).
3. The user logs out of all sessions and logs back in. The MDR Logon
   flow pushes the corrected role set down to VDD.
4. Verify by hitting `/discovery/api/user` and confirming
   `userOrigin != "TA_PUSH"` and the roles array matches the admin UI.

If the VDD-side ghost record persists (userOrigin stays TA_PUSH after
re-login), a Symphony super-admin can call the MDR endpoint
`/managed/api/Admin/MigrateAccountServicesObjectsToDataDiscovery` to
force a clean re-push. This requires a session whose user is in
"System Administrators" — if the bootstrap `admin` user's password is
known, that's the safest credential to use for the migrate call.

### The `preserveGroups` trick (added later 2026-05-07)

When you must mint push tokens for a privileged user (because the
embedded resources only render with that user's role bag), include
the user's role-bearing VDD groups in EVERY push body. Composer
overwrites the user's group memberships on each push, so the body
must always carry the full set you want to keep.

In the Otto-OPC shell:

```js
const CONFIG = {
  sharedUsername: 'amin.hasan',
  preserveGroups: ['Administrators', 'Supervisors', 'Content Distributors'],
  // ...
};

async function getPushToken() {
  const groups = [...(CONFIG.preserveGroups || [])];
  if (CONFIG.group) groups.push(CONFIG.group);  // forced-filter group
  const body = { username: CONFIG.sharedUsername, account: CONFIG.account, groups };
  // POST as before
}
```

Real role-bearing group names (which the system recognises as
memberships) and arbitrary forced-filter strings can sit in the same
`groups` array. Real ones grant memberships; unknown strings act as
forced-filter scopes.

### Importing connections with their encrypted password

Composer doesn't expose passwords on `GET /api/connections/{id}` —
the JSON omits the encrypted blob. So a connection POSTed by reading
+ stripping + posting will land in the destination tenant with no
password. Workaround: use the source export bundle which DOES carry
the encrypted blob.

```bash
# Export a source from the source tenant; the dependency walk pulls
# the connection record with its encrypted password attached.
curl ... "/api/sources/export?ids={sourceId}"   # GET, returns JSON

# Import in the destination tenant. Composer dedupes connections by
# JDBC URL + USER_NAME (not by name), so to force a fresh CREATE in the
# destination you can bump the URL with a throwaway query param,
# import, then PUT to remove the bump and rename. Names with `(suffix)`
# alone do NOT force creation; only differing URL/USER does.
curl -X POST ... "/api/sources/import" -d @bundle.json
```

### Custom metrics live on a sub-endpoint

The standard `GET /api/sources/{id}` does NOT include custom
calculated metrics (ROAS, conversion_rate, etc). Read them via:

```
GET  /api/sources/{id}/custom-metrics
POST /api/sources/{id}/custom-metrics  (create one)
```

If you migrate sources without copying these, visuals that reference
calculated metrics render an "access denied / select new values"
error because the metric reference can't resolve.

### The recipe that worked on 2026-05-07

```bash
PW="<bootstrap admin password>"

# 1. Auth via MDR Logon
curl -s -X POST "$BASE/managed/API/Logon" \
  -H "Content-Type: application/json" \
  -d "{\"accountName\":\"admin\",\"password\":\"$PW\",
       \"isWindowsLogOn\":false,\"performDataDiscoveryLogon\":true,
       \"deleteOtherSessions\":true}" -o /tmp/admin-logon.json
SID=$(jq -r .sessionId /tmp/admin-logon.json)

# 2. Force MDR -> VDD re-sync for every account
curl -s -X POST \
  "$BASE/managed/API/Admin/MigrateAccountServicesObjectsToDataDiscovery?sessionId=$SID" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"options":{}}' -o /tmp/mig.json

# 3. Inspect the per-user message for the broken account
jq '.messages[] | select(.name=="amin.hasan")' /tmp/mig.json
# Look for "Migration succeeded" and the "user membership in the
# following groups is updated" line listing the restored groups.

# 4. Have the affected user log in fresh via /managed/LogOn (not
#    /discovery/login). Their session will pick up the restored roles
#    on first call.
```

The migrate endpoint is idempotent and operates over every account in
the system, not just the broken one. Errors on unrelated accounts
(`errorCount > 0` in the summary) are normal — usually old/orphaned
records from past tenant deletions. Filter the messages to your
specific user before celebrating or panicking.

### Per-persona row narrowing via the proxy + `visual.source.filters`

Added 2026-05-08 after the Otto Group UC4 build burned ~6 hours
walking into three independent Composer bugs trying to do per-persona
RLS the textbook way. The path that actually works is documented in
`SCHEMA_NOTES.md` "Forced filters" section (B+C); this block is the
"don't lose this recipe" version.

The setup:

* One MDR-synced underlying user (`amin.hasan` in the Otto demo). All
  personas mint push tokens against this user, with `preserveGroups`
  carrying the role bag.
* No source-level Row Security rule active for that user. (Leave
  rules in place if other users use them; just don't have the embed
  user as an assignee.)
* A small Python proxy server-side (admin Basic Auth never leaves
  the server) that takes a partner CSV and PUTs `source.filters` on
  every widget visual on the consolidated dashboard.

The proxy:

```python
def apply_persona_filter(partner_csv: str):
    """For every widget visual on the consolidated dashboard, write
    source.filters with the persona's partner names. Empty CSV clears."""
    dash = api_get(f"/api/dashboards/{DASHBOARD_ID}")
    vids = [w.get("visualId") or w.get("content", {}).get("visualId")
            for w in dash.get("widgets", []) if w]

    values = [s.strip() for s in (partner_csv or "").split(",") if s.strip()]
    new_filter = ([{"path": FILTER_PATH, "operation": "IN", "value": values}]
                  if values else [])

    for vid in vids:
        v = api_get(f"/api/visuals/{vid}")
        if v.get("source", {}).get("sourceId") != SOURCE_ID:
            continue
        for k in ("createdByUserID", "createdDate", "creatingUserName",
                  "lastModifiedByUserID", "lastModifiedDate", "originId",
                  "version"):
            v.pop(k, None)
        v["source"]["filters"] = new_filter
        api_put(f"/api/visuals/{vid}", v)
```

Critical shape detail: `value` (singular key). `values` (plural) is
accepted by PUT but Composer strips the array and stores `path: null`
 — filter persists structurally but never matches anything at runtime.
`value` accepts a single string OR an array of strings.

The shell side, on persona switch:

```js
sel.addEventListener('change', async () => {
  const csv = sel.options[sel.selectedIndex].dataset.partnerCsv || '';
  await fetch('/api/persona', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({partner_csv: csv}),
  });
  // Re-mint token, destroy + recreate the dashboard component.
  // The embed manager caches visual configs at createComponent time
  // (see LIMITATIONS.md "Visual config cache against the push-token
  // session"), so a destroy + recreate is required — a soft refresh
  // won't pick up the new filters.
});
```

Working reference shipping in this repo:
* `embed/serve_nocache.py` — proxy + dev server with `Cache-Control:
  no-store` on every response
* `embed/otto-opc-shell.html.template` — full shell with persona
  switcher wired

### What burned the hours (so you don't repeat it)

Three Composer behaviours that all look like they should give you
RLS and don't:

1. **Source-level Row Security** on a column in a cross-warehouse
   joined source 500s the field-stats pre-flight every render.
   "Error while preparing the request" on every widget. Not fixable
   client-side. See `LIMITATIONS.md` "Server bugs that look like API
   problems".
2. **TA_PUSH-only users** can't drive the data engine even with
   identical READ/DATA_ACCESS and role bag to a working user. The
   data engine seems to require an MDR-side user record. So you
   can't just spin up an embed user and have it work.
3. **`dashboard.rowFilters`** PUT is accepted, persists, and is
   ignored at runtime. **`embed.js createComponent({filters})`** is
   the filter pane visibility option, not row filtering.

Per-visual `source.filters` PUT with the singular-`value` shape is
the only API path that actually filters data at query time. Hence
the proxy.

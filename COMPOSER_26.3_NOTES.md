# Logi Composer 26.3: what changes for this MCP

Logi Composer 26.3 shipped on 29 September 2026. It is sold as Self-Service Analytics under
Simba Embedded Analytics. Every statement below comes from a public source, cited inline, and
was checked on 2 October 2026. Nothing here describes API behaviour beyond what those sources
show; the REST patterns in this repo were last tested on 26.2.0 and have not been retested on
26.3.

## Kubernetes chart

- Helm repo and chart, from the public install guide
  (https://insightsoftware.mintlify.app/simba-embedded-analytics/docs/self-service-analytics/26.3/administer/install/kubernetes-ov.md):

  ```bash
  helm repo add composer https://composer-repo.logianalytics.com/helm-charts/stable
  helm search repo composer/composer --versions
  ```

- The same guide says Kubernetes is supported for new installations only, for 26.3 and later.
- `helm search repo composer/composer --versions` lists chart **1.22.0** as app 26.3
  (published 2026-09-29), 1.21.0 as 26.2 and 1.20.0 as 26.1.
- Public images on Docker Hub: `insightsoftware/zoomdata:26.3.0` (2026-09-29) and new
  `26.3.0-k3s` tags the same day; `insightsoftware/simba-intelligence:26.3` (2026-09-25).

## Context path decides every API base path

In chart 1.22.0 (`helm pull composer/composer --version 1.22.0 --untar`, then read
`values.yaml`), `zoomdataWeb.contextPath` defaults to **`/composer`**. This MCP builds every
call as `{COMPOSER_BASE}{COMPOSER_CONTEXT_PATH}/api/...`, so set `COMPOSER_CONTEXT_PATH` to
whatever the install uses. A chart install on defaults is `/composer`; an install that set
`/discovery` (the path older bundled deployments used) stays `/discovery`.

To confirm the version and the path in one call:

```bash
curl -s https://<host><contextPath>/api/version
```

On the chart default that is `/composer/api/version`. It returned `26.3.0` on an install whose
context path was `/discovery`, at `/discovery/api/version`.

`zoomdataWeb.adminPassword` (or `zoomdataWeb.existingSecret`) is required at install.

## The opt-in `simbaIntelligence` block

Chart 1.22.0 carries Simba Agentic Intelligence as a sub-component. The `values.yaml` block is
described as "AI assistant features migrated in from the standalone Simba Intelligence chart"
and is **off by default** (`simbaIntelligence.enabled: false`). Keys in the public chart:

- `simbaIntelligence.composerPublicUrl`: the browser-reachable Composer URL. Left empty (the
  chart's recommended default), it is derived as `https://` plus the first ingress or Gateway API
  hostname plus `zoomdataWeb.contextPath`. With no hostname and no override the install still
  succeeds, `NOTES.txt` prints a warning, and SI fails later at runtime, so set one or the other.
- `.website`: the SI REST API, port 5050.
- `.mcp`: SI's own MCP server, opt-in (`.mcp.enabled`, `.mcp.baseUrl`), port 8001, always https.
- `.redis`, `.celery.worker`, `.celery.beat`.
- `.dbMigrate`: an Alembic Job.
- `.database.name: simbaintelligence`.

SI's base path is `<zoomdataWeb.contextPath>/intelligence`, so `/composer/intelligence` on chart
defaults. In the ingress, SI sits under that base path while SI's MCP (`/mcp`) and
`/.well-known` sit at the root. `GET <SI base>/api/v1/version` returned version 26.3.0, db_version
`4e6e81bb64b6`.

SI's MCP is a separate surface from this one: it answers questions as a user, while this repo
wraps the Composer authoring REST API. See `SI_26.2_NOTES.md` for that split.

## Internal PostgreSQL

The chart's internal PostgreSQL image is `postgres:18`, user `zoomdata`, with databases
`zoomdata`, `zoomdata-upload`, `zoomdata-keyset`, `zoomdata-user-auditing`, `zoomdata-qe`,
`zoomdata-config` and `simbaintelligence`.

## Standalone SI chart

`insightsoftware/simba-intelligence-chart` on Docker Hub has only `26.3.0-SNAPSHOT` for 26.3;
its latest GA tag is 26.2.1.

## What has not been checked

The 26.3 OpenAPI spec has not been diffed against 26.2. Until it is, treat the endpoint drift
table in `LIMITATIONS.md` as a 26.2.0 result.

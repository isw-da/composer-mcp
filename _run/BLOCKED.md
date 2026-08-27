# Blocked, and what it would take

## Nothing in this run was tested against a live instance

Checked at the time of writing: no Composer responds on 18080, 8080, 8082 or 8081 on
either context path, `COMPOSER_PASSWORD` is unset in the environment, and no Kubernetes
cluster answers for the `simba-intel` namespace. So every runtime claim absorbed here
carries whatever was true on the box its author tested against.

That matters more than usual for this material, because Confluence 18520178765 and
17512824891 record that `spring-security-oauth2` was removed entirely and OAuth2 plus
Trusted Access were re-implemented on Spring Security 6.x between v25 and v26. Peter's
corpus was written against a v25-era UAT host.

## Three contradictions that need a live instance to settle

**1. Custom metric write shape.** Peter documents `PUT /api/sources/{id}/custom-metrics/{name}`
with a body of exactly `label`, `expression` and `dataType`, and says `numberFormat` or
`visible` in the body cause a 400 (`Composer-Custom-Metrics-Guide.md:14`, `:40`, `:204`).
Amin's MCP does `POST` to the collection with `name`, `label`, `expression`, `visible` and
optional `numberFormat`, and no `dataType`
(`composer-mcp/src/composer_mcp/tools/sources.py:550`, corroborated by `SAFETY.md:187-188`).
Both are empirical, against different instances, and neither has been re-run.
**To settle:** create one custom metric each way against a 26.2 source and record which
returns 2xx. `CUSTOM_METRICS.md` carries both with a fallback recipe rather than a guess.

**2. Divide by zero.** Peter says division by zero returns null and Composer copes
(`:90`). Amin's `safe_div_expression()` wraps it in `CASE WHEN`. Peter documents no
`CASE WHEN` support at all, so a build matching his shape may reject the wrapper.
**To settle:** evaluate both expressions on one source.

**3. The confirmed-not-working list.** Three items at
`Logi-Composer-Symphony-Embedding-Reference.md:643-646`. The word "still" is load-bearing:
the same section retracts an earlier claim of his own at `:641`, marked "Previously
incorrect documentation". None of the three carries a date, and the only dated bench
result nearby is 2026-05-12. **To settle:** retest all three against 26.x before any of it
reaches a customer. `EMBEDDING_API.md` records them as true for a build of that vintage
rather than as current fact.

## Deliberately not absorbed, and why

Four sections of Peter's embedding reference were left, and naming them beats implying the
absorption was total:

- Section 10.4 (`:1071-1257`), the full context-menu data-fetch pattern including the
  `visualApi` key list. Amin covers `visualApi.thread.getData()` but not this path.
- Section 10.5 (`:1258-1313`), the context-menu positioning offset with its MutationObserver
  implementation. Amin has the symptom and the fix in one sentence; Peter has the code.
- Sections 11.3 and 11.4 (`:1380-1432`), complete flag tables for `settings` and
  `visualSettings`, roughly 45 keys. Amin lists about a dozen inline. **This is the largest
  remaining gap** and it was scoped out only because the brief pointed section 11 at a
  correction instead.
- Section 18 (`:2356-2669`), parameterisation across four mechanisms.

His `components.js` is also unabsorbed by design: it is code, and adopting it is a build
decision rather than an absorption.

## One fidelity note

`EMBEDDING_API.md` reproduces Peter's confirmed-not-working list with his em dash
separators replaced by colons, because the gate rejects em dashes. The wording is otherwise
verbatim. A reader comparing against his original will see that difference and it is
recorded here rather than left to surprise them.

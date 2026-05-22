# Modelling for NLQ accuracy

Field-tested patterns for getting reliable answers out of the Simba Intelligence
NLQ agent (the data-to-AI / query-agent layer), learned the hard way on a
competitive proof-of-value. Anonymised; no customer data.

## The one principle everything follows from

**The agent is deterministic when it picks a pre-computed answer, and
non-deterministic when it has to compose a query.** Every reliable result we got
was a single named metric or a value read off a small table. Every flaky or wrong
result was the agent building its own SQL: choosing COUNT vs SUM, filtering a
date, joining, or doing set logic. So the modelling job is to remove the agent's
degrees of freedom: make it select, not compose.

This held even on a high-quality backing model (gemini-2.5-flash). It is not a
weak-model artefact; it is intrinsic to one-shot LLM query generation.

## Patterns that worked (in priority order)

1. **One fact entity per source.** Co-locating two fact grains (e.g. a monthly
   and an all-time table) makes the agent cross-join them and inflate totals
   (seen: x2, and x24 against a second fact). Split each grain into its own
   single-fact source. Conformed 1:1 dimensions do not fan out and are fine.

2. **Named custom metrics for every canonical question.** Define the business's
   KPIs and common counts as metrics ("Total X", "Active Branches",
   "Number of Visits"). The agent reliably matches a question to a metric label
   and reads the precomputed aggregate. This is standard semantic-layer practice
   and it is the single biggest reliability lever after source structure.

3. **Single-entity sources for attribute counts.** A multi-entity source (hub +
   dims) corrupts plain counts: "total number of branches" returned 0 / ~160 /
   1000 across runs because the agent counted over a joined, sampled row set. The
   same question on a single-entity source with a `count(*)` metric returns the
   right number every time.

4. **Expose periods as natural-language text, not dates.** A TIME-typed period
   field triggers a default "last complete period" filter that the question
   cannot override (a documented date-handling behaviour; persists even with the
   global time bar off). Store the period as the text the user says, e.g.
   `to_char(month, 'FMMonth YYYY')` -> "April 2026". The agent then filters by
   plain string equality with no date conversion, which fixed specific-month and
   year-on-year questions outright.

5. **Pre-aggregate to the question's grain in a tiny source** for counts and set
   logic. "How many visits in April" against a 24k-row table samples (~8k cap)
   and undercounts; against a 24-row month-level table it is exact. Rank-change /
   "how many changed between two months" is set logic the metric syntax cannot
   express, so materialise it: one row per period-pair with the count, then the
   agent filters and reads it.

6. **Hide raw measures behind metrics, but per-source only.** On a count/status
   source, hiding the raw fields forces the agent to use the metric (good). On a
   fact source, hiding the summed field BREAKS the sum-metric (the agent then
   falls back to counting rows and returns nonsense). So apply field-hiding only
   to single-entity count sources, never globally.

7. **Best-of-N voting at the call layer.** Many "failures" are the host dropping
   the SSE stream (503 / IncompleteRead) or one-off variance. Calling N times and
   taking the majority converts mostly-right into reliably-right, with no model
   change. It cannot rescue a consistently-wrong answer (see drawbacks).

## The retrieval cap

The agent counts by retrieving rows (capped around 8,000) and counting them, so
`COUNT(*)` over a larger entity undercounts proportionally. `SUM(measure)` is
pushed down to SQL and stays exact at any size. Practical rule: turn every
"how many" into `SUM` of a count measure, or pre-aggregate so the filtered subset
is small.

## Routing and governance

- **`sourceId` is advisory.** The agent ranges across all sources and will defect
  to a foreign source whose field names match the question better. On a shared
  tenant this silently returns another project's data (we saw SaaS industries
  answer a finance question). Use a dedicated tenant holding only the customer's
  sources; tenant-wide rules do NOT reliably constrain source selection.
- **Tenant rules are weak and double-edged.** A synonym-mapping rule fixed the
  target phrasing but destabilised an unrelated count. Prefer structure and
  metrics over rules.

## Drawbacks (be honest about these)

- Pre-aggregation and minimal sources **overfit to anticipated grains**. A
  question at a grain you did not build for falls back to composition and fails.
- Minimal/single-fact sources **lose cross-dimensional slicing** (a perf source
  stripped of the industry dimension cannot answer "value by industry").
- It can look like teaching to the test. The defensible version is a clean
  dimensional model (conformed dims + defined metrics) the agent slices over, not
  one bespoke table per question.
- The long tail (arbitrary phrasing/grain, arithmetic) is **not** solvable in the
  semantic layer. It needs a stronger backing model and a verify-and-retry loop
  (the MCP-client / agentic layer). No semantic trick fixes a non-deterministic
  composer.

## Model choice

- gemini-2.5-flash: fast, but non-deterministic one-shot (the above is mandatory).
- A Claude / GPT-class model: materially more reliable on composed queries, but
  slower. Until per-purpose LLM routing exists, that is the speed/accuracy
  trade-off. BYOLLM, so swap per environment.

## Absolute-gate playbook (pass/fail criteria)

To clear the gates a serious evaluation uses:
- **Simple lookups >=90%**: single-entity sources + a metric per canonical
  count/total. Got this to 5/5 stable.
- **No fabrication / honest refusal**: tenant rules that refuse undefined metrics
  and out-of-window dates, plus "do not synthesise a metric from other fields",
  plus a dedicated tenant so it cannot borrow a foreign field. Got this to 7/7.
- **No unauthorised access (incl. summary)**: verify on the exact build, the query
  agent has not always enforced column-level security, and row rules can differ
  between summary and raw API output. Do not assume; test bounded roles directly.

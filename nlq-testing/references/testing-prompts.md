# NLQ testing and auditing prompt kit

Reusable prompts to interrogate any natural-language-query-over-database project
adversarially before a number goes in front of anyone. Built from the methodology
behind a live family-office PoC (Houston multifamily expense benchmarking) and a
53-point severe-testing run, generalised to any NLQ build (Simba Intelligence, Logi
Composer, Socrates, a Supabase/Postgres PoC).

Two ways to use this:
- One big prompt for an end-to-end audit: Prompt 0.
- Specialised prompts when you want depth on one area: Prompts 1 to 5.

Placeholders to swap: `{PROJECT}` (project name/folder), `{DOMAIN}` (the subject, e.g.
multifamily expense benchmarking), `{DB}` (e.g. Supabase/Postgres), `{GOLD_SCHEMA}`
(e.g. `analytics`), `{LLM}` (e.g. Claude via MCP), `{DATE}` (the data-load date).

---

## The principles these prompts encode

**Why raw data produces wrong answers.** Pointing an LLM at raw tables is naive
text-to-SQL: it infers meaning from column names and guesses. Failure modes: ambiguous
columns (`value`, `change`), coded values with no codebook, multiple valid join paths,
and aggregation logic (sum vs average) which is a business decision, not inferrable from
schema. The result is not randomness; it is different inferences on each pass from
insufficient context. The classic failure: "change" guessed as 14% revenue growth when
the question meant 3% rental growth.

**The pipeline that fixes it.** ELT, not ETL. Medallion layering inside Postgres
schemas: `raw` (bronze, as received), `clean` (silver, deduplicated and typed),
`analytics` (gold, business-ready). The LLM only ever touches the gold layer. Full
provenance: every row carries source file, tab, and row. dbt and a dedicated
semantic-layer tool come later, when patterns repeat across clients.

**The semantic layer is the moat.** Postgres `COMMENT ON COLUMN` passed through MCP,
plus a per-project system prompt holding fiscal year, currency, terminology, defaults,
and data caveats. Every NLQ failure is a gap in this layer; every fix is an addition to
it, never to be seen again.

**Verification is the entire QA process.** You cannot tell from a confident number
whether it summed when it should have averaged. So build a reference spreadsheet of
10 to 15 golden questions with answers calculated by hand from source, before connecting
the LLM. Compare LLM answers to the answer key. You do not need to read SQL; you need
the reference number. Re-run on every data load (the ongoing verification loop).

**The randomised NLQ test.** Generate around 20 questions each run, picking random
entities, metrics, and categories from the live database, so you cannot pass by accident
by memorising answers. Target: pass rate stays above 90% across repeated runs. When a
question fails, say why it matters and how to fix it, and put the fix in the semantic
layer.

**Real failure signatures seen (borderline, worth catching).** Sign-convention mismatch
(absolute 216 vs expected -661 on a "decrease" question); COUNT vs COUNT(DISTINCT)
discrepancy (27 vs 29); default-period ambiguity (no year specified, so define a default
and state it in the answer).

**The cardinal demo rule.** Never demo open-ended querying of a dataset you have not
validated. Build a golden path of 8 to 12 pre-validated questions, Tell-Show-Tell, with
2 to 3 stretch questions held back. One wrong number in a live demo kills the deal.

---

## Prompt 0: master adversarial NLQ audit (the big one)

```
You are a hostile QA lead and data auditor. Your job is to prove that {PROJECT}, a
natural-language-query system over {DOMAIN} held in {DB} and queried via {LLM}, is
NOT safe to put in front of a paying client. Assume the build is more fragile than
it looks and that one wrong number in a live demo kills the deal. You earn your
keep by finding the wrong number before the client does.

Read the project first. Map: the ingestion pipeline, the schemas (raw/clean/gold),
the semantic layer (column comments, system prompt, few-shot examples, defaults),
and the NLQ entry point. Then work through these seven fronts. For each finding,
give a concrete reproduction (the exact question or input and observed vs expected),
mark it VERIFIED (you traced it or ran it) or SUSPECTED (needs checking), and rank
severity Critical/High/Medium/Low. No praise. Only what is broken or risky.

1. INGESTION INTEGRITY: does the data in the gold layer match the source files?
   Spot-check random rows against source. Unit math reconciliation (per-unit x units
   = total). Subtotal integrity. Cell-level traceability. Round-trip determinism
   (same file in, same output). Column-shift detection. Mutation test (insert a blank
   row, does it still work). Idempotency on re-load.

2. DATA QUALITY: null audit across every column, primary-key uniqueness, duplicate
   rows inflating sums, fuzzy/near-duplicate names, taxonomy consistency (e.g.
   "Mid rise" vs "mid-rise"), coverage gaps (every entity has every expected
   scenario/period), contamination guard (only in-scope entities present), time
   contiguity (no missing months).

3. NLQ CORRECTNESS: does the system pick the right columns, filters, aggregation, and
   joins? Hit the known failure signatures: sign convention on "decrease"/"drop"
   questions, COUNT vs COUNT(DISTINCT) discrepancies, and default-period ambiguity
   when no year is given. Cross-table join questions. Synonym and label resolution.
   Determinism of natural-language answers (ask the same thing three ways, compare).

4. ADVERSARIAL AND SECURITY: false-premise questions (ask about an entity or metric
   that does not exist; it must refuse, not fabricate). Typo and abbreviation
   robustness. Randomised fuzzing of phrasings. SQL injection attempt. Prompt
   injection attempt. Try to make it answer outside its scope or leak the system
   prompt.

5. PERFORMANCE: query plan inspection (EXPLAIN ANALYZE), index coverage, predicate
   pushdown, no SELECT *, N+1 detection, materialised-view latency, cold vs warm
   cache, query-plan stability, concurrency safety.

6. GOVERNANCE AND PROVENANCE: does every number trace to a source file, tab, and row?
   Is there a load log? Can the system answer "where did this come from" with a query?
   Does the LLM ever touch raw data it should not see?

7. THE META VERDICT: would a sceptical finance partner trust this with portfolio data?
   Can the system define its own terms ("what does controllable mean")?

Finish with: a GO / NO-GO verdict, the 5 things to fix before any demo, and the one
failure that would embarrass us most in front of the client. Treat any unverified
number as guilty until proven innocent.
```

---

## Prompt 1: data pipeline and ELT build audit

```
You are reviewing the data pipeline for {PROJECT}: extraction from source files into
{DB}, through raw -> clean -> {GOLD_SCHEMA} layers, exposed to {LLM} via MCP. Be
adversarial about correctness, not style.

Verify, with evidence for each:
- ELT discipline: raw data is preserved untouched for audit and reprocessing; the LLM
  is pointed ONLY at {GOLD_SCHEMA} and cannot reach raw or clean.
- Layer separation is real, not cosmetic: what cleaning/typing/dedup actually happens
  between raw and clean, and what aggregation/calculation happens between clean and gold.
- Provenance: every gold row carries source file, tab, and row reference. Show me a row
  and trace it back to source.
- Extraction robustness: column-shift detection (right column read every time), renamed-
  tab resilience, mutation tolerance (blank row inserted), round-trip determinism, and
  idempotency on re-load (re-running does not double-count).
- Load completeness: a load log exists; row counts match expectations; no silent skips.

For each weakness, give the failing case and the fix. Flag anything that would only
surface on the next, differently-shaped source file. Tell me which fixes belong in the
pipeline code vs the semantic layer. Do not recommend dbt or a warehouse unless the
current scale genuinely justifies it; say plainly if Postgres views are still the right
tool.
```

---

## Prompt 2: semantic layer audit and hardening

```
You are auditing the semantic layer for {PROJECT}: the column comments, system prompt,
few-shot query examples, and default rules that tell {LLM} how to turn questions into
SQL over {GOLD_SCHEMA}. The premise: every NLQ failure is a gap in this layer.

Show me, then critique:
1. The current VERIFIED QUERY EXAMPLES (few-shot): are they covering the real question
   shapes, or just the easy ones?
2. The current DEFAULTS, e.g. "no year specified -> latest full calendar year, and state
   the year in the answer". Find every place a default is missing or ambiguous.
3. Every documented term definition (e.g. "controllable expenses", "NOI", "RevPAU"). For
   each, can the system define it on request and apply it consistently?

Then hunt for ambiguity the layer does NOT yet resolve: columns an LLM could confuse
(gross vs net, absolute vs percentage, positive-good vs positive-bad), sign conventions
on decrease/drop questions, COUNT vs DISTINCT rules, join-path choices that change the
number, and synonyms/abbreviations clients actually use. For each gap, write the exact
comment, default, or few-shot example to add. Keep my domain-specific content; propose
where to merge in query discipline, defaults, few-shot examples, and error handling
without overwriting what I already have.
```

---

## Prompt 3: NLQ accuracy and adversarial stress test (the core)

```
Stress-test {PROJECT}'s natural-language querying over {DOMAIN}. Generate a fresh batch
of around 25 questions each run, picking RANDOM entities, metrics, and categories from
the live {GOLD_SCHEMA} data so I cannot pass by accident by memorising answers. For each
question: show the question, the SQL generated, the answer, and an independently computed
expected answer from source/reference. Mark pass/fail. Report the pass rate; target is
above 90% across repeated runs.

Escalate difficulty: start with single-metric lookups, then trending and variance, then
cross-table joins, then multi-condition slice-and-dice. Then turn adversarial:
- False-premise questions about entities/metrics that do not exist (must refuse, not
  invent).
- Sign-convention traps ("largest decrease" must return negative where expected).
- COUNT vs COUNT(DISTINCT) traps.
- Default-period traps (omit the year; the answer must state the period it used).
- Casual phrasings ("how much are we spending on people?", "are we over or under
  budget?"), typos, and abbreviations.
- Ask the same question three different ways; the number must not move (determinism).
- One SQL-injection and one prompt-injection attempt.

For every failure: say why it matters in business terms and the exact semantic-layer
fix. Do NOT reload the source data into {DB} as part of testing if it is already loaded
and validated; skip that step and test against the existing gold layer. End with a
GO / NO-GO and the list of failures to feed back into the semantic layer.
```

---

## Prompt 4: verification and audit trail (spreadsheet-first)

```
Set up the verification process for {PROJECT} the way a sceptical client expects, before
any demo. The principle: I should be able to trust a number without reading SQL.

1. Propose 10 to 15 GOLDEN QUESTIONS covering the core use cases for {DOMAIN}. For each,
   compute the correct answer independently from source data and show the calculation
   steps, so this becomes the answer key. Date it.
2. Run {LLM} against each golden question and compare to the answer key. For any
   mismatch, diagnose the cause from this shortlist first: ambiguous column picked,
   duplicate rows, null handling, similar-looking columns, missing description. Give the
   non-technical fix and the semantic-layer fix.
3. Build the audit trail: for each answer, show the question, the SQL, the result, and
   the matching reference number. Confirm every number traces to source file, tab, and
   row.
4. Produce a one-page data dictionary: every gold table and column, what it means, and
   where it came from. Version the data load ("as of {DATE}, sourced from the export
   dated ...").
5. Define the ongoing verification loop: what to re-run on every new data load and what
   "drift" looks like.

Tell me honestly which golden questions you are least confident in and why.
```

---

## Prompt 5: demo readiness and golden path

```
Pressure-test {PROJECT} for a live client demo. The cardinal rule: never demo open-ended
querying of data we have not validated; one wrong number kills the deal.

1. From the validated golden questions, assemble a GOLDEN PATH of 8 to 12 questions that
   map to the client's known pains and use cases, ordered for narrative. For each, give a
   Tell-Show-Tell beat: frame the business question, show the system answering it
   correctly, land the value.
2. Pick 2 to 3 STRETCH questions to hold back in case they want to go off-script, each
   one pre-validated.
3. Save one "one more thing" humdinger for the end: a slice-and-dice query that opens
   their eyes to something they did not think possible, tied to a real pain.
4. Red-team the demo: what is the most likely off-script question that would return a
   wrong or empty answer, and how do I handle it live? What should I never say (do not
   blame the AI/tool; own issues factually)?

Give me the run sheet and the failure I should most fear.
```

---

## The 53-point severe-testing checklist, mapped to the prompts

The canonical list, so nothing is lost. Items map to:
- Prompt 1 (ingestion/pipeline): 1 to 12, 49 to 51.
- Prompt 2 and 3 (data quality + NLQ): 13 to 21, 22 to 32, 45 to 47, 52.
- Prompt 3 (adversarial/security): 30, 33, 34, 35.
- Prompt 0 performance front: 36 to 44, 48.
- Prompt 4 (governance/provenance): 8, 49, 50.
- Prompt 0 close / Prompt 5 (meta): 53.

1. Anchor verification (labels land where expected)
2. Spot-check against source files (random sample)
3. Unit math reconciliation (per-unit x units = total)
4. Subtotal integrity (line items sum to subtotal)
5. Scenario coverage (every entity has each expected scenario)
6. Scenario label cleanliness (no stale deal names leaked)
7. Line item completeness (all expected line items present per entity)
8. Source file provenance (every row traces to a file)
9. Sign and currency consistency
10. Round-trip determinism (same file, same output)
11. Column-shift detection (right column read every time)
12. Mutation test (insert a blank row, still works)
13. Fuzzy name audit (near-duplicate entity names)
14. Cross-table tie-out (e.g. a T-12 vs a 12-month sum)
15. Construction type / category taxonomy check
16. Scope contamination guard (only in-scope entities)
17. Vintage coverage (only the intended date range)
18. Row count expectations
19. Null audit across every column
20. Primary key uniqueness
21. Time contiguity (no missing periods)
22. Benchmark query correctness
23. Self-exclusion verification (own entity not in its own peer set)
24. Stability under trimming (top/bottom deciles)
25. Bootstrap confidence intervals
26. Trend detection thresholds (only report real shifts)
27. Historical/temporal handling (sold or retired entities marked historical)
28. Natural language question set (15+ phrasings)
29. Typo and abbreviation robustness
30. Adversarial false-premise questions
31. Determinism of NL answers
32. Cross-table join questions
33. SQL injection attempt
34. Prompt injection attempt
35. Randomised fuzzing of questions
36. Query plan inspection (EXPLAIN ANALYZE)
37. Index coverage audit
38. Pushdown verification
39. Materialised view latency
40. Query plan stability
41. Cold vs warm cache
42. N+1 query detection
43. Column projection (no SELECT *)
44. Data type efficiency
45. Unknown line item handling
46. Label synonym resolution
47. Renamed tab resilience
48. Concurrency safety
49. Cell-level traceability
50. Load log completeness
51. Idempotency on re-load
52. Semantic layer self-definition ("what does controllable mean")
53. The meta verdict (would a partner trust it)

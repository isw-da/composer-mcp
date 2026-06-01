---
name: nlq-testing
description: >
  Adversarially test and audit a natural-language-query (NLQ / text-to-SQL)
  project before a number goes in front of anyone. Use whenever the user wants to
  stress-test, QA, audit, pressure-test, or "trip up" an NLQ-over-database build,
  its semantic layer, its data pipeline, or its demo. Trigger on phrases like
  "test my work", "stress test the NLQ", "run severe testing", "interrogate this
  project", "audit the semantic layer", "is this demo-ready", "verify the numbers
  match the source", "find where it breaks", "golden questions", "go or no-go", or
  "adversarial QA on my data project". Covers Simba Intelligence, Logi Composer,
  Socrates, Supabase/Postgres NLQ builds, and client PoCs. Provides one master
  end-to-end audit plus five specialised prompts: ingestion integrity, semantic-layer
  hardening, NLQ accuracy and adversarial stress testing, verification and audit
  trail, and demo readiness. Do NOT use for auditing an LLM eval suite or running a
  model/parameter sweep (use eval-audit-and-sweep), nor for generic code review.
---

<!-- Skill version: 2026-06-01 -->
<!-- Canonical source of truth: https://github.com/isw-da/simba-intelligence-skill (nlq-testing/) -->

# NLQ testing and auditing

This skill turns any natural-language-query-over-database project into something a
sceptical finance partner would trust. The premise, learned the hard way on a live
demo: you cannot tell from a confident number whether the system summed when it
should have averaged. So verification is the entire QA process, not an afterthought.
Treat every unverified number as guilty until proven innocent.

## When to reach for this

Reach for it whenever the user is about to put an NLQ answer in front of a client, or
wants to know where their build breaks. The output is always the same shape: concrete
reproductions, a VERIFIED/SUSPECTED tag on each finding, a severity rank, and a
go/no-go verdict. No praise, only what is broken or risky.

## How to use this skill

1. **Identify the target.** Establish what is being tested before writing a single
   query: the project name and folder, the domain, the database (Supabase/Postgres
   or other), the gold schema the LLM is pointed at, and how questions reach the
   model (MCP, app, API). Do not start testing until the grain and the source of
   truth are explicit.

2. **Pick the prompt(s).** Read `references/testing-prompts.md` and choose:
   - Whole-system audit before a demo: **Prompt 0** (the master).
   - Just one front: **Prompt 1** pipeline/ingestion, **Prompt 2** semantic layer,
     **Prompt 3** NLQ accuracy and adversarial, **Prompt 4** verification and audit
     trail, **Prompt 5** demo readiness.

3. **Fill the placeholders** (`{PROJECT}`, `{DOMAIN}`, `{DB}`, `{GOLD_SCHEMA}`,
   `{LLM}`, `{DATE}`) from step 1, then run the prompt against the project.

4. **Demand an independent expected answer for every NLQ question.** This is the
   single load-bearing rule. Without a reference number computed from source, an
   adversarial pass invents plausible failures that do not exist. A pass rate only
   means something when checked against an answer key.

5. **Feed every failure back into the semantic layer.** Each NLQ failure is a gap in
   the semantic layer (column comments, defaults, few-shot examples, error handling).
   Each fix is an addition to it, never to be seen again. Log what was added.

6. **Skip the reload if data is already validated.** The full pipeline test will, by
   default, reload source data into the database. If the load is already validated,
   instruct the run to test against the existing gold layer instead; it takes a while.

## The seven fronts (what a full audit covers)

Ingestion integrity, data quality, NLQ correctness, adversarial and security,
performance, governance and provenance, and the meta verdict (would a partner trust
it). The 53-point severe-testing checklist behind these lives in
`references/testing-prompts.md`, with a map showing which prompt covers which items.

## Known failure signatures to always probe

- Sign convention: a "largest decrease" question that returns positive absolute values.
- COUNT vs COUNT(DISTINCT): a count that is off by a handful because of duplicates or
  an extra filter.
- Default-period ambiguity: no year given, so the answer must state the period it used.
- False premise: a question about an entity or metric that does not exist must refuse,
  not fabricate.

## Guardrails

- Keep client specifics out of any committed copy. The prompts use generic placeholders
  on purpose. Do not bake in a client's asset names, figures, or engagement detail.
- The LLM must only ever touch the gold layer. If a test can reach raw or clean data,
  that is itself a Critical finding.
- Never recommend dbt, a warehouse, or a dedicated semantic-layer tool unless the
  current scale genuinely justifies it. Say plainly when Postgres views are still right.

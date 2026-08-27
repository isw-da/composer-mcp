# Disclosure tier crossed with truth grade

Provenance: absorbed from Peter Armstrong's material, 27 August 2026, from
`/Users/aminhasan/logi-composer/peter-kb/delivered-2026-08-27/Prospect-Requirement-Responses-PLAYBOOK.md`
(146 lines), with counts taken from the document it governs,
`/Users/aminhasan/logi-composer/peter-kb/delivered-2026-08-27/Prospect-Requirement-Responses.md`.

## Citation shorthand

| Shorthand | File |
|---|---|
| `Playbook :N` | the playbook path above, line N |
| `Peter :N` | `Prospect-Requirement-Responses.md`, line N |
| `sources :N` | `/Users/aminhasan/logi-composer/composer-vs-legacy/sources.md` (78 lines), line N |
| `cvl-readme :N` | `/Users/aminhasan/logi-composer/composer-vs-legacy/README.md`, line N |

## Peter's axis: who may see it

Every source bullet in his 26 answers carries one glyph. The definitions are at
`Playbook :55` to `:57`.

| Glyph | Tier | Rule |
|---|---|---|
| 🌐 | public | official documentation and insightsoftware.com. Safe to quote to a customer verbatim. |
| 🔒 | internal | Jira, Confluence, SharePoint and GRC, local toolkits, internal tool and vendor names. Never quoted outward. Used only to keep the answer honest. |
| 🤝 | **NDA** | SOC 2 Type 2 reports, penetration-test summaries, the VPAT. Customer-facing, but released through the account or security team under **NDA**. |

Measured usage across the document: 83 public, 66 internal, 2 **NDA**.

The 66 internal bullets are doing real work. They are what stops an answer
overclaiming, for example the still-open bundle-optimisation work behind the
"minimal footprint" answer (`Peter :153`) and the open keyboard and focus
defects behind the accessibility answer (`Peter :236`). `Playbook :60` states
the operating rule: prefer public for anything the prospect reads, back it with
internal evidence for honesty, keep the internal evidence internal.

## Two flaws in that scheme, to fix rather than inherit

**The NDA tier is invisible where it is used.** It is defined only in the
playbook. The main document declares its legend three times, at `Peter :11`,
`Peter :18` and `Peter :53`, and all three name two tiers. Yet the glyph appears
twice in the body, at `Peter :1086` and `Peter :1135`, both as `🔒→🤝`, meaning
an internal artefact promoted to NDA-shareable. A reader working from the
document alone meets a glyph with no definition, on exactly the two bullets
where getting the handling wrong matters most, because both are the SOC 2 Type 2
report. Whichever legend a reader trusts, it is wrong.

The fix is mechanical. Any file that uses the tiers declares all three, in the
file, and the promotion arrow is spelled out rather than left as notation.

**The scheme is honour-system.** A glyph is a note to a careful reader. Nothing
stops an internal-tier fact being paraphrased into a customer-facing paragraph,
and paraphrase is exactly how internal material escapes: the ticket number gets
dropped and the finding it carried survives. `Peter :944` names the failure mode
without solving it, warning that internal security tool and vendor names must
be presented as capabilities rather than named. That instruction depends
entirely on whoever writes the next draft remembering it.

## The other axis: is it true

`sources.md` in `composer-vs-legacy` grades something different. Its markers
are defined at `cvl-readme :22` to `:27`.

| Marker | Grade | Meaning |
|---|---|---|
| **[G]** | grounded | a named source positively supports the claim |
| **[P]** | partial | a source supports one half, the other half rests on absence of evidence |
| **[U]** | unverified | reasoning from architecture, no direct source. Do not put in front of a customer without checking with product |

Those definitions are written comparatively, because that document compares
Composer against Exago and Izenda, so the "other half" is the competitor side.
Generalised for a knowledge base, drop the competitor half: **[G]** is
positively sourced, **[P]** is sourced on the claim but not on its limit, and
**[U]** is inference.

Two features of that file are worth importing wholesale.

**The corrections table comes first.** `sources :10` to `:22` lists eleven
claims that two adversarial passes refuted or downgraded, each with the source
that was misread and what went wrong. `sources :8` instructs the reader to read
the corrections before trusting any citation below them. That ordering is the
right default.

**The systemic finding is stated as a systemic finding.** `sources :24` to `:26`
records that almost every Exago claim traced back to a single page last modified
21 May 2024, written for a different purpose. `cvl-readme :30` adds the harder
point: eight claims were refuted, seven of the eight refutations flattered the
original draft. A grade that only ever moves in the flattering direction is
evidence of a process fault, not a run of bad luck.

## Why both axes, and the combined scheme

They answer different questions and neither implies the other. A fact can be
public and unverified: an insightsoftware marketing page saying Composer embeds
natively rather than through iframes is fully quotable and grounds nothing about
what the SDK does. A fact can be internal and grounded: an open ticket
establishes a limitation beyond doubt and can never be shown to a customer. A
knowledge base meant for customer reuse needs to answer both questions before
anyone pastes anything anywhere.

Tag every source bullet with a tier and a grade, written together, for example
`🌐 [P]` or `🔒 [G]`.

| | **[G]** grounded | **[P]** partial | **[U]** unverified |
|---|---|---|---|
| **🌐 public** | Quote it. This is the load-bearing cell and the only one that can carry a written commitment on its own. | Quote the supported half only. State the limit as unconfirmed rather than letting the sentence imply it. Peter's WCAG 2.0 answer sits here. | Do not quote. A public source that is merely consistent with the claim is not evidence for it. Send it to product before it goes anywhere. |
| **🔒 internal** | Believe it, act on it, never write it outward. This is where the honest caveats come from. Convert to a capability statement with no ticket, no tool name, no URL. | Believe it provisionally. Say the caveat is provisional when you convert it. Do not let a provisional internal finding harden into a customer-facing absolute. | Delete or re-source. An internal guess is the lowest-value cell in the table and the easiest to mistake for knowledge later. |
| **🤝 NDA** | Do not paraphrase it into a public answer. Name the artefact and route the request, for example "the SOC 2 Type 2 report evidences an annual independent penetration test, available under **NDA** through the security team". The prospect gets the document; the answer gets a pointer. | As above, and additionally say what the artefact does not cover. Peter's VPAT scoping note at `Peter :237`, that the VPAT covers embedded viewing and not authoring, is the model. | Should not exist. If an **NDA** artefact does not actually establish the claim, the claim has no evidence and the **NDA** tag is decoration. |

Two rules that fall out of the table and are worth stating on their own.

The grade governs whether a claim survives; the tier governs where it can be
written. Resolve the grade first. There is no point deciding how to disclose
something that is not established.

A cell is a routing decision, not a warning label. Every cell above says what to
do with the bullet, because a tag that only expresses caution gets ignored under
deadline.

## Wiring the internal tier to a mechanical gate

The internal tier is the one flaw that can be fixed by a machine rather than by
discipline, and this workspace already has the machine.
`/Users/aminhasan/claude-ai-projects/si-content-pipeline/sanitiser/sanitise.py`
runs in two modes. `sanitise.py <file>` rewrites, `sanitise.py --check <file>`
exits 1 if anything internal remains. The si-content-pipeline skill already
makes the check mandatory before anything leaves the boundary
(`~/.claude/skills/si-content-pipeline/SKILL.md:13`).

What it catches, from its own source: Jira issue keys by pattern, with
structurally identical technical tokens such as SHA-256 and ISO-8601
allowlisted; email addresses; any URL on atlassian.net; and a named replacement
list in `redactions.json` beside it. The docstring notes the output is
idempotent, so sanitising twice gives the same text.

**How to wire the tier to it.** Treat the 🔒 glyph as an assertion that the
bullet will not survive `--check`, and the 🌐 and 🤝 glyphs as an assertion that
it will. Then the tagging becomes testable rather than declarative:

1. Any file intended for reuse outside the boundary gets `sanitise.py --check`
   as a gate condition, alongside the existing checks in
   `/Users/aminhasan/composer-mcp-parity/_run/verify-parity.sh`.
2. A 🔒 bullet that passes `--check` is either mis-tagged or has already been
   converted to a capability statement. Both cases need a human decision, so
   surface it rather than passing silently.
3. A 🌐 or 🤝 bullet that fails `--check` is a leak. That is the case the gate
   exists for, and it should fail the run.

**What the gate cannot do.** It matches tokens. It cannot tell that a sentence
carries an internal finding once the ticket number is stripped, which is the
paraphrase route described above and the most likely way internal material
actually escapes. Peter's own instruction at `Peter :944` is aimed exactly at
that route and remains a human judgement. So the gate is a floor, not a
substitute for the glyph. It catches the mechanical leak and leaves the semantic
one to review.

State that limit whenever the gate is cited as evidence of safety. A green
`--check` means no internal token survived, and nothing more.

**One false positive to expect, verified.** Running `--check` against
`SECURITY_ANSWERS.md` in this directory reports two `jira_key` hits. Both are
the AES key-length token, the letters `AES` joined by a hyphen to `256`, which
matches the issue-key pattern exactly. `SHA-256` and `ISO-8601` are on the
allowlist inside the script; the AES token is not. The script's own comment says
it errs towards a false alarm rather than a leak, so this is intended behaviour
rather than a bug, but anyone gating a security document on `--check` will hit
it on the first run. Either add the token to the allowlist or record the
expected hit count for the file. Do not resolve it by removing the gate. This
file avoids writing the token literally so that it passes its own check.

## Applying this to the two NDA bullets

Both sit in `SECURITY_ANSWERS.md`, at Requirement 24 and Requirement 25. The
handling that follows from the table:

- Do not reproduce the control identifier, the quoted control text, or the
  internal document path from `Peter :1086`.
- Do state the substance, that an independent third-party penetration test is
  performed annually and the external auditor inspected the most recent results,
  and attribute it to a SOC 2 Type 2 control available under **NDA**.
- Do carry the scoping caveat at `Peter :1076`: insightsoftware publishes several
  product-scoped SOC 2 reports and the one covering Composer must be confirmed
  before it is cited as the product's attestation. An **NDA** artefact cited
  against the wrong scope is worse than no artefact, because it looks like
  evidence.
- Do not name the pen-test methodology. `Peter :1071` establishes that the
  control text confirms annual and third-party but does not name the tester's
  framework. Naming OWASP WSTG or PTES from memory would be a **[U]** claim
  wearing an **NDA** artefact's credibility.

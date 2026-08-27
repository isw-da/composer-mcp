# Progress: absorbing to parity and past it

## Shape

A real graph. Eight absorption targets, none reading another's output, each writing exactly
one new file, so there is no merge to resolve and no race to lose. Piloted one node (P2,
chatbot events) end to end and read its output before spawning the rest.

## Why new files rather than edits

Two constraints pointed the same way. `composer-mcp` is currently held by another session
with uncommitted work in `README.md`, `SCHEMA_NOTES.md`, `THEMES.md` and `tools/themes.py`
from the theme-palette fix, so editing those would race. And absorption into a new topic
file keeps the provenance visible: each file opens by naming Peter's source path and date,
so when his material moves the drift is findable rather than silently baked in.

## Gate

`_run/verify-parity.sh`, 16 capability rows in `parity.tsv`. Each row checks two things:
the target file carries the marker that defines the capability, and the source in Peter's
bundle that justified it still resolves. The marker check is content-level on purpose, so
an empty file or a deleted section goes red where `touch` would otherwise satisfy it.

Baseline before any work:

```
$ ./_run/verify-parity.sh; echo $?
PARITY FAILED: 16 of 16 checks
1
```

The gate starts red on every row, which is the only honest starting state for a run whose
whole claim is that something was added.

## What the pilot found

The chatbot node returned the kind of thing that justifies reading a pilot rather than
trusting a fan-out. Fourteen of the fifteen chatbot events use a `composer-chat-` prefix
and the fifteenth uses `composer-bot-`, so any listener built by concatenating onto the
common stem drops suggestion failures silently. It also resolved the destroy-on-close
question correctly: the conflict is inside Peter's own material, between his chatbot guide
at :323-331 and his Stitch guide at :1815, :1845 and :1871, rather than between the two
knowledge bases. It reconciled the two by scoping `destroy()` to genuine teardown instead
of discarding one side.

## Standing risk

Every file here is written from Peter's documentation and from Confluence, not from a live
instance. Nothing in this run was executed against a running Composer. Claims about
runtime behaviour therefore inherit whatever was true on the box Peter tested against,
which was a UAT host on a v25-era build, and the auth stack was rebuilt underneath between
v25 and v26. `BEYOND_PARITY.md` carries that warning; it belongs here too.

# SPEC: absorb what Peter's knowledge base has and mine lacks

## The mission, expanded

"Absorb anything mine is lacking to get to parity, if not better." Terse, so this spec
defines done from the verified comparison in
`/Users/aminhasan/logi-composer-peterkb/peter-comparison/COMPARISON.md`, which survived an
adversarial pass that refuted eight rows of an earlier draft.

Parity means: for every capability that comparison confirms Peter has and this side lacks,
this side now has an equivalent, and a search proves it. Exceeding parity means also
absorbing what the comparison found **neither** side had, which is sitting in Confluence.

## What absorption is, and is not

Not copying his files. They are internal insightsoftware material written against a UAT
host, and a copy starts drifting the moment he edits his. Absorption means writing a
distilled reference in this repo's house style, citing his file and line as the source, so
the claim is traceable and the drift is visible.

Not editing files another session is holding either. `composer-mcp` currently has
uncommitted work in `README.md`, `SCHEMA_NOTES.md`, `THEMES.md` and `tools/themes.py` from
the theme-palette fix. Every absorption target here is a NEW file, which removes the
collision rather than making it unlikely.

## Done

`_run/verify-parity.sh` exits 0. It checks two things per capability:

1. The absorbed reference exists here and contains the specific marker the capability is
   defined by, so the check would fail if the file were emptied or the section deleted.
2. The source citation resolves: the file and line in Peter's bundle that justified it.

A capability with no marker search is not gated, and an ungated capability is exactly how
the previous run shipped eight false rows. Every row in `parity.tsv` carries its search.

## Out of scope

His `components.js` is code, not knowledge, and adopting it is a build decision rather than
an absorption. Recorded in the comparison, not actioned here.

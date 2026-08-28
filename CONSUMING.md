# Using this repo, and the others alongside it

These repositories are a shared knowledge base for insightsoftware's Logi Composer, Simba
Intelligence and Logi Report. They are maintained by Amin Hasan and anyone on the team is
welcome to clone, pin, fork or open an issue against them.

## The set

<!-- toolkit-table: generated from toolkit.json, do not edit by hand -->

| Repo | What it holds | Refresh |
|---|---|---|
| [`isw-da/logi-si-docs`](https://github.com/isw-da/logi-si-docs) | Documentation mirror: SI, Composer v25 and v26, the legacy devnet archive, and the Composer OpenAPI specs | **Automatic**, weekly |
| [`isw-da/composer-mcp`](https://github.com/isw-da/composer-mcp) | Composer REST API as MCP tools, with guards, plus the reference docs | Manual |
| [`isw-da/simba-intelligence-skill`](https://github.com/isw-da/simba-intelligence-skill) | SI install, configuration and troubleshooting skills | Manual |
| [`isw-da/symphony-dashboard-builder-skill`](https://github.com/isw-da/symphony-dashboard-builder-skill) | Building Composer dashboards server side, and the client-side assembly around them | Manual |
| [`isw-da/simba-intelligence-mcp`](https://github.com/isw-da/simba-intelligence-mcp) | SI API as MCP tools (private) | Manual |
| [`isw-da/logi-report-kb`](https://github.com/isw-da/logi-report-kb) | Logi Report and JReport documentation and API surface | **Automatic**, weekly, but only the 3,891 current articles. The 9,344-article devnet archive is frozen because that host is dead, and `api/` needs a running instance CI cannot reach |

<!-- /toolkit-table -->

## Pin a version, do not track a branch

Every repo cuts tagged releases. `main` moves, sometimes several times a day, and it moves
because something turned out to be wrong. Pin unless you want that.

```bash
git clone --branch v0.3.0 --depth 1 https://github.com/isw-da/composer-mcp.git
```

Release notes name what changed and, where it matters, what was found to be **wrong** in the
previous version. That second part is the useful one.

## How to trust what you read here

Most of these repos carry a `verify-*` script. It is not decoration: each one is proven to
fail before it is trusted, and several were written after something in this repo turned out
to be confidently wrong.

```bash
python3 verify-*.py     # or bash verify-*.sh
echo $?                 # on its own line: a pipe reports the pipe's status, not the gate's
```

If a gate is red, the documentation is wrong, not the gate. That is the whole point of
having one.

Some checks report **NOT APPLICABLE** rather than passing or failing. That means the thing
they check is real but not present in your checkout, usually because it is internal material
that is never published. A skip is always named and counted, never silent.

## What is deliberately not here

Customer names, deployed customer artefacts, NDA-tagged material, and anything derived from
unreleased internal roadmap. Where a real customer theme or dashboard is used as evidence it
appears as "deployed theme A", and the identifying copy stays in a private working tree.

If you spot something that should not be public, say so and it comes out the same day.

## Contributing

Open an issue or a pull request. Two asks:

1. **Run the gates before you open it.** If your change makes a claim, the gate should be
   the thing that proves it, and if no existing check covers your claim, add one.
2. **Say how you know.** A file and line, a command and its output, a Confluence page id or
   a Jira key. "I believe" is fine as long as it says so; the corpus already contains several
   confident claims that turned out to be wrong, and each one cost somebody a day.

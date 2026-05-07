# Agents

Subagent definitions designed to drive `composer-mcp` end-to-end. Drop them
into your Claude Code agents directory and they're available via the
`Agent` tool with `subagent_type: "<name>"`.

## bi-developer

A Principal BI Developer subagent that operates with a phase-gated workflow
(Frame → Sketch → Build → Verify → Hand-over) and refuses to write SQL
until grain, conformed dimensions, and metric definitions are explicit.
Knows how to use this MCP's tools — `composer_test_dashboard_render` for
verification, `composer_set_kpi_conditional_format` for thresholding,
`composer_generate_snapshot_dashboard` for templated starting points,
`composer_health_check` + `composer_whoami` for orientation, and so on.

Reach for it for any BI / analytics engineering / dashboarding work. Not
just Composer — the agent covers Power BI, Tableau, Looker, dbt Semantic
Layer, Sigma, Mode, ThoughtSpot, Superset and more, with the same
phase-gated rigour.

### Install

**User scope (available across every project on your machine):**

```bash
mkdir -p ~/.claude/agents
cp agents/bi-developer.md ~/.claude/agents/
```

Restart Claude Code. The agent registers at session start and is then
available to any project.

**Project scope (this codebase only):**

```bash
mkdir -p .claude/agents
cp agents/bi-developer.md .claude/agents/
```

Restart Claude Code in this project. The agent only loads when the working
directory is inside this repo.

### Use

Once installed, dispatch via the `Agent` tool:

```
Agent(
  subagent_type: "bi-developer",
  description: "Build the Q3 partner snapshot",
  prompt: "..."
)
```

Or just say "use the BI developer agent to..." in your message — Claude
will dispatch automatically.

### Customisation notes

* The agent is set to `model: opus` because the phase-gating and chain-of-
  verification rigour benefit from deeper reasoning. Change to `sonnet` in
  the YAML frontmatter if you'd rather trade rigour for speed/cost.
* The "Autonomous mode" clause in Phase 1 instructs the agent to state its
  assumption ledger explicitly when there's no human to answer questions
  mid-task, then proceed. Remove it if you want the agent to block on
  clarification instead.
* The agent inherits the parent session's tool access by default. Pin the
  `tools:` list in the YAML frontmatter if you want to lock it down to
  read-only or to specific MCPs.

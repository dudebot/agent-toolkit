# agent-toolkit

A marketplace of hooks, plugins, and MCP servers for AI coding agents — primarily Claude Code today, with cross-harness support (Codex, etc.) where the tool is universal (MCP) or the hook contract converges.

## Install the marketplace

Use the GitHub-backed marketplace for normal installs. Local path installs are only for active
development of this repository.

In Claude Code:

```
/plugin marketplace add dudebot/agent-toolkit
```

Then list and install any plugin from it:

```
/plugin
/plugin install <plugin-name>@agent-toolkit
```

Refresh after an upstream update:

```
/plugin marketplace update agent-toolkit
```

In Codex:

```
codex plugin marketplace add dudebot/agent-toolkit --ref main
codex plugin add workflow-factory@agent-toolkit
```

Refresh after an upstream update:

```
codex plugin marketplace upgrade agent-toolkit
codex plugin remove workflow-factory@agent-toolkit
codex plugin add workflow-factory@agent-toolkit
```

If you previously installed the marketplace from a local checkout, remove it before installing the
GitHub-backed source:

```
codex plugin remove workflow-factory@agent-toolkit
codex plugin marketplace remove agent-toolkit
codex plugin marketplace add dudebot/agent-toolkit --ref main
codex plugin add workflow-factory@agent-toolkit
```

Codex also supports local repo marketplaces while developing this repository:

```
codex plugin marketplace add /path/to/agent-toolkit
codex plugin add workflow-factory@agent-toolkit
```

Run Codex non-interactively with global options before the `exec` subcommand:

```
codex -a on-request exec -C /path/to/control-repo -s workspace-write -
```

## Plugins

| Plugin | What it does | Docs |
| --- | --- | --- |
| [`quota-watch`](./plugins/quota-watch/README.md) | Adaptive Claude Max quota monitor. Adds a `UserPromptSubmit` hook that silently watches your 5h quota, warns as you approach it, and instructs the model to park itself until reset when you cross the halt threshold. | [README](./plugins/quota-watch/README.md) |
| [`plan-project`](./plugins/plan-project/README.md) | Turns a settled architecture into a dispatch-ready workplan: task graph, paired test tasks, deterministic runbooks, and phase handoffs. | [README](./plugins/plan-project/README.md) |
| [`orchestrate-workplan`](./plugins/orchestrate-workplan/README.md) | Drives a workplan to completion with TodoWrite rails, runbook gates, verifier escalation, and phase validator triggers. | [README](./plugins/orchestrate-workplan/README.md) |
| [`claude-tee`](./plugins/claude-tee/README.md) | Mirrors `UserPromptSubmit` events to a local JSONL archive and optional fan-out targets. | [README](./plugins/claude-tee/README.md) |
| [`workflow-factory`](./plugins/workflow-factory/README.md) | Turns messy intent into durable, reviewable workflow prompts before execution starts. | [README](./plugins/workflow-factory/README.md) |

## Layout

```
.
├── .claude-plugin/marketplace.json
└── plugins/
    └── <plugin-name>/
        ├── .claude-plugin/plugin.json
        ├── .codex-plugin/plugin.json
        ├── hooks/          # optional: event handlers (hooks.json + scripts)
        ├── skills/         # optional: model-invoked skills (SKILL.md per folder)
        ├── agents/         # optional: custom subagents
        ├── .mcp.json       # optional: MCP server config
        └── README.md
```

Each plugin is self-contained under `plugins/<name>/`. The marketplace manifest at `.claude-plugin/marketplace.json` is what `/plugin marketplace add` reads to discover what's available.

## Cross-harness notes

- **MCP servers** are universal — they work with any harness that speaks MCP (Claude Code, Codex, Hermes, etc.).
- **Hooks**: Claude Code and Codex both have a `UserPromptSubmit` lifecycle hook with a similar JSON-on-stdin contract. Most hook scripts here aim to be harness-agnostic; where stdin payload differs, the script detects and adapts. Provider-specific tools (like quota-watch, which only talks to Anthropic's usage endpoint) are still useful to Claude Code users only.

## References

- [Claude Code plugins overview](https://code.claude.com/docs/en/plugins)
- [Claude Code plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)

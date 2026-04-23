# agent-toolkit

A marketplace of hooks, plugins, and MCP servers for AI coding agents — primarily Claude Code today, with cross-harness support (Codex, etc.) where the tool is universal (MCP) or the hook contract converges.

## Install the marketplace

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

## Plugins

| Plugin | What it does | Docs |
| --- | --- | --- |
| [`quota-watch`](./plugins/quota-watch/README.md) | Adaptive Claude Max quota monitor. Adds a `UserPromptSubmit` hook that silently watches your 5h quota, warns as you approach it, and instructs the model to park itself until reset when you cross the halt threshold. | [README](./plugins/quota-watch/README.md) |

## Layout

```
.
├── .claude-plugin/marketplace.json
└── plugins/
    └── <plugin-name>/
        ├── .claude-plugin/plugin.json
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

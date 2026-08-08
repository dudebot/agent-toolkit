# agent-toolkit

A marketplace of hooks, plugins, and skills for AI coding agents — primarily Claude Code today, with cross-harness support (Codex, etc.) where the contract converges. Each plugin is a self-contained tool for a specific recurring problem in agent-driven development: staying inside usage quotas, archiving prompts, turning designs into executable workplans, and cleaning up the residue that iterative AI-assisted development leaves behind in comments, docs, and dead code.

It exists because these tools are worth sharing between machines and harnesses, and a marketplace repo is the installation unit Claude Code understands: point `/plugin marketplace add` at it once, then install and update individual plugins from there.

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

In Codex (skill plugins only — see the compatibility column below):

```
codex plugin marketplace add dudebot/agent-toolkit --ref main
codex plugin add seam-machine@agent-toolkit
```

Refresh after an upstream update:

```
codex plugin marketplace upgrade agent-toolkit
codex plugin remove seam-machine@agent-toolkit
codex plugin add seam-machine@agent-toolkit
```

Local path installs (`codex plugin marketplace add /path/to/agent-toolkit`) are only for active development of this repository. If you previously installed from a local checkout, `codex plugin marketplace remove agent-toolkit` before adding the GitHub-backed source.

## Plugins

### Hooks (Claude Code only)

| Plugin | What it does |
| --- | --- |
| [`quota-watch`](./plugins/quota-watch/README.md) | Adaptive Claude Max quota monitor. A `UserPromptSubmit` hook that silently watches your 5h/7d utilization, warns as you approach the limit, and instructs the model to park itself until reset when you cross the halt threshold. Adaptive cache TTL keeps endpoint traffic low. |
| [`claude-tee`](./plugins/claude-tee/README.md) | Mirrors every `UserPromptSubmit` to a local JSONL archive, with optional SSE/HTTP fan-out for live transcript overlays or pipeline triggers. Blocking the model after capture is an opt-in debug flag. |

### Workflow skills

| Plugin | What it does | Codex |
| --- | --- | --- |
| [`plan-project`](./plugins/plan-project/README.md) | Turns a settled architecture into a dispatch-ready workplan: phase-tagged task graph, paired test tasks, deterministic runbooks, and phase handoffs. | ✓ |
| [`orchestrate-workplan`](./plugins/orchestrate-workplan/README.md) | Drives a workplan to completion on a cheap, fast model: TodoWrite rails, runbook gates, more-capable verifier subagent on failure, architecture validator at phase boundaries. | ✓ |

### Code-quality skills

| Plugin | What it does | Codex |
| --- | --- | --- |
| [`comment-hygiene`](./plugins/comment-hygiene/README.md) | De-dusts source comments after iterative development: strips ticket tokens, review provenance, and sprint narration while preserving invariants, contracts, and platform gotchas. Findings list first, behavior-neutral apply. | ✓ |
| [`seam-machine`](./plugins/seam-machine/README.md) | Evidence-based architecture pass for greedy module boundaries: falsifiable claims, adversarial verification with forced verdicts, then cheapest-first behavior-preserving extractions that each reduce a nameable coupling count. | ✓ |
| [`docs-autopsy`](./plugins/docs-autopsy/README.md) | Evidence-based docs audit: per-file verdicts verified against the code, authority-claiming docs audited hardest, superseded design capsules archived with provenance, coverage-gap sweep for undocumented features. | ✓ |
| [`dead-code-detector`](./plugins/dead-code-detector/README.md) | Confidence-tiered dead-code detection: ecosystem tools first, reference analysis, git-history abandonment patterns. Evidence shown, edge cases demote confidence, deletes nothing without explicit instruction. | ✓ |

`comment-hygiene`, `seam-machine`, and `docs-autopsy` form a hygiene trilogy — comments, architecture, and documentation respectively — all built on the same pattern: sweep, verify every claim against the code, present a findings list, apply only on approval.

## Layout

```
.
├── .claude-plugin/marketplace.json    # what /plugin marketplace add reads
└── plugins/
    └── <plugin-name>/
        ├── .claude-plugin/plugin.json # Claude Code manifest
        ├── .codex-plugin/plugin.json  # Codex manifest (skill plugins only)
        ├── hooks/                     # hook plugins: hooks.json + scripts
        ├── skills/                    # skill plugins: SKILL.md per folder
        └── README.md
```

Each plugin is self-contained under `plugins/<name>/`. The marketplace manifest at `.claude-plugin/marketplace.json` is the source of truth for what's installable.

## Cross-harness notes

- **Skills** are markdown instructions and port cleanly: the six skill plugins carry dual manifests (`.claude-plugin/` and `.codex-plugin/`) and install into either harness.
- **Hooks**: Claude Code and Codex both have a `UserPromptSubmit` lifecycle hook with a similar JSON-on-stdin contract, but the two hook plugins here are Claude Code-specific in practice — `quota-watch` talks to Anthropic's usage endpoint, and `claude-tee`'s payload handling targets Claude Code's schema.

## Status

Active. Plugins are added and revised as they prove themselves in daily use; each carries its own version in its `plugin.json`.

## References

- [Claude Code plugins overview](https://code.claude.com/docs/en/plugins)
- [Claude Code plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)

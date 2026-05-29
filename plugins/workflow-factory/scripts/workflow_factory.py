#!/usr/bin/env python3
"""Thin workflow-factory driver.

This is intentionally a small deterministic wrapper around the prompt-driven
workflow-factory skill. It creates run state, verifies basic prerequisites,
renders the long stage prompt, optionally launches Codex, and records trace and
telemetry artifacts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any


UTC = dt.timezone.utc


def utc_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "workflow"


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = read_text(path)
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, body


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def save_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def append_trace(
    run_dir: Path,
    *,
    run_id: str,
    event_type: str,
    actor_role: str,
    input_artifacts: list[str],
    output_artifacts: list[str],
    decision: str | None = None,
    rationale: str | None = None,
    prompt_ref: str | None = None,
    model_or_runner: str | None = None,
    confidence: str | None = "medium",
    notes: str = "",
) -> None:
    trace_dir = run_dir / "trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": utc_now(),
        "run_id": run_id,
        "event_id": f"evt-{int(time.time() * 1000)}-{slugify(event_type)}",
        "parent_event_id": None,
        "event_type": event_type,
        "actor_role": actor_role,
        "prompt_ref": prompt_ref,
        "model_or_runner": model_or_runner,
        "input_artifacts": input_artifacts,
        "output_artifacts": output_artifacts,
        "decision": decision,
        "rationale": rationale,
        "source_refs": input_artifacts,
        "confidence": confidence,
        "notes": notes,
    }
    with (trace_dir / "trace_ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def append_artifact_index(run_dir: Path, artifact: Path, description: str) -> None:
    index = run_dir / "trace" / "artifact_index.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    if not index.exists():
        write_text(
            index,
            "# Artifact Index\n\n"
            "| Artifact | SHA-256 | Description |\n"
            "| --- | --- | --- |\n",
        )
    digest = sha256_file(artifact) or ""
    with index.open("a", encoding="utf-8") as f:
        f.write(f"| `{artifact}` | `{digest}` | {description} |\n")


def infer_project_id(intent_path: Path, frontmatter: dict[str, str]) -> str:
    if frontmatter.get("project_id"):
        return frontmatter["project_id"]
    parts = intent_path.parts
    if "projects" in parts:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    if frontmatter.get("project"):
        return slugify(frontmatter["project"].replace("/", "-"))
    return "unknown-project"


def unique_run_dir(project_dir: Path, run_id: str) -> Path:
    base = project_dir / "runs" / run_id
    if not base.exists():
        return base
    for i in range(2, 1000):
        candidate = project_dir / "runs" / f"{run_id}-{i}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate unique run dir for {run_id}")


def init_run(args: argparse.Namespace) -> int:
    control_root = Path(args.control_root).resolve()
    intent_path = Path(args.intent).resolve()
    if not intent_path.exists():
        print(f"error: intent not found: {intent_path}", file=sys.stderr)
        return 2

    frontmatter, _ = load_frontmatter(intent_path)
    project_id = args.project or infer_project_id(intent_path, frontmatter)
    project_dir = control_root / "projects" / project_id
    title = frontmatter.get("title") or intent_path.stem
    base_run_id = args.run_id or f"{dt.datetime.now().strftime('%Y-%m-%d')}-{slugify(title)}"
    run_dir = unique_run_dir(project_dir, base_run_id)

    for subdir in ["prompts", "outputs", "trace", "blockers", "remediation"]:
        (run_dir / subdir).mkdir(parents=True, exist_ok=True)

    run = {
        "id": run_dir.name,
        "project_id": project_id,
        "project_dir": str(project_dir),
        "control_root": str(control_root),
        "intent_path": str(intent_path),
        "status": "started",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "stage": None,
        "runner": None,
        "add_dirs": [],
        "artifacts": [],
        "preflight": None,
        "telemetry": [],
    }
    save_json(run_dir / "run.json", run)
    append_trace(
        run_dir,
        run_id=run["id"],
        event_type="run_initialized",
        actor_role="workflow-factory driver",
        input_artifacts=[str(intent_path)],
        output_artifacts=[str(run_dir / "run.json")],
        decision="run initialized",
        rationale="Created deterministic run state for an inbox intent.",
    )
    append_artifact_index(run_dir, run_dir / "run.json", "Run metadata")
    print(run_dir)
    return 0


def load_run(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run.json"
    if not path.exists():
        raise FileNotFoundError(f"run metadata not found: {path}")
    return load_json(path)


def save_run(run_dir: Path, run: dict[str, Any]) -> None:
    run["updated_at"] = utc_now()
    save_json(run_dir / "run.json", run)


def check_writable(path: Path) -> bool:
    if not path.exists():
        return False
    probe = path / ".workflow_factory_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def run_preflight(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).resolve()
    run = load_run(run_dir)
    control_root = Path(run["control_root"])
    intent_path = Path(run["intent_path"])
    project_dir = Path(run["project_dir"])
    runner = args.runner or run.get("runner") or "codex"
    add_dirs = [Path(p).resolve() for p in (args.add_dir or run.get("add_dirs") or [])]

    checks: list[dict[str, Any]] = []

    def add_check(name: str, ok: bool, detail: str, required: bool = True) -> None:
        checks.append({"name": name, "ok": ok, "required": required, "detail": detail})

    add_check("control_root_exists", control_root.exists(), str(control_root))
    add_check("projects_dir_exists", (control_root / "projects").exists(), str(control_root / "projects"))
    add_check("intent_exists", intent_path.exists(), str(intent_path))
    add_check("project_dir_exists", project_dir.exists(), str(project_dir))

    if runner != "print":
        add_check(f"runner_command_{runner}", shutil.which(runner) is not None, runner)

    for command in args.require_command or []:
        add_check(f"command_{command}", shutil.which(command) is not None, command)

    for env_name in args.require_env or []:
        add_check(f"env_{env_name}", bool(os.environ.get(env_name)), env_name)

    for raw_path in args.require_path or []:
        p = Path(raw_path).resolve()
        add_check(f"path_{p.name}", p.exists(), str(p))

    for raw_path in args.require_writable or []:
        p = Path(raw_path).resolve()
        add_check(f"writable_{p.name}", check_writable(p), str(p))

    for p in add_dirs:
        add_check(f"add_dir_exists_{p.name}", p.exists(), str(p))

    failed = [c for c in checks if c["required"] and not c["ok"]]
    result = {
        "ts": utc_now(),
        "run_id": run["id"],
        "runner": runner,
        "status": "failed" if failed else "passed",
        "checks": checks,
    }
    preflight_path = run_dir / "preflight.json"
    save_json(preflight_path, result)
    append_artifact_index(run_dir, preflight_path, "Preflight results")

    run["runner"] = runner
    run["add_dirs"] = [str(p) for p in add_dirs]
    run["preflight"] = str(preflight_path)
    run["status"] = "blocked" if failed else "ready"
    save_run(run_dir, run)

    if failed:
        blocker = run_dir / "blockers" / "preflight_blocked.md"
        write_text(
            blocker,
            "# Preflight Blocked\n\n"
            f"Run: `{run['id']}`\n\n"
            "## Failed Checks\n\n"
            + "\n".join(f"- `{c['name']}`: {c['detail']}" for c in failed)
            + "\n\n## Required Action\n\n"
            "Create or approve remediation work before rerunning this workflow.\n",
        )
        append_artifact_index(run_dir, blocker, "Blocked preflight artifact")
        remediation = create_remediation_intent(run_dir, run, failed)
        append_trace(
            run_dir,
            run_id=run["id"],
            event_type="preflight_failed",
            actor_role="workflow-factory driver",
            input_artifacts=[str(run_dir / "run.json")],
            output_artifacts=[str(preflight_path), str(blocker), str(remediation)],
            decision="blocked",
            rationale="Required preflight checks failed.",
            model_or_runner=runner,
            confidence="high",
        )
        print(f"preflight failed: {preflight_path}", file=sys.stderr)
        return 1

    append_trace(
        run_dir,
        run_id=run["id"],
        event_type="preflight_passed",
        actor_role="workflow-factory driver",
        input_artifacts=[str(run_dir / "run.json")],
        output_artifacts=[str(preflight_path)],
        decision="ready",
        rationale="Required preflight checks passed.",
        model_or_runner=runner,
        confidence="high",
    )
    print(preflight_path)
    return 0


def create_remediation_intent(run_dir: Path, run: dict[str, Any], failed: list[dict[str, Any]]) -> Path:
    project_dir = Path(run["project_dir"])
    inbox = project_dir / "intents" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    stem = f"{dt.datetime.now().strftime('%Y-%m-%d-%H%M%S')}-remediate-{slugify(run['id'])}"
    path = inbox / f"{stem}.md"
    body = (
        "---\n"
        f"id: intent-{stem}\n"
        f"title: Remediate prerequisites for {run['id']}\n"
        f"project_id: {run['project_id']}\n"
        "status: inbox\n"
        "source: workflow_factory_preflight\n"
        "needs_user_review: true\n"
        f"parent_run_id: {run['id']}\n"
        "---\n\n"
        f"# Remediate Prerequisites For `{run['id']}`\n\n"
        "## Failed Checks\n\n"
        + "\n".join(f"- `{c['name']}`: {c['detail']}" for c in failed)
        + "\n\n## Desired Outcome\n\n"
        "Make the original workflow ready to rerun, or revise the workflow if the prerequisite is inappropriate.\n\n"
        "## Must Not Happen\n\n"
        "- Do not rerun the blocked workflow automatically.\n"
        "- Do not broaden permissions without user approval.\n"
    )
    write_text(path, body)
    return path


def render_propose_prompt(run_dir: Path, run: dict[str, Any], add_dirs: list[str]) -> str:
    intent_path = Path(run["intent_path"])
    project_dir = Path(run["project_dir"])
    return f"""Use workflow-factory.

You are being launched by the workflow-factory trace driver. Follow the installed skill.

Control repo:
{run["control_root"]}

Project id:
{run["project_id"]}

Intent:
{intent_path}

Run directory:
{run_dir}

Stage:
propose

Task:
Turn the inbox intent into durable workflow-factory artifacts. Do not execute implementation work.

Write artifacts under:
{project_dir}

Required outputs:
- {run_dir}/problem_brief.md
- {project_dir}/workflows/proposed/<workflow_id>.md
- {run_dir}/trace/artifact_index.md updates
- {run_dir}/trace/trace_ledger.jsonl updates
- blocker/remediation artifacts if the proposed workflow cannot be made runnable

Requirements:
- Preserve the original intent.
- Split feasibility from implementation if implementation depends on live-site, browser, auth, or media behavior.
- Include capability preflight for GitHub auth, repo access, browser/Playwright, login/session, network, writable paths, and permission mode.
- Include token/time budget expectations when the workflow is likely to be expensive.
- Include explicit missing-prerequisite behavior and remediation-intent behavior.
- Do not modify target implementation repos.
- Do not finalize or queue implementation.
- Do not rely on chat history.

Additional directories available to this run:
{chr(10).join(f"- {p}" for p in add_dirs) if add_dirs else "- none"}
"""


def render_stage(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).resolve()
    run = load_run(run_dir)
    add_dirs = args.add_dir or run.get("add_dirs") or []
    stage = args.stage
    if stage != "propose":
        print(f"error: unsupported stage for thin driver: {stage}", file=sys.stderr)
        return 2
    prompt = render_propose_prompt(run_dir, run, add_dirs)
    prompt_path = run_dir / "prompts" / f"{stage}.md"
    write_text(prompt_path, prompt)
    append_artifact_index(run_dir, prompt_path, f"Rendered {stage} stage prompt")
    append_trace(
        run_dir,
        run_id=run["id"],
        event_type="stage_prompt_created",
        actor_role="workflow-factory driver",
        input_artifacts=[run["intent_path"]],
        output_artifacts=[str(prompt_path)],
        decision=f"{stage} prompt rendered",
        rationale="Moved cargo-cult prompt content into deterministic driver.",
        prompt_ref="workflow-factory-driver:propose",
    )
    run["stage"] = stage
    run["status"] = "prompt_rendered"
    save_run(run_dir, run)
    print(prompt_path)
    return 0


def ensure_preflight_passed(run_dir: Path) -> bool:
    preflight_path = run_dir / "preflight.json"
    if not preflight_path.exists():
        return False
    try:
        return load_json(preflight_path).get("status") == "passed"
    except Exception:
        return False


def run_stage(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).resolve()
    run = load_run(run_dir)
    runner = args.runner or run.get("runner") or "codex"

    if args.auto_preflight and not ensure_preflight_passed(run_dir):
        pf_args = argparse.Namespace(
            run=str(run_dir),
            runner=runner,
            add_dir=args.add_dir,
            require_command=args.require_command,
            require_env=args.require_env,
            require_path=args.require_path,
            require_writable=args.require_writable,
        )
        rc = run_preflight(pf_args)
        if rc != 0:
            return rc

    rc = render_stage(args)
    if rc != 0 or not args.execute:
        return rc

    if runner != "codex":
        print(f"error: --execute currently supports only runner=codex, got {runner}", file=sys.stderr)
        return 2

    prompt_path = run_dir / "prompts" / f"{args.stage}.md"
    stdout_path = run_dir / "outputs" / f"{args.stage}.stdout.txt"
    stderr_path = run_dir / "outputs" / f"{args.stage}.stderr.txt"
    telemetry_path = run_dir / "trace" / "telemetry.jsonl"
    control_root = run["control_root"]
    command = [
        "codex",
        "-a",
        args.approval,
        "exec",
        "-C",
        control_root,
        "-s",
        args.sandbox,
    ]
    for p in args.add_dir or run.get("add_dirs") or []:
        command.extend(["--add-dir", p])
    command.append("-")

    start = time.monotonic()
    started_at = utc_now()
    proc = subprocess.run(
        command,
        input=read_text(prompt_path),
        text=True,
        capture_output=True,
        timeout=args.timeout,
    )
    elapsed = time.monotonic() - start
    completed_at = utc_now()
    write_text(stdout_path, proc.stdout)
    write_text(stderr_path, proc.stderr)

    telemetry = {
        "ts": completed_at,
        "run_id": run["id"],
        "stage": args.stage,
        "runner": runner,
        "command": command,
        "started_at": started_at,
        "completed_at": completed_at,
        "elapsed_seconds": round(elapsed, 3),
        "returncode": proc.returncode,
        "token_usage": "unknown",
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }
    with telemetry_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(telemetry, sort_keys=True) + "\n")
    append_artifact_index(run_dir, stdout_path, f"{args.stage} runner stdout")
    append_artifact_index(run_dir, stderr_path, f"{args.stage} runner stderr")
    append_artifact_index(run_dir, telemetry_path, "Run telemetry")
    append_trace(
        run_dir,
        run_id=run["id"],
        event_type="stage_executed",
        actor_role="workflow-factory driver",
        input_artifacts=[str(prompt_path)],
        output_artifacts=[str(stdout_path), str(stderr_path), str(telemetry_path)],
        decision="stage completed" if proc.returncode == 0 else "stage failed",
        rationale=f"Runner exited with code {proc.returncode}.",
        model_or_runner=runner,
        confidence="high",
    )
    run["status"] = "completed" if proc.returncode == 0 else "blocked"
    run["telemetry"].append(str(telemetry_path))
    save_run(run_dir, run)
    print(stdout_path)
    return proc.returncode


def validate_run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).resolve()
    errors: list[str] = []
    for path in [
        run_dir / "run.json",
        run_dir / "trace" / "trace_ledger.jsonl",
        run_dir / "trace" / "artifact_index.md",
    ]:
        if not path.exists():
            errors.append(f"missing {path}")
    if (run_dir / "preflight.json").exists():
        try:
            load_json(run_dir / "preflight.json")
        except Exception as e:
            errors.append(f"invalid preflight.json: {e}")
    trace_path = run_dir / "trace" / "trace_ledger.jsonl"
    if trace_path.exists():
        for idx, line in enumerate(read_text(trace_path).splitlines(), 1):
            try:
                json.loads(line)
            except Exception as e:
                errors.append(f"invalid trace JSONL line {idx}: {e}")
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"valid: {run_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workflow-factory", description="Thin workflow-factory trace driver")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-run", help="Create a workflow-factory run directory")
    p.add_argument("--control-root", default=".", help="Control repo root")
    p.add_argument("--project", help="Project id; inferred from intent when omitted")
    p.add_argument("--intent", required=True, help="Intent markdown file")
    p.add_argument("--run-id", help="Explicit run id")
    p.set_defaults(func=init_run)

    p = sub.add_parser("preflight", help="Verify runner and workflow prerequisites")
    p.add_argument("--run", required=True)
    p.add_argument("--runner", default="codex")
    p.add_argument("--add-dir", action="append")
    p.add_argument("--require-command", action="append")
    p.add_argument("--require-env", action="append")
    p.add_argument("--require-path", action="append")
    p.add_argument("--require-writable", action="append")
    p.set_defaults(func=run_preflight)

    p = sub.add_parser("render-stage", help="Render a stage prompt without executing it")
    p.add_argument("--run", required=True)
    p.add_argument("--stage", default="propose")
    p.add_argument("--add-dir", action="append")
    p.set_defaults(func=render_stage)

    p = sub.add_parser("run-stage", help="Render a stage prompt and optionally execute it")
    p.add_argument("--run", required=True)
    p.add_argument("--stage", default="propose")
    p.add_argument("--runner", default="codex")
    p.add_argument("--add-dir", action="append")
    p.add_argument("--require-command", action="append")
    p.add_argument("--require-env", action="append")
    p.add_argument("--require-path", action="append")
    p.add_argument("--require-writable", action="append")
    p.add_argument("--no-auto-preflight", dest="auto_preflight", action="store_false")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--approval", default="on-request")
    p.add_argument("--sandbox", default="workspace-write")
    p.add_argument("--timeout", type=int, default=3600)
    p.set_defaults(func=run_stage, auto_preflight=True)

    p = sub.add_parser("validate-run", help="Validate minimum run artifacts")
    p.add_argument("--run", required=True)
    p.set_defaults(func=validate_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

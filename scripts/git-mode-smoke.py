#!/usr/bin/env python3
"""Run a real-harness SUPER_GIT_MODE=none lifecycle in a disposable ordinary directory.

The runner preserves prompts, runtime transcripts, stderr, manifests, receipts, and its independent
inspection result under --run-dir. It never creates a scheduler or remote repository.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
HARNESS_BIN = {"claude": "claude", "codex": "codex", "cursor": "agent", "pi": "pi"}


def physical(path):
    return path.expanduser().resolve()


def sha_tree(git_dir):
    if not git_dir.exists():
        return None
    digest = hashlib.sha256()
    for path in sorted(git_dir.rglob("*")):
        rel = path.relative_to(git_dir).as_posix().encode()
        digest.update(rel + b"\0")
        if path.is_file() and not path.is_symlink():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def package_source(harness):
    if harness == "codex":
        return ROOT / "codex/plugins/superagent"
    if harness in ("cursor", "pi"):
        return ROOT / harness
    return ROOT


def tool_payloads(value):
    """Yield only emitted tool-call arguments, never model prose or prompts."""
    if isinstance(value, dict):
        kind = str(value.get("type", "")).lower()
        name = str(value.get("name", value.get("toolName", ""))).lower()
        if kind in {"tool_use", "function_call", "tool_call", "toolcall", "command_execution"} or name:
            if kind == "command_execution" or name in {
                "bash", "shell", "exec", "exec_command", "command_execution", "web", "http", "fetch"
            }:
                payload = value.get(
                    "command", value.get("input", value.get("arguments", value.get("args", {})))
                )
                if isinstance(payload, str):
                    yield payload
                else:
                    yield json.dumps(payload, sort_keys=True)
        for child in value.values():
            yield from tool_payloads(child)
    elif isinstance(value, list):
        for child in value:
            yield from tool_payloads(child)


def inspect_transcripts(run):
    forbidden = []
    patterns = [
        ("git command", re.compile(r"(^|[;&|\s])(?:/[^\s]*/)?git(?:\s|$)")),
        ("gh command", re.compile(r"(^|[;&|\s])(?:/[^\s]*/)?gh(?:\s|$)")),
        ("GitHub API", re.compile(r"api\.github\.com|github\.com/api|/repos/[^\s]+/(pulls|actions|git/)")),
        ("credential access", re.compile(r"gh auth token|hosts\.yml|GH_TOKEN|GITHUB_TOKEN|security find-generic-password|secret-tool")),
    ]
    inspected = []
    for transcript in sorted(run.glob("*.jsonl")):
        for number, line in enumerate(transcript.read_text(errors="replace").splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            for payload in tool_payloads(row):
                inspected.append({"file": transcript.name, "line": number, "payload": payload})
                for label, pattern in patterns:
                    if pattern.search(payload):
                        forbidden.append({"kind": label, "file": transcript.name,
                                          "line": number, "payload": payload})
    (run / "tool-calls.json").write_text(json.dumps(inspected, indent=2) + "\n")
    (run / "forbidden-tool-calls.json").write_text(json.dumps(forbidden, indent=2) + "\n")
    return forbidden


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=sorted(HARNESS_BIN), required=True)
    parser.add_argument("--vault", choices=["internal", "external"], required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--max-ticks", type=int, default=14)
    parser.add_argument("--resume", action="store_true",
                        help="resume a retained run directory after an interrupted harness phase")
    args = parser.parse_args()

    binary = shutil.which(HARNESS_BIN[args.harness])
    if args.harness == "cursor" and binary is None:
        binary = shutil.which("cursor-agent")
    if binary is None:
        raise SystemExit("git-mode-smoke: harness CLI unavailable: " + args.harness)

    run = physical(args.run_dir)
    repo, package = run / "project", run / "plugin"
    if args.resume:
        if not repo.is_dir() or not package.is_dir():
            raise SystemExit("git-mode-smoke: retained project/plugin missing from --run-dir")
    else:
        run.mkdir(parents=True, exist_ok=False)
        repo.mkdir()
        source = package_source(args.harness)
        if args.harness == "claude":
            # Claude consumes the canonical plugin layout; copy only runtime-owned paths.
            for name in ("skills", "scripts", "templates", ".claude-plugin"):
                src = source / name
                if src.is_dir():
                    shutil.copytree(src, package / name)
        else:
            shutil.copytree(source, package)
    vault = repo / "vault" if args.vault == "internal" else run / "external vault"
    if not args.resume:
        vault.mkdir(parents=True)
        (run / "tmp").mkdir()

    sentinel = run / "sentinel-bin"
    sentinel.mkdir(exist_ok=args.resume)
    sentinel_log = run / "sentinel-calls.jsonl"
    for name in ("git", "gh", "security", "secret-tool", "pass"):
        script = sentinel / name
        if not args.resume:
            script.write_text("#!/bin/sh\nprintf '{\"program\":\"%s\",\"argv\":\"%%s\"}\\n' \"$*\" >>'%s'\nexit 97\n" % (name, sentinel_log))
            script.chmod(0o755)

    model = {
        "claude": "claude:sonnet", "codex": "codex:gpt-5.6-sol",
        "cursor": "inherit", "pi": "pi:openai-codex/gpt-5.6-sol",
    }[args.harness]
    configured_vault = "vault" if args.vault == "internal" else str(vault)
    def assignment(name, value):
        return name + "=" + shlex.quote(value) + "\n"

    env_text = (
        "SUPER_GIT_MODE=none\n"
        f"SUPER_HARNESS={args.harness}\n"
        + assignment("SUPER_GOAL_ROOT", configured_vault) +
        "SUPER_TEST_EVIDENCE=local\nSUPER_GOAL_AUTOCONFIRM=true\n"
        f"SUPER_MODEL_SUPERVISOR={model}\nSUPER_MODEL_PLANNER={model}\n"
        f"SUPER_MODEL_EXECUTOR={model}\nSUPER_MODEL_IMPLEMENTER={model}\n"
        f"SUPER_MODEL_TASK_REVIEWER={model}\nSUPER_MODEL_RE_REVIEWER={model}\n"
        f"SUPER_MODEL_BRANCH_REVIEWER={model}\nSUPER_MODEL_EVALUATOR={model}\n"
    )
    if not args.resume:
        (repo / ".superenv").write_text(env_text)
        (repo / "AGENTS.md").write_text(
            "# Git-free acceptance fixture\nWork only in this ordinary directory and its configured vault.\n"
            "Use the copied plugin named in each prompt. Never run git, gh, GitHub API, credential,\n"
            "worktree, commit, push, PR, merge, sync, or CI operations. Run local tests and reviews.\n")

    env = dict(os.environ)
    for key in list(env):
        if key.startswith("SUPER_") or key in ("GH_TOKEN", "GITHUB_TOKEN"):
            del env[key]
    env.update({"PATH": str(sentinel) + os.pathsep + env.get("PATH", ""),
                "TMPDIR": str(run / "tmp") + "/", "REPO": str(repo),
                "SUPER_GIT_MODE": "none", "SUPER_HARNESS": args.harness,
                "SUPER_GOAL_ROOT": configured_vault, "SUPER_TEST_EVIDENCE": "local",
                "SUPER_GOAL_AUTOCONFIRM": "true", "SUPERAGENT_PI_SKILLS": str(package / "skills")})

    phase_counter = 0
    if args.resume:
        phase_counter = max(
            [int(path.name.split("-", 1)[0]) for path in run.glob("[0-9][0-9]-*.jsonl")],
            default=0,
        )

    def invoke(label, prompt):
        nonlocal phase_counter
        phase_counter += 1
        phase = f"{phase_counter:02d}-{label}"
        (run / f"{phase}.prompt.txt").write_text(prompt)
        if args.harness == "codex":
            argv = [binary, "exec", "-C", str(repo), "--skip-git-repo-check",
                    "--dangerously-bypass-approvals-and-sandbox", "-m", "gpt-5.6-sol",
                    "-c", "model_reasoning_effort=medium", "--json", "-"]
        elif args.harness == "claude":
            argv = [binary, "-p", "--dangerously-skip-permissions", "--plugin-dir", str(package),
                    "--output-format", "stream-json", "--verbose"]
        elif args.harness == "pi":
            argv = [binary, "-p", "--approve", "--no-session", "--mode", "json",
                    "--skill", str(package / "skills"), "--model", "openai-codex/gpt-5.6-sol:medium"]
        else:
            argv = [binary, "-p", "--trust", "--force", "--plugin-dir", str(package),
                    "--output-format", "stream-json"]
        with (run / f"{phase}.jsonl").open("w") as out, (run / f"{phase}.stderr").open("w") as err:
            process = subprocess.Popen(argv, cwd=repo, env=env, stdin=subprocess.PIPE, stdout=out,
                                       stderr=err, text=True, start_new_session=True)
            try:
                process.communicate(prompt, timeout=args.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait()
                raise RuntimeError(f"{phase} timed out; inspect {run}")
            except KeyboardInterrupt:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait()
                raise
            if process.returncode:
                raise RuntimeError(f"{phase} exited {process.returncode}; inspect {run}")

    def skill(name):
        return f"Read and follow {package}/skills/{name}/SKILL.md. Resolve every plugin skill and helper from {package}. "

    if not args.resume:
        invoke("init", skill("init") + "Initialize this SUPER_GIT_MODE=none project completely. Do not use git or GitHub.")
        # Add the intentional failing seed after initialization so init verification remains focused on
        # repository setup rather than trying to repair the implementation that the goal will own.
        (repo / "greeting.py").write_text('def greet(name="world"):\n    return "hello"\n')
        (repo / "test_greeting.py").write_text(
            "import unittest\nfrom greeting import greet\n\nclass GreetingTest(unittest.TestCase):\n"
            "    def test_default(self):\n        self.assertEqual(greet(), 'Hello, world!')\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n")
        goal = """Create a two-leaf goal. Leaf 1 fixes greet() and its local test so the default returns
Hello, world!. Leaf 2 extends it so greet('Ada') returns Hello, Ada! while preserving the default.
The existing implementation/test mismatch is an intentional failing seed: execute tests and all
required task/final reviews, repair review findings, and retain evidence. Use --autoconfirm and slug
git-free-smoke. Do not use git, GitHub, CI, or remote services."""
        invoke("goal", skill("supergoal") + "Run supergoal for this goal: " + goal)
    plans = list(vault.glob("*/master-plans/*.md"))
    if len(plans) != 1:
        raise RuntimeError(f"expected one root plan, found {plans}")
    root_plan = plans[0]
    root_text = root_plan.read_text()
    if "**Git mode:** none" not in root_text or f"**Project root:** {repo}" not in root_text:
        raise RuntimeError("root plan lacks immutable local mode/root markers")
    loop_dir = root_plan.parent.parent / "loop-status"
    loop = loop_dir / "git-free-smoke.md"
    if not args.resume:
        loop_dir.mkdir()
        stored_plan = str(root_plan.relative_to(repo)) if str(root_plan).startswith(str(repo) + os.sep) else str(root_plan)
        loop.write_text(
            "---\nmaster_plan: " + stored_plan + "\ngit_mode: none\nproject_root: " + str(repo) +
            "\nstatus: WAITING FOR PLAN\nplan_exhausted: false\nprior_status:\ndriver: external\n"
            "cron_id:\ncreated: smoke\niteration: 0\nsession_skill_count: 0\n---\n\n"
            "## Pending decision\n\n## Decisions\n\n## Iteration log\n")
    elif not loop.is_file():
        raise RuntimeError("retained loop file is missing")

    saw_resume = args.resume
    for tick in range(1, args.max_ticks + 1):
        before = re.search(r"^status:\s*(.+)$", loop.read_text(), re.M).group(1)
        if before == "DONE":
            break
        invoke(f"tick-{tick:02d}", skill("superagent") +
               f"Run exactly one unattended --tick on {loop}. Do not create or arm a scheduler.")
        after = re.search(r"^status:\s*(.+)$", loop.read_text(), re.M).group(1)
        if tick > 1:
            saw_resume = True
        if after == "WAITING FOR INPUT":
            raise RuntimeError("lifecycle parked for input; inspect retained decision")
        if after == "DONE":
            break
        if after in ("PLANNING", "RUNNING") and before == after:
            raise RuntimeError("tick left transient state")
    else:
        raise RuntimeError("lifecycle did not reach DONE within max ticks")

    if not saw_resume:
        raise RuntimeError("fresh-session resume was not exercised")
    receipts = list(vault.glob("*/reports/*completed-local*.md"))
    if len(receipts) < 2:
        raise RuntimeError(f"expected two completed-local receipts, found {receipts}")
    test = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=repo, env=env,
                          text=True, capture_output=True)
    (run / "final-tests.txt").write_text(test.stdout + test.stderr)
    if test.returncode:
        raise RuntimeError("final local tests failed")

    # Real snapshot command after lifecycle; its output and manifest remain as independent evidence.
    snap_parent = run / "snapshot-evidence"
    if args.resume and snap_parent.exists():
        shutil.rmtree(snap_parent)
    snap_parent.mkdir()
    snap = subprocess.run([sys.executable, str(package / "scripts/workspace-state.py"), "snapshot",
                           "--root", str(repo), "--vault", str(vault), "--out-parent", str(snap_parent)],
                          env=env, text=True, capture_output=True, check=True)
    (run / "snapshot.json").write_text(snap.stdout)

    # A judged local evaluation is part of the smoke contract. The project inputs bind a simple
    # source inspection objective to the same snapshot-based runner used by the skill.
    project = vault / "projects" / "smoke-evaluation"
    if args.resume and project.exists():
        shutil.rmtree(project)
    (project / "eval-reports").mkdir(parents=True)
    (project / "prd.md").write_text(
        "# Smoke PRD\n**Date:** 2026-09-17 · **Status:** READY\n\n## Objective\nVerify greeting.\n\n"
        "## Success criteria\n| Id | Criterion | Verified by (check ids) |\n|---|---|---|\n"
        "| SC1 | `greet()` returns `Hello, world!` and `greet('Ada')` returns `Hello, Ada!` | C1, J1 |\n\n"
        "## Constraints and non-goals\n- local only\n\n## Locked decisions\n- no git\n\n## Iteration ledger\n"
        "| Round | Meta-plan | Goal folder | Inner loop | Source | Eval report | Verdict |\n|---|---|---|---|---|---|---|\n"
        f"| 1 | - | [[{root_plan.parent.parent.relative_to(vault)}]] | [[{loop.relative_to(vault)}]] | - | - | - |\n")
    (project / "knowledge-base.md").write_text(
        "# Smoke knowledge\n**Date:** 2026-09-17 · **Status:** READY\n\n"
        "| Id | Kind | Locator | Read for |\n|---|---|---|---|\n"
        "| K1 | `repo-file` | `greeting.py` | behavior |\n"
        "| K2 | `repo-file` | `test_greeting.py` | exact assertions |\n")
    (project / "evaluation.md").write_text(
        "# Smoke evaluation\n**Date:** 2026-09-17 · **Status:** READY\n\n## Environment\n- setup: ``\n- cwd: `.`\n\n"
        "## Command checks\n| Id | Command | Cwd | Pass when | Timeout |\n|---|---|---|---|---|\n"
        f"| C1 | `{sys.executable} -m unittest -q` | `.` | `exit 0` | 2 |\n\n"
        "## Judged objectives\n| Id | Objective | Criteria | Evidence to inspect |\n|---|---|---|---|\n"
        "| J1 | Greeting implementation is direct | `greet()` is exactly `Hello, world!`; `greet('Ada')` is exactly `Hello, Ada!` | `greeting.py`, `test_greeting.py` |\n\n"
        "## Acceptance checklist\n**Approval:** Approved by smoke fixture on 2026-09-17.\n"
        "| Id | Source | Required case or rule | Expected result | Verification and check ids |\n|---|---|---|---|---|\n"
        "| AC1 | prd.md SC1 | Default and Ada names | `Hello, world!` and `Hello, Ada!` exactly | C1, J1 |\n\n## Coverage suggestions and decisions\nnone\n")
    invoke("evaluate", skill("supereval") + f"Run supereval {project} for round 1. Use the real read-only evaluator and do not repair code.")
    reports = list((project / "eval-reports").glob("*.md"))
    if len(reports) != 1 or "**PASS**" not in reports[0].read_text():
        raise RuntimeError("judged snapshot evaluation did not PASS")

    forbidden = inspect_transcripts(run)
    sentinel_calls = [json.loads(line) for line in sentinel_log.read_text().splitlines()] \
        if sentinel_log.exists() else []
    # Harness CLIs may probe git while starting (for example to discover their own plugin roots).
    # Those calls are retained as runtime evidence. Superagent-issued commands are independently
    # rejected from the structured transcripts above; every non-git sentinel remains prohibited.
    runtime_git_probes = [call for call in sentinel_calls if call.get("program") == "git"]
    prohibited_sentinel_calls = [call for call in sentinel_calls if call.get("program") != "git"]
    (run / "runtime-git-probes.json").write_text(json.dumps(runtime_git_probes, indent=2) + "\n")
    (run / "prohibited-sentinel-calls.json").write_text(
        json.dumps(prohibited_sentinel_calls, indent=2) + "\n"
    )
    if forbidden or prohibited_sentinel_calls:
        raise RuntimeError("prohibited git/GitHub/credential activity detected")
    if (repo / ".git").exists() or (vault / ".git").exists():
        raise RuntimeError("local lifecycle created git metadata")

    result = {
        "harness": args.harness, "vault": args.vault, "result": "PASS",
        "evidence_kind": "real harness execution", "project": str(repo), "root_plan": str(root_plan),
        "loop": str(loop), "receipts": [str(path) for path in receipts], "evaluation": str(reports[0]),
        "snapshot": json.loads(snap.stdout), "forbidden_tool_calls": 0,
        "prohibited_sentinel_calls": 0, "harness_runtime_git_probes": runtime_git_probes,
        "git_metadata": sha_tree(repo / ".git"),
    }
    (run / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

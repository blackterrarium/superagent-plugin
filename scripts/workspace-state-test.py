#!/usr/bin/env python3
"""Behavioral tests for workspace-state.py (Python 3.9 stdlib only)."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "workspace-state.py"


class WorkspaceStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="workspace-state-test-")
        self.base = Path(self.tmp.name)
        self.project = self.base / "project with spaces"
        self.vault = self.project / "vault"
        self.out = self.base / "snapshots"
        self.project.mkdir()
        self.vault.mkdir()
        self.out.mkdir()
        (self.project / "app.txt").write_text("hello\n", encoding="utf-8")
        (self.project / "unicodé file.txt").write_text("snowman ☃\n", encoding="utf-8")
        (self.vault / "private-plan.md").write_text("private\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, check=True, env=None):
        result = subprocess.run(
            [sys.executable, str(CLI), *map(str, args)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        if check and result.returncode:
            self.fail("command failed rc={}\nstdout={}\nstderr={}".format(
                result.returncode, result.stdout, result.stderr
            ))
        return result

    def snapshot(self):
        result = self.cli(
            "snapshot", "--root", self.project, "--vault", self.vault,
            "--out-parent", self.out,
        )
        return json.loads(result.stdout)

    @contextlib.contextmanager
    def writer(self, root=None):
        root = Path(root or self.project)
        env_file = self.base / (root.name + "-writer.json")
        code = (
            "import json,os,time,pathlib; "
            "pathlib.Path(os.environ['ENV_FILE']).write_text(json.dumps({"
            "'token':os.environ['SUPER_WORKSPACE_TOKEN'],"
            "'owner':os.environ['SUPER_WORKSPACE_OWNER_PID']})); "
            "time.sleep(60)"
        )
        env = os.environ.copy()
        env["ENV_FILE"] = str(env_file)
        proc = subprocess.Popen(
            [sys.executable, str(CLI), "run", "--root", str(root), "--",
             sys.executable, "-c", code],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        deadline = time.time() + 5
        while not env_file.exists() and proc.poll() is None and time.time() < deadline:
            time.sleep(0.02)
        self.assertTrue(env_file.exists(), "writer did not publish ownership")
        try:
            yield proc, json.loads(env_file.read_text(encoding="utf-8"))
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=5)

    def run_writer(self, root=None, check=False):
        root = Path(root or self.project)
        return self.cli(
            "run", "--root", root, "--", sys.executable, "-c", "pass",
            check=check,
        )

    def test_local_snapshot_identity(self):
        first = self.snapshot()
        second = self.snapshot()
        self.assertEqual(first["source_id"], second["source_id"])
        (self.project / "app.txt").write_text("changed\n", encoding="utf-8")
        self.assertNotEqual(first["source_id"], self.snapshot()["source_id"])

    def test_snapshot_manifest_and_exclusions(self):
        (self.project / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
        (self.project / ".env.local").write_text("TOKEN=secret\n", encoding="utf-8")
        (self.project / ".git").mkdir()
        (self.project / ".git" / "index").write_bytes(b"git")
        runtime = self.project / ".superagent-runtime"
        runtime.mkdir()
        (runtime / "state").write_text("runtime", encoding="utf-8")
        executable = self.project / "run me.sh"
        executable.write_text("#!/bin/sh\n", encoding="utf-8")
        executable.chmod(0o755)
        result = self.snapshot()
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        paths = [entry["path"] for entry in manifest["entries"]]
        self.assertEqual(paths, sorted(paths))
        self.assertIn("app.txt", paths)
        self.assertIn("unicodé file.txt", paths)
        self.assertNotIn(".env", paths)
        self.assertFalse(any(path.startswith(".git/") for path in paths))
        self.assertFalse(any(path.startswith("vault/") for path in paths))
        modes = {entry["path"]: entry["mode"] for entry in manifest["entries"]}
        self.assertEqual(modes["run me.sh"] & 0o111, 0o111)

    def test_compare_reports_add_modify_delete_and_mode(self):
        before = self.snapshot()
        (self.project / "new.txt").write_text("new\n", encoding="utf-8")
        (self.project / "app.txt").write_text("updated\n", encoding="utf-8")
        unicode_file = self.project / "unicodé file.txt"
        unicode_file.chmod(0o755)
        (self.project / "gone.txt").write_text("gone\n", encoding="utf-8")
        staged = self.snapshot()
        (self.project / "gone.txt").unlink()
        after = self.snapshot()
        first = json.loads(self.cli("compare", "--before", before["manifest"],
                                    "--after", staged["manifest"]).stdout)
        self.assertEqual(first["added"], ["gone.txt", "new.txt"])
        self.assertEqual(first["modified"], ["app.txt", "unicodé file.txt"])
        second = json.loads(self.cli("compare", "--before", staged["manifest"],
                                     "--after", after["manifest"]).stdout)
        self.assertEqual(second["deleted"], ["gone.txt"])

    def test_relative_internal_symlink_is_preserved(self):
        os.symlink("app.txt", self.project / "app-link")
        result = self.snapshot()
        copied = Path(result["workspace"]) / "app-link"
        self.assertTrue(copied.is_symlink())
        self.assertEqual(os.readlink(str(copied)), "app.txt")

    def test_external_absolute_dangling_and_excluded_symlinks_are_rejected(self):
        cases = {
            "external": str(self.base / "outside.txt"),
            "absolute": str(self.project / "app.txt"),
            "dangling": "missing.txt",
            "excluded": "vault/private-plan.md",
        }
        (self.base / "outside.txt").write_text("outside", encoding="utf-8")
        for name, target in cases.items():
            link = self.project / (name + "-link")
            os.symlink(target, link)
            result = self.cli(
                "snapshot", "--root", self.project, "--vault", self.vault,
                "--out-parent", self.out, check=False,
            )
            self.assertEqual(result.returncode, 2, (name, result.stderr))
            self.assertIn(link.name, result.stderr)
            link.unlink()

    def test_special_files_are_rejected_with_their_path(self):
        fifo = self.project / "unsafe fifo"
        os.mkfifo(str(fifo))
        result = self.cli(
            "snapshot", "--root", self.project, "--vault", self.vault,
            "--out-parent", self.out, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(fifo.name, result.stderr)

    def test_snapshot_can_change_without_changing_source(self):
        result = self.snapshot()
        copied = Path(result["workspace"]) / "app.txt"
        copied.write_text("test output\n", encoding="utf-8")
        self.assertEqual((self.project / "app.txt").read_text(encoding="utf-8"), "hello\n")

    def test_live_owner_cannot_be_stolen(self):
        with self.writer() as (owner, _):
            peer = self.run_writer(check=False)
            self.assertEqual(peer.returncode, 3)
            self.assertIsNone(owner.poll())

    def test_inherited_owner_borrows_lock_and_foreign_release_fails(self):
        with self.writer() as (_, identity):
            env = os.environ.copy()
            env["SUPER_WORKSPACE_TOKEN"] = identity["token"]
            env["SUPER_WORKSPACE_OWNER_PID"] = identity["owner"]
            borrowed = self.cli(
                "acquire", "--root", self.project, "--owner-pid", identity["owner"],
                "--token", identity["token"], "--operation", "nested", env=env,
            )
            self.assertTrue(json.loads(borrowed.stdout)["borrowed"])
            refused = self.cli(
                "release", "--root", self.project, "--token", "foreign", check=False,
            )
            self.assertEqual(refused.returncode, 3)

    def test_reversed_shared_vault_order_has_one_writer(self):
        other = self.base / "other"
        other.mkdir()
        with self.writer(root=other):
            result = self.cli(
                "run", "--root", self.project, "--root", other, "--",
                sys.executable, "-c", "pass", check=False,
            )
            self.assertEqual(result.returncode, 3)
            self.assertFalse((self.project / ".superagent-runtime/workspace.lockd").exists())

    def test_dead_owner_with_live_child_remains_busy(self):
        with self.writer() as (owner, _):
            os.kill(owner.pid, signal.SIGKILL)
            owner.wait(timeout=5)
            peer = self.run_writer(check=False)
            self.assertEqual(peer.returncode, 3)
            lock = self.project / ".superagent-runtime/workspace.lockd/owner.json"
            meta = json.loads(lock.read_text(encoding="utf-8"))
            try:
                os.killpg(int(meta["process_group"]), signal.SIGTERM)
            except ProcessLookupError:
                pass

    def test_owner_termination_releases_lock(self):
        with self.writer() as (owner, _):
            owner.terminate()
            owner.communicate(timeout=5)
        self.assertEqual(self.run_writer(check=False).returncode, 0)

    def test_partial_acquisition_is_cleaned_up(self):
        other = self.base / "z-other"
        other.mkdir()
        with self.writer(root=other):
            result = self.cli(
                "run", "--root", self.project, "--root", other, "--",
                sys.executable, "-c", "pass", check=False,
            )
            self.assertEqual(result.returncode, 3)
            self.assertFalse((self.project / ".superagent-runtime/workspace.lockd").exists())

    def test_ambiguous_owner_metadata_is_not_reaped(self):
        lock = self.project / ".superagent-runtime/workspace.lockd"
        lock.mkdir(parents=True)
        (lock / "owner.json").write_text("{}\n", encoding="utf-8")
        self.assertEqual(self.run_writer(check=False).returncode, 3)

    def test_dead_direct_owner_is_recovered(self):
        lock = self.project / ".superagent-runtime/workspace.lockd"
        lock.mkdir(parents=True)
        metadata = {
            "schema": 1, "token": "stale", "owner_pid": 99999999,
            "process_group": None, "operation": "abandoned", "root": str(self.project),
        }
        (lock / "owner.json").write_text(json.dumps(metadata), encoding="utf-8")
        self.assertEqual(self.run_writer(check=False).returncode, 0)

    def test_cleanup_requires_matching_token_and_refuses_unsafe_targets(self):
        snap = self.snapshot()
        refused = self.cli(
            "cleanup", "--workspace", snap["workspace"], "--token", "wrong", check=False,
        )
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(Path(snap["workspace"]).exists())
        self.cli("cleanup", "--workspace", snap["workspace"], "--token", snap["token"])
        self.assertFalse(Path(snap["workspace"]).exists())
        for unsafe in (self.project, Path.home(), Path("/")):
            result = self.cli(
                "cleanup", "--workspace", unsafe, "--token", "anything", check=False,
            )
            self.assertEqual(result.returncode, 2)

    def test_snapshot_refuses_destination_under_source_or_vault(self):
        for out in (self.project / "out", self.vault / "out"):
            out.mkdir()
            result = self.cli(
                "snapshot", "--root", self.project, "--vault", self.vault,
                "--out-parent", out, check=False,
            )
            self.assertEqual(result.returncode, 2)

    def test_source_mutation_during_copy_is_detected(self):
        spec = importlib.util.spec_from_file_location("workspace_state", CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        changed = {"done": False}

        def mutate(_source, _destination):
            if not changed["done"]:
                changed["done"] = True
                (self.project / "app.txt").write_text("raced\n", encoding="utf-8")

        with self.assertRaises(module.WorkspaceChanged):
            module.create_snapshot(self.project, self.vault, self.out, copy_callback=mutate)


if __name__ == "__main__":
    unittest.main(verbosity=2)

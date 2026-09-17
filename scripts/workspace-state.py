#!/usr/bin/env python3
"""Owned workspace locks and reproducible filesystem snapshots.

Python 3.9 standard library only. This helper deliberately has no git or GitHub
integration so SUPER_GIT_MODE=none can use it under command sentinels.
"""
import argparse
import datetime as _datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import uuid


EXIT_INVALID = 2
EXIT_BUSY = 3
EXIT_CHANGED = 4
LOCK_RELATIVE = Path(".superagent-runtime") / "workspace.lockd"
OWNER_FILE = "owner.json"
SNAPSHOT_MARKER = ".superagent-snapshot.json"


class WorkspaceError(Exception):
    exit_code = EXIT_INVALID


class WorkspaceBusy(WorkspaceError):
    exit_code = EXIT_BUSY


class WorkspaceChanged(WorkspaceError):
    exit_code = EXIT_CHANGED


def _json_print(value):
    print(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _physical_dir(value, label):
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise WorkspaceError("{} is not a directory: {}".format(label, value))
    return path


def _is_within(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except PermissionError:
        return True


def _group_alive(pgid):
    if pgid in (None, ""):
        return False
    try:
        os.killpg(int(pgid), 0)
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except PermissionError:
        return True


def _lock_path(root):
    return root / LOCK_RELATIVE


def _read_owner(lock):
    try:
        data = json.loads((lock / OWNER_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise WorkspaceBusy("workspace lock has ambiguous owner metadata: {}".format(lock))
    if not isinstance(data, dict):
        raise WorkspaceBusy("workspace lock has ambiguous owner metadata: {}".format(lock))
    if not isinstance(data.get("token"), str) or not data["token"]:
        raise WorkspaceBusy("workspace lock has ambiguous owner metadata: {}".format(lock))
    if not isinstance(data.get("owner_pid"), int) or data["owner_pid"] <= 0:
        raise WorkspaceBusy("workspace lock has ambiguous owner metadata: {}".format(lock))
    if not isinstance(data.get("operation"), str) or not data["operation"]:
        raise WorkspaceBusy("workspace lock has ambiguous owner metadata: {}".format(lock))
    if "process_group" not in data:
        raise WorkspaceBusy("workspace lock has ambiguous owner metadata: {}".format(lock))
    pgid = data.get("process_group")
    if pgid is not None and (not isinstance(pgid, int) or pgid <= 0):
        raise WorkspaceBusy("workspace lock has ambiguous owner metadata: {}".format(lock))
    return data


def _write_owner(lock, data):
    temporary = lock / (OWNER_FILE + ".tmp.{}".format(os.getpid()))
    temporary.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(lock / OWNER_FILE))


def _remove_owned_lock(root, token):
    lock = _lock_path(root)
    if not lock.exists():
        return False
    data = _read_owner(lock)
    if data["token"] != token:
        raise WorkspaceBusy("workspace lock token does not match: {}".format(lock))
    shutil.rmtree(str(lock))
    runtime = lock.parent
    try:
        runtime.rmdir()
    except OSError:
        pass
    return True


def acquire_roots(roots, owner_pid, token, operation, process_group=None):
    if not token or not operation or int(owner_pid) <= 0:
        raise WorkspaceError("lock token, live owner pid, and operation are required")
    owner_pid = int(owner_pid)
    if not _pid_alive(owner_pid):
        raise WorkspaceError("workspace owner pid is not live: {}".format(owner_pid))
    ordered = sorted(set(_physical_dir(root, "root") for root in roots), key=str)
    created = []
    borrowed = []
    try:
        for root in ordered:
            lock = _lock_path(root)
            lock.parent.mkdir(parents=True, exist_ok=True)
            while True:
                try:
                    lock.mkdir()
                except FileExistsError:
                    data = _read_owner(lock)
                    if data["token"] == token and data["owner_pid"] == owner_pid:
                        if not _pid_alive(owner_pid):
                            raise WorkspaceBusy("inherited workspace owner is no longer live: {}".format(lock))
                        borrowed.append(root)
                        break
                    if _pid_alive(data["owner_pid"]):
                        raise WorkspaceBusy("workspace is busy: {} (pid {})".format(root, data["owner_pid"]))
                    if data.get("process_group") is not None and _group_alive(data["process_group"]):
                        raise WorkspaceBusy(
                            "workspace owner exited but supervised process group is still live: {}".format(root)
                        )
                    # The recorded owner and supervised group are both gone.
                    shutil.rmtree(str(lock))
                    continue
                data = {
                    "schema": 1,
                    "token": token,
                    "owner_pid": owner_pid,
                    "process_group": process_group,
                    "operation": operation,
                    "acquired_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
                    "root": str(root),
                }
                _write_owner(lock, data)
                created.append(root)
                break
    except Exception:
        for root in reversed(created):
            try:
                _remove_owned_lock(root, token)
            except WorkspaceError:
                pass
        raise
    return {"roots": [str(root) for root in ordered],
            "created": [str(root) for root in created],
            "borrowed_roots": [str(root) for root in borrowed],
            "borrowed": bool(borrowed) and not created}


def _set_process_group(roots, token, process_group):
    for root in roots:
        lock = _lock_path(Path(root))
        data = _read_owner(lock)
        if data["token"] != token:
            raise WorkspaceBusy("lost workspace lock ownership: {}".format(root))
        data["process_group"] = int(process_group)
        _write_owner(lock, data)


def release_roots(roots, token):
    released = []
    for root in sorted(set(_physical_dir(root, "root") for root in roots), key=str, reverse=True):
        if _remove_owned_lock(root, token):
            released.append(str(root))
    return {"released": sorted(released)}


def run_owned(roots, command):
    if not command:
        raise WorkspaceError("run requires a command after --")
    inherited_token = os.environ.get("SUPER_WORKSPACE_TOKEN", "")
    inherited_owner = os.environ.get("SUPER_WORKSPACE_OWNER_PID", "")
    if inherited_token and inherited_owner:
        token = inherited_token
        try:
            owner_pid = int(inherited_owner)
        except ValueError:
            raise WorkspaceError("SUPER_WORKSPACE_OWNER_PID must be an integer")
    elif inherited_token or inherited_owner:
        raise WorkspaceError("inherited workspace ownership requires both token and owner pid")
    else:
        token = uuid.uuid4().hex
        owner_pid = os.getpid()

    ownership = acquire_roots(roots, owner_pid, token, "run: " + " ".join(command))
    created = ownership["created"]
    env = os.environ.copy()
    env["SUPER_WORKSPACE_TOKEN"] = token
    env["SUPER_WORKSPACE_OWNER_PID"] = str(owner_pid)
    child = None
    prior_handlers = {}

    def forward(signum, _frame):
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass

    try:
        child = subprocess.Popen(command, env=env, start_new_session=True)
        if created:
            _set_process_group(created, token, child.pid)
        for signum in (signal.SIGTERM, signal.SIGINT):
            prior_handlers[signum] = signal.signal(signum, forward)
        returncode = child.wait()
        return returncode if returncode >= 0 else 128 + abs(returncode)
    finally:
        for signum, handler in prior_handlers.items():
            signal.signal(signum, handler)
        for root in reversed(created):
            try:
                _remove_owned_lock(Path(root), token)
            except WorkspaceError as exc:
                print("workspace-state: {}".format(exc), file=sys.stderr)


def _excluded_reason(relative, internal_vault):
    parts = relative.parts
    if relative.name == SNAPSHOT_MARKER:
        return SNAPSHOT_MARKER
    if any(part == ".git" for part in parts):
        return ".git"
    if any(part == ".superagent-runtime" for part in parts):
        return ".superagent-runtime"
    if any(part == ".env" or part.startswith(".env.") for part in parts):
        return ".env"
    if internal_vault is not None:
        try:
            relative.relative_to(internal_vault)
            return "internal-vault"
        except ValueError:
            pass
    return None


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _manifest_for(root, vault):
    internal_vault = None
    if _is_within(vault, root):
        internal_vault = vault.relative_to(root)
    entries = []
    excluded = {".git", ".env", ".env.*", ".superagent-runtime", SNAPSHOT_MARKER}
    if internal_vault is not None and str(internal_vault) != ".":
        excluded.add(internal_vault.as_posix())

    def walk(directory, relative_dir):
        try:
            children = sorted(os.scandir(str(directory)), key=lambda item: item.name)
        except OSError as exc:
            raise WorkspaceError("cannot read {}: {}".format(directory, exc))
        for child in children:
            relative = relative_dir / child.name
            reason = _excluded_reason(relative, internal_vault)
            if reason:
                continue
            source = Path(child.path)
            try:
                info = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise WorkspaceError("cannot stat {}: {}".format(relative.as_posix(), exc))
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                target = os.readlink(str(source))
                if os.path.isabs(target):
                    raise WorkspaceError("absolute symlink is not allowed: {}".format(relative.as_posix()))
                try:
                    resolved = (source.parent / target).resolve(strict=True)
                except (OSError, RuntimeError):
                    raise WorkspaceError("dangling symlink is not allowed: {}".format(relative.as_posix()))
                if not _is_within(resolved, root):
                    raise WorkspaceError("external symlink is not allowed: {}".format(relative.as_posix()))
                resolved_relative = resolved.relative_to(root)
                if _excluded_reason(resolved_relative, internal_vault):
                    raise WorkspaceError("symlink targets excluded path: {}".format(relative.as_posix()))
                entries.append({"path": relative.as_posix(), "kind": "symlink",
                                "mode": mode, "target": target})
            elif stat.S_ISDIR(info.st_mode):
                entries.append({"path": relative.as_posix(), "kind": "directory", "mode": mode})
                walk(source, relative)
            elif stat.S_ISREG(info.st_mode):
                entries.append({"path": relative.as_posix(), "kind": "file", "mode": mode,
                                "sha256": _hash_file(source)})
            else:
                raise WorkspaceError("special file is not allowed: {}".format(relative.as_posix()))

    walk(root, Path())
    entries.sort(key=lambda item: item["path"])
    digest_bytes = json.dumps(entries, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8")
    source_id = "snapshot:" + hashlib.sha256(digest_bytes).hexdigest()
    return {
        "schema": 1,
        "source_root": str(root),
        "excluded_paths": sorted(excluded),
        "entries": entries,
    }, source_id


def _entry_map(manifest):
    return {entry["path"]: entry for entry in manifest["entries"]}


def _verify_copy(workspace, entries):
    for entry in entries:
        path = workspace / entry["path"]
        if entry["kind"] == "file":
            if not path.is_file() or path.is_symlink() or _hash_file(path) != entry["sha256"]:
                raise WorkspaceChanged("captured file differs from source: {}".format(entry["path"]))
            if stat.S_IMODE(path.stat().st_mode) != entry["mode"]:
                raise WorkspaceChanged("captured mode differs from source: {}".format(entry["path"]))
        elif entry["kind"] == "directory":
            if not path.is_dir() or path.is_symlink():
                raise WorkspaceChanged("captured directory differs from source: {}".format(entry["path"]))
        elif not path.is_symlink() or os.readlink(str(path)) != entry["target"]:
            raise WorkspaceChanged("captured symlink differs from source: {}".format(entry["path"]))


def create_snapshot(root_value, vault_value, out_parent_value, copy_callback=None):
    root = _physical_dir(root_value, "root")
    vault = _physical_dir(vault_value, "vault")
    out_parent = _physical_dir(out_parent_value, "out-parent")
    if _is_within(out_parent, root) or _is_within(out_parent, vault):
        raise WorkspaceError("snapshot output must be outside source and vault roots: {}".format(out_parent))

    before, source_id = _manifest_for(root, vault)
    token = uuid.uuid4().hex
    workspace = Path(tempfile.mkdtemp(prefix="superagent-snapshot-", dir=str(out_parent))).resolve()
    manifest_path = workspace.parent / (workspace.name + ".manifest.json")
    try:
        for entry in before["entries"]:
            source = root / entry["path"]
            destination = workspace / entry["path"]
            if entry["kind"] == "directory":
                destination.mkdir(exist_ok=True)
                destination.chmod(entry["mode"])
            elif entry["kind"] == "file":
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(source), str(destination))
                destination.chmod(entry["mode"])
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(entry["target"], str(destination))
            if copy_callback is not None:
                copy_callback(source, destination)

        after, after_id = _manifest_for(root, vault)
        if before["entries"] != after["entries"] or source_id != after_id:
            raise WorkspaceChanged("source changed while snapshot was being captured: {}".format(root))
        _verify_copy(workspace, before["entries"])
        manifest_path.write_text(
            json.dumps(before, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        marker = {
            "schema": 1, "token": token, "workspace": str(workspace),
            "manifest": str(manifest_path), "source_root": str(root),
        }
        (workspace / SNAPSHOT_MARKER).write_text(
            json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8"
        )
        return {"workspace": str(workspace), "manifest": str(manifest_path),
                "source_id": source_id, "token": token}
    except Exception:
        shutil.rmtree(str(workspace), ignore_errors=True)
        try:
            manifest_path.unlink()
        except FileNotFoundError:
            pass
        raise


def compare_manifests(before_path, after_path):
    def load(path):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise WorkspaceError("cannot read manifest {}: {}".format(path, exc))
        if data.get("schema") != 1 or not isinstance(data.get("entries"), list):
            raise WorkspaceError("unsupported manifest: {}".format(path))
        return _entry_map(data)

    before = load(before_path)
    after = load(after_path)
    before_paths = set(before)
    after_paths = set(after)
    return {
        "added": sorted(after_paths - before_paths),
        "modified": sorted(path for path in before_paths & after_paths if before[path] != after[path]),
        "deleted": sorted(before_paths - after_paths),
    }


def cleanup_snapshot(workspace_value, token):
    workspace = Path(workspace_value).expanduser().resolve()
    if workspace == Path("/") or workspace == Path.home().resolve():
        raise WorkspaceError("refusing unsafe cleanup target: {}".format(workspace))
    marker_path = workspace / SNAPSHOT_MARKER
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise WorkspaceError("workspace is not a helper-owned snapshot: {}".format(workspace))
    if marker.get("token") != token or marker.get("workspace") != str(workspace):
        raise WorkspaceError("snapshot cleanup token or workspace does not match")
    manifest = Path(marker.get("manifest", "")).resolve()
    if manifest.parent != workspace.parent or manifest.name != workspace.name + ".manifest.json":
        raise WorkspaceError("snapshot manifest path is unsafe: {}".format(manifest))
    shutil.rmtree(str(workspace))
    try:
        manifest.unlink()
    except FileNotFoundError:
        pass
    return {"cleaned": str(workspace)}


def _parser():
    parser = argparse.ArgumentParser(prog="workspace-state.py")
    commands = parser.add_subparsers(dest="action", required=True)

    run = commands.add_parser("run")
    run.add_argument("--root", action="append", required=True)
    run.add_argument("command", nargs=argparse.REMAINDER)

    acquire = commands.add_parser("acquire")
    acquire.add_argument("--root", action="append", required=True)
    acquire.add_argument("--owner-pid", type=int, required=True)
    acquire.add_argument("--token", required=True)
    acquire.add_argument("--operation", required=True)

    release = commands.add_parser("release")
    release.add_argument("--root", action="append", required=True)
    release.add_argument("--token", required=True)

    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--root", required=True)
    snapshot.add_argument("--vault", required=True)
    snapshot.add_argument("--out-parent", required=True)

    compare = commands.add_parser("compare")
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)

    cleanup = commands.add_parser("cleanup")
    cleanup.add_argument("--workspace", required=True)
    cleanup.add_argument("--token", required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.action == "run":
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            return run_owned(args.root, command)
        if args.action == "acquire":
            _json_print(acquire_roots(args.root, args.owner_pid, args.token, args.operation))
        elif args.action == "release":
            _json_print(release_roots(args.root, args.token))
        elif args.action == "snapshot":
            _json_print(create_snapshot(args.root, args.vault, args.out_parent))
        elif args.action == "compare":
            _json_print(compare_manifests(args.before, args.after))
        elif args.action == "cleanup":
            _json_print(cleanup_snapshot(args.workspace, args.token))
        return 0
    except WorkspaceError as exc:
        print("workspace-state: {}".format(exc), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())

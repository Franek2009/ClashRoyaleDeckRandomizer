"""Isolated, fail-closed catalog publication. No changes to the caller's checkout."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse

if __package__:
    from . import update_cards as updater
else:
    import update_cards as updater


REMOTE = "git@github.com-crdr-cards:Franek2009/ClashRoyaleDeckRandomizer.git"
COMMIT_MESSAGE = "chore(cards): sync official Clash Royale catalog"
COMPATIBILITY_SCRIPT = Path(__file__).with_name("check_catalog_compatibility.mjs")


class SyncBlocked(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def child_environment():
    # API delivery credentials are needed only by the parent fetch callback.
    excluded = {updater.TOKEN_ENV, "CREDENTIALS_DIRECTORY", "GH_TOKEN", "GITHUB_TOKEN",
                "PYTHONPATH", "PYTHONHOME", "NODE_OPTIONS", "GIT_DIR", "GIT_WORK_TREE",
                "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_SSH", "GIT_SSH_COMMAND"}
    env = {key: value for key, value in os.environ.items()
           if key not in excluded and not key.startswith(("GIT_CONFIG_", "GIT_AUTHOR_", "GIT_COMMITTER_"))}
    env.update(GIT_TERMINAL_PROMPT="0", PIP_NO_INPUT="1", CI="1",
               GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes")
    return env


def execute(command, cwd, stage, *, timeout=120, extra_env=None):
    print(f"Catalog sync: {stage}.", flush=True)
    try:
        env = child_environment()
        env.update(extra_env or {})
        with subprocess.Popen(command, cwd=cwd, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, start_new_session=True) as process:
            try:
                output, _ = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise SyncBlocked(f"{stage}_timeout") from None
            if process.returncode:
                raise SyncBlocked(stage)
            return output.strip()
    except OSError:
        raise SyncBlocked(stage) from None


def git(checkout, stage, *arguments):
    return execute(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                    "-c", "user.name=CRDR catalog sync",
                    "-c", "user.email=crdr-catalog-sync@users.noreply.github.com", *arguments], checkout, stage)


def publication_policy(current, candidate):
    updater.validate_snapshot(current)
    updater.validate_snapshot(candidate)
    diff = updater.compare_snapshots(current, candidate)
    # All removals require review; this also blocks truncated/partial API catalogs.
    if diff["removed"] or ({c["id"] for c in current["supportItems"]} - {c["id"] for c in candidate["supportItems"]}):
        raise SyncBlocked("removed_cards")
    for card in candidate["items"]:
        if not 26000000 <= card["id"] < 29000000:
            raise SyncBlocked("unknown_id_namespace")
        capability = card.get("maxEvolutionLevel", 0)
        if capability is None or (card["rarity"] == "champion" and capability):
            raise SyncBlocked("unsupported_mechanic")
        if card.get("elixirCost", 1) > 10:
            raise SyncBlocked("unsupported_elixir_cost")
    for card in diff["added"]:
        # Only the troop namespace is provisionally admitted for unseen IDs.
        # Spell/building namespaces already have known troop exceptions.
        if not 26000000 <= card["id"] < 27000000:
            raise SyncBlocked("new_card_type_requires_review")
    for card in candidate["supportItems"]:
        if not 159000000 <= card["id"] < 160000000:
            raise SyncBlocked("unknown_support_namespace")
    for card in candidate["items"] + candidate["supportItems"]:
        for url in card["iconUrls"].values():
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname != "api-assets.clashroyale.com" or parsed.username or parsed.password:
                raise SyncBlocked("unexpected_artwork_origin")


def validate_models(checkout, baseline_path):
    # This script imports the JS generator from THIS clone, not the user's source.
    js_types = json.loads(execute(
        ["node", str(COMPATIBILITY_SCRIPT), str(checkout), str(baseline_path)],
        checkout, "model_compatibility", timeout=60))
    python_code = (
        "import json; from card_model import card_type; "
        "cards=json.load(open('cards.json'))['items']; "
        "assert card_type({'id':28000016}).value == 'troop', 'R2 required'; "
        "print(json.dumps({str(c['id']):card_type(c).value for c in cards}))"
    )
    py_types = json.loads(execute([sys.executable, "-I", "-c",
        # Isolated Python normally omits cwd. Add only the tested clone explicitly.
        f"import sys; sys.path.insert(0, {str(checkout)!r}); " + python_code],
        checkout, "python_model_compatibility"))
    if js_types != py_types:
        raise SyncBlocked("classification_disagreement")


def browser_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return str(listener.getsockname()[1])


def run_project_tests(checkout):
    python = checkout / ".sync-venv/bin/python"
    execute([sys.executable, "-m", "venv", str(checkout / ".sync-venv")], checkout, "python_environment")
    execute([str(python), "-m", "pip", "install", "-r", "requirements-dev.txt"], checkout, "python_dependencies", timeout=300)
    execute(["npm", "ci", "--ignore-scripts"], checkout, "javascript_dependencies", timeout=300)
    execute(["npx", "--no-install", "playwright", "install", "chromium"], checkout, "browser_dependencies", timeout=300)
    execute([str(python), "-m", "pytest", "-q"], checkout, "python_tests", timeout=300)
    execute(["npm", "test"], checkout, "javascript_tests", timeout=180)
    execute(["npm", "run", "test:e2e"], checkout, "browser_tests", timeout=300,
            extra_env={"CRDR_E2E_PORT":browser_port()})


def success_message(current, candidate):
    before = {c["id"]: c for c in current["items"]}
    added = sum(c["id"] not in before for c in candidate["items"])
    evolutions = sum(bool((c.get("maxEvolutionLevel") or 0) & 1) and
                     not bool((before.get(c["id"], {}).get("maxEvolutionLevel") or 0) & 1)
                     for c in candidate["items"])
    heroes = sum(bool((c.get("maxEvolutionLevel") or 0) & 2) and
                 not bool((before.get(c["id"], {}).get("maxEvolutionLevel") or 0) & 2)
                 for c in candidate["items"])
    return f"CRDR: catalog updated — {added} new cards, {evolutions} new evolutions, {heroes} new heroes."


def synchronize(fetch_candidate, *, notify=False, dry_run=False, remote=REMOTE, tests=run_project_tests,
                models=validate_models):
    """The remote/runner injection is for local bare-repository tests, not CLI options."""
    directory = updater.state_directory()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    reports = directory / "sync"
    reports.mkdir(exist_ok=True, mode=0o700)
    with (directory / ".sync.lock").open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Catalog sync already running; no publication attempted.")
            return {"status": "busy"}
        result = {"status": "blocked", "reason": "initialization",
                  "checkedAt": datetime.now(timezone.utc).isoformat()}
        candidate = None
        current = None
        try:
            with tempfile.TemporaryDirectory(prefix="checkout-", dir=directory) as temporary:
                checkout = Path(temporary) / "repo"
                git(Path(temporary), "clone", "clone", "--single-branch", "--branch", "main", "--", remote, str(checkout))
                base = git(checkout, "base_revision", "rev-parse", "HEAD")
                result["base"] = base
                current = json.loads((checkout / "cards.json").read_text(encoding="utf-8"))
                candidate = fetch_candidate()
                updater.validate_snapshot(current)
                updater.validate_snapshot(candidate)
                result["candidateHash"] = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode()).hexdigest()
                updater.run_check(current, candidate, directory=reports)
                if not updater.check_report(current, candidate)["changed"]:
                    result.update(status="unchanged", reason=None)
                else:
                    publication_policy(current, candidate)
                    baseline = Path(temporary) / "baseline.json"
                    updater.write_json_atomic(baseline, current)
                    updater.write_json_atomic(checkout / "cards.json", candidate)
                    models(checkout, baseline)
                    tests(checkout)
                    # Tests must not alter the candidate, tracked code or index.
                    if git(checkout, "tested_base_revision", "rev-parse", "HEAD") != base:
                        raise SyncBlocked("unexpected_head_change")
                    if git(checkout, "tested_remote", "remote", "get-url", "origin") != remote:
                        raise SyncBlocked("unexpected_remote_change")
                    if json.loads((checkout / "cards.json").read_text()) != candidate:
                        raise SyncBlocked("candidate_modified_by_tests")
                    if git(checkout, "index_check", "diff", "--cached", "--name-only"):
                        raise SyncBlocked("unexpected_index_changes")
                    if git(checkout, "tracked_files_check", "diff", "--name-only").splitlines() != ["cards.json"]:
                        raise SyncBlocked("unexpected_tracked_changes")
                    git(checkout, "diff_check", "diff", "--check")
                    git(checkout, "refresh_remote", "fetch", "origin", "main")
                    if git(checkout, "remote_revision", "rev-parse", "origin/main") != base:
                        raise SyncBlocked("remote_advanced")
                    if dry_run:
                        result.update(status="validated", reason=None)
                    else:
                        git(checkout, "stage_catalog", "add", "--", "cards.json")
                        git(checkout, "commit_catalog", "commit", "-m", COMMIT_MESSAGE)
                        if git(checkout, "commit_files", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines() != ["cards.json"]:
                            raise SyncBlocked("unexpected_commit_files")
                        result["commit"] = git(checkout, "commit_revision", "rev-parse", "HEAD")
                        git(checkout, "push_rejected_or_unavailable", "push", "origin", "HEAD:refs/heads/main")
                        result.update(status="pushed", reason=None)
        except SyncBlocked as error:
            result["reason"] = error.reason
            if error.reason == "push_rejected_or_unavailable":
                result["remoteOutcome"] = "unconfirmed"
        except updater.UpdateError as error:
            result["reason"] = "api_or_credential_failure"
            result["detail"] = str(error)  # Controlled diagnostics only.
        except (ValueError, TypeError, KeyError):
            result["reason"] = "invalid_schema_or_model_output"
        except OSError:
            result["reason"] = "local_io_failure"
        try:
            updater.write_json_atomic(reports / "result.json", result)
        except OSError:
            print("Catalog sync result could not be saved; verify journal status and remote.", flush=True)
        print(f'Catalog sync: {result["status"]}; reason={result["reason"]}.', flush=True)
        if result.get("detail"):
            print(f'Catalog sync detail: {result["detail"]}', flush=True)
        if result["status"] == "pushed":
            print(success_message(current, candidate), flush=True)
        if notify and result["status"] in {"pushed", "blocked"}:
            # Failed attempts can produce different commit timestamps/SHAs. Those
            # must not cause repeated notifications for an otherwise identical failure.
            identity = {key: result.get(key) for key in ("status", "reason", "detail", "base", "candidateHash")}
            fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            message = success_message(current, candidate) if result["status"] == "pushed" else "CRDR: catalog update requires attention."
            updater.notify_changes(reports, fingerprint, title=message, message="See sync/result.json and journalctl. GitHub Pages deployment is a separate CI step.")
        return result

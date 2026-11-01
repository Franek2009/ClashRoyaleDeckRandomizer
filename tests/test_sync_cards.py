"""Publication tests use local bare Git repositories, never GitHub or real secrets."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts import sync_cards as sync
from scripts import update_cards as updater

ROOT = Path(__file__).resolve().parents[1]


def local_git(cwd, *arguments):
    return subprocess.check_output([
        "git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *arguments
    ], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()


@pytest.fixture
def repository(monkeypatch, tmp_path):
    # Never inspect actual API/GitHub credential environment variables.
    monkeypatch.setattr(sync.os, "environ", {"PATH":"/usr/bin:/bin", "XDG_STATE_HOME":str(tmp_path / "state"),
        "GIT_CONFIG_GLOBAL":"/dev/null", "GIT_CONFIG_NOSYSTEM":"1"})
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    seed.mkdir()
    local_git(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))
    local_git(seed, "init", "--initial-branch=main")
    for file in ["cards.json", "card_model.py", "package.json"]:
        shutil.copy2(ROOT / file, seed / file)
    (seed / "static").mkdir()
    shutil.copy2(ROOT / "static/randomizer.js", seed / "static/randomizer.js")
    (seed / "README.md").write_text("test fixture\n")
    local_git(seed, "add", ".")
    local_git(seed, "commit", "-m", "baseline")
    local_git(seed, "remote", "add", "origin", str(remote))
    local_git(seed, "push", "origin", "main")
    snapshot = json.loads((seed / "cards.json").read_text())
    return seed, remote, snapshot


def new_card(snapshot):
    candidate = deepcopy(snapshot)
    existing = {card["id"] for card in candidate["items"]}
    card_id = next(card_id for card_id in range(26999990, 26999800, -1) if card_id not in existing)
    candidate["items"].append({"id":card_id, "name":"New test troop", "rarity":"common", "maxLevel":16,
        "elixirCost":3, "iconUrls":{"medium":"https://api-assets.clashroyale.com/test.png"}})
    return candidate


def synchronize(repository, candidate, **options):
    seed, remote, current = repository
    before_status = local_git(seed, "status", "--porcelain")
    before_bytes = (seed / "cards.json").read_bytes()
    tested = []

    def tests(checkout):
        assert checkout != seed
        assert json.loads((checkout / "cards.json").read_text()) == candidate
        tested.append(checkout)

    result = sync.synchronize(lambda: deepcopy(candidate), remote=str(remote),
        tests=options.pop("tests", tests), models=options.pop("models", lambda *args: None), **options)
    assert local_git(seed, "status", "--porcelain") == before_status
    assert (seed / "cards.json").read_bytes() == before_bytes
    return result, tested


def remote_catalog(remote):
    return json.loads(local_git(remote, "show", "main:cards.json"))


def test_no_changes_no_tests_commit_or_push(repository):
    _, remote, current = repository
    head = local_git(remote, "rev-parse", "main")
    result, tested = synchronize(repository, current)
    assert result["status"] == "unchanged"
    assert tested == []
    assert local_git(remote, "rev-parse", "main") == head


def test_new_card_is_tested_and_only_catalog_committed(repository):
    _, remote, current = repository
    candidate = new_card(current)
    result, tested = synchronize(repository, candidate)
    assert result["status"] == "pushed"
    assert len(tested) == 1
    assert not tested[0].exists()  # isolated checkout is cleaned
    assert remote_catalog(remote) == candidate
    assert local_git(remote, "diff-tree", "--no-commit-id", "--name-only", "-r", "main") == "cards.json"
    assert local_git(remote, "log", "-1", "--format=%s", "main") == sync.COMMIT_MESSAGE


def test_repeat_after_success_creates_no_duplicate_commit(repository):
    _, remote, current = repository
    candidate = new_card(current)
    first, _ = synchronize(repository, candidate)
    second, tested = synchronize(repository, candidate)
    assert first["status"] == "pushed"
    assert second["status"] == "unchanged"
    assert tested == []
    assert local_git(remote, "rev-list", "--count", "main") == "2"


@pytest.mark.parametrize("capability,artwork", [(1, "evolutionMedium"), (2, "heroMedium")])
def test_new_supported_form_is_published(repository, capability, artwork):
    _, remote, current = repository
    candidate = deepcopy(current)
    card = next(c for c in candidate["items"] if not c.get("maxEvolutionLevel") and c["rarity"] != "champion")
    card["maxEvolutionLevel"] = capability
    card["iconUrls"][artwork] = "https://api-assets.clashroyale.com/new-form.png"
    result, _ = synchronize(repository, candidate)
    assert result["status"] == "pushed"
    assert remote_catalog(remote) == candidate


@pytest.mark.parametrize("damage,reason", [
    ("mechanic", "invalid_schema_or_model_output"), ("unknown-id", "unknown_id_namespace"),
    ("removed", "removed_cards"), ("spell", "new_card_type_requires_review"),
    ("artwork", "unexpected_artwork_origin"), ("duplicate", "invalid_schema_or_model_output"),
])
def test_unsafe_changes_never_publish(repository, damage, reason):
    _, remote, current = repository
    candidate = new_card(current)
    if damage == "mechanic":
        candidate["items"][-1]["maxEvolutionLevel"] = 4
    elif damage == "unknown-id":
        candidate["items"][-1]["id"] = 30000000
    elif damage == "removed":
        candidate["items"].pop(0)
    elif damage == "spell":
        candidate["items"][-1]["id"] = 28999990
    elif damage == "artwork":
        candidate["items"][-1]["iconUrls"]["medium"] = "https://example.com/untrusted.png"
    else:
        candidate["items"].append(deepcopy(candidate["items"][0]))
    result, tested = synchronize(repository, candidate)
    assert result["status"] == "blocked"
    assert result["reason"] == reason
    assert tested == []
    assert remote_catalog(remote) == current


def test_failed_tests_do_not_publish(repository):
    _, remote, current = repository

    def fail(checkout):
        raise sync.SyncBlocked("browser_tests")

    result, _ = synchronize(repository, new_card(current), tests=fail)
    assert result["reason"] == "browser_tests"
    assert remote_catalog(remote) == current


def test_offline_preserves_catalog(repository):
    _, remote, current = repository

    def offline():
        raise updater.UpdateError("cards download failed: network or TLS error")

    result = sync.synchronize(offline, remote=str(remote))
    assert result["reason"] == "api_or_credential_failure"
    assert remote_catalog(remote) == current


def test_rejected_push_never_uses_force(repository):
    _, remote, current = repository
    hook = remote / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o700)
    # Our Git wrapper disables local hooks; the bare server's receive hook still runs.
    result, _ = synchronize(repository, new_card(current))
    assert result["status"] == "blocked"
    assert result["reason"] == "push_rejected_or_unavailable"
    assert remote_catalog(remote) == current


def test_remote_advancing_during_tests_aborts_without_merge(repository):
    seed, remote, current = repository

    def advance(checkout):
        (seed / "README.md").write_text("remote changed\n")
        local_git(seed, "add", "README.md")
        local_git(seed, "commit", "-m", "remote advance")
        local_git(seed, "push", "origin", "main")

    result = sync.synchronize(lambda: new_card(current), remote=str(remote), tests=advance, models=lambda *args: None)
    assert result["reason"] == "remote_advanced"
    assert remote_catalog(remote) == current


def test_two_syncs_cannot_race(repository):
    _, remote, current = repository
    directory = updater.state_directory()
    directory.mkdir(parents=True)
    with (directory / ".sync.lock").open("a") as lock:
        sync.fcntl.flock(lock, sync.fcntl.LOCK_EX)
        result, tested = synchronize(repository, new_card(current))
    assert result["status"] == "busy"
    assert tested == []
    assert remote_catalog(remote) == current


def test_current_missing_r2_blocks_actual_model_gate(repository):
    seed, remote, current = repository
    # Make the defect explicit so this regression still works after R2 ships.
    (seed / "static/randomizer.js").write_text('export const cardType = () => "spell";\n')
    local_git(seed, "add", "static/randomizer.js")
    local_git(seed, "commit", "-m", "missing R2 fixture")
    local_git(seed, "push", "origin", "main")
    result, tested = synchronize(repository, new_card(current), models=sync.validate_models)
    assert result["reason"] == "model_compatibility"
    assert tested == []
    assert remote_catalog(remote) == current


def test_model_gate_uses_candidate_and_both_r2_fixed_models(repository):
    seed, remote, current = repository
    js = seed / "static/randomizer.js"
    js.write_text(js.read_text().replace("card.id === 27000010 ||", "card.id === 28000016 || card.id === 27000010 ||"))
    py = seed / "card_model.py"
    py.write_text(py.read_text().replace("CARD_TYPE_OVERRIDES = {", "CARD_TYPE_OVERRIDES = {\n    28000016: CardType.TROOP,"))
    local_git(seed, "add", ".")
    local_git(seed, "commit", "-m", "R2 fixture only")
    local_git(seed, "push", "origin", "main")
    result, tested = synchronize(repository, new_card(current), models=sync.validate_models)
    assert result["status"] == "pushed"
    assert len(tested) == 1


def test_changed_tracked_code_or_index_during_tests_blocks_commit(repository):
    _, remote, current = repository

    def mutate(checkout):
        (checkout / "README.md").write_text("unexpected edit\n")

    result, _ = synchronize(repository, new_card(current), tests=mutate)
    assert result["reason"] == "unexpected_tracked_changes"
    assert remote_catalog(remote) == current


def test_child_commands_never_receive_api_or_github_tokens(monkeypatch):
    monkeypatch.setattr(sync.os, "environ", {
        updater.TOKEN_ENV:"synthetic-api", "CREDENTIALS_DIRECTORY":"/fake", "GH_TOKEN":"synthetic-gh",
        "GITHUB_TOKEN":"synthetic-github", "GIT_CONFIG_COUNT":"1", "NODE_OPTIONS":"--inspect", "PATH":"/usr/bin"})
    env = sync.child_environment()
    assert not set(env) & {updater.TOKEN_ENV, "CREDENTIALS_DIRECTORY", "GH_TOKEN", "GITHUB_TOKEN", "GIT_CONFIG_COUNT", "NODE_OPTIONS"}
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_default_tests_run_in_candidate_checkout_with_bounded_commands(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(sync, "browser_port", lambda: "4187")
    monkeypatch.setattr(sync, "execute", lambda args, cwd, stage, **kwargs: calls.append((args, cwd, stage)))
    sync.run_project_tests(tmp_path)
    assert all(cwd == tmp_path for args, cwd, stage in calls)
    assert {stage for args, cwd, stage in calls} >= {"python_tests", "javascript_tests", "browser_tests"}


def test_dry_run_runs_validation_without_commit_or_push(repository):
    _, remote, current = repository
    before = local_git(remote, "rev-parse", "main")
    result, tested = synchronize(repository, new_card(current), dry_run=True)
    assert result["status"] == "validated"
    assert len(tested) == 1
    assert "commit" not in result
    assert local_git(remote, "rev-parse", "main") == before


@pytest.mark.parametrize("mutation,reason", [("head", "unexpected_head_change"), ("remote", "unexpected_remote_change"), ("candidate", "candidate_modified_by_tests"), ("index", "unexpected_index_changes")])
def test_tests_cannot_change_git_or_candidate_before_publication(repository, mutation, reason):
    _, remote, current = repository

    def mutate(checkout):
        if mutation == "head":
            local_git(checkout, "commit", "--allow-empty", "-m", "unexpected")
        elif mutation == "remote":
            local_git(checkout, "remote", "set-url", "origin", "/not-the-approved-remote")
        elif mutation == "candidate":
            (checkout / "cards.json").write_text(json.dumps(current))
        else:
            local_git(checkout, "add", "cards.json")

    result, _ = synchronize(repository, new_card(current), tests=mutate)
    assert result["reason"] == reason
    assert remote_catalog(remote) == current


def test_failed_sync_notifications_have_a_stable_fingerprint(repository, monkeypatch):
    _, remote, current = repository
    seen = []
    monkeypatch.setattr(updater, "notify_changes", lambda directory, fingerprint, **kwargs: seen.append((fingerprint, kwargs["title"])))

    def failed(checkout):
        raise sync.SyncBlocked("javascript_tests")

    for attempt in range(2):
        synchronize(repository, new_card(current), tests=failed, notify=True)
    assert seen[0] == seen[1]
    assert seen[0][1] == "CRDR: catalog update requires attention."


def test_sync_cli_passes_validated_candidate_without_reading_active_catalog(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.sys, "argv", ["update_cards.py", "--sync", "--dry-run"])
    monkeypatch.setattr(updater, "read_token", lambda: "synthetic-api-token")
    snapshot = json.loads((ROOT / "cards.json").read_text())
    monkeypatch.setattr(updater, "fetch_snapshot", lambda token: snapshot)
    monkeypatch.setattr(updater, "CARDS_PATH", tmp_path / "does-not-exist.json")
    calls = []

    def isolated(fetch, **kwargs):
        calls.append((fetch(), kwargs))
        return {"status":"validated"}

    monkeypatch.setattr(sync, "synchronize", isolated)
    assert updater.cli() == 0
    assert calls[0][0] == snapshot
    assert calls[0][1]["dry_run"] is True


@pytest.mark.parametrize("js_fixed,python_fixed,blocked_stage", [
    (False, False, "model_compatibility"),
    (False, True, "model_compatibility"),
    (True, False, "python_model_compatibility"),
    (True, True, None),
])
def test_r2_gate_requires_both_real_models(repository, js_fixed, python_fixed, blocked_stage):
    seed, _, _ = repository
    if not js_fixed:
        model = seed / "static/randomizer.js"
        source = model.read_text()
        assert " || card.id === 28000016" in source
        model.write_text(source.replace(" || card.id === 28000016", ""))
    if not python_fixed:
        model = seed / "card_model.py"
        model.write_text("\n".join(line for line in model.read_text().splitlines() if "28000016:" not in line) + "\n")
    if blocked_stage:
        with pytest.raises(sync.SyncBlocked) as error:
            sync.validate_models(seed, seed / "cards.json")
        assert error.value.reason == blocked_stage
    else:
        sync.validate_models(seed, seed / "cards.json")


def test_real_r2_models_allow_sync_dry_run_without_fixture_patching(repository):
    _, remote, current = repository
    before = local_git(remote, "rev-parse", "main")
    result, tested = synchronize(repository, new_card(current), dry_run=True, models=sync.validate_models)
    assert result["status"] == "validated"
    assert len(tested) == 1
    assert local_git(remote, "rev-parse", "main") == before

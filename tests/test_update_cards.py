from copy import deepcopy
import io
import json
import subprocess
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from scripts import update_cards as updater
from scripts.update_cards import compare_snapshots, validate_snapshot


def make_card(
    card_id,
    name,
    *,
    capability=None,
    elixir_cost=3,
):
    icons = {"medium": f"https://example.com/{card_id}.png"}
    if capability is not None and capability & 1:
        icons["evolutionMedium"] = f"https://example.com/{card_id}-evo.png"
    if capability is not None and capability & 2:
        icons["heroMedium"] = f"https://example.com/{card_id}-hero.png"

    card = {
        "id": card_id,
        "name": name,
        "maxLevel": 16,
        "rarity": "common",
        "iconUrls": icons,
    }
    if capability is not None:
        card["maxEvolutionLevel"] = capability
    if elixir_cost is not None:
        card["elixirCost"] = elixir_cost
    return card


@pytest.fixture
def valid_snapshot():
    return {
        "items": [
            make_card(26000000, "Knight", capability=3),
            make_card(28000006, "Mirror", elixir_cost=None),
        ],
        "supportItems": [],
    }


def test_valid_snapshot_passes_validation(valid_snapshot):
    validate_snapshot(valid_snapshot)


def test_duplicate_card_id_is_rejected(valid_snapshot):
    valid_snapshot["items"].append(deepcopy(valid_snapshot["items"][0]))

    with pytest.raises(ValueError, match="duplicate card id"):
        validate_snapshot(valid_snapshot)


def test_missing_required_field_is_rejected(valid_snapshot):
    del valid_snapshot["items"][0]["name"]

    with pytest.raises(ValueError, match="no valid name"):
        validate_snapshot(valid_snapshot)


@pytest.mark.parametrize("capability", [0, 4, True, "1"])
def test_invalid_max_evolution_level_is_rejected(
    valid_snapshot, capability
):
    valid_snapshot["items"][0]["maxEvolutionLevel"] = capability

    with pytest.raises(ValueError, match="invalid maxEvolutionLevel"):
        validate_snapshot(valid_snapshot)


def test_evolution_bit_without_artwork_is_rejected(valid_snapshot):
    del valid_snapshot["items"][0]["iconUrls"]["evolutionMedium"]

    with pytest.raises(ValueError, match="inconsistent Evo metadata"):
        validate_snapshot(valid_snapshot)


def test_hero_artwork_without_bit_is_rejected(valid_snapshot):
    card = valid_snapshot["items"][0]
    card["maxEvolutionLevel"] = 1

    with pytest.raises(ValueError, match="inconsistent Hero metadata"):
        validate_snapshot(valid_snapshot)


def test_empty_medium_artwork_is_rejected(valid_snapshot):
    valid_snapshot["items"][0]["iconUrls"]["medium"] = "   "

    with pytest.raises(ValueError, match="no medium artwork"):
        validate_snapshot(valid_snapshot)


def test_non_string_evolution_artwork_is_rejected(valid_snapshot):
    valid_snapshot["items"][0]["iconUrls"]["evolutionMedium"] = 123

    with pytest.raises(ValueError, match="invalid Evo artwork"):
        validate_snapshot(valid_snapshot)


def test_empty_hero_artwork_is_rejected(valid_snapshot):
    valid_snapshot["items"][0]["iconUrls"]["heroMedium"] = ""

    with pytest.raises(ValueError, match="invalid Hero artwork"):
        validate_snapshot(valid_snapshot)


def test_mirror_may_omit_elixir_cost(valid_snapshot):
    mirror = valid_snapshot["items"][1]

    assert mirror["id"] == 28000006
    assert "elixirCost" not in mirror
    validate_snapshot(valid_snapshot)


def test_regular_card_without_elixir_cost_is_rejected(valid_snapshot):
    del valid_snapshot["items"][0]["elixirCost"]

    with pytest.raises(ValueError, match="Mirror must be the only card"):
        validate_snapshot(valid_snapshot)


def test_snapshot_diff_detects_added_removed_and_changed_cards():
    unchanged_support_items = [{"id": 159000000, "name": "Tower Princess"}]
    removed = make_card(26000000, "Removed")
    changed_before = make_card(26000001, "Changed", elixir_cost=3)
    changed_after = make_card(26000001, "Changed", elixir_cost=4)
    added = make_card(26000002, "Added")
    current = {
        "items": [removed, changed_before],
        "supportItems": unchanged_support_items,
    }
    candidate = {
        "items": [changed_after, added],
        "supportItems": deepcopy(unchanged_support_items),
    }

    result = compare_snapshots(current, candidate)

    assert [card["id"] for card in result["added"]] == [26000002]
    assert [card["id"] for card in result["removed"]] == [26000000]
    assert [card["id"] for card in result["changed"]] == [26000001]
    assert result["changed"][0]["before"] == changed_before
    assert result["changed"][0]["after"] == changed_after
    assert result["supportItemsChanged"] is False


@pytest.fixture
def check_environment(monkeypatch, tmp_path, valid_snapshot):
    # Replace the environment rather than inspecting real credential variables.
    monkeypatch.setattr(updater.os, "environ", {
        updater.TOKEN_ENV: "synthetic-api-token-for-tests",
        "XDG_STATE_HOME": str(tmp_path / "state"),
    })
    path = tmp_path / "cards.json"
    path.write_text(json.dumps(valid_snapshot), encoding="utf-8")
    monkeypatch.setattr(updater, "CARDS_PATH", path)
    monkeypatch.setattr(updater.sys, "argv", ["update_cards.py", "--check"])
    monkeypatch.setattr("builtins.input", lambda *args: pytest.fail("check must never prompt"))
    return path, tmp_path / "state/crdr-card-updater"


def mock_response(monkeypatch, snapshot):
    requests = []

    def open_response(request, timeout):
        requests.append((request, timeout))
        response = io.StringIO(json.dumps(snapshot))
        response.status = 200
        return response

    monkeypatch.setattr(updater, "open_api_request", open_response)
    return requests


def test_check_unchanged_uses_official_request_without_writing_catalog(
    monkeypatch, check_environment, valid_snapshot, capsys
):
    path, directory = check_environment
    before = path.read_bytes()
    requests = mock_response(monkeypatch, valid_snapshot)
    assert updater.cli() == 0
    assert path.read_bytes() == before
    assert not (directory / "candidate.json").exists()
    assert json.loads((directory / "status.json").read_text())["changed"] is False
    request, timeout = requests[0]
    assert request.full_url == updater.API_URL
    assert request.get_header("Authorization") == "Bearer synthetic-api-token-for-tests"
    assert timeout == 30
    assert "unchanged" in capsys.readouterr().out


def test_check_writes_valid_candidate_and_classified_reports(
    monkeypatch, check_environment, valid_snapshot
):
    path, directory = check_environment
    before = path.read_bytes()
    candidate = deepcopy(valid_snapshot)
    candidate["items"][0]["elixirCost"] = 4
    candidate["items"][0]["rarity"] = "rare"
    candidate["items"][0]["maxEvolutionLevel"] = 1
    del candidate["items"][0]["iconUrls"]["heroMedium"]
    candidate["items"][0]["iconUrls"]["medium"] = "https://example.com/new.png"
    candidate["items"].append(make_card(26000002, "New"))
    mock_response(monkeypatch, candidate)
    assert updater.cli() == 0
    saved = json.loads((directory / "candidate.json").read_text())
    updater.validate_snapshot(saved)
    assert saved == candidate
    report = json.loads((directory / "diff.json").read_text())
    assert report["gameplayChanged"] is True
    assert report["metadataChanged"] is True
    assert report["cards"]["added"][0]["id"] == 26000002
    assert report["cards"]["changed"][0]["category"] == "gameplay"
    text = (directory / "diff.txt").read_text()
    assert "elixirCost: 3 -> 4" in text
    assert 'rarity: "common" -> "rare"' in text
    assert "Hero=False" in text
    assert "https://example.com/new.png" in text
    assert path.read_bytes() == before
    assert all("synthetic-api-token-for-tests" not in p.read_text() for p in directory.iterdir() if p.is_file())


def test_metadata_only_removals_and_support_changes(valid_snapshot):
    changed = deepcopy(valid_snapshot)
    changed["items"][0]["name"] = "Renamed Knight"
    changed["items"][0]["iconUrls"]["medium"] = "https://example.com/renamed.png"
    report = updater.check_report(valid_snapshot, changed)
    assert report["gameplayChanged"] is False
    assert report["metadataChanged"] is True
    assert report["cards"]["changed"][0]["category"] == "metadata-only"
    removed = deepcopy(valid_snapshot)
    removed["items"].pop(0)
    report = updater.check_report(valid_snapshot, removed)
    assert report["cards"]["removed"][0]["id"] == 26000000
    assert report["gameplayChanged"] is True
    support = deepcopy(valid_snapshot)
    support["supportItems"].append(make_card(159000000, "Tower", elixir_cost=None))
    updater.validate_snapshot(support)
    assert updater.check_report(valid_snapshot, support)["supportItems"]["added"][0]["id"] == 159000000


@pytest.mark.parametrize("code", [401, 403])
def test_http_failure_preserves_previous_reports_and_redacts_server_errors(
    monkeypatch, check_environment, valid_snapshot, capsys, code
):
    path, directory = check_environment
    before = path.read_bytes()
    changed = deepcopy(valid_snapshot)
    changed["items"][0]["elixirCost"] = 4
    updater.run_check(valid_snapshot, changed)
    previous = {p.name:p.read_bytes() for p in directory.iterdir()}

    def denied(*args, **kwargs):
        raise HTTPError(updater.API_URL, code, "synthetic-api-token-for-tests", {}, io.BytesIO(b"private response"))

    monkeypatch.setattr(updater, "open_api_request", denied)
    assert updater.cli() == 1
    output = capsys.readouterr()
    assert f"HTTP {code}" in output.err
    assert "synthetic-api-token-for-tests" not in output.out + output.err
    assert "private response" not in output.out + output.err
    assert path.read_bytes() == before
    assert {p.name:p.read_bytes() for p in directory.iterdir()} == previous


@pytest.mark.parametrize("error", [TimeoutError("synthetic-api-token-for-tests"), URLError("synthetic-api-token-for-tests")])
def test_network_failures_are_safe(monkeypatch, check_environment, capsys, error):
    path, directory = check_environment
    before = path.read_bytes()

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(updater, "open_api_request", fail)
    assert updater.cli() == 1
    output = capsys.readouterr()
    assert "synthetic-api-token-for-tests" not in output.out + output.err
    assert path.read_bytes() == before
    assert not (directory / "candidate.json").exists()


@pytest.mark.parametrize("damage", ["items", "duplicate", "unknown", "rarity", "capability", "support", "artwork", "reflected-token"])
def test_unexpected_schema_never_publishes_candidate(
    monkeypatch, check_environment, valid_snapshot, capsys, damage
):
    path, directory = check_environment
    before = path.read_bytes()
    candidate = deepcopy(valid_snapshot)
    if damage == "items":
        candidate["items"] = {}
    elif damage == "duplicate":
        candidate["items"].append(candidate["items"][0])
    elif damage == "unknown":
        candidate["newSchema"] = "unexpected"
    elif damage == "rarity":
        candidate["items"][0]["rarity"] = "new-rarity"
    elif damage == "capability":
        candidate["items"][0]["maxEvolutionLevel"] = 4
    elif damage == "support":
        candidate["supportItems"] = [{"id": 159000000}]
    elif damage == "artwork":
        candidate["items"][0]["iconUrls"]["newForm"] = "https://example.com/new.png"
    else:
        candidate["items"][0]["name"] = "synthetic-api-token-for-tests"
    mock_response(monkeypatch, candidate)
    assert updater.cli() == 1
    assert path.read_bytes() == before
    assert not (directory / "candidate.json").exists()
    output = capsys.readouterr()
    assert "synthetic-api-token-for-tests" not in output.out + output.err


def test_credentials_have_priority_and_missing_credential_does_not_fall_back(
    monkeypatch, check_environment, tmp_path
):
    credentials = tmp_path / "fake-credentials"
    credentials.mkdir()
    monkeypatch.setitem(updater.os.environ, "CREDENTIALS_DIRECTORY", str(credentials))
    with pytest.raises(updater.UpdateError, match="cannot read"):
        updater.read_token()
    (credentials / "crdr-api").write_text("synthetic-file-credential\n")
    assert updater.read_token() == "synthetic-file-credential"


@pytest.mark.parametrize("token", ["", "   ", "broken\nheader", "broken\x00header"])
def test_invalid_credentials_are_not_logged(monkeypatch, check_environment, capsys, token):
    monkeypatch.setitem(updater.os.environ, updater.TOKEN_ENV, token)
    assert updater.cli() == 1
    output = capsys.readouterr()
    assert "broken" not in output.err


def test_state_directory_uses_xdg_and_fallback(monkeypatch, check_environment, tmp_path):
    monkeypatch.setattr(updater.Path, "home", lambda: tmp_path)
    assert updater.state_directory() == tmp_path / "state/crdr-card-updater"
    for value in ("", "relative/path"):
        monkeypatch.setitem(updater.os.environ, "XDG_STATE_HOME", value)
        assert updater.state_directory() == tmp_path / ".local/state/crdr-card-updater"


def test_notification_is_optional_and_deduplicated_after_success(
    monkeypatch, check_environment, valid_snapshot
):
    _, directory = check_environment
    candidate = deepcopy(valid_snapshot)
    candidate["items"][0]["elixirCost"] = 4
    calls = []
    monkeypatch.setattr(updater.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(returncode=0))
    updater.run_check(valid_snapshot, candidate)
    assert calls == []
    updater.run_check(valid_snapshot, candidate, notify=True)
    updater.run_check(valid_snapshot, candidate, notify=True)
    assert len(calls) == 1
    assert updater.TOKEN_ENV not in calls[0][1]["env"]
    assert "CREDENTIALS_DIRECTORY" not in calls[0][1]["env"]
    assert len(json.loads((directory / "notified.json").read_text())) == 1
    # A different diff gets its own notification.
    candidate["items"][0]["elixirCost"] = 5
    updater.run_check(valid_snapshot, candidate, notify=True)
    assert len(calls) == 2


@pytest.mark.parametrize("failure", ["exit", "missing", "timeout"])
def test_notification_failure_does_not_fail_check(
    monkeypatch, check_environment, valid_snapshot, failure, capsys
):
    _, directory = check_environment
    candidate = deepcopy(valid_snapshot)
    candidate["items"][0]["elixirCost"] = 4
    mock_response(monkeypatch, candidate)
    monkeypatch.setattr(updater.sys, "argv", ["update_cards.py", "--check", "--notify"])

    def fail(*args, **kwargs):
        if failure == "missing":
            raise FileNotFoundError("synthetic-api-token-for-tests")
        if failure == "timeout":
            raise subprocess.TimeoutExpired("synthetic-api-token-for-tests", 5)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(updater.subprocess, "run", fail)
    assert updater.cli() == 0
    assert (directory / "candidate.json").exists()
    assert not (directory / "notified.json").exists()
    output = capsys.readouterr()
    assert "Notification unavailable" in output.out
    assert "synthetic-api-token-for-tests" not in output.out + output.err


def test_preview_and_apply_keep_the_explicit_confirmation_workflow(
    monkeypatch, check_environment, valid_snapshot, capsys
):
    path, _ = check_environment
    before = path.read_bytes()
    candidate = deepcopy(valid_snapshot)
    candidate["items"][0]["elixirCost"] = 4
    mock_response(monkeypatch, candidate)
    monkeypatch.setattr(updater.sys, "argv", ["update_cards.py"])
    assert updater.cli() == 0
    assert path.read_bytes() == before
    assert "Preview only" in capsys.readouterr().out
    monkeypatch.setattr(updater.sys, "argv", ["update_cards.py", "--apply"])
    monkeypatch.setattr("builtins.input", lambda *args: "NO")
    assert updater.cli() == 0
    assert path.read_bytes() == before
    monkeypatch.setattr("builtins.input", lambda *args: "REPLACE cards.json")
    assert updater.cli() == 0
    assert json.loads(path.read_text()) == candidate
    assert list(path.parent.glob("cards.*.json.tmp")) == []


@pytest.mark.parametrize("args", [["--check", "--apply"], ["--notify"]])
def test_incompatible_cli_modes_are_rejected(monkeypatch, args):
    monkeypatch.setattr(updater.sys, "argv", ["update_cards.py", *args])
    with pytest.raises(SystemExit) as error:
        updater.parse_args()
    assert error.value.code == 2


def test_redirect_destinations_never_receive_an_authorized_request(monkeypatch):
    request = updater.Request(updater.API_URL, headers={"Authorization":"Bearer synthetic-api-token-for-tests"})
    assert updater.NoRedirect().redirect_request(request, None, 302, "Found", {}, "https://example.com/") is None
    calls = []
    opener = SimpleNamespace(open=lambda request, **kwargs: calls.append((request, kwargs)))
    monkeypatch.setattr(updater, "build_opener", lambda handler: opener if handler is updater.NoRedirect else pytest.fail("redirect guard missing"))
    updater.open_api_request(request, timeout=30)
    assert calls == [(request, {"timeout":30})]


def test_malformed_api_json_is_reported_without_response_body(
    monkeypatch, check_environment, capsys
):
    def invalid_response(*args, **kwargs):
        response = io.StringIO('synthetic-api-token-for-tests invalid JSON')
        response.status = 200
        return response

    monkeypatch.setattr(updater, "open_api_request", invalid_response)
    assert updater.cli() == 1
    assert "synthetic-api-token-for-tests" not in capsys.readouterr().err


def test_api_list_reordering_is_unchanged(valid_snapshot):
    reordered = deepcopy(valid_snapshot)
    reordered["items"].reverse()
    assert updater.check_report(valid_snapshot, reordered)["changed"] is False


def test_schema_failure_retains_existing_validated_candidate(
    monkeypatch, check_environment, valid_snapshot
):
    _, directory = check_environment
    changed = deepcopy(valid_snapshot)
    changed["items"][0]["elixirCost"] = 4
    updater.run_check(valid_snapshot, changed)
    previous = {p.name:p.read_bytes() for p in directory.iterdir()}
    changed["items"][0]["rarity"] = ["unexpected"]
    mock_response(monkeypatch, changed)
    assert updater.cli() == 1
    assert {p.name:p.read_bytes() for p in directory.iterdir()} == previous


def test_report_lock_prevents_overlapping_notifications(
    monkeypatch, check_environment, valid_snapshot
):
    _, directory = check_environment
    directory.mkdir(parents=True)
    candidate = deepcopy(valid_snapshot)
    candidate["items"][0]["elixirCost"] = 4
    monkeypatch.setattr(updater.subprocess, "run", lambda *args, **kwargs: pytest.fail("overlapping notification"))
    with (directory / ".check.lock").open("a") as lock:
        updater.fcntl.flock(lock, updater.fcntl.LOCK_EX)
        updater.run_check(valid_snapshot, candidate, notify=True)
    assert not (directory / "candidate.json").exists()


def test_notification_marker_write_failure_is_nonfatal(
    monkeypatch, check_environment, valid_snapshot
):
    _, directory = check_environment
    candidate = deepcopy(valid_snapshot)
    candidate["items"][0]["elixirCost"] = 4
    write = updater.write_json_atomic

    def write_without_marker(path, value):
        if path.name == "notified.json":
            raise OSError("synthetic-api-token-for-tests")
        return write(path, value)

    monkeypatch.setattr(updater, "write_json_atomic", write_without_marker)
    monkeypatch.setattr(updater.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    updater.run_check(valid_snapshot, candidate, notify=True)
    assert json.loads((directory / "status.json").read_text())["changed"] is True


def test_unchanged_check_marks_older_candidate_as_historical(
    monkeypatch, check_environment, valid_snapshot
):
    _, directory = check_environment
    candidate = deepcopy(valid_snapshot)
    candidate["items"][0]["elixirCost"] = 4
    updater.run_check(valid_snapshot, candidate)
    old_candidate = (directory / "candidate.json").read_bytes()
    monkeypatch.setattr(updater.subprocess, "run", lambda *args, **kwargs: pytest.fail("unchanged notification"))
    updater.run_check(valid_snapshot, valid_snapshot, notify=True)
    assert json.loads((directory / "status.json").read_text())["changed"] is False
    assert (directory / "candidate.json").read_bytes() == old_candidate

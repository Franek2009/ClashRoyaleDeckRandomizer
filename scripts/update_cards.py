#!/usr/bin/env python3
"""Check, preview and explicitly apply official card snapshots; never log tokens."""

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_URL = "https://api.clashroyale.com/v1/cards"
TOKEN_ENV = "CLASH_ROYALE_API_TOKEN"
ROOT = Path(__file__).resolve().parents[1]
CARDS_PATH = ROOT / "cards.json"
ALLOWED_RARITIES = {"common", "rare", "epic", "legendary", "champion"}
ALLOWED_CAPABILITIES = {1, 2, 3}
MIRROR_ID = 28000006
CARD_FIELDS = {"id", "name", "rarity", "maxLevel", "maxEvolutionLevel", "iconUrls", "elixirCost"}
GAMEPLAY_FIELDS = {"id", "rarity", "maxLevel", "maxEvolutionLevel", "elixirCost"}


class UpdateError(RuntimeError):
    """A controlled diagnostic safe for terminal/journal output."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        # Do not forward Authorization to a redirect destination.
        return None


def open_api_request(request, timeout):
    return build_opener(NoRedirect).open(request, timeout=timeout)


def validate_card_shape(card, ids):
    if not isinstance(card, dict):
        raise ValueError("every item must be an object")
    if card.keys() - CARD_FIELDS:
        raise ValueError("unexpected card fields; review the API schema")
    card_id = card.get("id")
    if not isinstance(card_id, int) or isinstance(card_id, bool):
        raise ValueError("every card must have an integer id")
    if card_id in ids:
        raise ValueError(f"duplicate card id: {card_id}")
    ids.add(card_id)
    if not isinstance(card.get("name"), str) or not card["name"].strip():
        raise ValueError(f"card {card_id} has no valid name")
    if not isinstance(card.get("rarity"), str) or card["rarity"] not in ALLOWED_RARITIES:
        raise ValueError(f"card {card_id} has unknown rarity")
    maximum = card.get("maxLevel")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0:
        raise ValueError(f"card {card_id} has invalid maxLevel")
    icons = card.get("iconUrls")
    if not isinstance(icons, dict) or icons.keys() - {"medium", "evolutionMedium", "heroMedium"}:
        raise ValueError(f"card {card_id} has unexpected artwork schema")
    if not isinstance(icons.get("medium"), str) or not icons["medium"].strip():
        raise ValueError(f"card {card_id} has no medium artwork")


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError("response must be a JSON object")
    if snapshot.keys() - {"items", "supportItems"}:
        raise ValueError("unexpected response fields; review the API schema")
    if not isinstance(snapshot.get("items"), list) or not snapshot["items"]:
        raise ValueError("response must contain a non-empty items list")
    if not isinstance(snapshot.get("supportItems"), list):
        raise ValueError("response must contain a supportItems list")

    ids = set()
    missing_elixir_ids = set()
    for card in snapshot["items"]:
        validate_card_shape(card, ids)
        card_id = card.get("id")

        capability = card.get("maxEvolutionLevel")
        if capability is not None:
            if (
                not isinstance(capability, int)
                or isinstance(capability, bool)
                or capability not in ALLOWED_CAPABILITIES
            ):
                raise ValueError(
                    f"card {card_id} has invalid maxEvolutionLevel"
                )

        icons = card.get("iconUrls")

        has_evolution = bool((capability or 0) & 1)
        has_hero = bool((capability or 0) & 2)
        if has_evolution and "evolutionMedium" not in icons:
            raise ValueError(f"card {card_id} has inconsistent Evo metadata")
        if not has_evolution and "evolutionMedium" in icons:
            raise ValueError(f"card {card_id} has inconsistent Evo metadata")
        if has_evolution:
            evolution_medium = icons["evolutionMedium"]
            if (
                not isinstance(evolution_medium, str)
                or not evolution_medium.strip()
            ):
                raise ValueError(f"card {card_id} has invalid Evo artwork")

        if has_hero and "heroMedium" not in icons:
            raise ValueError(f"card {card_id} has inconsistent Hero metadata")
        if not has_hero and "heroMedium" in icons:
            raise ValueError(f"card {card_id} has inconsistent Hero metadata")
        if has_hero:
            hero_medium = icons["heroMedium"]
            if not isinstance(hero_medium, str) or not hero_medium.strip():
                raise ValueError(f"card {card_id} has invalid Hero artwork")

        if "elixirCost" not in card:
            missing_elixir_ids.add(card_id)
        elif (
            not isinstance(card["elixirCost"], int)
            or isinstance(card["elixirCost"], bool)
            or card["elixirCost"] <= 0
        ):
            raise ValueError(f"card {card_id} has invalid elixirCost")

    if missing_elixir_ids != {MIRROR_ID}:
        raise ValueError(
            "Mirror must be the only card without elixirCost; got "
            f"{sorted(missing_elixir_ids)}"
        )

    for card in snapshot["supportItems"]:
        validate_card_shape(card, ids)
        if card.keys() & {"maxEvolutionLevel", "elixirCost"} or set(card["iconUrls"]) != {"medium"}:
            raise ValueError("unexpected support-card schema; review manually")


def fetch_snapshot(token):
    request = Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "CRDR-cards-updater/1.1",
        },
    )
    try:
        with open_api_request(request, timeout=30) as response:
            if response.status != 200:
                raise UpdateError(
                    f"cards download failed with HTTP {response.status}"
                )
            return json.load(response)
    except HTTPError as error:
        # Never include response bodies, headers or exception text in diagnostics.
        raise UpdateError(f"cards download failed: HTTP {error.code}") from None
    except TimeoutError:
        raise UpdateError("cards download timed out") from None
    except URLError:
        raise UpdateError("cards download failed: network or TLS error") from None
    except OSError:
        raise UpdateError("cards download failed: network or TLS error") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise UpdateError("cards download failed: invalid JSON response") from None


def compare_snapshots(current, candidate):
    current_by_id = {card["id"]: card for card in current["items"]}
    candidate_by_id = {card["id"]: card for card in candidate["items"]}

    added_ids = sorted(candidate_by_id.keys() - current_by_id.keys())
    removed_ids = sorted(current_by_id.keys() - candidate_by_id.keys())
    changed_ids = sorted(
        card_id
        for card_id in current_by_id.keys() & candidate_by_id.keys()
        if current_by_id[card_id] != candidate_by_id[card_id]
    )
    return {
        "added": [candidate_by_id[card_id] for card_id in added_ids],
        "removed": [current_by_id[card_id] for card_id in removed_ids],
        "changed": [
            {
                "id": card_id,
                "name": candidate_by_id[card_id]["name"],
                "before": current_by_id[card_id],
                "after": candidate_by_id[card_id],
            }
            for card_id in changed_ids
        ],
        "supportItemsChanged": (
            current.get("supportItems") != candidate.get("supportItems")
        ),
    }


def read_token():
    credentials = os.environ.get("CREDENTIALS_DIRECTORY")
    if credentials:
        try:
            token = (Path(credentials) / "crdr-api").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            raise UpdateError("cannot read the configured crdr-api credential") from None
    else:
        token = os.environ.get(TOKEN_ENV, "").strip()
    if not token or not token.isascii() or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in token):
        raise UpdateError("provide a valid crdr-api credential or CLASH_ROYALE_API_TOKEN")
    return token


def state_directory():
    configured = os.environ.get("XDG_STATE_HOME", "")
    base = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / ".local/state"
    return base / "crdr-card-updater"


def write_json_atomic(path, value):
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(value, temporary, ensure_ascii=False, indent=2, allow_nan=False)
            temporary.write("\n")
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def describe_changes(diff):
    """Enrich the existing comparison; keep raw fields for human review."""
    changed = []
    for card in diff["changed"]:
        before, after = card["before"], card["after"]
        fields = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key) or (key in before) != (key in after))
        changed.append({**card, "fields": fields,
                        "category": "gameplay" if GAMEPLAY_FIELDS.intersection(fields) else "metadata-only"})
    return {"added": diff["added"], "removed": diff["removed"], "changed": changed}


def check_report(current, candidate):
    diff = compare_snapshots(current, candidate)
    cards = describe_changes(diff)
    support = describe_changes(compare_snapshots(
        {"items": current["supportItems"]}, {"items": candidate["supportItems"]}))
    groups = (cards, support)
    gameplay = any(group["added"] or group["removed"] or any(card["category"] == "gameplay" for card in group["changed"]) for group in groups)
    metadata = any(any(set(card["fields"]) - GAMEPLAY_FIELDS for card in group["changed"]) for group in groups)
    # Ordering of API lists is not a gameplay or metadata change.
    changed = gameplay or metadata
    return {"version": 1, "changed": changed, "gameplayChanged": gameplay,
            "metadataChanged": metadata, "cards": cards, "supportItems": support}


def format_report(report):
    def summary(card):
        capability = card.get("maxEvolutionLevel") or 0
        return (f'{card["id"]} {json.dumps(card["name"], ensure_ascii=False)} | '
                f'cost={card.get("elixirCost", "not supplied")} rarity={card["rarity"]} '
                f'Evolution={bool(capability & 1)} Hero={bool(capability & 2)}')

    lines = [f'Gameplay changes: {report["gameplayChanged"]}; metadata changes: {report["metadataChanged"]}']
    for name in ("cards", "supportItems"):
        group = report[name]
        lines.append(f'{name}: +{len(group["added"])} -{len(group["removed"])} ~{len(group["changed"])}')
        for kind, marker in (("added", "+"), ("removed", "-")):
            lines.extend(f"{marker} {summary(card)}" for card in group[kind])
        for card in group["changed"]:
            lines.append(f'~ {summary(card["after"])} [{card["category"]}]')
            for field in card["fields"]:
                before = json.dumps(card["before"].get(field), ensure_ascii=False, sort_keys=True)
                after = json.dumps(card["after"].get(field), ensure_ascii=False, sort_keys=True)
                lines.append(f"  {field}: {before} -> {after}")
    return "\n".join(lines) + "\n"


def notify_changes(directory, fingerprint, *, title="CRDR: card catalog changed", message="Validated candidate and diff are ready for manual review. Nothing was published."):
    marker = directory / "notified.json"
    try:
        notified = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else []
        if not isinstance(notified, list) or not all(isinstance(item, str) for item in notified):
            notified = []
    except (OSError, ValueError, UnicodeError):
        notified = []
    if fingerprint in notified:
        print("Notification already sent for these changes.")
        return
    try:
        result = subprocess.run(
            ["notify-send", "--app-name=CRDR", title, message],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False,
            env={key: value for key, value in os.environ.items() if key not in {TOKEN_ENV, "CREDENTIALS_DIRECTORY"}},
        )
        if result.returncode != 0:
            raise OSError("notification unavailable")
        write_json_atomic(marker, [*notified, fingerprint])
        print("Notification sent.")
    except (OSError, subprocess.TimeoutExpired):
        print("Notification unavailable; the check and reports succeeded.")


def run_check(current, candidate, notify=False, *, directory=None):
    directory = directory or state_directory()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / ".check.lock").open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another catalog check is running; no reports changed.")
            return
        report = check_report(current, candidate)
        checked_at = datetime.now(timezone.utc).isoformat()
        fingerprint = hashlib.sha256(json.dumps(report, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        status = {"checkedAt": checked_at, "changed": report["changed"], "fingerprint": fingerprint}
        if report["changed"]:
            write_json_atomic(directory / "candidate.json", candidate)
            write_json_atomic(directory / "diff.json", report)
            # A JSON string would not be directly readable as a plain text report.
            text_path = directory / "diff.txt"
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                try:
                    temporary.write(format_report(report))
                    temporary.flush()
                    temporary_path.replace(text_path)
                finally:
                    temporary_path.unlink(missing_ok=True)
            print("Catalog changed; validated candidate.json, diff.json and diff.txt saved in the state directory.")
            print(format_report(report).splitlines()[0])
        else:
            print("Catalog unchanged; cards.json was not modified.")
        # Written last: this describes the latest successful check, not publication.
        write_json_atomic(directory / "status.json", status)
        if report["changed"] and notify:
            notify_changes(directory, fingerprint)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate and preview an official cards snapshot update."
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--apply",
        action="store_true",
        help="allow replacement after an interactive confirmation",
    )
    modes.add_argument("--check", action="store_true", help="noninteractive check; write reports outside the repository")
    parser.add_argument("--notify", action="store_true", help="optionally notify once per detected change (requires --check)")
    args = parser.parse_args()
    if args.notify and not args.check:
        parser.error("--notify requires --check")
    return args


def main():
    args = parse_args()
    token = read_token()

    with CARDS_PATH.open(encoding="utf-8") as source:
        current = json.load(source)

    downloaded = fetch_snapshot(token)
    # Do not persist/print a response that unexpectedly reflects the credential.
    if any(token in json.dumps(snapshot, ensure_ascii=False) for snapshot in (current, downloaded)):
        raise UpdateError("unexpected credential content in snapshot; nothing written")
    validate_snapshot(downloaded)
    validate_snapshot(current)
    if args.check:
        run_check(current, downloaded, args.notify)
        return

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CARDS_PATH.parent,
            prefix="cards.",
            suffix=".json.tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(downloaded, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")

        with temporary_path.open(encoding="utf-8") as source:
            candidate = json.load(source)
        validate_snapshot(candidate)
        print(json.dumps(compare_snapshots(current, candidate), indent=2))
        print(f"Validated candidate: {temporary_path}")
        if not args.apply:
            print("Preview only; cards.json was not changed.")
            return

        confirmation = input('Type "REPLACE cards.json" to apply: ')
        if confirmation != "REPLACE cards.json":
            print("Confirmation did not match; cards.json was not changed.")
            return
        temporary_path.replace(CARDS_PATH)
        temporary_path = None
        print("cards.json was replaced with the validated candidate.")
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def cli():
    try:
        main()
    except UpdateError as error:
        print(f"Catalog update failed: {error}. Review required.", file=sys.stderr)
        return 1
    except ValueError:
        print("Catalog update failed: invalid JSON or unexpected snapshot schema. Review required.", file=sys.stderr)
        return 1
    except OSError:
        print("Catalog update failed: local files could not be read or written. Review required.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())

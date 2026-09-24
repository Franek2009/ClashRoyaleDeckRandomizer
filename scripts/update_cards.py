#!/usr/bin/env python3
"""Preview and explicitly apply a cards.json update from the official API."""

import argparse
import json
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://api.clashroyale.com/v1/cards"
TOKEN_ENV = "CLASH_ROYALE_API_TOKEN"
ROOT = Path(__file__).resolve().parents[1]
CARDS_PATH = ROOT / "cards.json"
ALLOWED_RARITIES = {"common", "rare", "epic", "legendary", "champion"}
ALLOWED_CAPABILITIES = {1, 2, 3}
MIRROR_ID = 28000006


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError("response must be a JSON object")
    if not isinstance(snapshot.get("items"), list) or not snapshot["items"]:
        raise ValueError("response must contain a non-empty items list")
    if not isinstance(snapshot.get("supportItems"), list):
        raise ValueError("response must contain a supportItems list")

    ids = set()
    missing_elixir_ids = set()
    for card in snapshot["items"]:
        if not isinstance(card, dict):
            raise ValueError("every item must be an object")

        card_id = card.get("id")
        if not isinstance(card_id, int) or isinstance(card_id, bool):
            raise ValueError("every card must have an integer id")
        if card_id in ids:
            raise ValueError(f"duplicate card id: {card_id}")
        ids.add(card_id)

        if not isinstance(card.get("name"), str) or not card["name"].strip():
            raise ValueError(f"card {card_id} has no valid name")
        if card.get("rarity") not in ALLOWED_RARITIES:
            raise ValueError(f"card {card_id} has unknown rarity")

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
        if not isinstance(icons, dict):
            raise ValueError(f"card {card_id} has no medium artwork")
        medium = icons.get("medium")
        if not isinstance(medium, str) or not medium.strip():
            raise ValueError(f"card {card_id} has no medium artwork")

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
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"cards download failed with HTTP {response.status}"
                )
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cards download failed: {error}") from error


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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate and preview an official cards snapshot update."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="allow replacement after an interactive confirmation",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise SystemExit(f"set {TOKEN_ENV}; the token is never stored or logged")

    with CARDS_PATH.open(encoding="utf-8") as source:
        current = json.load(source)

    downloaded = fetch_snapshot(token)

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


if __name__ == "__main__":
    main()

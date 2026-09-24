from copy import deepcopy

import pytest

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

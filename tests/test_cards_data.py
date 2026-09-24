import json
from pathlib import Path

from randomizer import has_evolution, has_hero, is_champion


CARDS_PATH = Path(__file__).resolve().parents[1] / "cards.json"
ALLOWED_RARITIES = {"common", "rare", "epic", "legendary", "champion"}
ALLOWED_CAPABILITY_VALUES = {1, 2, 3}


def test_cards_snapshot_is_compatible_with_application():
    with CARDS_PATH.open(encoding="utf-8") as file:
        snapshot = json.load(file)

    assert isinstance(snapshot, dict)
    assert "items" in snapshot

    cards = snapshot["items"]
    assert isinstance(cards, list)
    assert cards
    assert len(cards) >= 8

    card_ids = []
    non_champion_count = 0
    cards_without_elixir = []

    for card in cards:
        assert isinstance(card, dict)
        assert isinstance(card.get("id"), int)
        assert not isinstance(card["id"], bool)
        assert isinstance(card.get("name"), str) and card["name"].strip()
        assert card.get("rarity") in ALLOWED_RARITIES

        if "maxEvolutionLevel" in card:
            capability = card["maxEvolutionLevel"]
            assert isinstance(capability, int)
            assert not isinstance(capability, bool)
            assert capability in ALLOWED_CAPABILITY_VALUES

        if "elixirCost" in card:
            assert isinstance(card["elixirCost"], int)
            assert not isinstance(card["elixirCost"], bool)
            assert card["elixirCost"] > 0
        else:
            cards_without_elixir.append((card["id"], card["name"]))

        icon_urls = card.get("iconUrls")
        assert isinstance(icon_urls, dict)
        assert isinstance(icon_urls.get("medium"), str)
        assert icon_urls["medium"].strip()

        if "evolutionMedium" in icon_urls:
            assert isinstance(icon_urls["evolutionMedium"], str)
            assert icon_urls["evolutionMedium"].strip()

        if "heroMedium" in icon_urls:
            assert isinstance(icon_urls["heroMedium"], str)
            assert icon_urls["heroMedium"].strip()

        assert has_evolution(card) is ("evolutionMedium" in icon_urls)
        assert has_hero(card) is ("heroMedium" in icon_urls)
        assert is_champion(card) is (card["rarity"] == "champion")

        if not is_champion(card):
            non_champion_count += 1

        card_ids.append(card["id"])

    assert len(card_ids) == len(set(card_ids))
    assert cards_without_elixir == [(28000006, "Mirror")]
    assert non_champion_count + min(
        sum(is_champion(card) for card in cards), 2
    ) >= 8

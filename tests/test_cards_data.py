import json
from pathlib import Path


CARDS_PATH = Path(__file__).resolve().parents[1] / "cards.json"


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
    champion_count = 0
    evolution_count = 0
    non_champion_count = 0

    for card in cards:
        assert isinstance(card, dict)
        assert isinstance(card.get("id"), int)
        assert not isinstance(card["id"], bool)
        assert isinstance(card.get("name"), str) and card["name"].strip()
        assert isinstance(card.get("rarity"), str) and card["rarity"].strip()

        if "elixirCost" in card:
            assert isinstance(card["elixirCost"], int)
            assert not isinstance(card["elixirCost"], bool)
            assert card["elixirCost"] > 0

        icon_urls = card.get("iconUrls")
        assert isinstance(icon_urls, dict)
        assert isinstance(icon_urls.get("medium"), str)
        assert icon_urls["medium"].strip()

        if "evolutionMedium" in icon_urls:
            assert isinstance(icon_urls["evolutionMedium"], str)
            assert icon_urls["evolutionMedium"].strip()
            evolution_count += 1

        if card["rarity"] == "champion":
            champion_count += 1
        else:
            non_champion_count += 1

        card_ids.append(card["id"])

    assert len(card_ids) == len(set(card_ids))
    assert champion_count >= 2
    assert evolution_count >= 2
    assert non_champion_count + min(champion_count, 2) >= 8

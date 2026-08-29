import json
from pathlib import Path

import pytest

from randomizer import arrange_deck, get_random_deck, has_evolution, is_champion


def make_card(card_id, *, rarity="common", has_evo=False):
    icon_urls = {"medium": f"https://example.com/{card_id}.png"}
    if has_evo:
        icon_urls["evolutionMedium"] = f"https://example.com/{card_id}-evo.png"

    return {
        "id": card_id,
        "name": f"Card {card_id}",
        "rarity": rarity,
        "iconUrls": icon_urls,
    }


def make_deck(champion_count=0, evolution_count=2):
    champions = [
        make_card(100 + index, rarity="champion")
        for index in range(champion_count)
    ]
    evolutions = [
        make_card(200 + index, has_evo=True)
        for index in range(evolution_count)
    ]
    normal_count = 8 - champion_count - evolution_count
    normal_cards = [make_card(300 + index) for index in range(normal_count)]
    return champions + evolutions + normal_cards


def test_has_evolution_detects_evolution_artwork():
    assert has_evolution(make_card(1, has_evo=True)) is True
    assert has_evolution(make_card(2)) is False
    assert has_evolution({"id": 3}) is False


def test_is_champion_checks_card_rarity():
    assert is_champion(make_card(1, rarity="champion")) is True
    assert is_champion(make_card(2, rarity="legendary")) is False
    assert is_champion({"id": 3}) is False


@pytest.mark.parametrize("champion_count", [0, 1, 2])
def test_generated_deck_has_expected_champion_count(champion_count):
    cards = make_deck(champion_count=champion_count)

    deck = get_random_deck(cards)

    assert len(deck) == 8
    assert len({card["id"] for card in deck}) == 8
    assert sum(is_champion(card) for card in deck) == champion_count


def test_generated_deck_contains_at_most_two_champions():
    cards = make_deck(champion_count=2) + [
        make_card(400 + index, rarity="champion")
        for index in range(3)
    ]

    deck = get_random_deck(cards)

    assert sum(is_champion(card) for card in deck) <= 2


@pytest.mark.parametrize("champion_count", [0, 1, 2])
def test_arrange_deck_places_active_cards_in_allowed_slots(champion_count):
    arranged_deck = arrange_deck(make_deck(champion_count=champion_count))

    assert len(arranged_deck) == 8

    for slot_number, slot in enumerate(arranged_deck, start=1):
        if slot["is_evolution"]:
            assert slot_number in (1, 3)
            assert has_evolution(slot["card"])

        if is_champion(slot["card"]):
            assert slot_number in (2, 3)

    assert arranged_deck[1]["is_evolution"] is False


def test_champion_has_priority_over_evolution_in_slot_three():
    arranged_deck = arrange_deck(make_deck(champion_count=2, evolution_count=2))

    assert is_champion(arranged_deck[1]["card"])
    assert is_champion(arranged_deck[2]["card"])
    assert arranged_deck[2]["is_evolution"] is False


def test_evolution_card_can_be_inactive_outside_evolution_slots():
    arranged_deck = arrange_deck(make_deck(champion_count=2, evolution_count=3))

    inactive_evolution_slots = [
        (slot_number, slot)
        for slot_number, slot in enumerate(arranged_deck, start=1)
        if has_evolution(slot["card"]) and not slot["is_evolution"]
    ]

    assert inactive_evolution_slots
    assert all(slot_number not in (1, 3) for slot_number, _ in inactive_evolution_slots)


def test_arrange_deck_returns_eight_slots_for_valid_deck():
    arranged_deck = arrange_deck(make_deck(champion_count=1, evolution_count=3))

    assert len(arranged_deck) == 8
    assert all(set(slot) == {"card", "is_evolution"} for slot in arranged_deck)


def test_random_deck_rules_stress_test():
    cards_path = Path(__file__).resolve().parents[1] / "cards.json"
    with cards_path.open(encoding="utf-8") as file:
        cards = json.load(file)["items"]

    for _ in range(1000):
        deck = get_random_deck(cards)
        arranged_deck = arrange_deck(deck)

        assert len(deck) == 8
        assert len({card["id"] for card in deck}) == 8
        assert sum(is_champion(card) for card in deck) <= 2
        assert len(arranged_deck) == 8

        for slot_number, slot in enumerate(arranged_deck, start=1):
            if slot["is_evolution"]:
                assert slot_number in (1, 3)
                assert has_evolution(slot["card"])

            if is_champion(slot["card"]):
                assert slot_number in (2, 3)

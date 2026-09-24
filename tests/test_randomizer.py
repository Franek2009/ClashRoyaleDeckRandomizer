import json
from pathlib import Path

import pytest

from randomizer import (
    ActiveForm,
    DeckSlot,
    SlotRole,
    arrange_deck,
    get_random_deck,
    has_evolution,
    has_hero,
    is_champion,
)


def make_card(
    card_id,
    *,
    rarity="common",
    has_evo=False,
    has_hero_form=False,
):
    icon_urls = {"medium": f"https://example.com/{card_id}.png"}
    max_evolution_level = 0
    if has_evo:
        max_evolution_level |= 1
        icon_urls["evolutionMedium"] = (
            f"https://example.com/{card_id}-evo.png"
        )
    if has_hero_form:
        max_evolution_level |= 2
        icon_urls["heroMedium"] = (
            f"https://example.com/{card_id}-hero.png"
        )

    card = {
        "id": card_id,
        "name": f"Card {card_id}",
        "rarity": rarity,
        "iconUrls": icon_urls,
    }
    if max_evolution_level:
        card["maxEvolutionLevel"] = max_evolution_level
    return card


def make_deck(*special_cards):
    normal_count = 8 - len(special_cards)
    normal_cards = [make_card(300 + index) for index in range(normal_count)]
    return list(special_cards) + normal_cards


@pytest.mark.parametrize(
    ("card", "evolution", "hero", "champion"),
    [
        (make_card(1, has_evo=True), True, False, False),
        (make_card(2, has_hero_form=True), False, True, False),
        (
            make_card(3, has_evo=True, has_hero_form=True),
            True,
            True,
            False,
        ),
        (make_card(4, rarity="champion"), False, False, True),
        (make_card(5), False, False, False),
    ],
)
def test_card_classification(card, evolution, hero, champion):
    assert has_evolution(card) is evolution
    assert has_hero(card) is hero
    assert is_champion(card) is champion


def test_classification_bits_match_corresponding_icon_urls():
    cards_path = Path(__file__).resolve().parents[1] / "cards.json"
    with cards_path.open(encoding="utf-8") as file:
        cards = json.load(file)["items"]

    for card in cards:
        assert has_evolution(card) is (
            "evolutionMedium" in card.get("iconUrls", {})
        )
        assert has_hero(card) is (
            "heroMedium" in card.get("iconUrls", {})
        )


@pytest.mark.parametrize("active_form", [ActiveForm.HERO, ActiveForm.CHAMPION])
def test_evolution_slot_rejects_hero_and_champion(active_form):
    card = make_card(
        1,
        rarity="champion" if active_form is ActiveForm.CHAMPION else "common",
        has_hero_form=active_form is ActiveForm.HERO,
    )

    with pytest.raises(ValueError, match="cannot be active"):
        DeckSlot(card, SlotRole.EVOLUTION, active_form)


def test_hero_slot_rejects_active_evolution():
    with pytest.raises(ValueError, match="cannot be active"):
        DeckSlot(
            make_card(1, has_evo=True),
            SlotRole.HERO,
            ActiveForm.EVOLUTION,
        )


@pytest.mark.parametrize(
    ("card", "active_form"),
    [
        (make_card(1, has_evo=True), ActiveForm.EVOLUTION),
        (make_card(2, has_hero_form=True), ActiveForm.HERO),
        (make_card(3, rarity="champion"), ActiveForm.CHAMPION),
    ],
)
def test_wild_slot_accepts_every_special_form(card, active_form):
    slot = DeckSlot(card, SlotRole.WILD, active_form)

    assert slot.active_form is active_form


def test_card_cannot_activate_a_form_it_does_not_support():
    with pytest.raises(ValueError, match="does not support"):
        DeckSlot(make_card(1), SlotRole.WILD, ActiveForm.HERO)


def test_evo_and_hero_card_activates_only_one_form():
    dual_form_card = make_card(1, has_evo=True, has_hero_form=True)
    arranged = arrange_deck(make_deck(dual_form_card))

    active_uses = [
        slot
        for slot in arranged
        if slot.card["id"] == dual_form_card["id"]
        and slot.active_form is not ActiveForm.NORMAL
    ]

    assert len(active_uses) == 1


def test_arrangement_uses_current_special_slot_roles():
    arranged = arrange_deck(
        make_deck(
            make_card(1, has_evo=True),
            make_card(2, has_evo=True),
            make_card(3, has_hero_form=True),
        )
    )

    assert [slot.role for slot in arranged[:3]] == [
        SlotRole.EVOLUTION,
        SlotRole.HERO,
        SlotRole.WILD,
    ]
    assert [slot.active_form for slot in arranged[:3]] == [
        ActiveForm.EVOLUTION,
        ActiveForm.HERO,
        ActiveForm.EVOLUTION,
    ]
    assert all(slot.role is SlotRole.NORMAL for slot in arranged[3:])
    assert all(
        slot.active_form is ActiveForm.NORMAL for slot in arranged[3:]
    )


def test_two_hero_family_cards_take_hero_and_wild_slots():
    arranged = arrange_deck(
        make_deck(
            make_card(1, has_evo=True),
            make_card(2, has_evo=True),
            make_card(3, has_hero_form=True),
            make_card(4, rarity="champion"),
        )
    )

    assert arranged[1].active_form is ActiveForm.HERO
    assert arranged[2].active_form is ActiveForm.CHAMPION


def test_arrangement_can_activate_at_most_two_evolutions():
    arranged = arrange_deck(
        make_deck(
            make_card(1, has_evo=True),
            make_card(2, has_evo=True),
            make_card(3, has_evo=True),
        )
    )

    assert sum(
        slot.active_form is ActiveForm.EVOLUTION for slot in arranged
    ) == 2


def test_arrangement_can_activate_at_most_two_heroes_or_champions():
    arranged = arrange_deck(
        make_deck(
            make_card(1, has_evo=True),
            make_card(2, has_hero_form=True),
            make_card(3, rarity="champion"),
            make_card(4, has_hero_form=True),
        )
    )

    assert sum(
        slot.active_form in {ActiveForm.HERO, ActiveForm.CHAMPION}
        for slot in arranged
    ) == 2


def test_arrangement_limits_active_special_forms():
    arranged = arrange_deck(
        make_deck(
            make_card(1, has_evo=True, has_hero_form=True),
            make_card(2, has_evo=True),
            make_card(3, has_hero_form=True),
            make_card(4, rarity="champion"),
        )
    )

    active_forms = [
        slot.active_form
        for slot in arranged
        if slot.active_form is not ActiveForm.NORMAL
    ]
    evolution_count = active_forms.count(ActiveForm.EVOLUTION)
    hero_champion_count = sum(
        form in {ActiveForm.HERO, ActiveForm.CHAMPION}
        for form in active_forms
    )

    assert len(active_forms) <= 3
    assert evolution_count <= 2
    assert hero_champion_count <= 2


def test_arrange_deck_rejects_duplicate_cards():
    card = make_card(1, has_evo=True)

    with pytest.raises(ValueError, match="duplicate"):
        arrange_deck([card, card] + [make_card(index) for index in range(2, 8)])


def test_generated_deck_has_eight_unique_cards_and_at_most_two_champions():
    cards = [
        make_card(1, has_evo=True),
        make_card(2, has_evo=True),
        *[make_card(10 + index, rarity="champion") for index in range(4)],
        *[make_card(20 + index) for index in range(8)],
    ]

    deck = get_random_deck(cards)

    assert len(deck) == 8
    assert len({card["id"] for card in deck}) == 8
    assert sum(is_champion(card) for card in deck) <= 2


def test_random_deck_rules_stress_test():
    cards_path = Path(__file__).resolve().parents[1] / "cards.json"
    with cards_path.open(encoding="utf-8") as file:
        cards = json.load(file)["items"]

    for _ in range(1000):
        deck = get_random_deck(cards)
        arranged = arrange_deck(deck)
        active_forms = [
            slot.active_form
            for slot in arranged
            if slot.active_form is not ActiveForm.NORMAL
        ]

        assert len(deck) == 8
        assert len({card["id"] for card in deck}) == 8
        assert len(arranged) == 8
        assert len(active_forms) <= 3
        assert active_forms.count(ActiveForm.EVOLUTION) <= 2
        assert sum(
            form in {ActiveForm.HERO, ActiveForm.CHAMPION}
            for form in active_forms
        ) <= 2

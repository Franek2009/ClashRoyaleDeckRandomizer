import json
from pathlib import Path

import pytest

from randomizer import (
    ActiveForm,
    ConstraintError,
    DeckConstraints,
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


def make_catalog():
    return [
        make_card(1, has_evo=True),
        make_card(2, has_evo=True),
        make_card(3, has_hero_form=True),
        make_card(4, has_hero_form=True),
        make_card(5, has_evo=True, has_hero_form=True),
        make_card(6, rarity="champion"),
        make_card(7, rarity="champion"),
        *[make_card(card_id) for card_id in range(8, 20)],
    ]


def active_counts(arranged):
    evolution_count = sum(
        slot.active_form is ActiveForm.EVOLUTION for slot in arranged
    )
    hero_count = sum(
        slot.active_form in {ActiveForm.HERO, ActiveForm.CHAMPION}
        for slot in arranged
    )
    return evolution_count, hero_count


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


def test_default_constraints_are_unrestricted():
    constraints = DeckConstraints()

    assert constraints.available_ids is None
    assert constraints.banned_ids == frozenset()
    assert constraints.required_ids == frozenset()
    assert constraints.evolution_count is None
    assert constraints.hero_champion_count is None


def test_available_none_uses_full_catalog():
    catalog = make_catalog()
    constraints = DeckConstraints(
        available_ids=None,
        evolution_count=0,
        hero_champion_count=0,
    )

    deck = get_random_deck(catalog, constraints)

    assert len(deck) == 8
    assert {card["id"] for card in deck} <= {card["id"] for card in catalog}


def test_limited_available_pool_is_respected():
    catalog = make_catalog()
    available_ids = frozenset(range(1, 11))
    constraints = DeckConstraints(
        available_ids=available_ids,
        evolution_count=1,
        hero_champion_count=1,
    )

    deck = get_random_deck(catalog, constraints)

    assert {card["id"] for card in deck} <= available_ids


def test_banned_cards_are_excluded():
    constraints = DeckConstraints(
        banned_ids=frozenset({8, 9}),
        evolution_count=1,
        hero_champion_count=1,
    )

    deck = get_random_deck(make_catalog(), constraints)

    assert {card["id"] for card in deck}.isdisjoint({8, 9})


def test_required_cards_are_included():
    constraints = DeckConstraints(
        required_ids=frozenset({1, 8, 9}),
        evolution_count=0,
        hero_champion_count=0,
    )

    deck = get_random_deck(make_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)

    assert {1, 8, 9} <= {card["id"] for card in deck}
    assert active_counts(arranged) == (0, 0)


def test_required_and_banned_conflict_is_rejected():
    constraints = DeckConstraints(
        banned_ids=frozenset({8}), required_ids=frozenset({8})
    )

    with pytest.raises(ConstraintError, match="required card 8 is banned"):
        get_random_deck(make_catalog(), constraints)


def test_required_card_outside_available_is_rejected():
    constraints = DeckConstraints(
        available_ids=frozenset(range(1, 9)),
        required_ids=frozenset({9}),
    )

    with pytest.raises(ConstraintError, match="not in available"):
        get_random_deck(make_catalog(), constraints)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("available_ids", "unknown available card ID 999"),
        ("banned_ids", "unknown banned card ID 999"),
        ("required_ids", "unknown required card ID 999"),
    ],
)
def test_unknown_card_ids_are_rejected(field, message):
    constraints = DeckConstraints(**{field: frozenset({999})})

    with pytest.raises(ConstraintError, match=message):
        get_random_deck(make_catalog(), constraints)


def test_more_than_eight_required_cards_are_rejected():
    constraints = DeckConstraints(required_ids=frozenset(range(1, 10)))

    with pytest.raises(ConstraintError, match="9 required cards"):
        get_random_deck(make_catalog(), constraints)


def test_effective_pool_smaller_than_eight_is_rejected():
    constraints = DeckConstraints(available_ids=frozenset(range(1, 8)))

    with pytest.raises(ConstraintError, match="pool has 7 cards"):
        get_random_deck(make_catalog(), constraints)


@pytest.mark.parametrize("evolution_count", [0, 1, 2])
def test_exact_evolution_count_is_respected(evolution_count):
    constraints = DeckConstraints(
        evolution_count=evolution_count,
        hero_champion_count=0,
    )

    deck = get_random_deck(make_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)

    assert active_counts(arranged) == (evolution_count, 0)


@pytest.mark.parametrize("hero_count", [0, 1, 2])
def test_exact_hero_champion_count_is_respected(hero_count):
    constraints = DeckConstraints(
        evolution_count=0,
        hero_champion_count=hero_count,
    )

    deck = get_random_deck(make_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)

    assert active_counts(arranged) == (0, hero_count)


@pytest.mark.parametrize("counts", [(2, 1), (1, 2)])
def test_three_special_slots_support_valid_mixed_counts(counts):
    constraints = DeckConstraints(
        evolution_count=counts[0],
        hero_champion_count=counts[1],
    )

    deck = get_random_deck(make_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)

    assert active_counts(arranged) == counts


def test_two_evolutions_and_two_heroes_are_rejected():
    constraints = DeckConstraints(
        evolution_count=2, hero_champion_count=2
    )

    with pytest.raises(ConstraintError, match="only 3 slots"):
        get_random_deck(make_catalog(), constraints)


def test_too_few_evolution_capable_cards_are_rejected():
    catalog = [make_card(1, has_evo=True)] + [
        make_card(card_id) for card_id in range(2, 10)
    ]
    constraints = DeckConstraints(
        evolution_count=2, hero_champion_count=0
    )

    with pytest.raises(ConstraintError, match="only 1 Evolution-capable"):
        get_random_deck(catalog, constraints)


def test_too_few_hero_champion_cards_are_rejected():
    catalog = [make_card(1, has_hero_form=True)] + [
        make_card(card_id) for card_id in range(2, 10)
    ]
    constraints = DeckConstraints(
        evolution_count=0, hero_champion_count=2
    )

    with pytest.raises(ConstraintError, match="only 1 Hero/Champion"):
        get_random_deck(catalog, constraints)


def test_dual_form_card_cannot_fill_two_active_slots():
    catalog = [make_card(1, has_evo=True, has_hero_form=True)] + [
        make_card(card_id) for card_id in range(2, 10)
    ]
    constraints = DeckConstraints(
        evolution_count=1, hero_champion_count=1
    )

    with pytest.raises(ConstraintError, match="distinct cards"):
        get_random_deck(catalog, constraints)


def test_required_champion_conflicts_with_requested_zero_hero_slots():
    constraints = DeckConstraints(
        required_ids=frozenset({6}),
        evolution_count=0,
        hero_champion_count=0,
    )

    with pytest.raises(ConstraintError, match="required Champions"):
        get_random_deck(make_catalog(), constraints)


def test_two_required_champions_conflict_with_one_hero_slot():
    constraints = DeckConstraints(
        required_ids=frozenset({6, 7}),
        evolution_count=0,
        hero_champion_count=1,
    )

    with pytest.raises(ConstraintError, match="required Champions"):
        get_random_deck(make_catalog(), constraints)


def test_required_dual_form_card_can_remain_normal():
    constraints = DeckConstraints(
        required_ids=frozenset({5}),
        evolution_count=0,
        hero_champion_count=0,
    )

    deck = get_random_deck(make_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)
    dual_form_slot = next(slot for slot in arranged if slot.card["id"] == 5)

    assert dual_form_slot.active_form is ActiveForm.NORMAL


def test_constrained_deck_is_unique_and_respects_all_lists_and_counts():
    constraints = DeckConstraints(
        available_ids=frozenset(range(1, 16)),
        banned_ids=frozenset({10, 11}),
        required_ids=frozenset({1, 6, 8}),
        evolution_count=2,
        hero_champion_count=1,
    )

    deck = get_random_deck(make_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)
    deck_ids = {card["id"] for card in deck}

    assert len(deck) == len(deck_ids) == 8
    assert constraints.required_ids <= deck_ids
    assert deck_ids.isdisjoint(constraints.banned_ids)
    assert deck_ids <= constraints.available_ids
    assert active_counts(arranged) == (2, 1)


def test_get_random_deck_without_constraints_remains_supported():
    deck = get_random_deck(make_catalog())

    assert len(deck) == 8
    assert len({card["id"] for card in deck}) == 8


@pytest.mark.parametrize(
    "constraints",
    [
        DeckConstraints(evolution_count=2, hero_champion_count=0),
        DeckConstraints(evolution_count=1, hero_champion_count=2),
        DeckConstraints(
            banned_ids=frozenset({10, 11}),
            required_ids=frozenset({1, 8}),
            evolution_count=2,
            hero_champion_count=1,
        ),
    ],
)
def test_constrained_generation_stress_test(constraints):
    for _ in range(100):
        deck = get_random_deck(make_catalog(), constraints)
        arranged = arrange_deck(deck, constraints)

        assert len(deck) == 8
        assert len({card["id"] for card in deck}) == 8
        assert constraints.required_ids <= {card["id"] for card in deck}
        assert {card["id"] for card in deck}.isdisjoint(
            constraints.banned_ids
        )
        assert active_counts(arranged) == (
            constraints.evolution_count,
            constraints.hero_champion_count,
        )


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

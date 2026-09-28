import json
import math
from pathlib import Path

import pytest

from randomizer import (
    ActiveForm,
    CardType,
    ConstraintError,
    DeckConstraints,
    DeckSlot,
    SlotRole,
    WildSlotMode,
    arrange_deck,
    average_elixir,
    card_type,
    effective_form,
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
    elixir_cost=3,
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
    if elixir_cost is not None:
        card["elixirCost"] = elixir_cost
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


def make_typed_catalog():
    troops = [
        make_card(26000001, has_evo=True),
        make_card(26000002, has_evo=True),
        make_card(26000003, has_hero_form=True),
        make_card(26000004, has_hero_form=True),
        make_card(26000005, has_evo=True, has_hero_form=True),
        make_card(26000006, rarity="champion"),
        make_card(26000007, rarity="champion"),
        *[make_card(card_id) for card_id in range(26000008, 26000015)],
    ]
    buildings = [make_card(card_id) for card_id in range(27000001, 27000011)]
    spells = [
        make_card(
            card_id,
            elixir_cost=None if card_id == 28000006 else 3,
        )
        for card_id in range(28000001, 28000011)
    ]
    return troops + buildings + spells


def deck_type_count(deck, kind):
    return sum(card_type(card) is kind for card in deck)


def active_counts(arranged):
    evolution_count = sum(
        slot.active_form is ActiveForm.EVOLUTION for slot in arranged
    )
    hero_count = sum(
        slot.active_form in {ActiveForm.HERO, ActiveForm.CHAMPION}
        for slot in arranged
    )
    return evolution_count, hero_count


def configured_active_counts(constraints):
    return (
        int(constraints.evolution_slot_enabled)
        + int(constraints.wild_slot_mode is WildSlotMode.EVOLUTION),
        int(constraints.hero_slot_enabled)
        + int(
            constraints.wild_slot_mode is WildSlotMode.HERO_CHAMPION
        ),
    )


@pytest.mark.parametrize(
    ("card_id", "expected"),
    [
        (26000001, CardType.TROOP),
        (27000001, CardType.BUILDING),
        (28000001, CardType.SPELL),
    ],
)
def test_card_type_uses_supported_card_id_spaces(card_id, expected):
    assert card_type(make_card(card_id)) is expected


@pytest.mark.parametrize("card_id", [26, 29000001])
def test_card_type_rejects_unknown_card_id_space(card_id):
    with pytest.raises(ValueError, match="unsupported card ID space"):
        card_type(make_card(card_id))


def test_card_type_rejects_bool_card_id():
    with pytest.raises(ValueError, match="card ID must be an integer"):
        card_type({"id": True})


def test_average_elixir_for_three_elixir_deck():
    deck = [make_card(26000001 + index, elixir_cost=3) for index in range(8)]

    assert average_elixir(deck) == 3.0


def test_average_elixir_for_mixed_deck():
    costs = [3, 3, 4, 4, 2, 5, 4, 3]
    deck = [
        make_card(26000001 + index, elixir_cost=cost)
        for index, cost in enumerate(costs)
    ]

    assert average_elixir(deck) == 3.5


def test_average_elixir_is_none_when_non_mirror_card_has_no_cost():
    deck = [make_card(26000001 + index) for index in range(8)]
    deck[0] = make_card(26000001, elixir_cost=None)

    assert average_elixir(deck) is None


def test_average_elixir_counts_mirror_as_one():
    deck = [make_card(26000001 + index, elixir_cost=4) for index in range(7)]
    deck.append(make_card(28000006, elixir_cost=None))

    assert average_elixir(deck) == 29 / 8
    assert average_elixir(deck) == 3.625


def test_average_elixir_requires_eight_cards():
    with pytest.raises(ValueError, match="exactly eight"):
        average_elixir([make_card(26000001)] * 7)


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
    assert constraints.evolution_slot_enabled is True
    assert constraints.hero_slot_enabled is True
    assert constraints.wild_slot_mode is WildSlotMode.EVOLUTION
    assert constraints.spell_count is None
    assert constraints.building_count is None
    assert constraints.min_average_elixir is None
    assert constraints.max_average_elixir is None


def test_available_none_uses_full_catalog():
    catalog = make_catalog()
    constraints = DeckConstraints(
        available_ids=None,
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
    )

    deck = get_random_deck(catalog, constraints)

    assert len(deck) == 8
    assert {card["id"] for card in deck} <= {card["id"] for card in catalog}


def test_limited_available_pool_is_respected():
    catalog = make_catalog()
    available_ids = frozenset(range(1, 11))
    constraints = DeckConstraints(
        available_ids=available_ids,
        evolution_slot_enabled=True,
        hero_slot_enabled=True,
        wild_slot_mode=WildSlotMode.OFF,
    )

    deck = get_random_deck(catalog, constraints)

    assert {card["id"] for card in deck} <= available_ids


def test_banned_cards_are_excluded():
    constraints = DeckConstraints(
        banned_ids=frozenset({8, 9}),
        evolution_slot_enabled=True,
        hero_slot_enabled=True,
        wild_slot_mode=WildSlotMode.OFF,
    )

    deck = get_random_deck(make_catalog(), constraints)

    assert {card["id"] for card in deck}.isdisjoint({8, 9})


def test_required_cards_are_included():
    constraints = DeckConstraints(
        required_ids=frozenset({1, 8, 9}),
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
    )

    deck = get_random_deck(make_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)

    assert {1, 8, 9} <= {card["id"] for card in deck}
    assert active_counts(arranged) == (0, 0)


def test_required_and_banned_conflict_is_rejected():
    constraints = DeckConstraints(
        banned_ids=frozenset({8}), required_ids=frozenset({8})
    )

    with pytest.raises(
        ConstraintError, match="required card 8 is banned"
    ) as error:
        get_random_deck(make_catalog(), constraints)
    assert error.value.code == "required_banned_conflict"


def test_required_card_outside_available_is_rejected():
    constraints = DeckConstraints(
        available_ids=frozenset(range(1, 9)),
        required_ids=frozenset({9}),
    )

    with pytest.raises(ConstraintError, match="not in available") as error:
        get_random_deck(make_catalog(), constraints)
    assert error.value.code == "required_not_available"


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

    with pytest.raises(ConstraintError, match=message) as error:
        get_random_deck(make_catalog(), constraints)
    assert error.value.code == "unknown_card_selection"


def test_more_than_eight_required_cards_are_rejected():
    constraints = DeckConstraints(required_ids=frozenset(range(1, 10)))

    with pytest.raises(ConstraintError, match="9 required cards") as error:
        get_random_deck(make_catalog(), constraints)
    assert error.value.code == "too_many_required"


def test_effective_pool_smaller_than_eight_is_rejected():
    constraints = DeckConstraints(available_ids=frozenset(range(1, 8)))

    with pytest.raises(ConstraintError, match="pool has 7 cards") as error:
        get_random_deck(make_catalog(), constraints)
    assert error.value.code == "not_enough_eligible_cards"


@pytest.mark.parametrize(
    ("evolution_enabled", "hero_enabled", "wild_mode", "counts"),
    [
        (False, False, WildSlotMode.OFF, (0, 0)),
        (True, False, WildSlotMode.OFF, (1, 0)),
        (False, True, WildSlotMode.OFF, (0, 1)),
        (True, True, WildSlotMode.OFF, (1, 1)),
        (True, False, WildSlotMode.EVOLUTION, (2, 0)),
        (False, True, WildSlotMode.HERO_CHAMPION, (0, 2)),
        (True, True, WildSlotMode.EVOLUTION, (2, 1)),
        (True, True, WildSlotMode.HERO_CHAMPION, (1, 2)),
        (False, False, WildSlotMode.EVOLUTION, (1, 0)),
        (False, False, WildSlotMode.HERO_CHAMPION, (0, 1)),
    ],
)
def test_slot_configuration_derives_active_counts(
    evolution_enabled, hero_enabled, wild_mode, counts
):
    constraints = DeckConstraints(
        evolution_slot_enabled=evolution_enabled,
        hero_slot_enabled=hero_enabled,
        wild_slot_mode=wild_mode,
    )

    deck = get_random_deck(make_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)

    assert [slot.role for slot in arranged[:3]] == [
        SlotRole.EVOLUTION,
        SlotRole.HERO,
        SlotRole.WILD,
    ]
    assert active_counts(arranged) == counts
    for slot in arranged:
        assert slot.active_form is effective_form(
            slot.card,
            slot.role,
            evolution_slot_enabled=evolution_enabled,
            hero_slot_enabled=hero_enabled,
            wild_slot_mode=wild_mode,
        )


def test_dual_form_card_uses_form_selected_by_physical_slot():
    dual = make_card(5, has_evo=True, has_hero_form=True)
    normal = [make_card(card_id) for card_id in range(8, 15)]

    cases = [
        (SlotRole.EVOLUTION, WildSlotMode.OFF, ActiveForm.EVOLUTION),
        (SlotRole.HERO, WildSlotMode.OFF, ActiveForm.HERO),
        (SlotRole.WILD, WildSlotMode.EVOLUTION, ActiveForm.EVOLUTION),
        (SlotRole.WILD, WildSlotMode.HERO_CHAMPION, ActiveForm.HERO),
        (SlotRole.NORMAL, WildSlotMode.OFF, ActiveForm.NORMAL),
    ]
    for role, wild_mode, expected in cases:
        assert effective_form(
            dual,
            role,
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=wild_mode,
        ) is expected

    constraints = DeckConstraints(
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        required_ids=frozenset({5}),
    )
    deck = get_random_deck([dual, *normal], constraints)
    arranged = arrange_deck(deck, constraints)
    dual_slot = next(slot for slot in arranged if slot.card["id"] == 5)
    assert dual_slot.role is SlotRole.NORMAL
    assert dual_slot.active_form is ActiveForm.NORMAL


def test_all_off_special_slots_remain_physically_safe_under_stress():
    constraints = DeckConstraints(
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
    )

    for _ in range(100):
        deck = get_random_deck(make_catalog(), constraints)
        arranged = arrange_deck(deck, constraints)

        assert active_counts(arranged) == (0, 0)
        assert not has_evolution(arranged[0].card)
        assert not has_hero(arranged[1].card)
        assert not is_champion(arranged[1].card)
        assert not has_evolution(arranged[2].card)
        assert not has_hero(arranged[2].card)
        assert not is_champion(arranged[2].card)


@pytest.mark.parametrize(
    ("field", "kind", "excluded_id"),
    [
        ("spell_count", CardType.SPELL, 28000025),
        ("building_count", CardType.BUILDING, 27000010),
    ],
)
def test_extreme_type_counts_use_real_types_from_snapshot(
    field, kind, excluded_id
):
    cards_path = Path(__file__).resolve().parents[1] / "cards.json"
    with cards_path.open(encoding="utf-8") as file:
        cards = json.load(file)["items"]
    constraints = DeckConstraints(
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        **{field: 8},
    )

    deck = get_random_deck(cards, constraints)

    assert all(card_type(card) is kind for card in deck)
    assert excluded_id not in {card["id"] for card in deck}


def test_required_champion_conflicts_with_requested_zero_hero_slots():
    constraints = DeckConstraints(
        required_ids=frozenset({6}),
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
    )

    with pytest.raises(ConstraintError, match="required Champions") as error:
        get_random_deck(make_catalog(), constraints)

    assert error.value.code == "required_champion_needs_slot"


def test_two_required_champions_conflict_with_one_hero_slot():
    constraints = DeckConstraints(
        required_ids=frozenset({6, 7}),
        evolution_slot_enabled=False,
        hero_slot_enabled=True,
        wild_slot_mode=WildSlotMode.OFF,
    )

    with pytest.raises(ConstraintError, match="required Champions"):
        get_random_deck(make_catalog(), constraints)


def test_required_dual_form_card_can_remain_normal():
    constraints = DeckConstraints(
        required_ids=frozenset({5}),
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
    )

    deck = get_random_deck(make_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)
    dual_form_slot = next(slot for slot in arranged if slot.card["id"] == 5)

    assert dual_form_slot.active_form is ActiveForm.NORMAL


@pytest.mark.parametrize("field", ["spell_count", "building_count"])
@pytest.mark.parametrize("value", [-1, 9, True, 1.5])
def test_type_counts_reject_invalid_values(field, value):
    constraints = DeckConstraints(**{field: value})

    with pytest.raises(ConstraintError, match=field):
        get_random_deck(make_typed_catalog(), constraints)


@pytest.mark.parametrize(
    "field", ["min_average_elixir", "max_average_elixir"]
)
@pytest.mark.parametrize(
    "value", [0, -1, True, "3.0", math.nan, math.inf, -math.inf]
)
def test_average_elixir_constraints_reject_invalid_values(field, value):
    constraints = DeckConstraints(**{field: value})

    with pytest.raises(ConstraintError, match="positive finite number"):
        get_random_deck(make_typed_catalog(), constraints)


@pytest.mark.parametrize("value", [3, 3.0])
def test_average_elixir_constraints_accept_int_and_float(value):
    constraints = DeckConstraints(
        min_average_elixir=value,
        max_average_elixir=value,
    )

    deck = get_random_deck(make_typed_catalog(), constraints)

    assert average_elixir(deck) == 3.0


def test_minimum_average_cannot_exceed_maximum():
    constraints = DeckConstraints(
        min_average_elixir=3.1,
        max_average_elixir=3.0,
    )

    with pytest.raises(ConstraintError, match="cannot be greater"):
        get_random_deck(make_typed_catalog(), constraints)


def test_non_integral_exact_average_can_be_mathematically_impossible():
    constraints = DeckConstraints(
        min_average_elixir=3.3,
        max_average_elixir=3.3,
    )

    with pytest.raises(ConstraintError, match="cannot be achieved"):
        get_random_deck(make_typed_catalog(), constraints)


@pytest.mark.parametrize(
    ("spell_count", "building_count"),
    [(0, None), (8, 0), (None, 0), (0, 8), (5, 3)],
)
def test_exact_spell_and_building_counts_are_respected(
    spell_count, building_count
):
    constraints = DeckConstraints(
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        spell_count=spell_count,
        building_count=building_count,
    )

    deck = get_random_deck(make_typed_catalog(), constraints)

    if spell_count is not None:
        assert deck_type_count(deck, CardType.SPELL) == spell_count
    if building_count is not None:
        assert deck_type_count(deck, CardType.BUILDING) == building_count


def test_unrestricted_spells_with_exactly_two_buildings():
    constraints = DeckConstraints(
        required_ids=frozenset({28000001}),
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        spell_count=None,
        building_count=2,
    )

    deck = get_random_deck(make_typed_catalog(), constraints)

    assert deck_type_count(deck, CardType.BUILDING) == 2
    assert deck_type_count(deck, CardType.SPELL) >= 1


def test_exactly_two_spells_with_unrestricted_buildings():
    constraints = DeckConstraints(
        required_ids=frozenset({27000001}),
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        spell_count=2,
        building_count=None,
    )

    deck = get_random_deck(make_typed_catalog(), constraints)

    assert deck_type_count(deck, CardType.SPELL) == 2
    assert deck_type_count(deck, CardType.BUILDING) >= 1


def test_unrestricted_card_types_do_not_become_zero_constraints():
    required_ids = frozenset({27000001, 28000001})
    constraints = DeckConstraints(
        required_ids=required_ids,
        evolution_slot_enabled=True,
        hero_slot_enabled=True,
        wild_slot_mode=WildSlotMode.EVOLUTION,
        spell_count=None,
        building_count=None,
    )

    deck = get_random_deck(make_typed_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)
    deck_ids = {card["id"] for card in deck}

    assert len(deck) == len(deck_ids) == 8
    assert required_ids <= deck_ids
    assert active_counts(arranged) == (2, 1)
    assert deck_type_count(deck, CardType.SPELL) >= 1
    assert deck_type_count(deck, CardType.BUILDING) >= 1


def test_mirror_can_be_available_without_average_constraint():
    deck = get_random_deck(
        make_typed_catalog(),
        DeckConstraints(
            evolution_slot_enabled=False,
            hero_slot_enabled=False,
            wild_slot_mode=WildSlotMode.OFF,
        ),
    )

    assert len(deck) == 8


def test_mirror_can_be_required_without_average_constraint():
    constraints = DeckConstraints(
        required_ids=frozenset({28000006}),
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
    )

    deck = get_random_deck(make_typed_catalog(), constraints)

    assert 28000006 in {card["id"] for card in deck}
    assert average_elixir(deck) is not None


def test_required_mirror_is_accepted_with_average_constraint():
    catalog = make_typed_catalog()
    for card in catalog:
        if card["id"] != 28000006:
            card["elixirCost"] = 4
    constraints = DeckConstraints(
        required_ids=frozenset({28000006}),
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        min_average_elixir=3.625,
        max_average_elixir=3.625,
    )

    deck = get_random_deck(catalog, constraints)

    assert 28000006 in {card["id"] for card in deck}
    assert average_elixir(deck) == 3.625


def test_banned_mirror_with_average_constraint_uses_normal_ban_behavior():
    constraints = DeckConstraints(
        banned_ids=frozenset({28000006}),
        min_average_elixir=3.0,
    )

    deck = get_random_deck(make_typed_catalog(), constraints)

    assert 28000006 not in {card["id"] for card in deck}
    assert average_elixir(deck) >= 3.0


@pytest.mark.parametrize(
    "constraints",
    [
        DeckConstraints(min_average_elixir=3.0),
        DeckConstraints(max_average_elixir=3.0),
        DeckConstraints(
            min_average_elixir=2.9,
            max_average_elixir=3.1,
        ),
        DeckConstraints(
            min_average_elixir=3.0,
            max_average_elixir=3.0,
        ),
    ],
)
def test_average_elixir_ranges_are_respected(constraints):
    deck = get_random_deck(make_typed_catalog(), constraints)
    average = average_elixir(deck)

    assert average is not None
    if constraints.min_average_elixir is not None:
        assert average >= constraints.min_average_elixir
    if constraints.max_average_elixir is not None:
        assert average <= constraints.max_average_elixir


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("max_average_elixir", 2.9, "cheapest possible"),
        ("min_average_elixir", 3.1, "most expensive possible"),
    ],
)
def test_unreachable_average_elixir_range_is_rejected(field, value, message):
    constraints = DeckConstraints(
        banned_ids=frozenset({28000006}), **{field: value}
    )

    with pytest.raises(ConstraintError, match=message):
        get_random_deck(make_typed_catalog(), constraints)


def test_solver_finds_exact_average_with_varied_card_costs():
    catalog = make_typed_catalog()
    for index, card in enumerate(catalog):
        if card["id"] != 28000006:
            card["elixirCost"] = 1 + index % 5
    constraints = DeckConstraints(
        min_average_elixir=3.25,
        max_average_elixir=3.25,
    )

    deck = get_random_deck(catalog, constraints)

    assert average_elixir(deck) == 3.25


def test_required_cards_can_make_maximum_average_impossible():
    catalog = make_typed_catalog()
    for card in catalog:
        if card["id"] != 28000006:
            card["elixirCost"] = 1
    for card in catalog:
        if card["id"] in {26000001, 26000002}:
            card["elixirCost"] = 8
    constraints = DeckConstraints(
        required_ids=frozenset({26000001, 26000002}),
        max_average_elixir=2.0,
    )

    with pytest.raises(ConstraintError, match="cheapest possible"):
        get_random_deck(catalog, constraints)


def test_required_cards_can_make_minimum_average_impossible():
    catalog = make_typed_catalog()
    for card in catalog:
        if card["id"] != 28000006:
            card["elixirCost"] = 5
    for card in catalog:
        if card["id"] in {26000001, 26000002}:
            card["elixirCost"] = 1
    constraints = DeckConstraints(
        required_ids=frozenset({26000001, 26000002}),
        min_average_elixir=4.5,
    )

    with pytest.raises(ConstraintError, match="most expensive possible"):
        get_random_deck(catalog, constraints)


def test_spell_and_building_counts_over_eight_are_rejected():
    constraints = DeckConstraints(spell_count=5, building_count=4)

    with pytest.raises(ConstraintError, match="cannot fit"):
        get_random_deck(make_typed_catalog(), constraints)


@pytest.mark.parametrize(
    ("available_ids", "constraints", "message"),
    [
        (
            frozenset(range(26000001, 26000010)) | {28000001},
            {"spell_count": 2},
            "only 1 Spell",
        ),
        (
            frozenset(range(26000001, 26000010)) | {27000001},
            {"building_count": 2},
            "only 1 Building",
        ),
    ],
)
def test_too_few_cards_of_requested_type_are_rejected(
    available_ids, constraints, message
):
    model = DeckConstraints(
        available_ids=available_ids,
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        **constraints,
    )

    with pytest.raises(ConstraintError, match=message):
        get_random_deck(make_typed_catalog(), model)


@pytest.mark.parametrize(
    ("required_id", "field", "message"),
    [
        (28000001, "spell_count", "1 required Spells exceed"),
        (27000001, "building_count", "1 required Buildings exceed"),
    ],
)
def test_required_typed_card_conflicts_with_zero_count(
    required_id, field, message
):
    constraints = DeckConstraints(
        required_ids=frozenset({required_id}),
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        **{field: 0},
    )

    with pytest.raises(ConstraintError, match=message):
        get_random_deck(make_typed_catalog(), constraints)


@pytest.mark.parametrize(
    ("required_ids", "field", "limit", "message"),
    [
        (
            frozenset({28000001, 28000002, 28000003}),
            "spell_count",
            2,
            "3 required Spells exceed",
        ),
        (
            frozenset({27000001, 27000002, 27000003}),
            "building_count",
            2,
            "3 required Buildings exceed",
        ),
    ],
)
def test_required_typed_cards_cannot_exceed_requested_count(
    required_ids, field, limit, message
):
    constraints = DeckConstraints(
        required_ids=required_ids,
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        **{field: limit},
    )

    with pytest.raises(ConstraintError, match=message):
        get_random_deck(make_typed_catalog(), constraints)


def test_required_spells_use_the_requested_spell_slots():
    required_spells = frozenset({28000001, 28000002})
    constraints = DeckConstraints(
        required_ids=required_spells,
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        spell_count=2,
    )

    deck = get_random_deck(make_typed_catalog(), constraints)

    assert required_spells <= {card["id"] for card in deck}
    assert deck_type_count(deck, CardType.SPELL) == 2


def test_banned_cards_reduce_available_type_pool():
    constraints = DeckConstraints(
        available_ids=(
            frozenset(range(26000001, 26000010))
            | {28000001, 28000002}
        ),
        banned_ids=frozenset({28000002}),
        evolution_slot_enabled=False,
        hero_slot_enabled=False,
        wild_slot_mode=WildSlotMode.OFF,
        spell_count=2,
    )

    with pytest.raises(ConstraintError, match="only 1 Spell"):
        get_random_deck(make_typed_catalog(), constraints)


def test_type_and_special_form_constraints_are_satisfied_together():
    constraints = DeckConstraints(
        banned_ids=frozenset({28000010}),
        required_ids=frozenset({28000001}),
        evolution_slot_enabled=True,
        hero_slot_enabled=True,
        wild_slot_mode=WildSlotMode.EVOLUTION,
        spell_count=2,
        building_count=1,
    )

    deck = get_random_deck(make_typed_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)
    deck_ids = {card["id"] for card in deck}

    assert 28000001 in deck_ids
    assert 28000010 not in deck_ids
    assert active_counts(arranged) == (2, 1)
    assert deck_type_count(deck, CardType.SPELL) == 2
    assert deck_type_count(deck, CardType.BUILDING) == 1


@pytest.mark.parametrize(
    "constraints",
    [
        DeckConstraints(
            banned_ids=frozenset({28000010}),
            required_ids=frozenset({28000001}),
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=WildSlotMode.EVOLUTION,
            spell_count=2,
            building_count=1,
            min_average_elixir=2.9,
            max_average_elixir=3.1,
        ),
        DeckConstraints(
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=WildSlotMode.HERO_CHAMPION,
            spell_count=0,
            building_count=2,
            max_average_elixir=3.0,
        ),
        DeckConstraints(
            spell_count=2,
            building_count=1,
            min_average_elixir=3.0,
        ),
        DeckConstraints(
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=WildSlotMode.EVOLUTION,
            min_average_elixir=3.0,
            max_average_elixir=3.0,
        ),
    ],
)
def test_average_elixir_integrates_with_all_existing_constraints(constraints):
    deck = get_random_deck(make_typed_catalog(), constraints)
    arranged = arrange_deck(deck, constraints)
    deck_ids = {card["id"] for card in deck}
    average = average_elixir(deck)

    assert len(deck) == len(deck_ids) == 8
    assert constraints.required_ids <= deck_ids
    assert not deck_ids & constraints.banned_ids
    assert 28000006 not in deck_ids
    assert active_counts(arranged) == configured_active_counts(constraints)
    if constraints.spell_count is not None:
        assert deck_type_count(deck, CardType.SPELL) == constraints.spell_count
    if constraints.building_count is not None:
        assert (
            deck_type_count(deck, CardType.BUILDING)
            == constraints.building_count
        )
    if constraints.min_average_elixir is not None:
        assert average >= constraints.min_average_elixir
    if constraints.max_average_elixir is not None:
        assert average <= constraints.max_average_elixir


@pytest.mark.parametrize(
    "constraints",
    [
        DeckConstraints(
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=WildSlotMode.EVOLUTION,
            spell_count=2,
            building_count=1,
            min_average_elixir=3.0,
            max_average_elixir=3.0,
        ),
        DeckConstraints(
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=WildSlotMode.HERO_CHAMPION,
            spell_count=0,
            building_count=2,
            max_average_elixir=3.0,
        ),
        DeckConstraints(
            spell_count=3,
            building_count=2,
            min_average_elixir=2.9,
        ),
    ],
)
def test_average_elixir_constraint_stress_test(constraints):
    for _ in range(20):
        deck = get_random_deck(make_typed_catalog(), constraints)
        arranged = arrange_deck(deck, constraints)
        average = average_elixir(deck)

        assert len(deck) == len({card["id"] for card in deck}) == 8
        assert 28000006 not in {card["id"] for card in deck}
        assert active_counts(arranged) == configured_active_counts(constraints)
        if constraints.spell_count is not None:
            assert (
                deck_type_count(deck, CardType.SPELL)
                == constraints.spell_count
            )
        if constraints.building_count is not None:
            assert (
                deck_type_count(deck, CardType.BUILDING)
                == constraints.building_count
            )
        if constraints.min_average_elixir is not None:
            assert average >= constraints.min_average_elixir
        if constraints.max_average_elixir is not None:
            assert average <= constraints.max_average_elixir


@pytest.mark.parametrize(
    "constraints",
    [
        DeckConstraints(
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=WildSlotMode.EVOLUTION,
            spell_count=2,
            building_count=1,
        ),
        DeckConstraints(
            required_ids=frozenset({28000001, 27000001}),
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=WildSlotMode.HERO_CHAMPION,
            spell_count=3,
            building_count=2,
        ),
        DeckConstraints(
            banned_ids=frozenset({28000010, 27000010}),
            evolution_slot_enabled=False,
            hero_slot_enabled=False,
            wild_slot_mode=WildSlotMode.OFF,
            spell_count=4,
            building_count=4,
        ),
    ],
)
def test_type_and_special_constraint_stress_test(constraints):
    for _ in range(100):
        deck = get_random_deck(make_typed_catalog(), constraints)
        arranged = arrange_deck(deck, constraints)

        assert len(deck) == len({card["id"] for card in deck}) == 8
        assert constraints.required_ids <= {card["id"] for card in deck}
        assert active_counts(arranged) == configured_active_counts(constraints)
        assert deck_type_count(deck, CardType.SPELL) == constraints.spell_count
        assert (
            deck_type_count(deck, CardType.BUILDING)
            == constraints.building_count
        )


def test_constrained_deck_is_unique_and_respects_all_lists_and_counts():
    constraints = DeckConstraints(
        available_ids=frozenset(range(1, 16)),
        banned_ids=frozenset({10, 11}),
        required_ids=frozenset({1, 6, 8}),
        evolution_slot_enabled=True,
        hero_slot_enabled=True,
        wild_slot_mode=WildSlotMode.EVOLUTION,
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
        DeckConstraints(
            evolution_slot_enabled=True,
            hero_slot_enabled=False,
            wild_slot_mode=WildSlotMode.EVOLUTION,
        ),
        DeckConstraints(
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=WildSlotMode.HERO_CHAMPION,
        ),
        DeckConstraints(
            banned_ids=frozenset({10, 11}),
            required_ids=frozenset({1, 8}),
            evolution_slot_enabled=True,
            hero_slot_enabled=True,
            wild_slot_mode=WildSlotMode.EVOLUTION,
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
        assert active_counts(arranged) == configured_active_counts(constraints)


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

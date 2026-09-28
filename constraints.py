from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from card_model import CardType, WildSlotMode, card_type, is_champion


MIRROR_ID = 28000006
MIRROR_AVERAGE_ELIXIR = 1


class ConstraintError(ValueError):
    def __init__(self, message, *, code="invalid_constraints"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DeckConstraints:
    available_ids: frozenset[int] | None = None
    banned_ids: frozenset[int] = frozenset()
    required_ids: frozenset[int] = frozenset()
    evolution_slot_enabled: bool = True
    hero_slot_enabled: bool = True
    wild_slot_mode: WildSlotMode = WildSlotMode.EVOLUTION
    spell_count: int | None = None
    building_count: int | None = None
    min_average_elixir: float | None = None
    max_average_elixir: float | None = None


def average_elixir(cards):
    if len(cards) != 8:
        raise ValueError("average elixir requires exactly eight cards")
    costs = [elixir_cost_for_average(card) for card in cards]
    if any(cost is None for cost in costs):
        return None
    return sum(costs) / 8


def elixir_cost_for_average(card):
    if card.get("id") == MIRROR_ID:
        return MIRROR_AVERAGE_ELIXIR
    return card.get("elixirCost")


def _validate_average(name, value):
    if (
        value is not None
        and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not Decimal(str(value)).is_finite()
            or value <= 0
        )
    ):
        raise ConstraintError(f"{name} must be a positive finite number")


def _elixir_total_bounds(constraints):
    minimum = constraints.min_average_elixir
    maximum = constraints.max_average_elixir
    min_total = (
        int((Decimal(str(minimum)) * 8).to_integral_value(ROUND_CEILING))
        if minimum is not None
        else None
    )
    max_total = (
        int((Decimal(str(maximum)) * 8).to_integral_value(ROUND_FLOOR))
        if maximum is not None
        else None
    )
    return min_total, max_total


def _validate_type_count(name, value):
    if value is not None and (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value not in range(9)
    ):
        raise ConstraintError(f"{name} must be None or an integer from 0 to 8")


def validate_constraints(cards, constraints):
    catalog_by_id = {card["id"]: card for card in cards}
    catalog_ids = set(catalog_by_id)

    if len(constraints.required_ids) > 8:
        raise ConstraintError(
            f"{len(constraints.required_ids)} required cards cannot fit "
            "in an 8-card deck",
            code="too_many_required",
        )

    id_sets = (
        ("required", constraints.required_ids),
        ("banned", constraints.banned_ids),
    )
    if constraints.available_ids is not None:
        id_sets += (("available", constraints.available_ids),)
    for label, ids in id_sets:
        unknown_ids = sorted(set(ids) - catalog_ids)
        if unknown_ids:
            raise ConstraintError(
                f"unknown {label} card ID {unknown_ids[0]}",
                code="unknown_card_selection",
            )

    banned_required = constraints.required_ids & constraints.banned_ids
    if banned_required:
        card_id = min(banned_required)
        raise ConstraintError(
            f"required card {card_id} is banned",
            code="required_banned_conflict",
        )
    if constraints.available_ids is not None:
        unavailable_required = (
            constraints.required_ids - constraints.available_ids
        )
        if unavailable_required:
            card_id = min(unavailable_required)
            raise ConstraintError(
                f"required card {card_id} is not in available cards",
                code="required_not_available",
            )

    eligible_ids = (
        catalog_ids
        if constraints.available_ids is None
        else set(constraints.available_ids)
    )
    eligible_ids -= constraints.banned_ids
    eligible_cards = [card for card in cards if card["id"] in eligible_ids]
    if len(eligible_cards) < 8:
        raise ConstraintError(
            f"effective card pool has {len(eligible_cards)} cards; "
            "at least 8 are required",
            code="not_enough_eligible_cards",
        )

    if not isinstance(constraints.evolution_slot_enabled, bool):
        raise ConstraintError("evolution_slot_enabled must be a boolean")
    if not isinstance(constraints.hero_slot_enabled, bool):
        raise ConstraintError("hero_slot_enabled must be a boolean")
    if not isinstance(constraints.wild_slot_mode, WildSlotMode):
        raise ConstraintError("wild_slot_mode must be a WildSlotMode")
    _validate_type_count("spell_count", constraints.spell_count)
    _validate_type_count("building_count", constraints.building_count)
    _validate_average("min_average_elixir", constraints.min_average_elixir)
    _validate_average("max_average_elixir", constraints.max_average_elixir)
    if (
        constraints.min_average_elixir is not None
        and constraints.max_average_elixir is not None
        and constraints.min_average_elixir > constraints.max_average_elixir
    ):
        raise ConstraintError(
            "min_average_elixir cannot be greater than max_average_elixir",
            code="average_min_greater_than_max",
        )
    min_total, max_total = _elixir_total_bounds(constraints)
    if (
        min_total is not None
        and max_total is not None
        and min_total > max_total
    ):
        raise ConstraintError(
            "average elixir range cannot be achieved by an 8-card deck"
        )
    if (
        constraints.spell_count is not None
        and constraints.building_count is not None
        and constraints.spell_count + constraints.building_count > 8
    ):
        raise ConstraintError(
            f"spell_count={constraints.spell_count} and "
            f"building_count={constraints.building_count} cannot fit in "
            "an 8-card deck",
            code="type_counts_exceed_deck_size",
        )

    average_is_active = min_total is not None or max_total is not None

    type_constraints = (
        (
            CardType.SPELL,
            "Spell",
            constraints.spell_count,
            "not_enough_spells",
        ),
        (
            CardType.BUILDING,
            "Building",
            constraints.building_count,
            "not_enough_buildings",
        ),
    )
    for kind, label, requested, error_code in type_constraints:
        if requested is None:
            continue
        available_count = sum(
            card_type(card) is kind for card in eligible_cards
        )
        if available_count < requested:
            raise ConstraintError(
                f"only {available_count} {label} is available, "
                f"but {requested} were requested",
                code=error_code,
            )
        required_count = sum(
            card_type(catalog_by_id[card_id]) is kind
            for card_id in constraints.required_ids
        )
        if required_count > requested:
            raise ConstraintError(
                f"{required_count} required {label}s exceed "
                f"{kind.value}_count={requested}"
            )

    required_champions = sum(
        is_champion(catalog_by_id[card_id])
        for card_id in constraints.required_ids
    )
    champion_slots = int(constraints.hero_slot_enabled) + int(
        constraints.wild_slot_mode is WildSlotMode.HERO_CHAMPION
    )
    if required_champions > champion_slots:
        raise ConstraintError(
            f"{required_champions} required Champions cannot fit in "
            f"{champion_slots} active Hero/Champion slots",
            code="required_champion_needs_slot",
        )

    if average_is_active:
        required_cards = [
            catalog_by_id[card_id] for card_id in constraints.required_ids
        ]
        required_total = sum(
            elixir_cost_for_average(card) for card in required_cards
        )
        required_ids = constraints.required_ids
        remaining_costs = sorted(
            elixir_cost_for_average(card)
            for card in eligible_cards
            if card["id"] not in required_ids
        )
        needed = 8 - len(required_cards)
        cheapest_total = required_total + sum(remaining_costs[:needed])
        most_expensive_total = required_total + sum(
            remaining_costs[-needed:] if needed else []
        )
        if max_total is not None and cheapest_total > max_total:
            raise ConstraintError(
                "average elixir maximum is below the cheapest possible deck"
            )
        if min_total is not None and most_expensive_total < min_total:
            raise ConstraintError(
                "average elixir minimum is above the most expensive possible "
                "deck"
            )

    return eligible_cards

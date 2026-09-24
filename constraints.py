from dataclasses import dataclass

from card_model import CardType, card_type, has_evolution, has_hero, is_champion


class ConstraintError(ValueError):
    pass


@dataclass(frozen=True)
class DeckConstraints:
    available_ids: frozenset[int] | None = None
    banned_ids: frozenset[int] = frozenset()
    required_ids: frozenset[int] = frozenset()
    evolution_count: int | None = None
    hero_champion_count: int | None = None
    spell_count: int | None = None
    building_count: int | None = None


def validate_special_count(name, value):
    if value is not None and (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value not in range(3)
    ):
        raise ConstraintError(f"{name} must be None, 0, 1, or 2")


def _validate_type_count(name, value):
    if value is not None and (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value not in range(9)
    ):
        raise ConstraintError(f"{name} must be None or an integer from 0 to 8")


def _hero_capable(card):
    return has_hero(card) or is_champion(card)


def validate_constraints(cards, constraints):
    catalog_by_id = {card["id"]: card for card in cards}
    catalog_ids = set(catalog_by_id)

    if len(constraints.required_ids) > 8:
        raise ConstraintError(
            f"{len(constraints.required_ids)} required cards cannot fit "
            "in an 8-card deck"
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
            raise ConstraintError(f"unknown {label} card ID {unknown_ids[0]}")

    banned_required = constraints.required_ids & constraints.banned_ids
    if banned_required:
        card_id = min(banned_required)
        raise ConstraintError(f"required card {card_id} is banned")
    if constraints.available_ids is not None:
        unavailable_required = (
            constraints.required_ids - constraints.available_ids
        )
        if unavailable_required:
            card_id = min(unavailable_required)
            raise ConstraintError(
                f"required card {card_id} is not in available cards"
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
            "at least 8 are required"
        )

    validate_special_count("evolution_count", constraints.evolution_count)
    validate_special_count(
        "hero_champion_count", constraints.hero_champion_count
    )
    _validate_type_count("spell_count", constraints.spell_count)
    _validate_type_count("building_count", constraints.building_count)
    if (
        constraints.spell_count is not None
        and constraints.building_count is not None
        and constraints.spell_count + constraints.building_count > 8
    ):
        raise ConstraintError(
            f"spell_count={constraints.spell_count} and "
            f"building_count={constraints.building_count} cannot fit in "
            "an 8-card deck"
        )
    if (
        constraints.evolution_count is not None
        and constraints.hero_champion_count is not None
        and constraints.evolution_count + constraints.hero_champion_count > 3
    ):
        raise ConstraintError(
            f"{constraints.evolution_count} Evolutions and "
            f"{constraints.hero_champion_count} Hero/Champions require "
            "4 special forms, but only 3 slots are available"
        )

    if constraints.evolution_count is not None:
        available_evolutions = sum(map(has_evolution, eligible_cards))
        if available_evolutions < constraints.evolution_count:
            raise ConstraintError(
                f"only {available_evolutions} Evolution-capable card is "
                f"available, but {constraints.evolution_count} were requested"
            )
    if constraints.hero_champion_count is not None:
        available_heroes = sum(map(_hero_capable, eligible_cards))
        if available_heroes < constraints.hero_champion_count:
            raise ConstraintError(
                f"only {available_heroes} Hero/Champion card is available, "
                f"but {constraints.hero_champion_count} were requested"
            )

    type_constraints = (
        (CardType.SPELL, "Spell", constraints.spell_count),
        (CardType.BUILDING, "Building", constraints.building_count),
    )
    for kind, label, requested in type_constraints:
        if requested is None:
            continue
        available_count = sum(
            card_type(card) is kind for card in eligible_cards
        )
        if available_count < requested:
            raise ConstraintError(
                f"only {available_count} {label} is available, "
                f"but {requested} were requested"
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
    if (
        constraints.hero_champion_count is not None
        and required_champions > constraints.hero_champion_count
    ):
        raise ConstraintError(
            f"{required_champions} required Champions cannot fit in "
            f"{constraints.hero_champion_count} requested Hero/Champion slots"
        )

    return eligible_cards

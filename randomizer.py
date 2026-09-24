import random
from itertools import combinations

from card_model import (
    EVOLUTION_BIT,
    HERO_BIT,
    ActiveForm,
    CardType,
    DeckSlot,
    SlotRole,
    card_type,
    has_evolution,
    has_hero,
    is_champion,
)
from constraints import (
    ConstraintError,
    DeckConstraints,
    validate_constraints,
    validate_special_count,
)


def _hero_capable(card):
    return has_hero(card) or is_champion(card)


def _find_special_assignment(
    eligible_cards,
    required_ids,
    evolution_count,
    hero_champion_count,
):
    evolution_cards = [card for card in eligible_cards if has_evolution(card)]
    hero_cards = [card for card in eligible_cards if _hero_capable(card)]
    required_champion_ids = {
        card["id"]
        for card in eligible_cards
        if card["id"] in required_ids and is_champion(card)
    }

    for heroes in combinations(hero_cards, hero_champion_count):
        hero_ids = {card["id"] for card in heroes}
        if not required_champion_ids <= hero_ids:
            continue

        available_evolutions = [
            card for card in evolution_cards if card["id"] not in hero_ids
        ]
        for evolutions in combinations(
            available_evolutions, evolution_count
        ):
            active_cards = (*evolutions, *heroes)
            active_ids = {card["id"] for card in active_cards}
            selected_ids = required_ids | active_ids
            if len(selected_ids) > 8:
                continue

            allowed_fillers = [
                card
                for card in eligible_cards
                if not is_champion(card) or card["id"] in hero_ids
            ]
            if len(allowed_fillers) < 8:
                continue
            return list(evolutions), list(heroes)
    return None


def _count_options(constraints):
    options = [
        (1, 2),
        (2, 1),
        (2, 0),
        (1, 1),
        (0, 2),
        (1, 0),
        (0, 1),
        (0, 0),
    ]
    return [
        (evolution_count, hero_count)
        for evolution_count, hero_count in options
        if constraints.evolution_count in (None, evolution_count)
        and constraints.hero_champion_count in (None, hero_count)
    ]


def _resolve_special_assignment(cards, required_ids, constraints):
    for evolution_count, hero_count in _count_options(constraints):
        assignment = _find_special_assignment(
            cards,
            required_ids,
            evolution_count,
            hero_count,
        )
        if assignment is not None:
            return assignment
    return None


def _complete_deck(eligible_cards, required_ids, evolutions, heroes, constraints):
    chosen_by_id = {
        card["id"]: card for card in (*evolutions, *heroes)
    }
    catalog_by_id = {card["id"]: card for card in eligible_cards}
    chosen_by_id.update(
        (card_id, catalog_by_id[card_id]) for card_id in required_ids
    )
    if len(chosen_by_id) > 8:
        return None

    hero_ids = {card["id"] for card in heroes}
    candidates = [
        card
        for card in eligible_cards
        if card["id"] not in chosen_by_id
        and (not is_champion(card) or card["id"] in hero_ids)
    ]
    chosen = list(chosen_by_id.values())
    if constraints.spell_count is None and constraints.building_count is None:
        needed = 8 - len(chosen)
        if len(candidates) < needed:
            return None
        completed = chosen + random.sample(candidates, needed)
        return random.sample(completed, len(completed))

    chosen_counts = {
        kind: sum(card_type(card) is kind for card in chosen)
        for kind in CardType
    }
    candidates_by_type = {
        kind: [card for card in candidates if card_type(card) is kind]
        for kind in CardType
    }

    spell_targets = (
        [constraints.spell_count]
        if constraints.spell_count is not None
        else list(range(9))
    )
    building_targets = (
        [constraints.building_count]
        if constraints.building_count is not None
        else list(range(9))
    )
    target_pairs = [
        (spells, buildings)
        for spells in spell_targets
        for buildings in building_targets
        if spells + buildings <= 8
    ]
    random.shuffle(target_pairs)

    for spell_target, building_target in target_pairs:
        targets = {
            CardType.SPELL: spell_target,
            CardType.BUILDING: building_target,
            CardType.TROOP: 8 - spell_target - building_target,
        }
        needed = {
            kind: targets[kind] - chosen_counts[kind] for kind in CardType
        }
        if any(count < 0 for count in needed.values()):
            continue
        if any(
            needed[kind] > len(candidates_by_type[kind])
            for kind in CardType
        ):
            continue

        completed = list(chosen)
        for kind in CardType:
            completed.extend(
                random.sample(candidates_by_type[kind], needed[kind])
            )
        return random.sample(completed, len(completed))
    return None


def _resolve_constrained_deck(eligible_cards, required_ids, constraints):
    for evolution_count, hero_count in _count_options(constraints):
        evolution_cards = [
            card for card in eligible_cards if has_evolution(card)
        ]
        hero_cards = [card for card in eligible_cards if _hero_capable(card)]
        required_champion_ids = {
            card["id"]
            for card in eligible_cards
            if card["id"] in required_ids and is_champion(card)
        }

        for heroes in combinations(hero_cards, hero_count):
            hero_ids = {card["id"] for card in heroes}
            if not required_champion_ids <= hero_ids:
                continue
            available_evolutions = [
                card
                for card in evolution_cards
                if card["id"] not in hero_ids
            ]
            for evolutions in combinations(
                available_evolutions, evolution_count
            ):
                deck = _complete_deck(
                    eligible_cards,
                    required_ids,
                    evolutions,
                    heroes,
                    constraints,
                )
                if deck is not None:
                    return deck
    return None


def _prepare_constraints(cards, constraints):
    eligible_cards = validate_constraints(cards, constraints)

    deck = _resolve_constrained_deck(
        eligible_cards, constraints.required_ids, constraints
    )
    if deck is not None:
        return eligible_cards, deck

    if constraints.spell_count is None and constraints.building_count is None:
        raise ConstraintError(
            "requested special forms cannot be assigned to distinct cards "
            "in an 8-card deck"
        )
    raise ConstraintError(
        "requested card types and special forms cannot be assigned to "
        "a valid 8-card deck"
    )


def get_random_deck(cards, constraints=None):
    if constraints is not None:
        eligible_cards, deck = _prepare_constraints(
            cards, constraints
        )
        _validate_generated_deck(deck, eligible_cards, constraints)
        return deck

    chosen_cards = []
    evolution_cards = [card for card in cards if has_evolution(card)]

    chosen_cards.extend(random.sample(evolution_cards, 2))

    champion_count = sum(is_champion(card) for card in chosen_cards)
    remaining_cards = [card for card in cards if card not in chosen_cards]
    non_champions = [card for card in remaining_cards if not is_champion(card)]
    champions = [card for card in remaining_cards if is_champion(card)]
    allowed_champions = random.sample(
        champions, min(2 - champion_count, len(champions))
    )
    allowed_cards = non_champions + allowed_champions
    if len(allowed_cards) < 6:
        raise ValueError("card pool cannot produce a valid 8-card deck")
    chosen_cards.extend(random.sample(allowed_cards, 6))
    return chosen_cards


def _validate_generated_deck(deck, eligible_cards, constraints):
    deck_ids = {card["id"] for card in deck}
    if len(deck) != 8 or len(deck_ids) != 8:
        raise ConstraintError("generated deck must contain 8 unique cards")
    if not constraints.required_ids <= deck_ids:
        raise ConstraintError("generated deck is missing a required card")
    if deck_ids & constraints.banned_ids:
        raise ConstraintError("generated deck contains a banned card")
    if not deck_ids <= {card["id"] for card in eligible_cards}:
        raise ConstraintError("generated deck contains an unavailable card")

    arranged = arrange_deck(deck, constraints)
    active_evolutions = sum(
        slot.active_form is ActiveForm.EVOLUTION for slot in arranged
    )
    active_heroes = sum(
        slot.active_form in {ActiveForm.HERO, ActiveForm.CHAMPION}
        for slot in arranged
    )
    if (
        constraints.evolution_count is not None
        and active_evolutions != constraints.evolution_count
    ):
        raise ConstraintError("generated deck has the wrong Evolution count")
    if (
        constraints.hero_champion_count is not None
        and active_heroes != constraints.hero_champion_count
    ):
        raise ConstraintError(
            "generated deck has the wrong Hero/Champion count"
        )

    for kind, requested in (
        (CardType.SPELL, constraints.spell_count),
        (CardType.BUILDING, constraints.building_count),
    ):
        if requested is not None and sum(
            card_type(card) is kind for card in deck
        ) != requested:
            raise ConstraintError(
                f"generated deck has the wrong {kind.value} count"
            )


def _take_first(cards, predicate):
    for index, card in enumerate(cards):
        if predicate(card):
            return cards.pop(index)
    return None


def _hero_form(card):
    if is_champion(card):
        return ActiveForm.CHAMPION
    return ActiveForm.HERO


def arrange_deck(deck, constraints=None):
    """Assign eight unique cards to the current Evo, Hero and Wild slots."""
    if len(deck) != 8:
        raise ValueError("a Clash Royale deck must contain exactly eight cards")

    card_ids = [card["id"] for card in deck]
    if len(card_ids) != len(set(card_ids)):
        raise ValueError("a Clash Royale deck cannot contain duplicate cards")

    effective_constraints = constraints or DeckConstraints()
    missing_required = effective_constraints.required_ids - set(card_ids)
    if missing_required:
        raise ConstraintError(
            f"required card {min(missing_required)} is not in the deck"
        )
    validate_special_count(
        "evolution_count", effective_constraints.evolution_count
    )
    validate_special_count(
        "hero_champion_count",
        effective_constraints.hero_champion_count,
    )
    if (
        effective_constraints.evolution_count is not None
        and effective_constraints.hero_champion_count is not None
        and effective_constraints.evolution_count
        + effective_constraints.hero_champion_count
        > 3
    ):
        raise ConstraintError("requested special forms exceed 3 slots")
    assignment = _resolve_special_assignment(
        deck, effective_constraints.required_ids, effective_constraints
    )
    if assignment is None:
        raise ConstraintError(
            "requested special forms cannot be assigned to distinct cards"
        )
    evolutions, heroes = assignment
    remaining = list(deck)
    arranged = []

    active_evolutions = [
        _take_first(
            remaining,
            lambda card, card_id=active["id"]: card["id"] == card_id,
        )
        for active in evolutions
    ]
    active_heroes = [
        _take_first(remaining, lambda card, card_id=active["id"]: card["id"] == card_id)
        for active in heroes
    ]

    evolution_card = (
        active_evolutions.pop(0) if active_evolutions else remaining.pop(0)
    )
    evolution_form = (
        ActiveForm.EVOLUTION
        if has_evolution(evolution_card) and evolution_card in evolutions
        else ActiveForm.NORMAL
    )
    arranged.append(DeckSlot(evolution_card, SlotRole.EVOLUTION, evolution_form))

    hero_card = active_heroes.pop(0) if active_heroes else remaining.pop(0)
    hero_form = (
        _hero_form(hero_card) if hero_card in heroes else ActiveForm.NORMAL
    )
    arranged.append(DeckSlot(hero_card, SlotRole.HERO, hero_form))

    if active_heroes:
        wild_card = active_heroes.pop(0)
        wild_form = _hero_form(wild_card)
    elif active_evolutions:
        wild_card = active_evolutions.pop(0)
        wild_form = ActiveForm.EVOLUTION
    else:
        wild_card = remaining.pop(0)
        wild_form = ActiveForm.NORMAL
    arranged.append(DeckSlot(wild_card, SlotRole.WILD, wild_form))

    arranged.extend(
        DeckSlot(card, SlotRole.NORMAL, ActiveForm.NORMAL)
        for card in remaining
    )
    return arranged

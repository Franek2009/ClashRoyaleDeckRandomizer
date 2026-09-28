import random

from card_model import (
    EVOLUTION_BIT,
    HERO_BIT,
    ActiveForm,
    CardType,
    DeckSlot,
    SlotRole,
    WildSlotMode,
    card_type,
    effective_form,
    has_evolution,
    has_hero,
    is_champion,
)
from constraints import (
    ConstraintError,
    DeckConstraints,
    _elixir_total_bounds,
    average_elixir,
    validate_constraints,
)


def _hero_capable(card):
    return has_hero(card) or is_champion(card)


def _type_targets(constraints):
    spell_targets = (
        [constraints.spell_count]
        if constraints.spell_count is not None
        else range(9)
    )
    building_targets = (
        [constraints.building_count]
        if constraints.building_count is not None
        else range(9)
    )
    targets = [
        {
            CardType.SPELL: spells,
            CardType.BUILDING: buildings,
            CardType.TROOP: 8 - spells - buildings,
        }
        for spells in spell_targets
        for buildings in building_targets
        if spells + buildings <= 8
    ]
    random.shuffle(targets)
    return targets


def _card_allowed_for_slot(card, role, constraints):
    if role is SlotRole.EVOLUTION:
        if is_champion(card):
            return False
        if constraints.evolution_slot_enabled:
            return has_evolution(card)
        return not has_evolution(card)
    if role is SlotRole.HERO:
        if constraints.hero_slot_enabled:
            return _hero_capable(card)
        return not _hero_capable(card)
    if role is SlotRole.WILD:
        if constraints.wild_slot_mode is WildSlotMode.EVOLUTION:
            return has_evolution(card) and not is_champion(card)
        if constraints.wild_slot_mode is WildSlotMode.HERO_CHAMPION:
            return _hero_capable(card)
        return not has_evolution(card) and not _hero_capable(card)
    return not is_champion(card)


def _select_elixir_fillers(candidates_by_type, needed, chosen_total, bounds):
    candidates = [
        card
        for kind in sorted(
            CardType, key=lambda item: len(candidates_by_type[item])
        )
        for card in candidates_by_type[kind]
        if needed[kind]
    ]
    random.shuffle(candidates)
    min_total, max_total = bounds
    failed_states = set()

    def search(index, remaining, total, selected):
        state = (index, tuple(remaining[kind] for kind in CardType), total)
        if state in failed_states:
            return None
        if not any(remaining.values()):
            if (min_total is None or total >= min_total) and (
                max_total is None or total <= max_total
            ):
                return list(selected)
            failed_states.add(state)
            return None

        available_costs = {
            kind: sorted(
                card["elixirCost"]
                for card in candidates[index:]
                if card_type(card) is kind
            )
            for kind in CardType
        }
        if any(
            len(available_costs[kind]) < remaining[kind]
            for kind in CardType
        ):
            failed_states.add(state)
            return None

        cheapest = total + sum(
            sum(available_costs[kind][: remaining[kind]])
            for kind in CardType
        )
        most_expensive = total + sum(
            sum(available_costs[kind][-remaining[kind] :])
            if remaining[kind]
            else 0
            for kind in CardType
        )
        if (max_total is not None and cheapest > max_total) or (
            min_total is not None and most_expensive < min_total
        ):
            failed_states.add(state)
            return None

        card = candidates[index]
        kind = card_type(card)
        if remaining[kind]:
            remaining[kind] -= 1
            selected.append(card)
            result = search(
                index + 1,
                remaining,
                total + card["elixirCost"],
                selected,
            )
            if result is not None:
                return result
            selected.pop()
            remaining[kind] += 1

        result = search(index + 1, remaining, total, selected)
        if result is not None:
            return result
        failed_states.add(state)
        return None

    return search(0, dict(needed), chosen_total, [])


def _select_untyped_elixir_fillers(candidates, needed, chosen_total, bounds):
    candidates = list(candidates)
    random.shuffle(candidates)
    min_total, max_total = bounds
    failed_states = set()

    def search(index, remaining, total, selected):
        state = (index, remaining, total)
        if state in failed_states:
            return None
        if remaining == 0:
            if (min_total is None or total >= min_total) and (
                max_total is None or total <= max_total
            ):
                return list(selected)
            failed_states.add(state)
            return None
        if len(candidates) - index < remaining:
            failed_states.add(state)
            return None

        costs = sorted(card["elixirCost"] for card in candidates[index:])
        if (max_total is not None and total + sum(costs[:remaining]) > max_total) or (
            min_total is not None
            and total + sum(costs[-remaining:]) < min_total
        ):
            failed_states.add(state)
            return None

        card = candidates[index]
        selected.append(card)
        result = search(
            index + 1,
            remaining - 1,
            total + card["elixirCost"],
            selected,
        )
        if result is not None:
            return result
        selected.pop()
        result = search(index + 1, remaining, total, selected)
        if result is not None:
            return result
        failed_states.add(state)
        return None

    return search(0, needed, chosen_total, [])


def _complete_ordered_deck(
    eligible_cards, slot_cards, target_counts, constraints
):
    slot_ids = {card["id"] for card in slot_cards}
    catalog_by_id = {card["id"]: card for card in eligible_cards}
    required_normal = [
        catalog_by_id[card_id]
        for card_id in constraints.required_ids - slot_ids
    ]
    if any(is_champion(card) for card in required_normal):
        return None

    normal_cards = list(required_normal)
    chosen_ids = slot_ids | {card["id"] for card in normal_cards}
    if len(chosen_ids) > 8:
        return None
    chosen = [*slot_cards, *normal_cards]
    chosen_counts = {
        kind: sum(card_type(card) is kind for card in chosen)
        for kind in CardType
    }
    needed = {
        kind: target_counts[kind] - chosen_counts[kind]
        for kind in CardType
    }
    if any(count < 0 for count in needed.values()) or sum(needed.values()) != (
        8 - len(chosen)
    ):
        return None

    candidates = [
        card
        for card in eligible_cards
        if card["id"] not in chosen_ids and not is_champion(card)
    ]
    candidates_by_type = {
        kind: [card for card in candidates if card_type(card) is kind]
        for kind in CardType
    }
    if any(
        needed[kind] > len(candidates_by_type[kind]) for kind in CardType
    ):
        return None

    bounds = _elixir_total_bounds(constraints)
    if any(bound is not None for bound in bounds):
        fillers = _select_elixir_fillers(
            candidates_by_type,
            needed,
            sum(card["elixirCost"] for card in chosen),
            bounds,
        )
        if fillers is None:
            return None
    else:
        fillers = []
        for kind in CardType:
            fillers.extend(
                random.sample(candidates_by_type[kind], needed[kind])
            )

    normal_cards.extend(fillers)
    random.shuffle(normal_cards)
    return [*slot_cards, *normal_cards]


def _complete_untyped_ordered_deck(eligible_cards, slot_cards, constraints):
    slot_ids = {card["id"] for card in slot_cards}
    catalog_by_id = {card["id"]: card for card in eligible_cards}
    required_normal = [
        catalog_by_id[card_id]
        for card_id in constraints.required_ids - slot_ids
    ]
    if any(is_champion(card) for card in required_normal):
        return None
    chosen_ids = slot_ids | {card["id"] for card in required_normal}
    candidates = [
        card
        for card in eligible_cards
        if card["id"] not in chosen_ids and not is_champion(card)
    ]
    needed = 5 - len(required_normal)
    if needed < 0 or len(candidates) < needed:
        return None
    bounds = _elixir_total_bounds(constraints)
    if any(bound is not None for bound in bounds):
        fillers = _select_untyped_elixir_fillers(
            candidates,
            needed,
            sum(card["elixirCost"] for card in [*slot_cards, *required_normal]),
            bounds,
        )
        if fillers is None:
            return None
    else:
        fillers = random.sample(candidates, needed)
    normal_cards = [*required_normal, *fillers]
    random.shuffle(normal_cards)
    return [*slot_cards, *normal_cards]


def _resolve_constrained_deck(eligible_cards, constraints):
    roles = (SlotRole.EVOLUTION, SlotRole.HERO, SlotRole.WILD)
    candidates_by_role = {
        role: [
            card
            for card in eligible_cards
            if _card_allowed_for_slot(card, role, constraints)
        ]
        for role in roles
    }
    for cards in candidates_by_role.values():
        random.shuffle(cards)

    bounds = _elixir_total_bounds(constraints)
    if constraints.spell_count is None and constraints.building_count is None:
        def choose_untyped_slots(index, selected):
            if index == len(roles):
                return _complete_untyped_ordered_deck(
                    eligible_cards, selected, constraints
                )
            role = roles[index]
            selected_ids = {card["id"] for card in selected}
            for card in candidates_by_role[role]:
                if card["id"] in selected_ids:
                    continue
                result = choose_untyped_slots(index + 1, [*selected, card])
                if result is not None:
                    return result
            return None

        return choose_untyped_slots(0, [])

    for target_counts in _type_targets(constraints):
        def choose_slots(index, selected, remaining_counts):
            if index == len(roles):
                return _complete_ordered_deck(
                    eligible_cards, selected, target_counts, constraints
                )

            role = roles[index]
            selected_ids = {card["id"] for card in selected}
            candidates = [
                card
                for card in candidates_by_role[role]
                if card["id"] not in selected_ids
                and remaining_counts[card_type(card)] > 0
            ]
            for card in candidates:
                kind = card_type(card)
                remaining_counts[kind] -= 1
                result = choose_slots(
                    index + 1, [*selected, card], remaining_counts
                )
                remaining_counts[kind] += 1
                if result is not None:
                    return result
            return None

        deck = choose_slots(0, [], dict(target_counts))
        if deck is not None:
            return deck
    return None


def _prepare_constraints(cards, constraints):
    eligible_cards = validate_constraints(cards, constraints)
    deck = _resolve_constrained_deck(eligible_cards, constraints)
    if deck is not None:
        return eligible_cards, deck
    raise ConstraintError(
        "requested slot, card type, and elixir constraints cannot produce "
        "a valid 8-card deck",
        code="constraints_not_feasible",
    )


def get_random_deck(cards, constraints=None):
    if constraints is not None:
        eligible_cards, deck = _prepare_constraints(cards, constraints)
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


def _slot_active_counts(arranged):
    evolutions = sum(
        slot.active_form is ActiveForm.EVOLUTION for slot in arranged
    )
    heroes = sum(
        slot.active_form in {ActiveForm.HERO, ActiveForm.CHAMPION}
        for slot in arranged
    )
    return evolutions, heroes


def _validate_generated_deck(deck, eligible_cards, constraints):
    deck_ids = {card["id"] for card in deck}
    if len(deck) != 8 or len(deck_ids) != 8:
        raise RuntimeError("generated deck must contain 8 unique cards")
    if not constraints.required_ids <= deck_ids:
        raise RuntimeError("generated deck is missing a required card")
    if deck_ids & constraints.banned_ids:
        raise RuntimeError("generated deck contains a banned card")
    if not deck_ids <= {card["id"] for card in eligible_cards}:
        raise RuntimeError("generated deck contains an unavailable card")

    arranged = arrange_deck(deck, constraints)
    for slot in arranged:
        expected = effective_form(
            slot.card,
            slot.role,
            evolution_slot_enabled=constraints.evolution_slot_enabled,
            hero_slot_enabled=constraints.hero_slot_enabled,
            wild_slot_mode=constraints.wild_slot_mode,
        )
        if slot.active_form is not expected:
            raise RuntimeError("generated deck has an inconsistent active form")
    for slot in arranged[:3]:
        if not _card_allowed_for_slot(slot.card, slot.role, constraints):
            raise RuntimeError("generated deck has an unsafe special slot")

    for kind, requested in (
        (CardType.SPELL, constraints.spell_count),
        (CardType.BUILDING, constraints.building_count),
    ):
        if requested is not None and sum(
            card_type(card) is kind for card in deck
        ) != requested:
            raise RuntimeError(f"generated deck has the wrong {kind.value} count")

    min_total, max_total = _elixir_total_bounds(constraints)
    if min_total is not None or max_total is not None:
        average = average_elixir(deck)
        if average is None:
            raise RuntimeError("generated deck has no static average elixir")
        total = sum(card["elixirCost"] for card in deck)
        if (min_total is not None and total < min_total) or (
            max_total is not None and total > max_total
        ):
            raise RuntimeError(
                "generated deck violates average elixir constraints"
            )


def _legacy_arrange_deck(deck):
    remaining = list(deck)
    evolution_card = next(
        (card for card in remaining if has_evolution(card)), remaining[0]
    )
    remaining.remove(evolution_card)
    hero_card = next(
        (card for card in remaining if _hero_capable(card)), remaining[0]
    )
    remaining.remove(hero_card)
    wild_card = next(
        (card for card in remaining if _hero_capable(card)),
        next(
            (card for card in remaining if has_evolution(card)),
            remaining[0],
        ),
    )
    remaining.remove(wild_card)
    if _hero_capable(wild_card):
        wild_form = (
            ActiveForm.CHAMPION
            if is_champion(wild_card)
            else ActiveForm.HERO
        )
    elif has_evolution(wild_card):
        wild_form = ActiveForm.EVOLUTION
    else:
        wild_form = ActiveForm.NORMAL
    return [
        DeckSlot(
            evolution_card,
            SlotRole.EVOLUTION,
            ActiveForm.EVOLUTION
            if has_evolution(evolution_card)
            else ActiveForm.NORMAL,
        ),
        DeckSlot(
            hero_card,
            SlotRole.HERO,
            ActiveForm.CHAMPION
            if is_champion(hero_card)
            else (
                ActiveForm.HERO
                if has_hero(hero_card)
                else ActiveForm.NORMAL
            ),
        ),
        DeckSlot(wild_card, SlotRole.WILD, wild_form),
        *[
            DeckSlot(card, SlotRole.NORMAL, ActiveForm.NORMAL)
            for card in remaining
        ],
    ]


def _arrange_ordered_deck(deck, constraints, *, validate_safety=True):
    roles = [
        SlotRole.EVOLUTION,
        SlotRole.HERO,
        SlotRole.WILD,
        *([SlotRole.NORMAL] * 5),
    ]
    arranged = []
    for card, role in zip(deck, roles):
        if (
            validate_safety
            and role is not SlotRole.NORMAL
            and not _card_allowed_for_slot(card, role, constraints)
        ):
            raise ConstraintError(
                f"card {card['id']} is not valid for the {role.value} slot",
                code="invalid_slot_assignment",
            )
        active = effective_form(
            card,
            role,
            evolution_slot_enabled=constraints.evolution_slot_enabled,
            hero_slot_enabled=constraints.hero_slot_enabled,
            wild_slot_mode=constraints.wild_slot_mode,
        )
        arranged.append(DeckSlot(card, role, active))
    return arranged


def arrange_deck(deck, constraints=None):
    """Map an ordered eight-card deck to its three physical special slots."""
    if len(deck) != 8:
        raise ValueError("a Clash Royale deck must contain exactly eight cards")
    card_ids = [card["id"] for card in deck]
    if len(card_ids) != len(set(card_ids)):
        raise ValueError("a Clash Royale deck cannot contain duplicate cards")
    if constraints is None:
        return _legacy_arrange_deck(deck)
    missing_required = constraints.required_ids - set(card_ids)
    if missing_required:
        raise ConstraintError(
            f"required card {min(missing_required)} is not in the deck"
        )
    return _arrange_ordered_deck(deck, constraints)

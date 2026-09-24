import random
from dataclasses import dataclass
from enum import Enum


EVOLUTION_BIT = 1
HERO_BIT = 2


class ActiveForm(Enum):
    NORMAL = "normal"
    EVOLUTION = "evolution"
    HERO = "hero"
    CHAMPION = "champion"


class SlotRole(Enum):
    EVOLUTION = "evolution"
    HERO = "hero"
    WILD = "wild"
    NORMAL = "normal"


def has_evolution(card):
    return bool(card.get("maxEvolutionLevel", 0) & EVOLUTION_BIT)


def has_hero(card):
    return bool(card.get("maxEvolutionLevel", 0) & HERO_BIT)


def is_champion(card):
    return card.get("rarity") == "champion"


@dataclass(frozen=True)
class DeckSlot:
    card: dict
    role: SlotRole
    active_form: ActiveForm = ActiveForm.NORMAL

    def __post_init__(self):
        if self.active_form is ActiveForm.NORMAL:
            return

        allowed_forms = {
            SlotRole.EVOLUTION: {ActiveForm.EVOLUTION},
            SlotRole.HERO: {ActiveForm.HERO, ActiveForm.CHAMPION},
            SlotRole.WILD: {
                ActiveForm.EVOLUTION,
                ActiveForm.HERO,
                ActiveForm.CHAMPION,
            },
            SlotRole.NORMAL: set(),
        }
        if self.active_form not in allowed_forms[self.role]:
            raise ValueError(
                f"{self.active_form.value} cannot be active in "
                f"a {self.role.value} slot"
            )

        capability_checks = {
            ActiveForm.EVOLUTION: has_evolution,
            ActiveForm.HERO: has_hero,
            ActiveForm.CHAMPION: is_champion,
        }
        if not capability_checks[self.active_form](self.card):
            raise ValueError(
                f"card does not support active form {self.active_form.value}"
            )

    @property
    def is_evolution(self):
        """Compatibility property for the current, unchanged template."""
        return self.active_form is ActiveForm.EVOLUTION


def get_random_deck(cards):
    chosen_cards = []
    evolution_cards = [card for card in cards if has_evolution(card)]

    chosen_cards.extend(random.sample(evolution_cards, 2))

    champion_count = sum(is_champion(card) for card in chosen_cards)
    remaining_cards = [card for card in cards if card not in chosen_cards]

    while len(chosen_cards) < 8:
        card = random.choice(remaining_cards)

        if is_champion(card) and champion_count >= 2:
            continue

        chosen_cards.append(card)

        if is_champion(card):
            champion_count += 1

        remaining_cards.remove(card)

    return chosen_cards


def _take_first(cards, predicate):
    for index, card in enumerate(cards):
        if predicate(card):
            return cards.pop(index)
    return None


def _hero_form(card):
    if is_champion(card):
        return ActiveForm.CHAMPION
    return ActiveForm.HERO


def arrange_deck(deck):
    """Assign eight unique cards to the current Evo, Hero and Wild slots."""
    if len(deck) != 8:
        raise ValueError("a Clash Royale deck must contain exactly eight cards")

    card_ids = [card["id"] for card in deck]
    if len(card_ids) != len(set(card_ids)):
        raise ValueError("a Clash Royale deck cannot contain duplicate cards")

    remaining = list(deck)
    arranged = []

    evolution_card = _take_first(remaining, has_evolution)
    if evolution_card is None:
        evolution_card = remaining.pop(0)
        evolution_form = ActiveForm.NORMAL
    else:
        evolution_form = ActiveForm.EVOLUTION
    arranged.append(
        DeckSlot(evolution_card, SlotRole.EVOLUTION, evolution_form)
    )

    hero_card = _take_first(
        remaining, lambda card: is_champion(card) or has_hero(card)
    )
    if hero_card is None:
        hero_card = remaining.pop(0)
        hero_form = ActiveForm.NORMAL
    else:
        hero_form = _hero_form(hero_card)
    arranged.append(DeckSlot(hero_card, SlotRole.HERO, hero_form))

    wild_card = _take_first(
        remaining, lambda card: is_champion(card) or has_hero(card)
    )
    if wild_card is not None:
        wild_form = _hero_form(wild_card)
    else:
        wild_card = _take_first(remaining, has_evolution)
        if wild_card is None:
            wild_card = remaining.pop(0)
            wild_form = ActiveForm.NORMAL
        else:
            wild_form = ActiveForm.EVOLUTION
    arranged.append(DeckSlot(wild_card, SlotRole.WILD, wild_form))

    arranged.extend(
        DeckSlot(card, SlotRole.NORMAL, ActiveForm.NORMAL)
        for card in remaining
    )
    return arranged

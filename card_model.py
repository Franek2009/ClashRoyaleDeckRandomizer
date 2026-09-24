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


class CardType(Enum):
    TROOP = "troop"
    SPELL = "spell"
    BUILDING = "building"


def card_type(card):
    card_id = card.get("id")
    if not isinstance(card_id, int) or isinstance(card_id, bool):
        raise ValueError("card ID must be an integer")

    supported_spaces = (
        (range(26_000_000, 27_000_000), CardType.TROOP),
        (range(27_000_000, 28_000_000), CardType.BUILDING),
        (range(28_000_000, 29_000_000), CardType.SPELL),
    )
    for card_ids, kind in supported_spaces:
        if card_id in card_ids:
            return kind
    raise ValueError(f"unsupported card ID space for card {card_id}")


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

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


class WildSlotMode(Enum):
    OFF = "off"
    EVOLUTION = "evolution"
    HERO_CHAMPION = "hero_champion"


class CardType(Enum):
    TROOP = "troop"
    SPELL = "spell"
    BUILDING = "building"


CARD_TYPE_OVERRIDES = {
    27000010: CardType.TROOP,  # Furnace, reworked from a Building
    28000025: CardType.TROOP,  # Spirit Empress
}


def card_type(card):
    card_id = card.get("id")
    if not isinstance(card_id, int) or isinstance(card_id, bool):
        raise ValueError("card ID must be an integer")

    if card_id in CARD_TYPE_OVERRIDES:
        return CARD_TYPE_OVERRIDES[card_id]

    # Legacy ID namespaces provide a derived classification for this snapshot;
    # the API does not expose an authoritative card-type field.
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


def effective_form(
    card,
    role,
    *,
    evolution_slot_enabled=True,
    hero_slot_enabled=True,
    wild_slot_mode=WildSlotMode.EVOLUTION,
):
    if role is SlotRole.EVOLUTION:
        if evolution_slot_enabled and has_evolution(card):
            return ActiveForm.EVOLUTION
        return ActiveForm.NORMAL
    if role is SlotRole.HERO:
        if not hero_slot_enabled:
            return ActiveForm.NORMAL
        if is_champion(card):
            return ActiveForm.CHAMPION
        if has_hero(card):
            return ActiveForm.HERO
        return ActiveForm.NORMAL
    if role is SlotRole.WILD:
        if wild_slot_mode is WildSlotMode.EVOLUTION and has_evolution(card):
            return ActiveForm.EVOLUTION
        if wild_slot_mode is WildSlotMode.HERO_CHAMPION:
            if is_champion(card):
                return ActiveForm.CHAMPION
            if has_hero(card):
                return ActiveForm.HERO
        return ActiveForm.NORMAL
    return ActiveForm.NORMAL


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

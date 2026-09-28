import json

from flask import Flask, render_template, request

from deck_link import generate_deck_link
from randomizer import (
    ActiveForm,
    CardType,
    ConstraintError,
    DeckConstraints,
    WildSlotMode,
    arrange_deck,
    average_elixir,
    card_type,
    get_random_deck,
    has_evolution,
    has_hero,
)


app = Flask(__name__)

COUNT_FIELDS = (
    "spell_count",
    "building_count",
)
SLOT_FIELDS = (
    "evolution_slot_enabled",
    "hero_slot_enabled",
    "wild_slot_mode",
)
AVERAGE_FIELDS = ("min_average_elixir", "max_average_elixir")
CARD_POOL_FIELDS = ("available_ids", "banned_ids", "required_ids")

FRIENDLY_ERRORS = {
    "type_counts_exceed_deck_size": (
        "You selected more card types than can fit in an 8-card deck."
    ),
    "not_enough_spells": (
        "There aren't enough Spell cards available for this selection."
    ),
    "not_enough_buildings": (
        "There aren't enough Building cards available for this selection."
    ),
    "required_champion_needs_slot": (
        "A required Champion needs the Hero Slot or Wild Slot set to "
        "Hero / Champion."
    ),
    "average_min_greater_than_max": (
        "Minimum deck average cannot be greater than maximum deck average."
    ),
    "constraints_not_feasible": (
        "These settings cannot produce a valid deck. Try relaxing one or "
        "more constraints."
    ),
    "invalid_count": "Choose Any or a whole number from the list.",
    "invalid_average": "Enter a valid number for the deck average.",
    "invalid_slot_selection": "Choose a valid special-slot setting.",
    "invalid_card_selection": (
        "One or more selected cards are no longer available. Refresh the "
        "page and try again."
    ),
    "unknown_card_selection": (
        "One or more selected cards are no longer available. Refresh the "
        "page and try again."
    ),
    "required_banned_conflict": "Required cards cannot also be banned.",
    "required_not_available": (
        "Every required card must also be included in the available card "
        "pool."
    ),
    "not_enough_eligible_cards": (
        "There aren't enough available cards to build an 8-card deck."
    ),
    "too_many_required": "A deck can contain at most 8 required cards.",
}

GENERIC_CONSTRAINT_ERROR = (
    "These settings cannot produce a valid deck. Try relaxing one or more "
    "constraints."
)


def _default_form_values():
    return {
        "evolution_slot_enabled": "on",
        "hero_slot_enabled": "on",
        "wild_slot_mode": WildSlotMode.EVOLUTION.value,
        "available_mode": "all",
        **{field: [] for field in CARD_POOL_FIELDS},
        **{field: "any" for field in COUNT_FIELDS},
        **{field: "" for field in AVERAGE_FIELDS},
    }


def _parse_optional_int(field, value):
    if value.strip().lower() in {"", "any"}:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise ConstraintError(
            f"{field} must be an integer or Any", code="invalid_count"
        ) from error


def _parse_optional_float(field, value):
    if value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError as error:
        raise ConstraintError(
            f"{field} must be a number", code="invalid_average"
        ) from error


def _parse_wild_mode(value):
    try:
        return WildSlotMode(value)
    except ValueError as error:
        raise ConstraintError(
            "wild_slot_mode is invalid", code="invalid_slot_selection"
        ) from error


def _parse_card_ids(values):
    try:
        return frozenset(int(value) for value in values)
    except (TypeError, ValueError) as error:
        raise ConstraintError(
            "card IDs must be integers", code="invalid_card_selection"
        ) from error


def _constraints_from_form(form_values):
    available_mode = form_values["available_mode"]
    if available_mode not in {"all", "custom"}:
        raise ConstraintError(
            "available_mode is invalid", code="invalid_card_selection"
        )
    return DeckConstraints(
        available_ids=(
            None
            if available_mode == "all"
            else _parse_card_ids(form_values["available_ids"])
        ),
        banned_ids=_parse_card_ids(form_values["banned_ids"]),
        required_ids=_parse_card_ids(form_values["required_ids"]),
        evolution_slot_enabled=form_values["evolution_slot_enabled"] == "on",
        hero_slot_enabled=form_values["hero_slot_enabled"] == "on",
        wild_slot_mode=_parse_wild_mode(form_values["wild_slot_mode"]),
        **{
            field: _parse_optional_int(field, form_values[field])
            for field in COUNT_FIELDS
        },
        **{
            field: _parse_optional_float(field, form_values[field])
            for field in AVERAGE_FIELDS
        },
    )


def _deck_summary(deck, arranged_deck):
    average = average_elixir(deck)
    if average is None:
        average_display = "—"
    else:
        average_display = f"{average:.2f}".rstrip("0")
        if average_display.endswith("."):
            average_display += "0"

    return {
        "evolutions": sum(
            slot.active_form is ActiveForm.EVOLUTION
            for slot in arranged_deck
        ),
        "heroes": sum(
            slot.active_form in {ActiveForm.HERO, ActiveForm.CHAMPION}
            for slot in arranged_deck
        ),
        "spells": sum(card_type(card) is CardType.SPELL for card in deck),
        "buildings": sum(
            card_type(card) is CardType.BUILDING for card in deck
        ),
        "average_elixir": average_display,
        "has_variable_elixir": average is None,
        "special_slots": [
            {
                "role": slot.role.value,
                "form": slot.active_form.value,
            }
            for slot in arranged_deck[:3]
        ],
    }


@app.route("/")
def home():
    with open("cards.json", encoding="utf-8") as file:
        cards = json.load(file)["items"]
    return render_template(
        "index.html", cards=cards, form_values=_default_form_values()
    )


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/generate", methods=["POST"])
def generate():
    defaults = _default_form_values()
    form_values = {
        field: request.form.get(field, defaults[field])
        for field in (*SLOT_FIELDS, *COUNT_FIELDS, *AVERAGE_FIELDS)
    }
    form_values["available_mode"] = request.form.get(
        "available_mode", defaults["available_mode"]
    )
    form_values.update(
        {field: request.form.getlist(field) for field in CARD_POOL_FIELDS}
    )

    with open("cards.json", encoding="utf-8") as file:
        cards = json.load(file)["items"]

    try:
        constraints = _constraints_from_form(form_values)
        random_deck = get_random_deck(cards, constraints)
        arranged_deck = arrange_deck(random_deck, constraints)
    except ConstraintError as error:
        return render_template(
            "index.html",
            error_message=FRIENDLY_ERRORS.get(
                error.code, GENERIC_CONSTRAINT_ERROR
            ),
            cards=cards,
            form_values=form_values,
        )

    deck_link = generate_deck_link(arranged_deck)
    wild_card = arranged_deck[2].card
    wild_form_notice = None
    if has_evolution(wild_card) and has_hero(wild_card):
        selected_form = (
            "Evolution"
            if constraints.wild_slot_mode is WildSlotMode.EVOLUTION
            else "Hero"
        )
        wild_form_notice = (
            "After importing the deck, set the Wild Slot to "
            f"{selected_form}."
        )

    return render_template(
        "index.html",
        deck=arranged_deck,
        deck_link=deck_link,
        deck_summary=_deck_summary(random_deck, arranged_deck),
        wild_form_notice=wild_form_notice,
        cards=cards,
        form_values=form_values,
    )


if __name__ == "__main__":
    app.run(debug=True)

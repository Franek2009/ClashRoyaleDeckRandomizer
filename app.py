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

FRIENDLY_ERRORS = {
    "type_counts_exceed_deck_size": (
        "You selected more card types than can fit in an 8-card deck. "
        "Reduce one of the values."
    ),
    "not_enough_spells": (
        "There aren't enough available Spell cards to build this deck."
    ),
    "not_enough_buildings": (
        "There aren't enough available Building cards to build this deck."
    ),
    "required_champion_needs_slot": (
        "A required Champion needs either the Hero Slot or the Wild Slot "
        "set to Hero / Champion."
    ),
    "average_min_greater_than_max": (
        "Minimum deck average cannot be greater than maximum deck average."
    ),
    "constraints_not_feasible": (
        "These slot and deck constraints cannot be satisfied together. "
        "Try relaxing one of the selections."
    ),
}


def _default_form_values():
    return {
        "evolution_slot_enabled": "on",
        "hero_slot_enabled": "on",
        "wild_slot_mode": WildSlotMode.EVOLUTION.value,
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
            f"{field} must be an integer or Any"
        ) from error


def _parse_optional_float(field, value):
    if value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError as error:
        raise ConstraintError(f"{field} must be a number") from error


def _parse_wild_mode(value):
    try:
        return WildSlotMode(value)
    except ValueError as error:
        raise ConstraintError("wild_slot_mode is invalid") from error


def _constraints_from_form(form_values):
    return DeckConstraints(
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
        average_display = "N/A (Mirror)"
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
    return render_template(
        "index.html", form_values=_default_form_values()
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

    with open("cards.json", encoding="utf-8") as file:
        cards = json.load(file)["items"]

    try:
        constraints = _constraints_from_form(form_values)
        random_deck = get_random_deck(cards, constraints)
        arranged_deck = arrange_deck(random_deck, constraints)
    except ConstraintError as error:
        return render_template(
            "index.html",
            error_message=FRIENDLY_ERRORS.get(error.code, str(error)),
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
            "After importing the deck, select the "
            f"{selected_form} form for the Wild Slot in Clash Royale."
        )

    return render_template(
        "index.html",
        deck=arranged_deck,
        deck_link=deck_link,
        deck_summary=_deck_summary(random_deck, arranged_deck),
        wild_form_notice=wild_form_notice,
        form_values=form_values,
    )


if __name__ == "__main__":
    app.run(debug=True)

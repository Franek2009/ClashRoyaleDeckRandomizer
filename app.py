import json

from flask import Flask, render_template, request

from deck_link import generate_deck_link
from randomizer import (
    ActiveForm,
    CardType,
    ConstraintError,
    DeckConstraints,
    arrange_deck,
    average_elixir,
    card_type,
    get_random_deck,
)


app = Flask(__name__)

COUNT_FIELDS = (
    "evolution_count",
    "hero_champion_count",
    "spell_count",
    "building_count",
)
AVERAGE_FIELDS = ("min_average_elixir", "max_average_elixir")


def _default_form_values():
    return {
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


def _constraints_from_form(form_values):
    return DeckConstraints(
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
        for field in (*COUNT_FIELDS, *AVERAGE_FIELDS)
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
            error_message=str(error),
            form_values=form_values,
        )

    deck_link = generate_deck_link(arranged_deck)

    return render_template(
        "index.html",
        deck=arranged_deck,
        deck_link=deck_link,
        deck_summary=_deck_summary(random_deck, arranged_deck),
        form_values=form_values,
    )


if __name__ == "__main__":
    app.run(debug=True)

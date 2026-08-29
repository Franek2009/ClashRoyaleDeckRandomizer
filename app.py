import json

from flask import Flask, render_template

from deck_link import generate_deck_link
from randomizer import arrange_deck, get_random_deck


app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    with open("cards.json", encoding="utf-8") as file:
        cards = json.load(file)["items"]

    random_deck = get_random_deck(cards)
    arranged_deck = arrange_deck(random_deck)
    deck_link = generate_deck_link(arranged_deck)

    return render_template(
        "index.html",
        deck=arranged_deck,
        deck_link=deck_link,
    )


if __name__ == "__main__":
    app.run(debug=True)

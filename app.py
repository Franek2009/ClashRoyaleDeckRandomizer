from flask import Flask, render_template
import json
from randomizer import get_random_deck


app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    with open("cards.json", "r") as file:
        cards = json.load(file)

    cards = cards["items"]

    deck = get_random_deck(cards)

    return render_template("index.html", deck=deck)


if __name__ == "__main__":
    app.run(debug=True)

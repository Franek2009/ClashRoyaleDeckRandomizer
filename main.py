import json

from randomizer import get_random_deck

with open("cards.json", encoding="utf-8") as file:
    cards = json.load(file)["items"]

deck = get_random_deck(cards)
for position, card in enumerate(deck, start=1):
    print(f"{position}. {card['name']}")

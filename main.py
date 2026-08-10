import json
from randomizer import get_random_deck

with open("cards.json", "r") as file:
    cards = json.load(file)

cards = cards['items']

deck = get_random_deck(cards)

for i, card in enumerate(deck, 1):
    print(f"{i}. {card['name']}")

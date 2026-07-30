import json

with open("cards.json", "r") as file:
    cards = json.load(file)
print(cards[0])

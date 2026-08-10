import json
from randomizer import get_random_deck

with open("cards.json", "r") as file:
    cards = json.load(file)

with open("unavailable_cards.json", "r") as file:
    unavailable_cards = json.load(file)

unavailable_cards_id = []
available_cards = []

for unavailable_card in unavailable_cards:
    unavailable_cards_id.append(unavailable_card['id'])

for card in cards:
    if card['id'] not in unavailable_cards_id:
        available_cards.append(card)

deck = get_random_deck(available_cards)
for number, card in enumerate(deck, 1):
    print(number, card['name'])

#print(len(cards))
#print(len(available_cards))
#print(cards[0])
#print(unavailable_cards[0])
#print(card_names)
#print(card_id)
#print(unavailable_cards_id)
#print(available_cards)

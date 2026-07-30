import json

with open("cards.json", "r") as file:
    cards = json.load(file)

card_names = []
#card_id = []

for card in cards:
    card_names.append(card['name'])
#    card_id.append(card['id'])

#print(cards[0])

#print(card_names)
#print(card_id)

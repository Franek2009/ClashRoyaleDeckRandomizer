import json

with open("cards.json", "r") as file:
    cards = json.load(file)

with open("unavailable_cards.json", "r") as file:
    unavailable_cards = json.load(file)

card_names = []
card_id = []
unavailable_cards_id = []
available_cards = []

for unavailable_card in unavailable_cards:
    unavailable_cards_id.append(unavailable_card['id'])


for card in cards:
    card_names.append(card['name'])
    card_id.append(card['id'])
    if card['id'] not in unavailable_cards_id:
        available_cards.append(card)

for card in available_cards:
    if card['id'] in unavailable_cards_id:
        print("BŁĄD:", card['name'])


#print(len(cards))
#print(len(available_cards))

#print(cards[0])
#print(unavailable_cards[0])
#print(card_names)
#print(card_id)
#print(unavailable_cards_id)

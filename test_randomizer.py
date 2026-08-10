import json
from randomizer import get_random_deck

with open("cards.json", "r") as file:
    cards = json.load(file)

cards = cards["items"]

for i in range(1000):
    deck = get_random_deck(cards)

    if len(deck) != 8:
        print("BŁĄD: deck nie ma 8 kart")
        break

    ids = [card["id"] for card in deck]

    if len(ids) != len(set(ids)):
        print("BŁĄD: znaleziono duplikat")
        break

    evolution_count = 0
    champion_count = 0

    for card in deck:
        if "evolutionMedium" in card["iconUrls"]:
            evolution_count += 1

        if card["rarity"] == "champion":
            champion_count += 1

    if evolution_count < 2:
        print("BŁĄD: mniej niż 2 Evo")
        break

    if champion_count > 2:
        print("BŁĄD: więcej niż 2 Championów")
        break

else:
    print("1000 testów zakończonych pomyślnie!")

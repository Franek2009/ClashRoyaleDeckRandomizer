import json
from randomizer import get_random_deck, arrange_deck, has_evolution


with open("cards.json", "r") as file:
    cards = json.load(file)["items"]


for i in range(1000):

    deck = get_random_deck(cards)

    # 1. Deck ma 8 kart
    if len(deck) != 8:
        print("BŁĄD: deck nie ma 8 kart")
        print("Test:", i + 1)
        break

    # 2. Brak duplikatów
    ids = [card["id"] for card in deck]

    if len(ids) != len(set(ids)):
        print("BŁĄD: znaleziono duplikat")
        print("Test:", i + 1)
        break

    # 3. Maksymalnie 2 Championów
    champion_count = sum(
        card["rarity"] == "champion"
        for card in deck
    )

    if champion_count > 2:
        print("BŁĄD: więcej niż 2 Championów")
        print("Test:", i + 1)
        break

    # 4. Ułożenie decku
    try:
        arranged_deck = arrange_deck(deck)

    except Exception as error:
        print("BŁĄD podczas arrange_deck()")
        print("Test:", i + 1)
        print("Błąd:", error)
        break

    # 5. Nadal musi być 8 slotów
    if len(arranged_deck) != 8:
        print("BŁĄD: arranged deck nie ma 8 kart")
        print("Test:", i + 1)
        break

    for slot_number, slot in enumerate(arranged_deck, start=1):

        card = slot["card"]
        is_evolution = slot["is_evolution"]

        # 6. EVO tylko na slocie 1 lub 3
        if is_evolution and slot_number not in (1, 3):
            print(
                f"BŁĄD: EVO znajduje się na slocie {slot_number}"
            )
            print("Test:", i + 1)
            break

        # 7. Jeśli slot jest EVO, karta musi mieć EVO
        if is_evolution and not has_evolution(card):
            print(
                "BŁĄD: slot oznaczony jako EVO, "
                "ale karta nie ma ewolucji"
            )
            print("Test:", i + 1)
            break

        # 8. Slot 2 nigdy nie może być EVO
        if slot_number == 2 and is_evolution:
            print("BŁĄD: EVO znajduje się na slocie 2")
            print("Test:", i + 1)
            break

        # 9. Champion tylko na slocie 2 lub 3
        if card["rarity"] == "champion":
            if slot_number not in (2, 3):
                print(
                    f"BŁĄD: Champion znajduje się na slocie {slot_number}"
                )
                print("Test:", i + 1)
                break

    else:
        # Wszystkie sloty przeszły testy
        continue

    # Jeden ze slotów miał błąd
    break

else:
    print("1000 testów zakończonych pomyślnie!")

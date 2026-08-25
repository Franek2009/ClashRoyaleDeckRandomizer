import random


def has_evolution(card):
    return "evolutionMedium" in card.get("iconUrls", {})


def is_champion(card):
    return card.get("rarity") == "champion"


def get_random_deck(loadCards):
    champion_count = 0
    chosen_cards = []
    evolution_cards = []
    remaining_cards = []

    for card in loadCards:
        if has_evolution(card):
            evolution_cards.append(card)

    chosen_cards.extend(random.sample(evolution_cards, 2))

    for card in chosen_cards:
        if is_champion(card):
            champion_count += 1

    for card in loadCards:
        if card not in chosen_cards:
            remaining_cards.append(card)

    while len(chosen_cards) < 8:
        card = random.choice(remaining_cards)

        if card["rarity"] == "champion" and champion_count >= 2:
            continue

        chosen_cards.append(card)

        if card["rarity"] == "champion":
            champion_count += 1

        remaining_cards.remove(card)

    return chosen_cards


def arrange_deck(deck):
    evolution_cards = []
    champion_cards = []
    normal_cards = []

    for card in deck:
        if is_champion(card):
            champion_cards.append(card)
        elif has_evolution(card):
            evolution_cards.append(card)
        else:
            normal_cards.append(card)

    arranged_deck = []

    if evolution_cards:
        arranged_deck.append(evolution_cards.pop())

    if champion_cards:
        arranged_deck.append(champion_cards.pop())

    if champion_cards:
        arranged_deck.append(champion_cards.pop())
    elif evolution_cards:
        arranged_deck.append(evolution_cards.pop())

    arranged_deck.extend(evolution_cards)
    arranged_deck.extend(normal_cards)

    return arranged_deck

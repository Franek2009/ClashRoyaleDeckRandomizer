import random

def get_random_deck(loadCards):
    champion_count = 0
    chosen_cards = []
    evolution_cards = []
    remaining_cards = []

    for card in loadCards:
        if 'evolutionMedium' in card['iconUrls']:
            evolution_cards.append(card)

    chosen_cards.extend(random.sample(evolution_cards, 2))

    for card in chosen_cards:
        if card['rarity'] == 'champion':
            champion_count += 1

    for card in loadCards:
        if card not in chosen_cards:
            remaining_cards.append(card)

    while len(chosen_cards) < 8:
        card = random.choice(remaining_cards)

        if card['rarity'] == 'champion' and champion_count >= 2:
            continue

        chosen_cards.append(card)

        if card['rarity'] == 'champion':
            champion_count += 1

        remaining_cards.remove(card)

    return chosen_cards

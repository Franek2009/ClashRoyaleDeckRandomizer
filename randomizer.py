import random

def get_random_deck(loadCards):
    chosen_cards = []
    evolution_cards = []
    remaining_cards = []

    for card in loadCards:
        if 'evolutionMedium' in card['iconUrls']:
            evolution_cards.append(card)

    chosen_cards.extend(random.sample(evolution_cards, 2))
    for card in loadCards:
        if card not in chosen_cards:
            remaining_cards.append(card)

    chosen_cards.extend(random.sample(remaining_cards, 6))
    return chosen_cards

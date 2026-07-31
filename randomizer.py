import random

def get_random_deck(loadCards):
    chosen_cards = []
    for i in range(8):
        chosen_cards.append(random.choice(loadCards))
    return chosen_cards

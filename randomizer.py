import random

def get_random_deck(loadCards):
    chosen_cards = []
    chosen_cards.extend(random.sample(loadCards, 8))
    return chosen_cards

# Kod Pawła
#    while len(chosen_cards) < 8:
#        card = random.choice(loadCards)
#        if card not in chosen_cards:
#            chosen_cards.append(card)
#     return chosen_cards

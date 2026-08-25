def generate_deck_link(deck):
    card_ids = [str(slot["card"]["id"]) for slot in deck]

    deck_string = ";".join(card_ids)

    return f"https://link.clashroyale.com/en/?clashroyale://copyDeck?deck={deck_string}&l=Royals&tt=159000000"

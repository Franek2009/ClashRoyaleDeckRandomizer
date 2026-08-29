from deck_link import generate_deck_link


def test_generate_deck_link_preserves_slot_order_and_all_card_ids():
    card_ids = [26000000 + index for index in range(8)]
    deck = [
        {"card": {"id": card_id}, "is_evolution": False}
        for card_id in card_ids
    ]

    link = generate_deck_link(deck)

    expected_ids = ";".join(str(card_id) for card_id in card_ids)
    expected_prefix = (
        "https://link.clashroyale.com/en/"
        "?clashroyale://copyDeck?deck="
    )

    assert link.startswith(expected_prefix)
    assert f"deck={expected_ids}&" in link
    assert link.count(";") == 7
    assert link == f"{expected_prefix}{expected_ids}&l=Royals&tt=159000000"

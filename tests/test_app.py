import re

import app as app_module
from app import app


def post(client, **overrides):
    data = {
        "evolution_slot_enabled": "on",
        "hero_slot_enabled": "on",
        "wild_slot_mode": "evolution",
        "spell_count": "any",
        "building_count": "any",
        "min_average_elixir": "",
        "max_average_elixir": "",
    }
    data.update(overrides)
    return client.post("/generate", data=data)


def test_home_returns_new_slot_form():
    response = app.test_client().get("/")

    assert response.status_code == 200
    for field in (
        b"evolution_slot_enabled",
        b"hero_slot_enabled",
        b"wild_slot_mode",
        b"spell_count",
        b"building_count",
        b"min_average_elixir",
        b"max_average_elixir",
    ):
        assert b'name="' + field + b'"' in response.data
    assert b'id="special-slots-heading">Special Slots' in response.data
    assert b'id="deck-composition-heading">Deck Composition' in response.data
    assert b'id="average-elixir-heading">Average Elixir' in response.data
    assert b"Choose what each special deck slot should activate" in response.data
    assert b"Exact number in the 8-card deck" in response.data
    assert b"Limits the average cost of the entire 8-card deck" in response.data


def test_default_slot_values_are_selected():
    response = app.test_client().get("/")

    assert re.search(
        rb'name="evolution_slot_enabled"\s+value="on"\s+checked',
        response.data,
    )
    assert re.search(
        rb'name="hero_slot_enabled"\s+value="on"\s+checked', response.data
    )
    assert re.search(
        rb'name="wild_slot_mode"\s+value="evolution"\s+checked',
        response.data,
    )


def test_generate_default_renders_eight_cards_and_derived_counts():
    response = post(app.test_client())

    assert response.status_code == 200
    assert response.data.count(b'class="card"') == 8
    assert b'id="summary-evolutions">2</dd>' in response.data
    assert b'id="summary-heroes">1</dd>' in response.data


def test_wild_hero_champion_mode_derives_one_evo_two_heroes():
    response = post(app.test_client(), wild_slot_mode="hero_champion")

    assert response.status_code == 200
    assert b'id="summary-evolutions">1</dd>' in response.data
    assert b'id="summary-heroes">2</dd>' in response.data


def test_all_special_slots_off_have_no_active_forms():
    response = post(
        app.test_client(),
        evolution_slot_enabled="off",
        hero_slot_enabled="off",
        wild_slot_mode="off",
    )

    assert response.status_code == 200
    assert b'id="summary-evolutions">0</dd>' in response.data
    assert b'id="summary-heroes">0</dd>' in response.data
    assert b'data-active-form="evolution"' not in response.data
    assert b'data-active-form="hero"' not in response.data
    assert b'data-active-form="champion"' not in response.data


def test_spell_and_building_counts_are_rendered_from_deck():
    response = post(app.test_client(), spell_count="2", building_count="1")

    assert response.status_code == 200
    assert b'id="summary-spells">2</dd>' in response.data
    assert b'id="summary-buildings">1</dd>' in response.data


def test_average_range_is_respected():
    response = post(
        app.test_client(),
        min_average_elixir="3.0",
        max_average_elixir="3.5",
    )
    match = re.search(
        rb'id="summary-average-elixir">([^<]+)</dd>', response.data
    )

    assert response.status_code == 200
    assert match is not None
    assert 3.0 <= float(match.group(1)) <= 3.5


def test_excess_type_counts_show_friendly_error_only():
    response = post(app.test_client(), spell_count="8", building_count="8")

    assert response.status_code == 200
    assert b'role="alert"' in response.data
    assert b"more card types than can fit" in response.data
    assert b"spell_count=8" not in response.data


def test_inverted_average_range_shows_friendly_error_only():
    response = post(
        app.test_client(),
        min_average_elixir="4.0",
        max_average_elixir="3.0",
    )

    assert response.status_code == 200
    assert b"Minimum deck average cannot be greater" in response.data
    assert b"min_average_elixir cannot" not in response.data


def test_invalid_number_is_a_readable_error():
    response = post(app.test_client(), spell_count="not-a-number")

    assert response.status_code == 200
    assert b'role="alert"' in response.data
    assert b"Choose Any or a whole number from the list" in response.data
    assert b"spell_count must" not in response.data


def test_unknown_constraint_error_uses_safe_fallback(monkeypatch):
    def fail(cards, constraints):
        raise app_module.ConstraintError(
            "internal_field=bad", code="unexpected_backend_code"
        )

    monkeypatch.setattr(app_module, "get_random_deck", fail)

    response = post(app.test_client())

    assert response.status_code == 200
    assert b'role="alert"' in response.data
    assert b"These settings cannot produce a valid deck" in response.data
    assert b"internal_field" not in response.data


def test_form_values_are_preserved_after_error():
    response = post(
        app.test_client(),
        evolution_slot_enabled="off",
        hero_slot_enabled="off",
        wild_slot_mode="hero_champion",
        spell_count="7",
        building_count="2",
        min_average_elixir="3.2",
        max_average_elixir="3.8",
    )

    assert re.search(
        rb'name="evolution_slot_enabled"\s+value="off"\s+checked',
        response.data,
    )
    assert re.search(
        rb'name="hero_slot_enabled"\s+value="off"\s+checked', response.data
    )
    assert re.search(
        rb'name="wild_slot_mode"\s+value="hero_champion"\s+checked',
        response.data,
    )
    assert b'<option value="7" selected>7</option>' in response.data
    assert b'<option value="2" selected>2</option>' in response.data
    assert b'value="3.2"' in response.data
    assert b'value="3.8"' in response.data


def test_normal_active_form_is_not_rendered_as_visible_badge():
    response = post(
        app.test_client(),
        evolution_slot_enabled="off",
        hero_slot_enabled="off",
        wild_slot_mode="off",
    )

    assert b"Normal</span>" not in response.data
    assert b"Off" in response.data


def test_dual_form_in_wild_slot_renders_manual_selection_notice(monkeypatch):
    def card(card_id, *, evo=False, hero=False):
        icons = {"medium": f"https://example.com/{card_id}.png"}
        capability = int(evo) + 2 * int(hero)
        if evo:
            icons["evolutionMedium"] = "https://example.com/evo.png"
        if hero:
            icons["heroMedium"] = "https://example.com/hero.png"
        return {
            "id": card_id,
            "name": f"Card {card_id}",
            "rarity": "common",
            "elixirCost": 3,
            "iconUrls": icons,
            "maxEvolutionLevel": capability,
        }

    deck = [
        card(26000001, evo=True),
        card(26000002, hero=True),
        card(26000003, evo=True, hero=True),
        *[card(card_id) for card_id in range(26000004, 26000009)],
    ]
    monkeypatch.setattr(app_module, "get_random_deck", lambda cards, constraints: deck)

    response = post(app.test_client(), wild_slot_mode="hero_champion")

    assert b"set the Wild Slot to Hero" in response.data


def test_regular_wild_card_does_not_render_manual_selection_notice():
    response = post(
        app.test_client(),
        evolution_slot_enabled="off",
        hero_slot_enabled="off",
        wild_slot_mode="off",
    )

    assert b"After importing the deck, set the Wild Slot" not in response.data


def test_result_summary_has_user_facing_groups_and_slot_values():
    response = post(app.test_client(), wild_slot_mode="hero_champion")

    assert b'id="slot-summary-heading">Special Slots' in response.data
    assert b'id="deck-summary-heading">Deck' in response.data
    assert re.search(rb'id="summary-slot-evolution">\s*Evolution', response.data)
    assert re.search(
        rb'id="summary-slot-hero">\s*(Hero|Champion)', response.data
    )
    assert re.search(
        rb'id="summary-slot-wild">\s*(Hero|Champion)', response.data
    )
    assert b"Heroes / Champions" in response.data
    assert b"ActiveForm" not in response.data


def test_health_returns_ok():
    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

import re

from app import app


def test_home_returns_application_page():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"<title>Clash Royale Deck Randomizer</title>" in response.data
    for field in (
        b'evolution_count',
        b'hero_champion_count',
        b'spell_count',
        b'building_count',
        b'min_average_elixir',
        b'max_average_elixir',
    ):
        assert b'name="' + field + b'"' in response.data


def test_generate_renders_eight_card_deck_and_game_link():
    client = app.test_client()

    response = client.post("/generate")

    assert response.status_code == 200
    assert b"<h2>Your Deck</h2>" in response.data
    assert response.data.count(b'class="card"') == 8
    assert response.data.count(b'data-active-form=') == 8
    assert b"https://link.clashroyale.com/en/?clashroyale://copyDeck?deck=" in response.data
    assert b"Open in Clash Royale" in response.data


def test_generate_with_default_form_uses_unrestricted_constraints():
    client = app.test_client()

    response = client.post(
        "/generate",
        data={
            "evolution_count": "any",
            "hero_champion_count": "any",
            "spell_count": "any",
            "building_count": "any",
            "min_average_elixir": "",
            "max_average_elixir": "",
        },
    )

    assert response.status_code == 200
    assert response.data.count(b'class="card"') == 8
    assert b'id="summary-evolutions"' in response.data
    assert b'id="summary-average-elixir"' in response.data


def test_generate_respects_special_form_counts():
    client = app.test_client()

    response = client.post(
        "/generate",
        data={
            "evolution_count": "2",
            "hero_champion_count": "1",
        },
    )

    assert response.status_code == 200
    assert b'id="summary-evolutions">2</dd>' in response.data
    assert b'id="summary-heroes">1</dd>' in response.data


def test_generate_respects_spell_and_building_counts():
    client = app.test_client()

    response = client.post(
        "/generate",
        data={"spell_count": "2", "building_count": "1"},
    )

    assert response.status_code == 200
    assert b'id="summary-spells">2</dd>' in response.data
    assert b'id="summary-buildings">1</dd>' in response.data


def test_generate_respects_average_elixir_range():
    client = app.test_client()

    response = client.post(
        "/generate",
        data={
            "min_average_elixir": "3.0",
            "max_average_elixir": "3.5",
        },
    )

    assert response.status_code == 200
    match = re.search(
        rb'id="summary-average-elixir">([^<]+)</dd>', response.data
    )
    assert match is not None
    assert 3.0 <= float(match.group(1)) <= 3.5


def test_impossible_special_form_counts_render_error_instead_of_500():
    client = app.test_client()

    response = client.post(
        "/generate",
        data={"evolution_count": "2", "hero_champion_count": "2"},
    )

    assert response.status_code == 200
    assert b'role="alert"' in response.data
    assert b"only 3 slots are available" in response.data
    assert b'class="card"' not in response.data


def test_inverted_average_range_renders_error():
    client = app.test_client()

    response = client.post(
        "/generate",
        data={
            "min_average_elixir": "4.0",
            "max_average_elixir": "3.0",
        },
    )

    assert response.status_code == 200
    assert b'role="alert"' in response.data
    assert b"cannot be greater than" in response.data


def test_invalid_numeric_string_renders_readable_error():
    client = app.test_client()

    response = client.post(
        "/generate", data={"spell_count": "not-a-number"}
    )

    assert response.status_code == 200
    assert b'role="alert"' in response.data
    assert b"spell_count must be an integer or Any" in response.data


def test_form_values_are_preserved_after_validation_error():
    client = app.test_client()

    response = client.post(
        "/generate",
        data={
            "evolution_count": "2",
            "hero_champion_count": "2",
            "spell_count": "3",
            "min_average_elixir": "3.2",
        },
    )

    assert response.status_code == 200
    assert b'<option value="2" selected>2</option>' in response.data
    assert b'<option value="3" selected>3</option>' in response.data
    assert b'value="3.2"' in response.data


def test_health_returns_ok():
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

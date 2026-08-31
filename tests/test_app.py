from app import app


def test_home_returns_application_page():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"<title>Clash Royale Deck Randomizer</title>" in response.data


def test_generate_renders_eight_card_deck_and_game_link():
    client = app.test_client()

    response = client.post("/generate")

    assert response.status_code == 200
    assert b"<h2>Your Deck</h2>" in response.data
    assert response.data.count(b'<article class="card">') == 8
    assert b"https://link.clashroyale.com/en/?clashroyale://copyDeck?deck=" in response.data
    assert b"Open in Clash Royale" in response.data


def test_health_returns_ok():
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

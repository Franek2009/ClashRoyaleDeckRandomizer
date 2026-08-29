# Clash Royale Deck Randomizer

A Python-based Clash Royale deck randomizer with a Flask web interface.

The application generates random 8-card Clash Royale decks, applies custom deck-slot rules for Champions and Evolutions, displays the generated deck in a web interface, and creates a link that can be used to open the deck directly in Clash Royale.

## Features

- Generates random 8-card decks.
- Prevents duplicate cards.
- Supports Champions.
- Supports Evolution-capable cards.
- Applies custom deck-slot rules.
- Gives Champions priority over Evolutions when assigning slot 3.
- Displays Evolution artwork only when a card occupies an Evolution slot.
- Displays card names, rarities and Elixir costs.
- Generates Clash Royale deck links.
- Includes automated tests for deck generation and deck arrangement.
- Uses card data stored locally in `cards.json`.

## Deck Rules

The randomizer generates a deck containing exactly 8 unique cards.

### Evolution Rules

Evolution-capable cards can use the following slots:

- Slot 1
- Slot 3

Slot 2 can never contain an Evolution.

A card having an available Evolution does not automatically mean that its Evolution is active. The Evolution is active only when the card is assigned to an Evolution slot.

### Champion Rules

Champions can occupy:

- Slot 2
- Slot 3

A deck can contain a maximum of 2 Champions.

### Slot Priority

Champions have priority over Evolutions when assigning slot 3.

The intended slot order is:

| Slot | Priority |
|------|----------|
| 1 | Evolution |
| 2 | Champion |
| 3 | Champion → Evolution |
| 4–8 | Remaining cards |

For example, a deck containing two Champions and two Evolution-capable cards can be arranged as:

```text
Slot 1 → Evolution
Slot 2 → Champion
Slot 3 → Champion
Slot 4 → Normal card
Slot 5 → Normal card
Slot 6 → Normal card
Slot 7 → Normal card
Slot 8 → Normal card
````

In this case, only one Evolution is active.

With one Champion and two Evolution-capable cards:

```text
Slot 1 → Evolution
Slot 2 → Champion
Slot 3 → Evolution
Slot 4 → Normal card
Slot 5 → Normal card
Slot 6 → Normal card
Slot 7 → Normal card
Slot 8 → Normal card
```

Both Evolutions are active.

## Web Interface

The application provides a simple Flask web interface.

The user can:

1. Open the application.
2. Click **Generate Deck**.
3. View the generated deck.
4. See the correct artwork for each card.
5. See card rarity and Elixir cost.
6. Open the generated deck directly in Clash Royale.

## Clash Royale Deck Links

After generating and arranging a deck, the application creates a Clash Royale deck link using the IDs of the cards in their final slot order.

The generated link can be opened using the **Open in Clash Royale** button.

## Card Data

Card information is stored in:

```text
cards.json
```

The database contains information such as:

* card name,
* card ID,
* rarity,
* Elixir cost,
* regular card artwork,
* Evolution artwork.

Evolution availability is detected by checking for the `evolutionMedium` entry in the card's `iconUrls` data.

For example:

```json
{
    "iconUrls": {
        "medium": "...",
        "evolutionMedium": "..."
    }
}
```

## Project Structure

```text
ClashRoyaleDeckRandomizer/
├── app.py
├── main.py
├── randomizer.py
├── deck_link.py
├── cards.json
├── test_randomizer.py
├── templates/
│   └── index.html
├── static/
│   └── style.css
├── .gitignore
└── README.md
```

### `app.py`

The Flask web application.

Responsible for:

* starting the web server,
* loading the card database,
* generating decks,
* arranging decks,
* generating Clash Royale links,
* rendering the web interface.

### `randomizer.py`

Contains the main deck-generation and deck-arrangement logic.

Important functions:

* `has_evolution(card)` — checks whether a card has an Evolution available.
* `is_champion(card)` — checks whether a card is a Champion.
* `get_random_deck(loadCards)` — generates a random 8-card deck.
* `arrange_deck(deck)` — assigns cards to their appropriate deck slots and marks active Evolutions.

### `deck_link.py`

Generates a Clash Royale deck link from the final arranged deck.

### `cards.json`

Local card database used by the application.

### `main.py`

Command-line entry point for working with the project outside the Flask web interface.

### `test_randomizer.py`

Automated tests for the deck generator and deck arrangement logic.

### `templates/index.html`

HTML template used by Flask for the web interface.

### `static/style.css`

Stylesheet used by the web interface.

## Requirements

* Python 3
* pip

## Installation

Clone the repository:

```bash
git clone https://github.com/Franek2009/ClashRoyaleDeckRandomizer.git
```

Enter the project directory:

```bash
cd ClashRoyaleDeckRandomizer
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install the production and development dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running the Application

Start the Flask development server:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

Click **Generate Deck** to generate a new deck.

## Testing

The project includes automated tests for the randomizer and deck arrangement.

Run:

```bash
python test_randomizer.py
```

The test suite generates 1000 random decks and checks that the implemented rules are respected.

The tests verify:

* the deck contains exactly 8 cards,
* there are no duplicate cards,
* there are no more than 2 Champions,
* the deck can be successfully arranged,
* the arranged deck contains exactly 8 cards,
* Evolutions only occupy slots 1 or 3,
* slot 2 never contains an Evolution,
* Champions only occupy slots 2 or 3,
* cards marked as Evolutions actually have an Evolution available.

A successful run ends with:

```text
1000 testów zakończonych pomyślnie!
```

Because the deck generator is random, running the test suite multiple times can produce different decks while still validating the same rules.

## Development

The project separates deck generation from the web interface.

The general flow is:

```text
cards.json
    ↓
randomizer.py
    ↓
Random 8-card deck
    ↓
Deck slot arrangement
    ↓
deck_link.py
    ↓
Flask application
    ↓
Web interface
```

This makes the randomizer logic possible to test independently from the Flask application.

## Current Status

The core functionality is implemented and working:

* random deck generation,
* unique-card selection,
* Champion handling,
* Evolution handling,
* deck-slot arrangement,
* correct Evolution artwork,
* Clash Royale deck links,
* Flask web interface,
* automated validation tests.

The project is still under development. Future changes may include additional deck-generation rules, improvements to the user interface, and further testing.

## Disclaimer

This material is unofficial and is not endorsed by Supercell.

This project is an independent fan-made project and is not affiliated with,
sponsored by, or endorsed by Supercell.

For more information, see Supercell's Fan Content Policy:
https://supercell.com/en/fan-content-policy/

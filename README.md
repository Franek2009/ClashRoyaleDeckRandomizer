# Clash Royale Deck Randomizer

A Python-based Clash Royale deck randomizer with a simple web interface built with Flask.

The application generates an 8-card deck using the card data stored in `cards.json`.

## Features

* Generates a random deck of 8 unique cards.
* Always includes at least 2 cards with evolutions.
* Allows up to 2 champions in a deck.
* Uses card data from `cards.json`.
* Displays the generated deck through a Flask web interface.
* Displays card names and images from the card data.

## Requirements

* Python 3
* Flask

## Running the application

Clone the repository and enter the project directory.

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install Flask:

```bash
pip install flask
```

Start the web application:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Project structure

```text
ClashRoyaleDeckRandomizer/
├── app.py
├── main.py
├── randomizer.py
├── cards.json
├── test_randomizer.py
├── templates/
│   └── index.html
├── .gitignore
└── README.md
```

### Files

* `app.py` — Flask web application.
* `main.py` — command-line interface for generating decks.
* `randomizer.py` — deck generation logic.
* `cards.json` — card database.
* `test_randomizer.py` — automated tests for the randomizer.
* `templates/index.html` — web interface.

## Testing

The randomizer includes automated validation tests.

Run them with:

```bash
python test_randomizer.py
```

The current test suite generates 1000 decks and checks that the randomizer follows the implemented deck rules.

## Status

The project is currently in development.

The core deck randomizer is working and the Flask web interface is being developed.

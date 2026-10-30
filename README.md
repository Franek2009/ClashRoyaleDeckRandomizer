# Clash Royale Deck Randomizer

A static browser application that generates random eight-card Clash Royale
decks, applies configurable Evolution, Hero, and Wild Slot rules, and creates a
link for opening the result in Clash Royale.

## Live demo

The site is deployed automatically from `main` to:
<https://franek2009.github.io/ClashRoyaleDeckRandomizer/>

## Features

- Generates exactly eight unique cards.
- Configures Evolution, Hero / Champion, and Wild Slots.
- Supports custom available, banned, and required card pools.
- Filters by exact Spell and Building counts.
- Filters by minimum and maximum average Elixir.
- Uses the local `cards.json` snapshot; deck generation calls no API.
- Builds a Clash Royale deck link in the displayed slot order.
- Locks individual slots while regenerating the rest of a deck.
- Keeps recent and favorite decks in browser-local storage.
- Runs entirely in the browser without a backend or build step.

## Running locally

Serve the repository with any static HTTP server, for example:

```bash
python -m http.server 8000
```

Open <http://127.0.0.1:8000>. Opening `index.html` as a `file://` URL is not
supported because browsers restrict loading `cards.json` from local files.

## Testing

The deployed JavaScript implementation requires Node.js 22 or newer for tests:

```bash
npm test
```

The retained Flask implementation has its original Python test suite:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions runs both suites. JavaScript tests cover catalog classification,
special-slot safety, uniqueness, card pools, type and Elixir constraints, and
deck-link construction, including repeated randomized generation.

## Project structure

```text
ClashRoyaleDeckRandomizer/
├── .github/workflows/
│   ├── ci.yml
│   ├── pages.yml
│   └── release.yml
├── static/
│   ├── app.js
│   ├── deck-store.js
│   ├── randomizer.js
│   └── style.css
├── tests-js/
│   └── randomizer.test.js
├── tests/                  # retained Flask tests
├── cards.json
├── index.html
├── package.json
├── app.py                  # retained during migration
├── randomizer.py           # retained during migration
└── render.yaml             # retained during migration
```

## Architecture

```text
cards.json
    -> static/app.js loads card data and manages the interface
    -> static/deck-store.js keeps history and favorites in localStorage
    -> static/randomizer.js validates, selects, and arranges the deck
    -> index.html displays the result and Clash Royale link
```

All asset paths are relative, so the application works below the
`/ClashRoyaleDeckRandomizer/` GitHub Pages project path.

## GitHub Pages deployment

The `pages.yml` workflow tests the JavaScript application, packages only
`index.html`, `cards.json`, and `static/`, and deploys that artifact after every
push to `main`.

In the repository settings, set **Pages → Build and deployment → Source** to
**GitHub Actions** once. The Flask and Render files remain temporarily so the
old implementation can be compared with the new site. They can be removed
after the Pages deployment is verified.

## Card data and fan content

`cards.json` is a local snapshot shaped like the official Clash Royale
Developer API `/v1/cards` response. Artwork fields point to Supercell-hosted
`api-assets.clashroyale.com` URLs, so artwork still requires network access.

The MIT license applies only to original repository code. It does not cover
card data, names, artwork, trademarks, or other Supercell materials. This is an
unofficial fan-made project and is not affiliated with, sponsored by, or
endorsed by Supercell. Use of those materials remains subject to Supercell's
[Fan Content Policy](https://supercell.com/en/fan-content-policy/).

## Current limitations

- `cards.json` can become outdated as the game changes.
- There are no arena, card-level, or player-collection filters.
- History and favorites belong to one browser and are not synchronized between
  devices.
- Card artwork depends on external Supercell asset URLs.

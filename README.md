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
- Exports and imports local deck history as a validated JSON backup.
- Shows an Elixir distribution chart and objective deck insights.
- Filters the card pool by rarity, Elixir cost, Evolution, Hero, and Champion status.
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
npm ci
npm test
npx playwright install chromium --with-deps
npm run test:e2e
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
deck-link construction, including repeated randomized generation. Playwright
also exercises the complete interface in desktop Chromium and an emulated
Pixel viewport.

## Project structure

```text
ClashRoyaleDeckRandomizer/
├── .github/workflows/
│   ├── ci.yml
│   ├── pages.yml
│   └── release.yml
├── static/
│   ├── arena.css             # browser UI; style.css is retained for Flask
│   ├── assets/                # original generated arena and emblem
│   ├── fonts/                 # locally hosted Barlow fonts and OFL license
│   ├── app.js
│   ├── card-filter.js
│   ├── deck-analysis.js
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
    -> static/app.js loads card data and manages the interface and paginated picker
    -> static/deck-store.js keeps history and favorites in localStorage
    -> static/randomizer.js validates, selects, and arranges the deck
    -> index.html displays the result and Clash Royale link
```

All asset paths are relative, so the application works below the
`/ClashRoyaleDeckRandomizer/` GitHub Pages project path.

## Browser interface

UI copy is functional: keep the header to the app name and navigation. Do not
add slogans, hero descriptions, promotional claims, feature showcases, or
redundant helper text. Explain mechanics only when needed; preserve errors,
accessibility labels, and the fan-content notice.

The interface uses flat dark navy surfaces, thin borders, blue primary actions,
a small original emblem, locally hosted Barlow fonts, and CSS/SVG controls.
Decorative arena artwork remains in the repository but is not loaded by the UI.
The existing generator and local deck storage format are preserved. The retained Flask template continues to use `static/style.css`;
the static application uses `static/arena.css`, scoped to `.arena-app`.

- Desktop: a 380px rules column beside the larger card pool, with the deck below.
  Smaller screens stack the panels; at 390px the picker has three columns and
  the generated deck has four columns in two rows. Both navigation links remain
  available on mobile.
- The catalog shows 12 cards per page. Search covers the entire catalog and only
  changes the visible cards; advanced filters constrain deck generation.
- All is read-only. Available, Banned, and Required edit the corresponding pools;
  Available supports all cards or a custom selection. Selections survive paging.
- Analysis and history are collapsible. Eight empty slots are visible before the
  first generation as compact placeholders. Invalid configurations preserve the
  previous result. Locks sit below the card artwork with 44px touch targets.
- Pool selections use different symbols as well as borders: available ✓, banned
  ×, required !. Slot names and lock states remain explicitly labeled.

Screenshots at 1440px desktop and 390px mobile, captured with actual loaded
card artwork (the automated functional tests block external artwork):

| View | Before generation | Generated deck |
| --- | --- | --- |
| Desktop | [Empty](docs/ui/desktop-empty.png) | [Result](docs/ui/desktop.png) |
| Mobile | [Empty](docs/ui/mobile-empty.png) | [Result](docs/ui/mobile.png) |

Original artwork provenance is documented in
[asset provenance and generation prompts](static/assets/README.md).

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

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
│   ├── assets/                # UI artwork, paper texture, and provenance
│   ├── fonts/                 # retained inactive fonts and their licenses
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

The retro fan-site interface uses warm paper panels, blue section bars, and a
small original fortress illustration confined to the header. The page background
is solid navy. `static/arena.css` is scoped to `.arena-app`; the retained Flask
interface continues to use `static/style.css`.

Headings, navigation, and primary actions use **Trebuchet MS Bold**, with Verdana,
Arial, and sans-serif fallbacks. Body copy and card names retain regular-weight
system fonts. No webfont is loaded; earlier font files and their licenses remain
in the repository but are inactive. Appearance may vary slightly with locally
available system fonts.

The header uses the author's approved project logo at 48px on desktop and 32px
on mobile, preserving its proportions. It has an empty alt because the full app
name is alongside it. The exact PNG export also supplies the favicon. The source
SVG still depends on Lilita One, so PNG is used until the author approves an
outlined SVG. Crown-source attribution is not yet established; see the
[logo asset audit](static/assets/README.md#project-authors-approved-logo).
Generate Deck is a flat blue, text-only button with no dice icon.

Current logo previews: [desktop 1440px](docs/ui/logo-desktop.png) and
[mobile 390px](docs/ui/logo-mobile.png). The earlier generator screenshots below
precede logo integration.

- Desktop: rules occupy about 32% and the card pool 68%; the deck appears below.
- Below 1024px: a single column, rules initially collapsed and the pool expanded.
  Both panels can be toggled, while Generate Deck stays accessible. Closing a
  panel does not disable its fields or discard their values. Native validation
  reopens panels and filters when an invalid field needs focus. Desktop always
  shows both panels; returning to mobile restores that tab's expansion choices.
- The catalog has 12 cards per page, six columns on desktop and three on compact
  screens. Search covers the entire catalog; advanced filters constrain generation.
- All is read-only. Available, Banned, and Required edit their respective pools.
  Available supports all cards or a custom selection. Selection symbols remain
  distinct: available ✓, banned ×, required !.
- The result has eight cards on desktop and a 4×2 grid on compact screens, with
  explicit slot labels and 44px lock buttons. Analysis and history remain
  collapsible, and invalid configurations preserve the previous result.
- The generator, Mirror average policy, deck links, and local storage format are
  unchanged. There are no additional controls inferred from the visual mockups.

Screenshots captured with loaded card artwork (functional tests block external
artwork). The mobile previews use the initial collapsed-rules layout:

| View | Before generation | Generated deck |
| --- | --- | --- |
| Desktop 1440px | [Empty](docs/ui/desktop-empty.png) | [Result](docs/ui/desktop.png) |
| Mobile 390px | [Empty](docs/ui/mobile-empty.png) | [Result](docs/ui/mobile.png) |

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

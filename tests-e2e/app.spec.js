import {expect, test} from "@playwright/test";

const browserErrors = new WeakMap();

test.beforeEach(async ({page}) => {
    browserErrors.set(page, []);
    page.on("pageerror", error => browserErrors.get(page).push(error.message));
    await page.route("https://api-assets.clashroyale.com/**", route => route.abort());
    await page.goto("/");
});

test.afterEach(async ({page}) => {
    expect(browserErrors.get(page)).toEqual([]);
});

async function generateDeck(page) {
    await page.getByRole("button", {name: "Generate Deck"}).click();
    await expect(page.locator("[data-deck] .card")).toHaveCount(8);
}

test("generates a deck and preserves the official game-link format", async ({page}) => {
    await generateDeck(page);
    const ids = await page.locator("[data-deck] .card").evaluateAll(items => items.map(item => item.dataset.cardId));
    await expect(page.locator("[data-deck-link]")).toHaveAttribute("href", `https://link.clashroyale.com/en/?clashroyale://copyDeck?deck=${ids.join(";")}&l=Royals&tt=159000000`);
});

test("filters can be cleared and all settings reset", async ({page}) => {
    await page.getByRole("button", {name: "Filters", exact: true}).click();
    await page.getByLabel("Exclude Champions").check();
    await expect(page.locator("[data-filter-count]")).not.toHaveText("All");
    await page.getByRole("button", {name: "Clear filters"}).click();
    await expect(page.locator("[data-filter-count]")).toHaveText("All");
    await page.getByLabel("Rare", {exact: true}).check();
    await page.getByRole("button", {name: "Reset all settings"}).click();
    await expect(page.getByLabel("Rare", {exact: true})).not.toBeChecked();
    await expect(page.getByLabel("All cards")).toBeChecked();
});

test("explains when filters leave too few cards", async ({page}) => {
    await page.getByRole("button", {name: "Filters", exact: true}).click();
    await page.getByLabel("Minimum Elixir").fill("10");
    await page.getByRole("button", {name: "Generate Deck"}).click();
    await expect(page.locator("[data-error]")).toContainText("fewer than 8 cards");
});

test("locked cards remain in the same slot after regeneration", async ({page}) => {
    await generateDeck(page);
    const card = page.locator("[data-deck] .card").nth(4), id = await card.getAttribute("data-card-id");
    await card.locator("[data-lock-slot]").click();
    await page.getByRole("button", {name: "Generate again"}).click();
    await expect(page.locator("[data-deck] .card").nth(4)).toHaveAttribute("data-card-id", id);
});

test("favorites persist across a page reload", async ({page}) => {
    await generateDeck(page);
    await page.getByRole("button", {name: "Add to favorites"}).click();
    await page.reload();
    await page.getByRole("link", {name: "Saved decks"}).click();
    await page.getByRole("button", {name: "Favorites", exact: true}).click();
    await expect(page.locator("[data-saved-decks] .saved-deck")).toHaveCount(1);
});

test("exported data can be deleted and imported again", async ({page}) => {
    await generateDeck(page);
    await page.getByRole("link", {name: "Saved decks"}).click();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", {name: "Export data"}).click();
    const download = await downloadPromise, path = await download.path();
    expect(path).toBeTruthy();
    page.on("dialog", dialog => dialog.accept());
    await page.getByRole("button", {name: "Delete all data"}).click();
    await expect(page.locator("[data-saved-decks] .saved-deck")).toHaveCount(0);
    await page.locator("[data-import-file]").setInputFiles(path);
    await expect(page.locator("[data-data-status]")).toContainText("1 added");
    await expect(page.locator("[data-saved-decks] .saved-deck")).toHaveCount(1);
});

test("deck grid adapts to desktop and mobile viewports", async ({page}, testInfo) => {
    await generateDeck(page);
    const columns = await page.locator("[data-deck]").evaluate(element => getComputedStyle(element).gridTemplateColumns.split(" ").length);
    expect(columns).toBe(testInfo.project.name === "mobile-chromium" ? 4 : 8);
});


test("starts with eight empty slots and a browsable catalog", async ({page}) => {
    await expect(page.locator(".empty-card")).toHaveCount(8);
    await expect(page.locator("[data-picker-card]:visible")).toHaveCount(12);
    await expect(page.locator("[data-pool-status]")).toContainText("of 122 cards");
    await expect(page.locator("[data-saved-section]")).not.toHaveAttribute("open");
    await expect(page.locator("#card-filters")).toBeHidden();
});

test("searches the entire catalog and resets pagination", async ({page}) => {
    await page.getByRole("button", {name: "Next page", exact: true}).click();
    await expect(page.getByRole("button", {name: "Page 2", exact: true})).toHaveAttribute("aria-current", "page");
    await page.getByRole("searchbox", {name: "Search cards"}).fill("Skeletons");
    await expect(page.locator("[data-picker-card]:visible")).toHaveCount(1);
    await expect(page.getByRole("button", {name: "Page 1", exact: true})).toHaveAttribute("aria-current", "page");
    await page.getByRole("searchbox", {name: "Search cards"}).fill("no-such-card");
    await expect(page.locator("[data-pool-empty]")).toBeVisible();
    await expect(page.getByRole("button", {name: "Next page", exact: true})).toBeDisabled();
});

test("keeps selected cards across pages and editing contexts", async ({page}) => {
    await page.locator('[data-picker-context="required"]').click();
    const first = page.locator('[data-picker-card]:visible').first();
    const id = await first.getAttribute("data-card-id");
    await first.getByRole('checkbox').check();
    await page.getByRole("button", {name: "Next page", exact: true}).click();
    await page.locator('[data-picker-context="banned"]').click();
    await page.locator('[data-picker-context="required"]').click();
    await expect(page.locator(`[data-picker-card][data-card-id="${id}"]`).getByRole('checkbox')).toBeChecked();
    await generateDeck(page);
    await expect(page.locator(`[data-deck] [data-card-id="${id}"]`)).toHaveCount(1);
});

test("all-available mode prevents editing until custom mode is chosen", async ({page}) => {
    await page.locator('[data-picker-context="available"]').click();
    await expect(page.locator('[data-picker-card]:visible').first().getByRole('checkbox')).toBeDisabled();
    await page.getByLabel('Custom selection', {exact:true}).check();
    await expect(page.locator('[data-picker-card]:visible').first().getByRole('checkbox')).toBeEnabled();
    await page.getByRole('button', {name:'Select all',exact:true}).click();
    await expect(page.locator('[data-available-label]')).toHaveText('122');
    await generateDeck(page);
});

test("a failed generation preserves the current deck", async ({page}) => {
    await generateDeck(page);
    const ids = await page.locator('[data-deck] .card').evaluateAll(cards => cards.map(card => card.dataset.cardId));
    await page.getByRole('button', {name:'Filters',exact:true}).click();
    await page.getByLabel('Minimum Elixir', {exact:true}).fill('10');
    await page.getByRole('button', {name:'Generate Deck',exact:true}).click();
    await expect(page.locator('[data-error]')).toBeVisible();
    expect(await page.locator('[data-deck] .card').evaluateAll(cards => cards.map(card => card.dataset.cardId))).toEqual(ids);
});

test("reports catalog loading errors and disables generation", async ({page}) => {
    await page.route('**/cards.json', route => route.abort());
    await page.reload();
    await expect(page.locator('[data-error]')).toContainText('Card data could not be loaded');
    await expect(page.getByRole('button', {name:'Generate Deck',exact:true})).toBeDisabled();
});

test("layout fits supported viewport widths", async ({page}) => {
    await generateDeck(page);
    for (const width of [360,390,768,1024,1440]) {
        await page.setViewportSize({width,height:900});
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
});


test("keyboard users can select cards and expand analysis", async ({page}) => {
    const context = page.locator('[data-picker-context="required"]');
    await context.focus();
    await page.keyboard.press('Enter');
    const checkbox = page.locator('[data-picker-card]:visible').first().getByRole('checkbox');
    await checkbox.focus();
    await page.keyboard.press('Space');
    await expect(checkbox).toBeChecked();
    await generateDeck(page);
    await page.locator('[data-analysis] summary').focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-analysis]')).toHaveAttribute('open', '');
    await expect(page.locator('[data-elixir-chart]')).toBeVisible();
});

test("elixir steppers preserve decimal increments and reset to optional", async ({page}) => {
    const input = page.getByRole('spinbutton', {name:'Deck average elixir — minimum',exact:true});
    await input.fill('2');
    await page.getByRole('button', {name:'Increase minimum average Elixir',exact:true}).click();
    await expect(input).toHaveValue('2.1');
    await page.getByRole('button', {name:'Decrease minimum average Elixir',exact:true}).click();
    await expect(input).toHaveValue('2');
    await page.getByRole('button', {name:'Reset all settings',exact:true}).click();
    await expect(input).toHaveValue('');
});

test("relative assets work under the GitHub Pages project path", async ({page}) => {
    const prefix = '/ClashRoyaleDeckRandomizer/';
    await page.route(`**${prefix}**`, async route => {
        const url = new URL(route.request().url());
        url.pathname = url.pathname.replace(prefix, '/');
        const response = await route.fetch({url:url.toString()});
        await route.fulfill({response});
    });
    await page.goto(prefix);
    await generateDeck(page);
    await expect(page.locator('[data-picker-card]:visible')).toHaveCount(12);
    expect(await page.locator('.deck').evaluate(node => getComputedStyle(node).display)).toBe('grid');
});

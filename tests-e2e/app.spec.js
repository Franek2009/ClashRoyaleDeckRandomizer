import {expect, test} from "@playwright/test";

test.beforeEach(async ({page}) => {
    await page.route("https://api-assets.clashroyale.com/**", route => route.abort());
    await page.goto("/");
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
    await page.getByRole("button", {name: "Favorites", exact: true}).click();
    await expect(page.locator("[data-saved-decks] .saved-deck")).toHaveCount(1);
});

test("exported data can be deleted and imported again", async ({page}) => {
    await generateDeck(page);
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
    expect(columns).toBe(testInfo.project.name === "mobile-chromium" ? 2 : 4);
});

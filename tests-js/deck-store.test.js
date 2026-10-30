import assert from "node:assert/strict";
import test from "node:test";

import {clearAllDecks, clearHistory, exportDeckData, importDeckData, readDecks, removeDeck, restoreSlots, saveDeck, toggleFavorite} from "../static/deck-store.js";

function memoryStorage() {
    const values = new Map();
    return {getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value)};
}

const cards = Array.from({length: 10}, (_, index) => ({id: index + 1, name: `Card ${index + 1}`}));
const slots = cards.slice(0, 8).map((card, index) => ({card, role: index < 3 ? ["evolution", "hero", "wild"][index] : "normal", activeForm: "normal"}));

test("decks can be saved and restored without changing slot metadata", () => {
    const storage = memoryStorage();
    const entry = saveDeck(slots, storage, 1000);
    assert.deepEqual(restoreSlots(entry, cards), slots);
    assert.equal(readDecks(storage).length, 1);
});

test("saving the same deck updates it instead of duplicating it", () => {
    const storage = memoryStorage();
    saveDeck(slots, storage, 1000);
    saveDeck(slots, storage, 2000);
    assert.equal(readDecks(storage).length, 1);
    assert.equal(readDecks(storage)[0].createdAt, 2000);
});

test("favorites survive clearing history and can be removed", () => {
    const storage = memoryStorage();
    const favorite = saveDeck(slots, storage, 1000);
    toggleFavorite(favorite.id, storage);
    saveDeck(slots.map((slot, index) => ({...slot, card: cards[index + 1]})), storage, 2000);
    clearHistory(storage);
    assert.deepEqual(readDecks(storage).map(deck => deck.id), [favorite.id]);
    removeDeck(favorite.id, storage);
    assert.deepEqual(readDecks(storage), []);
});

test("corrupt local data is ignored", () => {
    const storage = memoryStorage();
    storage.setItem("clash-royale-randomizer.decks.v1", "not json");
    assert.deepEqual(readDecks(storage), []);
});

test("exported decks can be imported into another browser", () => {
    const source = memoryStorage(), target = memoryStorage();
    const entry = saveDeck(slots, source, 1000);
    toggleFavorite(entry.id, source);
    const payload = JSON.stringify(exportDeckData(source, 2000));
    const result = importDeckData(payload, new Set(cards.map(card => card.id)), target);
    assert.deepEqual(result, {imported: 1, updated: 0, skipped: 0, error: null});
    assert.equal(readDecks(target)[0].favorite, true);
    assert.deepEqual(readDecks(target)[0].cardIds, slots.map(slot => slot.card.id));
});

test("import merges favorites and skips duplicate or unknown decks", () => {
    const source = memoryStorage(), target = memoryStorage();
    const sourceEntry = saveDeck(slots, source, 1000);
    toggleFavorite(sourceEntry.id, source);
    saveDeck(slots, target, 900);
    const exported = exportDeckData(source, 2000);
    exported.decks.push({...exported.decks[0], id: "unknown", cardIds: [999, 2, 3, 4, 5, 6, 7, 8]});
    const result = importDeckData(exported, new Set(cards.map(card => card.id)), target);
    assert.deepEqual(result, {imported: 0, updated: 1, skipped: 1, error: null});
    assert.equal(readDecks(target)[0].favorite, true);
});

test("invalid import files are rejected without changing storage", () => {
    const storage = memoryStorage();
    saveDeck(slots, storage, 1000);
    assert.equal(importDeckData("not json", new Set(), storage).error, "invalid_json");
    assert.equal(importDeckData({decks: []}, new Set(), storage).error, "invalid_format");
    assert.equal(readDecks(storage).length, 1);
});

test("all local deck data can be deleted", () => {
    const storage = memoryStorage();
    saveDeck(slots, storage, 1000);
    clearAllDecks(storage);
    assert.deepEqual(readDecks(storage), []);
});

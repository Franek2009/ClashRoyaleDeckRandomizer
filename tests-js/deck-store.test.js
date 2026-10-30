import assert from "node:assert/strict";
import test from "node:test";

import {clearHistory, readDecks, removeDeck, restoreSlots, saveDeck, toggleFavorite} from "../static/deck-store.js";

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

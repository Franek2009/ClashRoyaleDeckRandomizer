import assert from "node:assert/strict";
import test from "node:test";

import {DeckStorageError, STORAGE_KEY, clearAllDecks, clearHistory, exportDeckData, importDeckData, readDecks, removeDeck, restoreSlots, saveDeck, toggleFavorite, writeDecks} from "../static/deck-store.js";

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

test("corrupt storage containers cannot be overwritten by automatic saves", () => {
    for (const raw of ["not json", "null", '{}']) {
        const storage = memoryStorage();
        storage.setItem(STORAGE_KEY, raw);
        assert.throws(() => readDecks(storage), DeckStorageError);
        assert.throws(() => saveDeck(slots, storage), DeckStorageError);
        assert.equal(storage.getItem(STORAGE_KEY), raw);
    }
});

test("exported decks can be imported into another browser", () => {
    const source = memoryStorage(), target = memoryStorage();
    const entry = saveDeck(slots, source, 1000);
    toggleFavorite(entry.id, source);
    const payload = JSON.stringify(exportDeckData(source, 2000));
    const result = importDeckData(payload, cards, target);
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
    const result = importDeckData(exported, cards, target);
    assert.deepEqual(result, {imported: 0, updated: 1, skipped: 1, error: null});
    assert.equal(readDecks(target)[0].favorite, true);
});

test("invalid import files are rejected without changing storage", () => {
    const storage = memoryStorage();
    saveDeck(slots, storage, 1000);
    assert.equal(importDeckData("not json", cards, storage).error, "invalid_json");
    assert.equal(importDeckData({decks: []}, cards, storage).error, "invalid_format");
    assert.equal(readDecks(storage).length, 1);
});

test("all local deck data can be deleted", () => {
    const storage = memoryStorage();
    saveDeck(slots, storage, 1000);
    clearAllDecks(storage);
    assert.deepEqual(readDecks(storage), []);
});

const payloadFor = decks => ({format:"clash-royale-deck-randomizer", version:1, decks});
const record = overrides => ({...saveDeck(slots, memoryStorage(), 1000), ...overrides});

test("invalid imported dates are skipped without rewriting existing data", () => {
    for (const createdAt of [1e100, NaN, Infinity, -Infinity, null, "1000", -8640000000000001]) {
        const storage = memoryStorage();
        saveDeck(slots, storage, 1000);
        const before = storage.getItem(STORAGE_KEY);
        assert.deepEqual(importDeckData(payloadFor([record({createdAt})]), cards, storage),
            {imported:0, updated:0, skipped:1, error:null});
        assert.equal(storage.getItem(STORAGE_KEY), before);
    }
});

test("the complete JS Date range including negative timestamps is supported", () => {
    for (const createdAt of [-8640000000000000, -1, 0, Date.now(), 8640000000000000]) {
        const storage = memoryStorage(), entry = record({createdAt});
        assert.equal(importDeckData(payloadFor([entry]), cards, storage).imported, 1);
        assert.equal(readDecks(storage)[0].createdAt, createdAt);
        assert.doesNotThrow(() => new Intl.DateTimeFormat(undefined, {dateStyle:"medium", timeStyle:"short"}).format(createdAt));
        assert.doesNotThrow(() => new Date(createdAt).toISOString());
    }
});

test("reading persisted invalid dates preserves valid entries and never writes storage", () => {
    const storage = memoryStorage(), good = record({favorite:true});
    const raw = JSON.stringify([record({id:"bad", createdAt:1e100}), good, record({id:"null", createdAt:null})]);
    storage.setItem(STORAGE_KEY, raw);
    assert.deepEqual(readDecks(storage, cards), [good]);
    assert.deepEqual(readDecks(storage, cards), [good]);
    assert.equal(storage.getItem(STORAGE_KEY), raw);
    assert.equal(restoreSlots(record({createdAt:1e100}), cards), null);
});

const capableCards = [...cards,
    {id:11, name:"Evolution", maxEvolutionLevel:1},
    {id:12, name:"Hero", maxEvolutionLevel:2},
    {id:13, name:"Dual", maxEvolutionLevel:3},
    {id:14, name:"Champion", rarity:"champion"},
];
const inSlot = (index, id, form) => {
    const entry = record();
    entry.cardIds[index] = id; entry.activeForms[index] = form;
    return entry;
};

test("import and restoration reject impossible roles and active forms", () => {
    const wrongRole = record(); wrongRole.roles[0] = "normal";
    const swapped = record(); [swapped.roles[0], swapped.roles[1]] = [swapped.roles[1], swapped.roles[0]];
    const invalid = [
        wrongRole, swapped, record({roles:Array(8).fill("invalid")}),
        record({activeForms:Array(8).fill("champion")}),
        inSlot(0, 1, "evolution"), inSlot(1, 2, "hero"), inSlot(2, 3, "unknown"),
        inSlot(0, 12, "hero"), inSlot(1, 11, "evolution"),
        inSlot(3, 11, "evolution"), inSlot(3, 12, "hero"),
        inSlot(3, 14, "champion"), inSlot(0, 14, "champion"),
        inSlot(1, 14, "normal"), inSlot(1, 14, "hero"),
    ];
    for (const entry of invalid) {
        const storage = memoryStorage();
        assert.deepEqual(importDeckData(payloadFor([entry]), capableCards, storage),
            {imported:0, updated:0, skipped:1, error:null});
        assert.equal(restoreSlots(entry, capableCards), null);
        storage.setItem(STORAGE_KEY, JSON.stringify([entry, record()]));
        assert.deepEqual(readDecks(storage, capableCards), [record()]);
    }
});

test("valid Evolution, Hero, dual-form, Champion and inactive historical metadata survive", () => {
    const entries = [
        inSlot(0, 11, "evolution"), inSlot(1, 12, "hero"),
        inSlot(2, 13, "evolution"), inSlot(2, 13, "hero"),
        inSlot(1, 14, "champion"), inSlot(2, 14, "champion"),
        inSlot(3, 13, "normal"), inSlot(0, 11, "normal"),
        inSlot(1, 12, "normal"), inSlot(2, 13, "normal"),
    ];
    for (const entry of entries) {
        const storage = memoryStorage();
        assert.equal(importDeckData(payloadFor([entry]), capableCards, storage).imported, 1);
        const restored = restoreSlots(readDecks(storage, capableCards)[0], capableCards);
        assert.deepEqual(restored.map(slot => slot.activeForm), entry.activeForms);
        assert.deepEqual(restored.map(slot => slot.role), entry.roles);
    }
});

test("mixed imports preserve valid history and favorites while rejecting bad records", () => {
    const storage = memoryStorage(), favorite = saveDeck(slots, storage, 1000);
    toggleFavorite(favorite.id, storage);
    const next = record({cardIds:cards.slice(1,9).map(card => card.id), createdAt:2000});
    assert.deepEqual(importDeckData(payloadFor([record({createdAt:1e100}), next]), cards, storage),
        {imported:1, updated:0, skipped:1, error:null});
    assert.equal(readDecks(storage).length, 2);
    assert.equal(readDecks(storage).find(deck => deck.id === favorite.id).favorite, true);
});

test("all consumers contain a throwing localStorage getter inside DeckStorageError", t => {
    const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
    Object.defineProperty(globalThis, "localStorage", {configurable:true, get() {throw new DOMException("blocked", "SecurityError");}});
    t.after(() => {
        if (original) Object.defineProperty(globalThis, "localStorage", original);
        else delete globalThis.localStorage;
    });
    for (const operation of [
        () => readDecks(), () => writeDecks([]), () => saveDeck(slots),
        () => toggleFavorite("id"), () => removeDeck("id"), () => clearHistory(),
        () => clearAllDecks(), () => exportDeckData(),
        () => importDeckData(payloadFor([record()]), cards),
    ]) assert.throws(operation, error => error instanceof DeckStorageError && error.cause.name === "SecurityError");
});

test("failed reads stop mutations; failed writes report quota errors and preserve stored data", () => {
    let writes = 0;
    const blocked = {getItem() {throw new DOMException("blocked", "SecurityError");}, setItem() {writes++;}};
    assert.throws(() => readDecks(blocked), DeckStorageError);
    assert.throws(() => saveDeck(slots, blocked), DeckStorageError);
    assert.throws(() => importDeckData(payloadFor([record()]), cards, blocked), DeckStorageError);
    assert.equal(writes, 0);
    const raw = JSON.stringify([record()]);
    const full = {getItem:() => raw, setItem() {throw new DOMException("full", "QuotaExceededError");}};
    for (const operation of [
        () => saveDeck(slots, full), () => toggleFavorite(record().id, full),
        () => removeDeck(record().id, full), () => clearHistory(full), () => clearAllDecks(full),
        () => importDeckData(payloadFor([record({cardIds:cards.slice(1,9).map(c => c.id)})]), cards, full),
    ]) assert.throws(operation, error => error instanceof DeckStorageError && error.cause.name === "QuotaExceededError");
    assert.equal(full.getItem(STORAGE_KEY), raw);
});

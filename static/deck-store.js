import {ActiveForm, SlotRole, hasEvolution, hasHero, isChampion} from "./randomizer.js";

export const HISTORY_LIMIT = 20;
export const STORAGE_KEY = "clash-royale-randomizer.decks.v1";
export const EXPORT_FORMAT = "clash-royale-deck-randomizer";
export const EXPORT_VERSION = 1;

const ROLES = [SlotRole.EVOLUTION, SlotRole.HERO, SlotRole.WILD, ...Array(5).fill(SlotRole.NORMAL)];
const FORMS = new Set(Object.values(ActiveForm));

export class DeckStorageError extends Error {
    constructor(cause) {
        super("Deck storage could not be accessed.", {cause});
        this.name = "DeckStorageError";
    }
}

// Resolve the browser getter inside the try: even accessing localStorage can throw.
function accessStorage(storage, action) {
    try { return action(storage === undefined ? globalThis.localStorage : storage); }
    catch (cause) { throw new DeckStorageError(cause); }
}

// Numeric epoch milliseconds in the inclusive JS Date range (±8.64e15).
// Pre-1970 timestamps are supported; null/strings and non-finite numbers are not.
function validDate(value) {
    return typeof value === "number" && Number.isFinite(value) && !Number.isNaN(new Date(value).getTime());
}

function validDeck(entry) {
    return entry && typeof entry.id === "string" && Array.isArray(entry.cardIds) &&
        entry.cardIds.length === 8 && entry.cardIds.every(Number.isInteger) && new Set(entry.cardIds).size === 8 &&
        Array.isArray(entry.roles) && entry.roles.length === 8 && entry.roles.every((role, index) => role === ROLES[index]) &&
        Array.isArray(entry.activeForms) && entry.activeForms.length === 8 && entry.activeForms.every(form => FORMS.has(form)) &&
        validDate(entry.createdAt) && typeof entry.favorite === "boolean";
}

function validForms(entry, byId) {
    return entry.cardIds.every((id, index) => {
        const card = byId.get(id), role = entry.roles[index], form = entry.activeForms[index];
        if (!card) return false;
        if (isChampion(card))
            return form === ActiveForm.CHAMPION && [SlotRole.HERO, SlotRole.WILD].includes(role);
        // Version 1 never stored the original settings. Preserve inactive historical
        // forms on non-Champions, including cards that gained capabilities later.
        if (form === ActiveForm.NORMAL) return true;
        if (form === ActiveForm.EVOLUTION)
            return hasEvolution(card) && [SlotRole.EVOLUTION, SlotRole.WILD].includes(role);
        return form === ActiveForm.HERO && hasHero(card) && [SlotRole.HERO, SlotRole.WILD].includes(role);
    });
}

export function readDecks(storage, cards) {
    const raw = accessStorage(storage, target => target.getItem(STORAGE_KEY));
    try {
        const parsed = JSON.parse(raw || "[]");
        if (!Array.isArray(parsed)) throw new TypeError("Stored deck history must be an array.");
        const byId = cards && new Map(cards.map(card => [card.id, card]));
        return parsed.filter(entry => validDeck(entry) && (!byId || validForms(entry, byId)));
    } catch (cause) {
        // An unreadable container cannot be safely merged. Never turn it into an
        // empty history that the next automatic save would overwrite.
        throw new DeckStorageError(cause);
    }
}

export function writeDecks(decks, storage) {
    accessStorage(storage, target => target.setItem(STORAGE_KEY, JSON.stringify(decks)));
    return decks;
}

export function saveDeck(slots, storage, now = Date.now()) {
    const cardIds = slots.map(slot => slot.card.id);
    const signature = cardIds.join(";");
    const existing = readDecks(storage);
    const duplicate = existing.find(deck => deck.cardIds.join(";") === signature);
    const entry = {
        id: duplicate?.id || `${now}-${cardIds.join("-")}`,
        createdAt: now,
        favorite: duplicate?.favorite || false,
        cardIds,
        roles: slots.map(slot => slot.role),
        activeForms: slots.map(slot => slot.activeForm),
    };
    const next = [entry, ...existing.filter(deck => deck.id !== entry.id)];
    const favorites = next.filter(deck => deck.favorite);
    const recent = next.filter(deck => !deck.favorite).slice(0, HISTORY_LIMIT);
    writeDecks([...favorites, ...recent].sort((a, b) => b.createdAt - a.createdAt), storage);
    return entry;
}

export function toggleFavorite(id, storage) {
    const decks = readDecks(storage).map(deck => deck.id === id ? {...deck, favorite: !deck.favorite} : deck);
    writeDecks(decks, storage);
    return decks.find(deck => deck.id === id) || null;
}

export function removeDeck(id, storage) {
    return writeDecks(readDecks(storage).filter(deck => deck.id !== id), storage);
}

export function clearHistory(storage) {
    return writeDecks(readDecks(storage).filter(deck => deck.favorite), storage);
}

export function clearAllDecks(storage) {
    accessStorage(storage, target => {
        if (typeof target.removeItem === "function") target.removeItem(STORAGE_KEY);
        else target.setItem(STORAGE_KEY, "[]");
    });
    return [];
}

export function exportDeckData(storage, now = Date.now(), cards) {
    return {
        format: EXPORT_FORMAT,
        version: EXPORT_VERSION,
        exportedAt: new Date(now).toISOString(),
        decks: readDecks(storage, cards),
    };
}

export function importDeckData(payload, cards, storage) {
    let data;
    try { data = typeof payload === "string" ? JSON.parse(payload) : payload; }
    catch { return {imported: 0, updated: 0, skipped: 0, error: "invalid_json"}; }
    if (!data || data.format !== EXPORT_FORMAT || data.version !== EXPORT_VERSION || !Array.isArray(data.decks))
        return {imported: 0, updated: 0, skipped: 0, error: "invalid_format"};

    const existing = readDecks(storage);
    const byId = new Map(cards.map(card => [card.id, card]));
    const bySignature = new Map(existing.map(deck => [deck.cardIds.join(";"), deck]));
    let imported = 0, updated = 0, skipped = 0;
    for (const candidate of data.decks) {
        if (!validDeck(candidate) || !validForms(candidate, byId)) { skipped++; continue; }
        const signature = candidate.cardIds.join(";");
        const duplicate = bySignature.get(signature);
        if (duplicate) {
            if (candidate.favorite && !duplicate.favorite) { duplicate.favorite = true; updated++; }
            else skipped++;
            continue;
        }
        const copy = {
            id: `imported-${candidate.createdAt}-${signature.replaceAll(";", "-")}`,
            createdAt: candidate.createdAt,
            favorite: candidate.favorite,
            cardIds: [...candidate.cardIds], roles: [...candidate.roles], activeForms: [...candidate.activeForms],
        };
        existing.push(copy); bySignature.set(signature, copy); imported++;
    }
    const favorites = existing.filter(deck => deck.favorite);
    const recent = existing.filter(deck => !deck.favorite).sort((a, b) => b.createdAt - a.createdAt).slice(0, HISTORY_LIMIT);
    if (imported || updated) writeDecks([...favorites, ...recent].sort((a, b) => b.createdAt - a.createdAt), storage);
    return {imported, updated, skipped, error: null};
}

export function restoreSlots(entry, cards) {
    const byId = new Map(cards.map(card => [card.id, card]));
    if (!validDeck(entry) || !validForms(entry, byId)) return null;
    return entry.cardIds.map((id, index) => ({card: byId.get(id), role: entry.roles[index], activeForm: entry.activeForms[index]}));
}

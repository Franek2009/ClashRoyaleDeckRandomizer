export const HISTORY_LIMIT = 20;
export const STORAGE_KEY = "clash-royale-randomizer.decks.v1";

function validDeck(entry) {
    return entry && typeof entry.id === "string" && Array.isArray(entry.cardIds) &&
        entry.cardIds.length === 8 && entry.cardIds.every(Number.isInteger) &&
        Array.isArray(entry.roles) && entry.roles.length === 8 &&
        Array.isArray(entry.activeForms) && entry.activeForms.length === 8;
}

export function readDecks(storage = localStorage) {
    try {
        const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || "[]");
        return Array.isArray(parsed) ? parsed.filter(validDeck) : [];
    } catch {
        return [];
    }
}

export function writeDecks(decks, storage = localStorage) {
    storage.setItem(STORAGE_KEY, JSON.stringify(decks));
    return decks;
}

export function saveDeck(slots, storage = localStorage, now = Date.now()) {
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

export function toggleFavorite(id, storage = localStorage) {
    const decks = readDecks(storage).map(deck => deck.id === id ? {...deck, favorite: !deck.favorite} : deck);
    writeDecks(decks, storage);
    return decks.find(deck => deck.id === id) || null;
}

export function removeDeck(id, storage = localStorage) {
    return writeDecks(readDecks(storage).filter(deck => deck.id !== id), storage);
}

export function clearHistory(storage = localStorage) {
    return writeDecks(readDecks(storage).filter(deck => deck.favorite), storage);
}

export function restoreSlots(entry, cards) {
    const byId = new Map(cards.map(card => [card.id, card]));
    if (!validDeck(entry) || entry.cardIds.some(id => !byId.has(id))) return null;
    return entry.cardIds.map((id, index) => ({card: byId.get(id), role: entry.roles[index], activeForm: entry.activeForms[index]}));
}

export const HISTORY_LIMIT = 20;
export const STORAGE_KEY = "clash-royale-randomizer.decks.v1";
export const EXPORT_FORMAT = "clash-royale-deck-randomizer";
export const EXPORT_VERSION = 1;

const ROLES = new Set(["evolution", "hero", "wild", "normal"]);
const FORMS = new Set(["normal", "evolution", "hero", "champion"]);

function validDeck(entry) {
    return entry && typeof entry.id === "string" && Array.isArray(entry.cardIds) &&
        entry.cardIds.length === 8 && entry.cardIds.every(Number.isInteger) && new Set(entry.cardIds).size === 8 &&
        Array.isArray(entry.roles) && entry.roles.length === 8 && entry.roles.every(role => ROLES.has(role)) &&
        Array.isArray(entry.activeForms) && entry.activeForms.length === 8 && entry.activeForms.every(form => FORMS.has(form)) &&
        Number.isFinite(entry.createdAt) && typeof entry.favorite === "boolean";
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

export function clearAllDecks(storage = localStorage) {
    if (typeof storage.removeItem === "function") storage.removeItem(STORAGE_KEY);
    else storage.setItem(STORAGE_KEY, "[]");
    return [];
}

export function exportDeckData(storage = localStorage, now = Date.now()) {
    return {
        format: EXPORT_FORMAT,
        version: EXPORT_VERSION,
        exportedAt: new Date(now).toISOString(),
        decks: readDecks(storage),
    };
}

export function importDeckData(payload, knownCardIds, storage = localStorage) {
    let data;
    try { data = typeof payload === "string" ? JSON.parse(payload) : payload; }
    catch { return {imported: 0, updated: 0, skipped: 0, error: "invalid_json"}; }
    if (!data || data.format !== EXPORT_FORMAT || data.version !== EXPORT_VERSION || !Array.isArray(data.decks))
        return {imported: 0, updated: 0, skipped: 0, error: "invalid_format"};

    const existing = readDecks(storage);
    const bySignature = new Map(existing.map(deck => [deck.cardIds.join(";"), deck]));
    let imported = 0, updated = 0, skipped = 0;
    for (const candidate of data.decks) {
        if (!validDeck(candidate) || candidate.cardIds.some(id => !knownCardIds.has(id))) { skipped++; continue; }
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
    writeDecks([...favorites, ...recent].sort((a, b) => b.createdAt - a.createdAt), storage);
    return {imported, updated, skipped, error: null};
}

export function restoreSlots(entry, cards) {
    const byId = new Map(cards.map(card => [card.id, card]));
    if (!validDeck(entry) || entry.cardIds.some(id => !byId.has(id))) return null;
    return entry.cardIds.map((id, index) => ({card: byId.get(id), role: entry.roles[index], activeForm: entry.activeForms[index]}));
}

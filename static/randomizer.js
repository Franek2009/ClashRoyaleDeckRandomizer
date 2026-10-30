export const ActiveForm = Object.freeze({
    NORMAL: "normal", EVOLUTION: "evolution", HERO: "hero", CHAMPION: "champion",
});
export const SlotRole = Object.freeze({
    EVOLUTION: "evolution", HERO: "hero", WILD: "wild", NORMAL: "normal",
});
export const WildSlotMode = Object.freeze({
    OFF: "off", EVOLUTION: "evolution", HERO_CHAMPION: "hero_champion",
});
export const CardType = Object.freeze({ TROOP: "troop", SPELL: "spell", BUILDING: "building" });

const TYPES = Object.values(CardType);
const ROLES = [SlotRole.EVOLUTION, SlotRole.HERO, SlotRole.WILD];
const MIRROR_ID = 28000006;
const FRIENDLY_ERRORS = {
    type_counts_exceed_deck_size: "You selected more card types than can fit in an 8-card deck.",
    not_enough_spells: "There aren't enough Spell cards available for this selection.",
    not_enough_buildings: "There aren't enough Building cards available for this selection.",
    required_champion_needs_slot: "A required Champion needs the Hero Slot or Wild Slot set to Hero / Champion.",
    average_min_greater_than_max: "Minimum deck average cannot be greater than maximum deck average.",
    invalid_count: "Choose Any or a whole number from the list.",
    invalid_average: "Enter a valid number for the deck average.",
    invalid_slot_selection: "Choose a valid special-slot setting.",
    required_banned_conflict: "Required cards cannot also be banned.",
    required_not_available: "Every required card must also be included in the available card pool.",
    not_enough_eligible_cards: "There aren't enough available cards to build an 8-card deck.",
    too_many_required: "A deck can contain at most 8 required cards.",
    constraints_not_feasible: "These settings cannot produce a valid deck. Try relaxing one or more constraints.",
    invalid_locked_cards: "Locked cards must be unique and available for their current slots.",
};

export class ConstraintError extends Error {
    constructor(message, code = "invalid_constraints") {
        super(message); this.name = "ConstraintError"; this.code = code;
    }
    get friendlyMessage() { return FRIENDLY_ERRORS[this.code] || FRIENDLY_ERRORS.constraints_not_feasible; }
}

export function cardType(card) {
    if (!Number.isInteger(card.id)) throw new TypeError("card ID must be an integer");
    if (card.id === 27000010 || card.id === 28000025) return CardType.TROOP;
    if (card.id >= 26000000 && card.id < 27000000) return CardType.TROOP;
    if (card.id >= 27000000 && card.id < 28000000) return CardType.BUILDING;
    if (card.id >= 28000000 && card.id < 29000000) return CardType.SPELL;
    throw new TypeError(`unsupported card ID space for card ${card.id}`);
}
export const hasEvolution = card => Boolean((card.maxEvolutionLevel || 0) & 1);
export const hasHero = card => Boolean((card.maxEvolutionLevel || 0) & 2);
export const isChampion = card => card.rarity === "champion";
const heroCapable = card => hasHero(card) || isChampion(card);
export const elixirCostForAverage = card => card.id === MIRROR_ID ? 1 : card.elixirCost;

export function averageElixir(cards) {
    if (cards.length !== 8) throw new TypeError("average elixir requires exactly eight cards");
    const costs = cards.map(elixirCostForAverage);
    return costs.some(cost => cost == null) ? null : costs.reduce((sum, cost) => sum + cost, 0) / 8;
}

export function effectiveForm(card, role, constraints) {
    if (role === SlotRole.EVOLUTION)
        return constraints.evolutionSlotEnabled && hasEvolution(card) ? ActiveForm.EVOLUTION : ActiveForm.NORMAL;
    if (role === SlotRole.HERO) {
        if (!constraints.heroSlotEnabled) return ActiveForm.NORMAL;
        if (isChampion(card)) return ActiveForm.CHAMPION;
        return hasHero(card) ? ActiveForm.HERO : ActiveForm.NORMAL;
    }
    if (role === SlotRole.WILD) {
        if (constraints.wildSlotMode === WildSlotMode.EVOLUTION && hasEvolution(card)) return ActiveForm.EVOLUTION;
        if (constraints.wildSlotMode === WildSlotMode.HERO_CHAMPION) {
            if (isChampion(card)) return ActiveForm.CHAMPION;
            if (hasHero(card)) return ActiveForm.HERO;
        }
    }
    return ActiveForm.NORMAL;
}

export function createConstraints(values = {}) {
    const lockedIds = Array.from({length: 8}, (_, index) => values.lockedIds?.[index] ?? null);
    const requiredIds = new Set(values.requiredIds ?? []);
    for (const id of lockedIds) if (id != null) requiredIds.add(id);
    return {
        availableIds: values.availableIds ?? null,
        bannedIds: values.bannedIds ?? new Set(),
        requiredIds,
        lockedIds,
        evolutionSlotEnabled: values.evolutionSlotEnabled ?? true,
        heroSlotEnabled: values.heroSlotEnabled ?? true,
        wildSlotMode: values.wildSlotMode ?? WildSlotMode.EVOLUTION,
        spellCount: values.spellCount ?? null,
        buildingCount: values.buildingCount ?? null,
        minAverageElixir: values.minAverageElixir ?? null,
        maxAverageElixir: values.maxAverageElixir ?? null,
    };
}

function shuffle(items) {
    for (let i = items.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [items[i], items[j]] = [items[j], items[i]];
    }
    return items;
}
const sum = values => values.reduce((total, value) => total + value, 0);
const intersection = (a, b) => new Set([...a].filter(value => b.has(value)));
const difference = (a, b) => new Set([...a].filter(value => !b.has(value)));

function bounds(constraints) {
    return [
        constraints.minAverageElixir == null ? null : Math.ceil(constraints.minAverageElixir * 8 - 1e-9),
        constraints.maxAverageElixir == null ? null : Math.floor(constraints.maxAverageElixir * 8 + 1e-9),
    ];
}

function validateConstraints(cards, constraints) {
    const byId = new Map(cards.map(card => [card.id, card]));
    const catalogIds = new Set(byId.keys());
    const locked = constraints.lockedIds.filter(id => id != null);
    if (new Set(locked).size !== locked.length)
        throw new ConstraintError("locked cards must be unique", "invalid_locked_cards");
    if (constraints.requiredIds.size > 8) throw new ConstraintError("too many required cards", "too_many_required");
    for (const ids of [constraints.requiredIds, constraints.bannedIds, ...(constraints.availableIds ? [constraints.availableIds] : [])])
        if ([...ids].some(id => !catalogIds.has(id))) throw new ConstraintError("unknown card", "unknown_card_selection");
    if (intersection(constraints.requiredIds, constraints.bannedIds).size)
        throw new ConstraintError("required card is banned", "required_banned_conflict");
    if (constraints.availableIds && difference(constraints.requiredIds, constraints.availableIds).size)
        throw new ConstraintError("required card is unavailable", "required_not_available");
    for (let index = 0; index < constraints.lockedIds.length; index++) {
        const id = constraints.lockedIds[index];
        if (id == null || !byId.has(id)) continue;
        const role = index < ROLES.length ? ROLES[index] : SlotRole.NORMAL;
        if (!allowedForSlot(byId.get(id), role, constraints))
            throw new ConstraintError("locked card is unsafe for its slot", "invalid_locked_cards");
    }

    const eligibleIds = new Set(constraints.availableIds || catalogIds);
    for (const id of constraints.bannedIds) eligibleIds.delete(id);
    const eligible = cards.filter(card => eligibleIds.has(card.id));
    if (eligible.length < 8) throw new ConstraintError("not enough eligible cards", "not_enough_eligible_cards");

    for (const [name, value] of [["spell", constraints.spellCount], ["building", constraints.buildingCount]])
        if (value != null && (!Number.isInteger(value) || value < 0 || value > 8))
            throw new ConstraintError(`${name} count is invalid`, "invalid_count");
    for (const value of [constraints.minAverageElixir, constraints.maxAverageElixir])
        if (value != null && (!Number.isFinite(value) || value <= 0)) throw new ConstraintError("invalid average", "invalid_average");
    if (constraints.minAverageElixir != null && constraints.maxAverageElixir != null && constraints.minAverageElixir > constraints.maxAverageElixir)
        throw new ConstraintError("minimum exceeds maximum", "average_min_greater_than_max");
    if (constraints.spellCount != null && constraints.buildingCount != null && constraints.spellCount + constraints.buildingCount > 8)
        throw new ConstraintError("type counts exceed deck", "type_counts_exceed_deck_size");

    for (const [type, requested, code] of [
        [CardType.SPELL, constraints.spellCount, "not_enough_spells"],
        [CardType.BUILDING, constraints.buildingCount, "not_enough_buildings"],
    ]) {
        if (requested == null) continue;
        if (eligible.filter(card => cardType(card) === type).length < requested) throw new ConstraintError("not enough cards", code);
        if ([...constraints.requiredIds].filter(id => cardType(byId.get(id)) === type).length > requested)
            throw new ConstraintError("required type count exceeds requested", "constraints_not_feasible");
    }
    const championSlots = Number(constraints.heroSlotEnabled) + Number(constraints.wildSlotMode === WildSlotMode.HERO_CHAMPION);
    if ([...constraints.requiredIds].filter(id => isChampion(byId.get(id))).length > championSlots)
        throw new ConstraintError("required champion needs slot", "required_champion_needs_slot");
    return eligible;
}

function allowedForSlot(card, role, constraints) {
    if (role === SlotRole.EVOLUTION) {
        if (isChampion(card)) return false;
        return constraints.evolutionSlotEnabled ? hasEvolution(card) : !hasEvolution(card);
    }
    if (role === SlotRole.HERO) return constraints.heroSlotEnabled ? heroCapable(card) : !heroCapable(card);
    if (role === SlotRole.WILD) {
        if (constraints.wildSlotMode === WildSlotMode.EVOLUTION) return hasEvolution(card) && !isChampion(card);
        if (constraints.wildSlotMode === WildSlotMode.HERO_CHAMPION) return heroCapable(card);
        return !hasEvolution(card) && !heroCapable(card);
    }
    return !isChampion(card);
}

function chooseFillers(candidates, needed, chosenTotal, range) {
    shuffle(candidates);
    const [minimum, maximum] = range;
    const failed = new Set();
    function search(index, remaining, total, selected) {
        const key = `${index}|${remaining}|${total}`;
        if (failed.has(key)) return null;
        if (!remaining) return (minimum == null || total >= minimum) && (maximum == null || total <= maximum) ? [...selected] : null;
        if (candidates.length - index < remaining) return null;
        const costs = candidates.slice(index).map(elixirCostForAverage).sort((a, b) => a - b);
        if ((maximum != null && total + sum(costs.slice(0, remaining)) > maximum) ||
            (minimum != null && total + sum(costs.slice(-remaining)) < minimum)) return null;
        const card = candidates[index];
        let result = search(index + 1, remaining - 1, total + elixirCostForAverage(card), [...selected, card]);
        if (result) return result;
        result = search(index + 1, remaining, total, selected);
        if (!result) failed.add(key);
        return result;
    }
    return search(0, needed, chosenTotal, []);
}

function completeDeck(eligible, slots, constraints, target = null) {
    const slotIds = new Set(slots.map(card => card.id));
    const byId = new Map(eligible.map(card => [card.id, card]));
    const required = [...constraints.requiredIds].filter(id => !slotIds.has(id)).map(id => byId.get(id));
    if (required.some(isChampion)) return null;
    const chosenIds = new Set([...slotIds, ...required.map(card => card.id)]);
    let candidates = eligible.filter(card => !chosenIds.has(card.id) && !isChampion(card));
    const neededCount = 8 - slots.length - required.length;
    if (neededCount < 0) return null;

    let fillers;
    if (target) {
        const chosen = [...slots, ...required];
        const needed = Object.fromEntries(TYPES.map(type => [type, target[type] - chosen.filter(card => cardType(card) === type).length]));
        if (Object.values(needed).some(value => value < 0) || sum(Object.values(needed)) !== neededCount) return null;
        const selected = [];
        for (const type of TYPES) {
            const pool = candidates.filter(card => cardType(card) === type);
            if (pool.length < needed[type]) return null;
        }
        // Type counts reduce the search space; recurse across a shuffled union.
        candidates = shuffle(candidates);
        const [minimum, maximum] = bounds(constraints);
        function search(index, remaining, total) {
            if (!Object.values(remaining).some(Boolean))
                return (minimum == null || total >= minimum) && (maximum == null || total <= maximum) ? [...selected] : null;
            if (index >= candidates.length) return null;
            const card = candidates[index], type = cardType(card);
            if (remaining[type] > 0) {
                remaining[type]--; selected.push(card);
                const found = search(index + 1, remaining, total + elixirCostForAverage(card));
                if (found) return found;
                selected.pop(); remaining[type]++;
            }
            return search(index + 1, remaining, total);
        }
        fillers = search(0, {...needed}, sum([...slots, ...required].map(elixirCostForAverage)));
    } else {
        const range = bounds(constraints);
        fillers = range.some(value => value != null)
            ? chooseFillers(candidates, neededCount, sum([...slots, ...required].map(elixirCostForAverage)), range)
            : shuffle(candidates).slice(0, neededCount);
    }
    if (!fillers || fillers.length !== neededCount) return null;
    const normalCards = shuffle([...required, ...fillers]);
    const orderedNormal = Array(5).fill(null);
    for (let index = 3; index < 8; index++) {
        const lockedId = constraints.lockedIds[index];
        if (lockedId == null) continue;
        const cardIndex = normalCards.findIndex(card => card.id === lockedId);
        if (cardIndex < 0) return null;
        orderedNormal[index - 3] = normalCards.splice(cardIndex, 1)[0];
    }
    for (let index = 0; index < orderedNormal.length; index++)
        if (!orderedNormal[index]) orderedNormal[index] = normalCards.shift();
    return [...slots, ...orderedNormal];
}

function resolveDeck(eligible, constraints) {
    const candidates = Object.fromEntries(ROLES.map((role, index) => [role, shuffle(eligible.filter(card =>
        allowedForSlot(card, role, constraints) &&
        (constraints.lockedIds[index] == null || card.id === constraints.lockedIds[index])
    ))]));
    const chooseSlots = (target, index = 0, selected = []) => {
        if (index === ROLES.length) return completeDeck(eligible, selected, constraints, target);
        const used = new Set(selected.map(card => card.id));
        for (const card of candidates[ROLES[index]]) {
            if (used.has(card.id)) continue;
            if (target && selected.filter(item => cardType(item) === cardType(card)).length >= target[cardType(card)]) continue;
            const result = chooseSlots(target, index + 1, [...selected, card]);
            if (result) return result;
        }
        return null;
    };

    if (constraints.spellCount == null && constraints.buildingCount == null) return chooseSlots(null);

    const targets = [];
    const spells = constraints.spellCount == null ? [...Array(9).keys()] : [constraints.spellCount];
    const buildings = constraints.buildingCount == null ? [...Array(9).keys()] : [constraints.buildingCount];
    for (const spell of spells) for (const building of buildings) if (spell + building <= 8)
        targets.push({[CardType.SPELL]: spell, [CardType.BUILDING]: building, [CardType.TROOP]: 8 - spell - building});
    shuffle(targets);
    for (const target of targets) {
        const result = chooseSlots(target);
        if (result) return result;
    }
    return null;
}

export function generateDeck(cards, rawConstraints = {}) {
    const constraints = createConstraints(rawConstraints);
    const eligible = validateConstraints(cards, constraints);
    const deck = resolveDeck(eligible, constraints);
    if (!deck) throw new ConstraintError("constraints are not feasible", "constraints_not_feasible");
    return arrangeDeck(deck, constraints);
}

export function arrangeDeck(deck, constraints = createConstraints()) {
    if (deck.length !== 8 || new Set(deck.map(card => card.id)).size !== 8) throw new TypeError("deck must contain eight unique cards");
    const roles = [...ROLES, ...Array(5).fill(SlotRole.NORMAL)];
    return deck.map((card, index) => ({ card, role: roles[index], activeForm: effectiveForm(card, roles[index], constraints) }));
}

export function generateDeckLink(slots) {
    return `https://link.clashroyale.com/en/?clashroyale://copyDeck?deck=${slots.map(slot => slot.card.id).join(";")}&l=Royals&tt=159000000`;
}

import assert from "node:assert/strict";
import test from "node:test";
import {ConstraintError, generateDeck} from "../static/randomizer.js";

// Independent, exhaustive oracle: fixture types are explicit, not derived using
// the production classifier. Enumerate every 8-subset and every physical triple.
const card = (id, kind, cost, capability = 0, rarity = "common") =>
    ({id, kind, elixirCost:cost, maxEvolutionLevel:capability, rarity});
const catalog = [
    card(26000000,"troop",1,1), card(26000001,"troop",2,2),
    card(26000002,"troop",4,3), card(26000003,"troop",5,0,"champion"),
    card(26000004,"troop",2), card(27000000,"building",3),
    card(27000001,"building",7,1), card(28000000,"spell",2),
    card(28000001,"spell",4,2), card(28000006,"spell",undefined),
    card(28000016,"troop",1),
];
const cost = card => card.id === 28000006 ? 1 : card.elixirCost;
const evo = card => Boolean(card.maxEvolutionLevel & 1);
const hero = card => Boolean(card.maxEvolutionLevel & 2) || card.rarity === "champion";
const options = raw => ({evolutionSlotEnabled:true, heroSlotEnabled:true, wildSlotMode:"evolution", ...raw});

function allowed(card, index, config) {
    const champion = card.rarity === "champion";
    if (index === 0) return !champion && (config.evolutionSlotEnabled ? evo(card) : !evo(card));
    if (index === 1) return config.heroSlotEnabled ? hero(card) : !hero(card);
    if (index === 2) {
        if (config.wildSlotMode === "evolution") return evo(card) && !champion;
        if (config.wildSlotMode === "hero_champion") return hero(card);
        return !evo(card) && !hero(card);
    }
    return !champion;
}

function validSet(deck, config) {
    const ids = new Set(deck.map(card => card.id));
    const required = [...(config.requiredIds || []), ...(config.lockedIds || []).filter(id => id != null)];
    if (deck.length !== 8 || ids.size !== 8 || required.some(id => !ids.has(id))) return false;
    if (deck.some(card => config.bannedIds?.has(card.id) || (config.availableIds && !config.availableIds.has(card.id)))) return false;
    if (config.spellCount != null && deck.filter(card => card.kind === "spell").length !== config.spellCount) return false;
    if (config.buildingCount != null && deck.filter(card => card.kind === "building").length !== config.buildingCount) return false;
    const average = deck.reduce((total, card) => total + cost(card), 0) / 8;
    return !(config.minAverageElixir != null && average < config.minAverageElixir) &&
        !(config.maxAverageElixir != null && average > config.maxAverageElixir);
}

function* subsets(cards, start = 0, chosen = []) {
    if (chosen.length === 8) { yield chosen; return; }
    for (let index = start; index <= cards.length - (8 - chosen.length); index++)
        yield* subsets(cards, index + 1, [...chosen, cards[index]]);
}
const allSubsets = [...subsets(catalog)];

function oracle(raw) {
    const config = options(raw), locks = config.lockedIds || [];
    const lockValues = locks.filter(id => id != null);
    if (new Set(lockValues).size !== lockValues.length) return null;
    for (const deck of allSubsets) {
        if (!validSet(deck, config)) continue;
        for (const a of deck) for (const b of deck) for (const c of deck) {
            const triple = [a,b,c];
            if (new Set(triple.map(card => card.id)).size !== 3) continue;
            if (!triple.every((card,index) => allowed(card,index,config) &&
                (locks[index] == null || locks[index] === card.id) &&
                !locks.some((id,lockedIndex) => id === card.id && lockedIndex !== index))) continue;
            const rest = deck.filter(card => !triple.includes(card));
            if (!rest.every(card => allowed(card,3,config))) continue;
            const ordered = [...triple];
            for (let index = 3; index < 8; index++) {
                const at = locks[index] == null ? rest.findIndex(card => !locks.includes(card.id)) : rest.findIndex(card => card.id === locks[index]);
                if (at < 0) break;
                ordered.push(rest.splice(at,1)[0]);
            }
            if (ordered.length === 8) return ordered;
        }
    }
    return null;
}

function check(raw, seed) {
    const witness = oracle(raw), config = options(raw), original = Math.random;
    Math.random = () => ((seed = (1664525 * seed + 1013904223) >>> 0) / 2 ** 32);
    try {
        if (!witness) {
            assert.throws(() => generateDeck(catalog, raw), ConstraintError);
            return false;
        }
        const result = generateDeck(catalog, raw);
        const deck = result.map(slot => slot.card);
        assert.ok(validSet(deck, config));
        assert.deepEqual(result.map(slot => slot.role), ["evolution","hero","wild",...Array(5).fill("normal")]);
        deck.forEach((card,index) => {
            assert.ok(allowed(card,index,config));
            if (raw.lockedIds?.[index] != null) assert.equal(card.id,raw.lockedIds[index]);
            let form = "normal";
            if ((index === 0 && config.evolutionSlotEnabled) || (index === 2 && config.wildSlotMode === "evolution")) form = "evolution";
            if ((index === 1 && config.heroSlotEnabled) || (index === 2 && config.wildSlotMode === "hero_champion"))
                form = card.rarity === "champion" ? "champion" : "hero";
            assert.equal(result[index].activeForm,form);
        });
        return true;
    } finally { Math.random = original; }
}

test("complete search agrees with exhaustive subsets/slot permutations for every slot mode", () => {
    let feasible = 0, infeasible = 0;
    for (const evolutionSlotEnabled of [false,true]) for (const heroSlotEnabled of [false,true])
        for (const wildSlotMode of ["off","evolution","hero_champion"]) {
            const base = {evolutionSlotEnabled,heroSlotEnabled,wildSlotMode};
            const scenarios = [
                {}, {spellCount:2,buildingCount:1,minAverageElixir:2.5,maxAverageElixir:3},
                {spellCount:2,buildingCount:1,minAverageElixir:3.125,maxAverageElixir:3.125},
                {spellCount:2,minAverageElixir:0.1,maxAverageElixir:0.2},
                {buildingCount:1,minAverageElixir:9.9,maxAverageElixir:10},
                {spellCount:1,minAverageElixir:3.1,maxAverageElixir:3.1},
                {requiredIds:new Set([28000006,28000016]),spellCount:1},
                {requiredIds:new Set([26000003]),bannedIds:new Set([28000000])},
                {availableIds:new Set(catalog.slice(0,8).map(card => card.id)),spellCount:1},
                {requiredIds:new Set([26000002]),lockedIds:[null,null,null,26000000],spellCount:2},
            ];
            const witness = oracle(base);
            if (witness) scenarios.push({lockedIds:witness.map((card,index) => index === 7 ? null : card.id),
                minAverageElixir:witness.reduce((sum,card) => sum + cost(card),0)/8,
                maxAverageElixir:witness.reduce((sum,card) => sum + cost(card),0)/8});
            for (const scenario of scenarios) for (const seed of [123,456])
                check({...base,...scenario},seed) ? feasible++ : infeasible++;
        }
    assert.ok(feasible > 50 && infeasible > 50, `${feasible} feasible / ${infeasible} infeasible`);
});

test("seeded mixed constraints agree with brute force, including integer-sum gaps", () => {
    let state = 7321;
    const random = count => ((state = (1664525 * state + 1013904223) >>> 0) % count);
    for (let trial = 0; trial < 160; trial++) {
        const config = {evolutionSlotEnabled:Boolean(random(2)),heroSlotEnabled:Boolean(random(2)),
            wildSlotMode:["off","evolution","hero_champion"][random(3)],
            spellCount:[null,0,1,2,3][random(5)],buildingCount:[null,0,1,2][random(4)]};
        if (random(2)) {
            const total = 8 + random(32);
            config.minAverageElixir = total/8;
            config.maxAverageElixir = (total + random(3))/8;
        }
        config.requiredIds = new Set([catalog[random(catalog.length)].id]);
        config.bannedIds = new Set([catalog[random(catalog.length)].id]);
        config.availableIds = new Set(catalog.filter(() => random(6) !== 0).map(card => card.id));
        check(config,trial + 1);
    }
});

test("integer-sum holes are rejected without losing adjacent feasible totals", () => {
    const originals = catalog.map(card => card.elixirCost);
    try {
        // All selectable costs are even. 23 lies inside the min/max interval,
        // but cannot be achieved; this exercises DFS/memo rather than rounding.
        catalog.forEach((card,index) => { if (card.id !== 28000006) card.elixirCost = index % 2 ? 4 : 2; });
        for (const spellCount of [null,2]) {
            const base = {spellCount,bannedIds:new Set([28000006])};
            assert.equal(check({...base,minAverageElixir:23/8,maxAverageElixir:23/8},123),false);
            assert.equal(check({...base,minAverageElixir:3,maxAverageElixir:3},123),true);
        }
    } finally { catalog.forEach((card,index) => { card.elixirCost = originals[index]; }); }
});

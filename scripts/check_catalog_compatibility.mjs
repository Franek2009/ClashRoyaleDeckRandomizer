// Run against the isolated checkout and candidate cards.json before publication.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {pathToFileURL} from "node:url";

const [checkout, baselinePath] = process.argv.slice(2);
const model = await import(pathToFileURL(path.join(checkout, "static/randomizer.js")));
const {cardType, hasEvolution, hasHero, isChampion, generateDeck, averageElixir} = model;
const cards = JSON.parse(fs.readFileSync(path.join(checkout, "cards.json"))).items;
const previous = new Set(JSON.parse(fs.readFileSync(baselinePath)).items.map(card => card.id));
assert.equal(cardType({id:28000016}), "troop", "R2 Heal Spirit fix required before automatic publication");
assert.equal(cardType({id:27000010}), "troop");
assert.equal(cardType({id:28000025}), "troop");
for (const card of cards) {
    assert.ok(["troop", "spell", "building"].includes(cardType(card)));
    assert.equal(hasEvolution(card), "evolutionMedium" in card.iconUrls);
    assert.equal(hasHero(card), "heroMedium" in card.iconUrls);
    assert.ok(!(isChampion(card) && (hasEvolution(card) || hasHero(card))));
    if (!previous.has(card.id)) assert.equal(cardType(card), "troop");
}

let seed = 11002026;
Math.random = () => ((seed = (1664525 * seed + 1013904223) >>> 0) / 2 ** 32);
const roles = ["evolution", "hero", "wild", ...Array(5).fill("normal")];
function verify(slots, options = {}) {
    assert.equal(slots.length, 8);
    assert.equal(new Set(slots.map(slot => slot.card.id)).size, 8);
    assert.deepEqual(slots.map(slot => slot.role), roles);
    for (const {card, role, activeForm} of slots) {
        if (activeForm === "evolution") assert.ok(hasEvolution(card) && ["evolution", "wild"].includes(role));
        else if (activeForm === "hero") assert.ok(hasHero(card) && ["hero", "wild"].includes(role));
        else if (activeForm === "champion") assert.ok(isChampion(card) && ["hero", "wild"].includes(role));
        else assert.equal(activeForm, "normal");
        if (isChampion(card)) assert.equal(activeForm, "champion");
    }
    if (options.evolutionSlotEnabled === false) assert.ok(!hasEvolution(slots[0].card));
    if (options.heroSlotEnabled === false) assert.ok(!hasHero(slots[1].card) && !isChampion(slots[1].card));
    if (options.wildSlotMode === "off") assert.ok(!hasEvolution(slots[2].card) && !hasHero(slots[2].card) && !isChampion(slots[2].card));
    const plain = slots.map(slot => slot.card);
    const expected = plain.reduce((total, card) => total + (card.id === 28000006 ? 1 : card.elixirCost), 0) / 8;
    assert.equal(averageElixir(plain), expected);
    if (options.spellCount != null) assert.equal(plain.filter(card => cardType(card) === "spell").length, options.spellCount);
    if (options.buildingCount != null) assert.equal(plain.filter(card => cardType(card) === "building").length, options.buildingCount);
    if (options.minAverageElixir != null) assert.ok(expected >= options.minAverageElixir);
    if (options.maxAverageElixir != null) assert.ok(expected <= options.maxAverageElixir);
    for (const id of options.requiredIds || []) assert.ok(plain.some(card => card.id === id));
    for (const id of options.bannedIds || []) assert.ok(plain.every(card => card.id !== id));
}
for (const evolutionSlotEnabled of [false, true]) for (const heroSlotEnabled of [false, true])
    for (const wildSlotMode of ["off", "evolution", "hero_champion"]) {
        const options = {evolutionSlotEnabled, heroSlotEnabled, wildSlotMode};
        for (let trial = 0; trial < 20; trial++) verify(generateDeck(cards, options), options);
    }
const mirror = cards.find(card => card.id === 28000006);
assert.ok(mirror);
const required = cards.find(card => !isChampion(card) && card.id !== mirror.id);
const banned = cards.find(card => ![mirror.id, required.id].includes(card.id));
const options = {requiredIds:new Set([mirror.id, required.id]), bannedIds:new Set([banned.id]),
    spellCount:2, buildingCount:1, minAverageElixir:2, maxAverageElixir:6};
const deck = generateDeck(cards, options);
verify(deck, options);
const lockedIds = deck.map(slot => slot.card.id);
assert.deepEqual(generateDeck(cards, {...options, lockedIds}).map(slot => slot.card.id), lockedIds);
assert.deepEqual(generateDeck(cards, {...options, availableIds:new Set(lockedIds)}).map(slot => slot.card.id).sort(), [...lockedIds].sort());
assert.throws(() => generateDeck(cards, {requiredIds:new Set([mirror.id]), bannedIds:new Set([mirror.id])}));
// A machine-readable parity check for the Python model; no test logs on stdout.
console.log(JSON.stringify(Object.fromEntries(cards.map(card => [card.id, cardType(card)]))));

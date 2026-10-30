import assert from "node:assert/strict";
import test from "node:test";

import {filterCards} from "../static/card-filter.js";

const cards = [
    {id: 26000001, rarity: "common", elixirCost: 2, maxEvolutionLevel: 1},
    {id: 26000002, rarity: "rare", elixirCost: 4, maxEvolutionLevel: 2},
    {id: 26000003, rarity: "epic", elixirCost: 6, maxEvolutionLevel: 3},
    {id: 26000004, rarity: "champion", elixirCost: 5},
    {id: 28000006, rarity: "epic"},
];

test("empty filters keep every card", () => {
    assert.deepEqual(filterCards(cards), cards);
});

test("rarity and Elixir filters are combined", () => {
    const result = filterCards(cards, {rarities: new Set(["rare", "epic"]), minElixir: 3, maxElixir: 5});
    assert.deepEqual(result.map(card => card.id), [26000002]);
});

test("Evolution and Hero filters can be combined", () => {
    const result = filterCards(cards, {evolutionOnly: true, heroOnly: true});
    assert.deepEqual(result.map(card => card.id), [26000003]);
});

test("Champions can be excluded independently", () => {
    assert.ok(!filterCards(cards, {excludeChampions: true}).some(card => card.rarity === "champion"));
});

test("Mirror uses cost one in Elixir filters", () => {
    assert.ok(filterCards(cards, {maxElixir: 1}).some(card => card.id === 28000006));
});

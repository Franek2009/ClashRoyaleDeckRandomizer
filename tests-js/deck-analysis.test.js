import assert from "node:assert/strict";
import test from "node:test";

import {deckInsights, elixirDistribution} from "../static/deck-analysis.js";

function card(id, elixirCost) {
    return {id, elixirCost, rarity: "common"};
}

test("elixir distribution groups costs of six and above", () => {
    const cards = [card(26000001, 1), card(26000002, 2), card(26000003, 3), card(26000004, 4), card(26000005, 5), card(26000006, 6), card(26000007, 7), card(26000008, 3)];
    assert.deepEqual(elixirDistribution(cards), {"1": 1, "2": 1, "3": 2, "4": 1, "5": 1, "6+": 2});
});

test("Mirror is represented using its average cost", () => {
    const cards = [card(28000006, undefined), ...Array.from({length: 7}, (_, index) => card(26000001 + index, 3))];
    assert.equal(elixirDistribution(cards)["1"], 1);
});

test("insights describe objective type and elixir patterns", () => {
    const cards = Array.from({length: 8}, (_, index) => card(26000001 + index, index < 3 ? 6 : 5));
    const messages = deckInsights(cards).map(insight => insight.text);
    assert.ok(messages.some(message => message.startsWith("Heavy deck")));
    assert.ok(messages.some(message => message.startsWith("No Spell")));
    assert.ok(messages.some(message => message.startsWith("No Building")));
    assert.ok(messages.some(message => message.includes("cost 6 or more")));
});

test("ordinary decks receive a neutral positive result", () => {
    const cards = [
        card(26000001, 3), card(26000002, 3), card(26000003, 4), card(26000004, 4),
        card(26000005, 3), card(26000006, 4), card(27000001, 4), card(28000001, 3),
    ];
    assert.deepEqual(deckInsights(cards), [{kind: "positive", text: "No unusual Elixir or card-type patterns detected."}]);
});

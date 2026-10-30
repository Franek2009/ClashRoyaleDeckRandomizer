import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
    ActiveForm, CardType, ConstraintError, SlotRole, averageElixir, cardType,
    generateDeck, generateDeckLink, hasEvolution, hasHero, isChampion,
} from "../static/randomizer.js";

const cards = JSON.parse(fs.readFileSync(new URL("../cards.json", import.meta.url), "utf8")).items;

test("card catalog uses supported types and matching special-form artwork", () => {
    for (const card of cards) {
        assert.ok(Object.values(CardType).includes(cardType(card)));
        assert.equal(hasEvolution(card), "evolutionMedium" in card.iconUrls);
        assert.equal(hasHero(card), "heroMedium" in card.iconUrls);
    }
});

test("default generation creates eight unique cards in safe slots", () => {
    for (let index = 0; index < 500; index++) {
        const slots = generateDeck(cards);
        assert.equal(slots.length, 8);
        assert.equal(new Set(slots.map(slot => slot.card.id)).size, 8);
        assert.deepEqual(slots.slice(0, 3).map(slot => slot.role), [SlotRole.EVOLUTION, SlotRole.HERO, SlotRole.WILD]);
        assert.equal(slots[0].activeForm, ActiveForm.EVOLUTION);
        assert.ok([ActiveForm.HERO, ActiveForm.CHAMPION].includes(slots[1].activeForm));
        assert.equal(slots[2].activeForm, ActiveForm.EVOLUTION);
        assert.ok(slots.slice(3).every(slot => !isChampion(slot.card)));
    }
});

test("required and banned card pools are respected", () => {
    const required = cards.find(card => !isChampion(card) && !hasEvolution(card) && !hasHero(card));
    const banned = cards.find(card => card.id !== required.id);
    const slots = generateDeck(cards, {requiredIds: new Set([required.id]), bannedIds: new Set([banned.id])});
    const ids = new Set(slots.map(slot => slot.card.id));
    assert.ok(ids.has(required.id));
    assert.ok(!ids.has(banned.id));
});

test("type and average constraints are respected", () => {
    for (let index = 0; index < 30; index++) {
        const slots = generateDeck(cards, {spellCount: 2, buildingCount: 1, minAverageElixir: 2.5, maxAverageElixir: 4.5});
        const deck = slots.map(slot => slot.card);
        assert.equal(deck.filter(card => cardType(card) === CardType.SPELL).length, 2);
        assert.equal(deck.filter(card => cardType(card) === CardType.BUILDING).length, 1);
        assert.ok(averageElixir(deck) >= 2.5 && averageElixir(deck) <= 4.5);
    }
});

test("invalid selections return stable friendly error codes", () => {
    const id = cards[0].id;
    assert.throws(() => generateDeck(cards, {requiredIds: new Set([id]), bannedIds: new Set([id])}), error => error instanceof ConstraintError && error.code === "required_banned_conflict");
});

test("deck link preserves all slot IDs in order", () => {
    const slots = generateDeck(cards);
    const ids = slots.map(slot => slot.card.id).join(";");
    assert.equal(generateDeckLink(slots), `https://link.clashroyale.com/en/?clashroyale://copyDeck?deck=${ids}&l=Royals&tt=159000000`);
});

test("locked cards stay in their exact slots when the rest is generated again", () => {
    const first = generateDeck(cards);
    const lockedIds = [first[0].card.id, null, null, null, first[4].card.id, null, null, first[7].card.id];
    for (let index = 0; index < 30; index++) {
        const next = generateDeck(cards, {lockedIds});
        assert.equal(next[0].card.id, lockedIds[0]);
        assert.equal(next[4].card.id, lockedIds[4]);
        assert.equal(next[7].card.id, lockedIds[7]);
    }
});

test("a card cannot be locked into an unsafe special slot", () => {
    const normal = cards.find(card => !hasEvolution(card) && !hasHero(card) && !isChampion(card));
    assert.throws(() => generateDeck(cards, {lockedIds: [normal.id]}), error => error instanceof ConstraintError && error.code === "invalid_locked_cards");
});

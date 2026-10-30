import {CardType, averageElixir, cardType, elixirCostForAverage} from "./randomizer.js";

export function elixirDistribution(cards) {
    const distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6+": 0};
    for (const card of cards) {
        const cost = elixirCostForAverage(card);
        if (cost == null) continue;
        const bucket = cost >= 6 ? "6+" : String(Math.max(1, cost));
        if (bucket in distribution) distribution[bucket]++;
    }
    return distribution;
}

export function deckInsights(cards) {
    const average = averageElixir(cards);
    const spells = cards.filter(card => cardType(card) === CardType.SPELL).length;
    const buildings = cards.filter(card => cardType(card) === CardType.BUILDING).length;
    const expensive = cards.filter(card => (elixirCostForAverage(card) ?? 0) >= 6).length;
    const insights = [];

    if (average != null && average <= 2.8) insights.push({kind: "info", text: "Very fast cycle: average Elixir is 2.8 or lower."});
    if (average != null && average >= 4.3) insights.push({kind: "warning", text: "Heavy deck: average Elixir is 4.3 or higher."});
    if (spells === 0) insights.push({kind: "warning", text: "No Spell cards in this deck."});
    if (spells >= 4) insights.push({kind: "info", text: `${spells} Spell cards make this a spell-heavy deck.`});
    if (buildings === 0) insights.push({kind: "info", text: "No Building cards in this deck."});
    if (expensive >= 3) insights.push({kind: "warning", text: `${expensive} cards cost 6 or more Elixir.`});
    if (!insights.length) insights.push({kind: "positive", text: "No unusual Elixir or card-type patterns detected."});
    return insights;
}

import {elixirCostForAverage, hasEvolution, hasHero, isChampion} from "./randomizer.js";

export function filterCards(cards, filters = {}) {
    const rarities = filters.rarities ?? new Set();
    return cards.filter(card => {
        const cost = elixirCostForAverage(card);
        if (rarities.size && !rarities.has(card.rarity)) return false;
        if (filters.minElixir != null && (cost == null || cost < filters.minElixir)) return false;
        if (filters.maxElixir != null && (cost == null || cost > filters.maxElixir)) return false;
        if (filters.evolutionOnly && !hasEvolution(card)) return false;
        if (filters.heroOnly && !hasHero(card)) return false;
        if (filters.excludeChampions && isChampion(card)) return false;
        return true;
    });
}

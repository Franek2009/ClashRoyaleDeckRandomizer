import {ActiveForm, ConstraintError, SlotRole, averageElixir, cardType, generateDeck, generateDeckLink, hasEvolution, hasHero} from "./randomizer.js";
import {clearHistory, readDecks, removeDeck, restoreSlots, saveDeck, toggleFavorite} from "./deck-store.js";
import {deckInsights, elixirDistribution} from "./deck-analysis.js";
import {filterCards} from "./card-filter.js";

document.documentElement.classList.add("js");
const form = document.querySelector("[data-generator-form]");
const cardPool = document.querySelector("[data-card-pool]");
const picker = document.querySelector("[data-card-picker]");
const contexts = ["available", "banned", "required"];
const descriptions = {available: "Cards the randomizer may use.", banned: "Cards that must not appear.", required: "Cards that must appear."};
let activeContext = "available";
let cards = [];
let currentSlots = null;
let currentEntryId = null;
let lockedIds = Array(8).fill(null);
let savedFilter = "all";

const escapeHtml = value => String(value).replace(/[&<>"]/g, char => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[char]);
const checkedIds = context => new Set([...cardPool.querySelectorAll(`input[name="${context}_ids"]:checked`)].map(input => Number(input.value)));

function renderPicker() {
    picker.innerHTML = cards.map(card => `<article class="picker-card" data-picker-card data-card-name="${escapeHtml(card.name.toLocaleLowerCase())}" data-card-id="${card.id}"><img src="${escapeHtml(card.iconUrls.medium)}" alt="" loading="lazy"><div class="picker-card-copy"><h3>${escapeHtml(card.name)}</h3><span>Elixir: ${card.elixirCost ?? "—"}</span></div><div class="picker-card-controls">${contexts.map(context => `<label class="picker-card-control" data-pool-control="${context}"><input type="checkbox" name="${context}_ids" value="${card.id}" aria-label="${context}: ${escapeHtml(card.name)}"><span>${context[0].toUpperCase() + context.slice(1)}</span></label>`).join("")}</div></article>`).join("");
    setContext(activeContext);
}

function updateChips(context) {
    const inputs = [...cardPool.querySelectorAll(`input[name="${context}_ids"]:checked`)];
    cardPool.querySelectorAll(`[data-selected-count="${context}"]`).forEach(node => { node.textContent = inputs.length; });
    const container = cardPool.querySelector(`[data-selected-chips="${context}"]`);
    container.replaceChildren(...inputs.map(input => {
        const card = input.closest("[data-picker-card]");
        const chip = document.createElement("span"); chip.className = "card-chip";
        chip.append(document.createTextNode(card.querySelector("h3").textContent));
        const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "×";
        remove.dataset.removeCard = context; remove.dataset.cardId = input.value;
        remove.setAttribute("aria-label", `Remove ${card.querySelector("h3").textContent} from ${context}`);
        chip.append(remove); return chip;
    }));
    if (context === "available") updateAvailableLabel();
}

function updateAvailableLabel() {
    const count = cardPool.querySelectorAll('input[name="available_ids"]:checked').length;
    cardPool.querySelector("[data-available-label]").textContent = cardPool.dataset.availableMode === "all" ? "All" : count;
}

function setContext(context) {
    activeContext = context; cardPool.dataset.context = context;
    cardPool.querySelectorAll("[data-picker-context]").forEach(button => { const active = button.dataset.pickerContext === context; button.classList.toggle("is-active", active); button.setAttribute("aria-pressed", String(active)); });
    cardPool.querySelectorAll("[data-selected-pool]").forEach(group => group.classList.toggle("is-active", group.dataset.selectedPool === context));
    cardPool.querySelectorAll("[data-pool-control]").forEach(control => control.classList.toggle("is-active", control.dataset.poolControl === context));
    cardPool.querySelectorAll("[data-picker-card]").forEach(card => card.classList.toggle("is-selected", card.querySelector(`input[name="${context}_ids"]`).checked));
    cardPool.querySelector("[data-picker-context-help]").textContent = descriptions[context];
}

function optionalNumber(data, name) { const value = data.get(name); return value === "" || value === "any" ? null : Number(value); }
function filtersFromForm(data = new FormData(form)) {
    return {
        rarities: new Set(data.getAll("filter_rarity")),
        minElixir: optionalNumber(data, "filter_min_elixir"),
        maxElixir: optionalNumber(data, "filter_max_elixir"),
        evolutionOnly: data.has("filter_evolution_only"),
        heroOnly: data.has("filter_hero_only"),
        excludeChampions: data.has("filter_exclude_champions"),
    };
}

function filtersAreActive(filters) {
    return filters.rarities.size > 0 || filters.minElixir != null || filters.maxElixir != null ||
        filters.evolutionOnly || filters.heroOnly || filters.excludeChampions;
}

function updateFilterCount() {
    if (!cards.length) return;
    const filters = filtersFromForm();
    const count = filterCards(cards, filters).length;
    document.querySelector("[data-filter-count]").textContent = filtersAreActive(filters) ? count : "All";
}

function constraintsFromForm() {
    const data = new FormData(form);
    const filters = filtersFromForm(data);
    if (filters.minElixir != null && filters.maxElixir != null && filters.minElixir > filters.maxElixir)
        throw new ConstraintError("minimum card cost exceeds maximum", "invalid_card_filter");
    let availableIds = data.get("available_mode") === "all" ? null : checkedIds("available");
    if (filtersAreActive(filters)) {
        const filteredIds = new Set(filterCards(cards, filters).map(card => card.id));
        availableIds = availableIds == null ? filteredIds : new Set([...availableIds].filter(id => filteredIds.has(id)));
    }
    return {availableIds, bannedIds: checkedIds("banned"), requiredIds: checkedIds("required"), lockedIds, evolutionSlotEnabled: data.get("evolution_slot_enabled") === "on", heroSlotEnabled: data.get("hero_slot_enabled") === "on", wildSlotMode: data.get("wild_slot_mode"), spellCount: optionalNumber(data, "spell_count"), buildingCount: optionalNumber(data, "building_count"), minAverageElixir: optionalNumber(data, "min_average_elixir"), maxAverageElixir: optionalNumber(data, "max_average_elixir")};
}

const summaryItem = (label, value) => `<div><dt>${label}</dt><dd>${value}</dd></div>`;
function updateFavoriteButton() {
    const button = document.querySelector("[data-favorite-current]");
    const entry = readDecks().find(deck => deck.id === currentEntryId);
    const favorite = Boolean(entry?.favorite);
    button.setAttribute("aria-pressed", String(favorite));
    button.textContent = favorite ? "★ Favorited" : "☆ Add to favorites";
}

function renderResult(slots, {save = true, scroll = true} = {}) {
    currentSlots = slots;
    const roleLabels = {[SlotRole.EVOLUTION]: "Evolution", [SlotRole.HERO]: "Hero", [SlotRole.WILD]: "Wild"};
    document.querySelector("[data-slot-summary]").innerHTML = slots.slice(0, 3).map(slot => summaryItem(roleLabels[slot.role], slot.activeForm === ActiveForm.NORMAL ? "Off" : slot.activeForm.replace("_", " ").replace(/^./, c => c.toUpperCase()))).join("");
    const plainCards = slots.map(slot => slot.card), average = averageElixir(plainCards);
    document.querySelector("[data-deck-summary]").innerHTML = [["Evolutions", slots.filter(slot => slot.activeForm === ActiveForm.EVOLUTION).length], ["Heroes / Champions", slots.filter(slot => [ActiveForm.HERO, ActiveForm.CHAMPION].includes(slot.activeForm)).length], ["Spells", plainCards.filter(card => cardType(card) === "spell").length], ["Buildings", plainCards.filter(card => cardType(card) === "building").length], ["Average Elixir", average == null ? "—" : Number(average.toFixed(3))]].map(([label, value]) => summaryItem(label, value)).join("");
    const distribution = elixirDistribution(plainCards), maximum = Math.max(1, ...Object.values(distribution));
    document.querySelector("[data-elixir-chart]").innerHTML = Object.entries(distribution).map(([cost, count]) => `<div class="chart-column"><span class="chart-value">${count}</span><div class="chart-track"><span style="height: ${count / maximum * 100}%"></span></div><span class="chart-label">${cost}</span></div>`).join("");
    document.querySelector("[data-deck-insights]").innerHTML = deckInsights(plainCards).map(insight => `<li class="is-${insight.kind}">${escapeHtml(insight.text)}</li>`).join("");
    document.querySelector("[data-deck]").innerHTML = slots.map(slot => {
        const image = slot.activeForm === ActiveForm.EVOLUTION ? slot.card.iconUrls.evolutionMedium : slot.activeForm === ActiveForm.HERO ? slot.card.iconUrls.heroMedium : slot.card.iconUrls.medium;
        const index = slots.indexOf(slot), locked = lockedIds[index] === slot.card.id;
        return `<article class="card${locked ? " is-locked" : ""}" data-card-id="${slot.card.id}" data-slot-role="${slot.role}" data-active-form="${slot.activeForm}">${slot.role === SlotRole.NORMAL ? "" : `<span class="slot-badge">${roleLabels[slot.role]} Slot</span>`}<button type="button" class="lock-button" data-lock-slot="${index}" aria-pressed="${locked}" aria-label="${locked ? "Unlock" : "Lock"} ${escapeHtml(slot.card.name)}">${locked ? "🔒" : "🔓"}</button><div class="card-image"><img src="${escapeHtml(image)}" alt="${escapeHtml(slot.card.name)}"></div><div class="card-info"><h3>${escapeHtml(slot.card.name)}</h3>${slot.activeForm === ActiveForm.NORMAL ? "" : `<span class="active-form form-badge">${slot.activeForm.replace(/^./, c => c.toUpperCase())}</span>`}<div class="card-details"><span class="rarity">${escapeHtml(slot.card.rarity)}</span><span class="elixir"><span class="elixir-icon"></span>${slot.card.elixirCost ?? "—"}</span></div></div></article>`;
    }).join("");
    document.querySelector("[data-deck-link]").href = generateDeckLink(slots);
    const wild = slots[2], notice = document.querySelector("[data-wild-notice]"), dual = hasEvolution(wild.card) && hasHero(wild.card);
    notice.hidden = !dual; if (dual) notice.textContent = `After importing the deck, set the Wild Slot to ${wild.activeForm === ActiveForm.EVOLUTION ? "Evolution" : "Hero"}.`;
    if (save) {
        try { currentEntryId = saveDeck(slots).id; } catch { currentEntryId = null; }
    }
    updateFavoriteButton();
    renderSavedDecks();
    const result = document.querySelector("[data-result]"); result.hidden = false;
    if (scroll) result.scrollIntoView({behavior: "smooth", block: "start"});
}

function renderSavedDecks() {
    if (!cards.length) return;
    const allDecks = readDecks();
    const decks = savedFilter === "favorites" ? allDecks.filter(deck => deck.favorite) : allDecks;
    const section = document.querySelector("[data-saved-section]");
    section.hidden = allDecks.length === 0;
    document.querySelector("[data-saved-empty]").hidden = decks.length !== 0;
    document.querySelector("[data-saved-decks]").innerHTML = decks.map(deck => {
        const slots = restoreSlots(deck, cards);
        if (!slots) return "";
        const date = new Intl.DateTimeFormat(undefined, {dateStyle: "medium", timeStyle: "short"}).format(deck.createdAt);
        return `<article class="saved-deck" data-saved-id="${escapeHtml(deck.id)}"><div class="saved-preview">${slots.map(slot => `<img src="${escapeHtml(slot.card.iconUrls.medium)}" alt="${escapeHtml(slot.card.name)}" title="${escapeHtml(slot.card.name)}" loading="lazy">`).join("")}</div><div class="saved-meta"><time datetime="${new Date(deck.createdAt).toISOString()}">${escapeHtml(date)}</time><div class="saved-actions"><button type="button" data-view-saved>View</button><button type="button" data-favorite-saved aria-pressed="${deck.favorite}">${deck.favorite ? "★" : "☆"}<span class="visually-hidden"> Toggle favorite</span></button><button type="button" data-remove-saved aria-label="Remove this deck">×</button></div></div></article>`;
    }).join("");
}

document.querySelector("[data-saved-section]").addEventListener("click", event => {
    const filter = event.target.closest("[data-saved-filter]");
    if (filter) {
        savedFilter = filter.dataset.savedFilter;
        document.querySelectorAll("[data-saved-filter]").forEach(button => { const active = button === filter; button.classList.toggle("is-active", active); button.setAttribute("aria-pressed", String(active)); });
        renderSavedDecks(); return;
    }
    if (event.target.closest("[data-clear-history]")) { clearHistory(); renderSavedDecks(); updateFavoriteButton(); return; }
    const item = event.target.closest("[data-saved-id]"); if (!item) return;
    const id = item.dataset.savedId;
    if (event.target.closest("[data-view-saved]")) {
        const entry = readDecks().find(deck => deck.id === id), slots = entry && restoreSlots(entry, cards);
        if (slots) { lockedIds = Array(8).fill(null); currentEntryId = id; renderResult(slots, {save: false}); }
    } else if (event.target.closest("[data-favorite-saved]")) {
        toggleFavorite(id); updateFavoriteButton(); renderSavedDecks();
    } else if (event.target.closest("[data-remove-saved]")) {
        removeDeck(id); if (currentEntryId === id) currentEntryId = null; updateFavoriteButton(); renderSavedDecks();
    }
});

form.addEventListener("submit", event => {
    event.preventDefault(); const error = document.querySelector("[data-error]");
    lockedIds = Array(8).fill(null);
    try { renderResult(generateDeck(cards, constraintsFromForm())); error.hidden = true; }
    catch (caught) { error.textContent = caught instanceof ConstraintError ? caught.friendlyMessage : "The deck could not be generated."; error.hidden = false; document.querySelector("[data-result]").hidden = true; }
});

document.querySelector("[data-deck]").addEventListener("click", event => {
    const button = event.target.closest("[data-lock-slot]");
    if (!button || !currentSlots) return;
    const index = Number(button.dataset.lockSlot);
    lockedIds[index] = lockedIds[index] == null ? currentSlots[index].card.id : null;
    renderResult(currentSlots, {save: false, scroll: false});
});

document.querySelector("[data-generate-again]").addEventListener("click", () => {
    const error = document.querySelector("[data-error]");
    try { renderResult(generateDeck(cards, constraintsFromForm())); error.hidden = true; }
    catch (caught) { error.textContent = caught instanceof ConstraintError ? caught.friendlyMessage : "The deck could not be generated."; error.hidden = false; }
});

document.querySelector("[data-favorite-current]").addEventListener("click", () => {
    if (!currentEntryId) return;
    toggleFavorite(currentEntryId); updateFavoriteButton(); renderSavedDecks();
});

cardPool.addEventListener("click", event => {
    const contextButton = event.target.closest("[data-picker-context]"); if (contextButton) return setContext(contextButton.dataset.pickerContext);
    const remove = event.target.closest("[data-remove-card]");
    if (remove) { const input = cardPool.querySelector(`input[name="${remove.dataset.removeCard}_ids"][value="${remove.dataset.cardId}"]`); input.checked = false; input.dispatchEvent(new Event("change", {bubbles: true})); return; }
    const card = event.target.closest("[data-picker-card]"); if (card && !event.target.closest("input, label, button")) { const input = card.querySelector(`input[name="${activeContext}_ids"]`); input.checked = !input.checked; input.dispatchEvent(new Event("change", {bubbles: true})); }
});
cardPool.addEventListener("change", event => {
    if (event.target.name === "available_mode") { cardPool.dataset.availableMode = event.target.value; updateAvailableLabel(); return; }
    if (event.target.matches('input[type="checkbox"]')) { updateChips(event.target.name.replace("_ids", "")); setContext(activeContext); }
});
cardPool.querySelector("[data-card-search]").addEventListener("input", event => { const query = event.target.value.trim().toLocaleLowerCase(); cardPool.querySelectorAll("[data-picker-card]").forEach(card => { card.hidden = !card.dataset.cardName.includes(query); }); });
cardPool.querySelector("[data-select-all-available]").addEventListener("click", () => { cardPool.querySelectorAll('input[name="available_ids"]').forEach(input => { input.checked = true; }); updateChips("available"); setContext("available"); });
cardPool.querySelector("[data-clear-available]").addEventListener("click", () => { cardPool.querySelectorAll('input[name="available_ids"]').forEach(input => { input.checked = false; }); updateChips("available"); setContext("available"); });
document.querySelectorAll("[data-count-select]").forEach(select => { for (let value = 0; value <= 8; value++) select.add(new Option(value, value)); });
document.querySelector("[data-card-filters]").addEventListener("input", updateFilterCount);

try {
    const response = await fetch("./cards.json"); if (!response.ok) throw new Error(`HTTP ${response.status}`);
    cards = (await response.json()).items; renderPicker(); contexts.forEach(updateChips); renderSavedDecks(); updateFilterCount();
} catch (error) {
    const message = document.querySelector("[data-error]"); message.textContent = "Card data could not be loaded. Please refresh the page."; message.hidden = false; form.querySelector('button[type="submit"]').disabled = true;
}

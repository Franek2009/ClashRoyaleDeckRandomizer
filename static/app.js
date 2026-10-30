import {ActiveForm, ConstraintError, SlotRole, averageElixir, cardType, generateDeck, generateDeckLink, hasEvolution, hasHero} from "./randomizer.js";

document.documentElement.classList.add("js");
const form = document.querySelector("[data-generator-form]");
const cardPool = document.querySelector("[data-card-pool]");
const picker = document.querySelector("[data-card-picker]");
const contexts = ["available", "banned", "required"];
const descriptions = {available: "Cards the randomizer may use.", banned: "Cards that must not appear.", required: "Cards that must appear."};
let activeContext = "available";
let cards = [];

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
function constraintsFromForm() {
    const data = new FormData(form);
    return {availableIds: data.get("available_mode") === "all" ? null : checkedIds("available"), bannedIds: checkedIds("banned"), requiredIds: checkedIds("required"), evolutionSlotEnabled: data.get("evolution_slot_enabled") === "on", heroSlotEnabled: data.get("hero_slot_enabled") === "on", wildSlotMode: data.get("wild_slot_mode"), spellCount: optionalNumber(data, "spell_count"), buildingCount: optionalNumber(data, "building_count"), minAverageElixir: optionalNumber(data, "min_average_elixir"), maxAverageElixir: optionalNumber(data, "max_average_elixir")};
}

const summaryItem = (label, value) => `<div><dt>${label}</dt><dd>${value}</dd></div>`;
function renderResult(slots) {
    const roleLabels = {[SlotRole.EVOLUTION]: "Evolution", [SlotRole.HERO]: "Hero", [SlotRole.WILD]: "Wild"};
    document.querySelector("[data-slot-summary]").innerHTML = slots.slice(0, 3).map(slot => summaryItem(roleLabels[slot.role], slot.activeForm === ActiveForm.NORMAL ? "Off" : slot.activeForm.replace("_", " ").replace(/^./, c => c.toUpperCase()))).join("");
    const plainCards = slots.map(slot => slot.card), average = averageElixir(plainCards);
    document.querySelector("[data-deck-summary]").innerHTML = [["Evolutions", slots.filter(slot => slot.activeForm === ActiveForm.EVOLUTION).length], ["Heroes / Champions", slots.filter(slot => [ActiveForm.HERO, ActiveForm.CHAMPION].includes(slot.activeForm)).length], ["Spells", plainCards.filter(card => cardType(card) === "spell").length], ["Buildings", plainCards.filter(card => cardType(card) === "building").length], ["Average Elixir", average == null ? "—" : Number(average.toFixed(3))]].map(([label, value]) => summaryItem(label, value)).join("");
    document.querySelector("[data-deck]").innerHTML = slots.map(slot => {
        const image = slot.activeForm === ActiveForm.EVOLUTION ? slot.card.iconUrls.evolutionMedium : slot.activeForm === ActiveForm.HERO ? slot.card.iconUrls.heroMedium : slot.card.iconUrls.medium;
        return `<article class="card" data-card-id="${slot.card.id}" data-slot-role="${slot.role}" data-active-form="${slot.activeForm}">${slot.role === SlotRole.NORMAL ? "" : `<span class="slot-badge">${roleLabels[slot.role]} Slot</span>`}<div class="card-image"><img src="${escapeHtml(image)}" alt="${escapeHtml(slot.card.name)}"></div><div class="card-info"><h3>${escapeHtml(slot.card.name)}</h3>${slot.activeForm === ActiveForm.NORMAL ? "" : `<span class="active-form form-badge">${slot.activeForm.replace(/^./, c => c.toUpperCase())}</span>`}<div class="card-details"><span class="rarity">${escapeHtml(slot.card.rarity)}</span><span class="elixir"><span class="elixir-icon"></span>${slot.card.elixirCost ?? "—"}</span></div></div></article>`;
    }).join("");
    document.querySelector("[data-deck-link]").href = generateDeckLink(slots);
    const wild = slots[2], notice = document.querySelector("[data-wild-notice]"), dual = hasEvolution(wild.card) && hasHero(wild.card);
    notice.hidden = !dual; if (dual) notice.textContent = `After importing the deck, set the Wild Slot to ${wild.activeForm === ActiveForm.EVOLUTION ? "Evolution" : "Hero"}.`;
    const result = document.querySelector("[data-result]"); result.hidden = false; result.scrollIntoView({behavior: "smooth", block: "start"});
}

form.addEventListener("submit", event => {
    event.preventDefault(); const error = document.querySelector("[data-error]");
    try { renderResult(generateDeck(cards, constraintsFromForm())); error.hidden = true; }
    catch (caught) { error.textContent = caught instanceof ConstraintError ? caught.friendlyMessage : "The deck could not be generated."; error.hidden = false; document.querySelector("[data-result]").hidden = true; }
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

try {
    const response = await fetch("./cards.json"); if (!response.ok) throw new Error(`HTTP ${response.status}`);
    cards = (await response.json()).items; renderPicker(); contexts.forEach(updateChips);
} catch (error) {
    const message = document.querySelector("[data-error]"); message.textContent = "Card data could not be loaded. Please refresh the page."; message.hidden = false; form.querySelector('button[type="submit"]').disabled = true;
}

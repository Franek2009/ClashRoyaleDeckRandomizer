document.documentElement.classList.add("js");

document.addEventListener("DOMContentLoaded", () => {
    const cardPool = document.querySelector(".card-pool");
    if (!cardPool) return;

    const contexts = ["available", "banned", "required"];
    const contextButtons = cardPool.querySelectorAll("[data-picker-context]");
    const cards = cardPool.querySelectorAll("[data-picker-card]");
    const search = cardPool.querySelector("[data-card-search]");
    const availableModes = cardPool.querySelectorAll(
        'input[name="available_mode"]'
    );
    const contextHelp = cardPool.querySelector("[data-picker-context-help]");
    const contextDescriptions = {
        available: "Cards the randomizer may use.",
        banned: "Cards that must not appear.",
        required: "Cards that must appear.",
    };
    let activeContext = "available";

    function checkboxFor(card, context) {
        return card.querySelector(`input[name="${context}_ids"]`);
    }

    function updateChips(context) {
        const checked = cardPool.querySelectorAll(
            `input[name="${context}_ids"]:checked`
        );
        cardPool.querySelectorAll(`[data-selected-count="${context}"]`)
            .forEach((count) => { count.textContent = checked.length; });

        const container = cardPool.querySelector(
            `[data-selected-chips="${context}"]`
        );
        container.replaceChildren();
        checked.forEach((input) => {
            const card = input.closest("[data-picker-card]");
            const name = card.querySelector("h3").textContent;
            const chip = document.createElement("span");
            chip.className = "card-chip";
            chip.dataset.cardId = input.value;
            chip.append(document.createTextNode(name));

            const remove = document.createElement("button");
            remove.type = "button";
            remove.dataset.removeCard = context;
            remove.dataset.cardId = input.value;
            remove.setAttribute("aria-label", `Remove ${name} from ${context}`);
            remove.textContent = "×";
            chip.append(remove);
            container.append(chip);
        });
        if (context === "available") updateAvailableLabel();
    }

    function updateAvailableLabel() {
        const label = cardPool.querySelector("[data-available-label]");
        const mode = cardPool.dataset.availableMode;
        const count = cardPool.querySelectorAll(
            'input[name="available_ids"]:checked'
        ).length;
        label.textContent = mode === "all" ? "All" : count;
    }

    function setContext(context) {
        activeContext = context;
        cardPool.dataset.context = context;
        contextButtons.forEach((button) => {
            const active = button.dataset.pickerContext === context;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", String(active));
        });
        cardPool.querySelectorAll("[data-selected-pool]").forEach((group) => {
            group.classList.toggle("is-active", group.dataset.selectedPool === context);
        });
        cardPool.querySelectorAll("[data-pool-control]").forEach((control) => {
            control.classList.toggle("is-active", control.dataset.poolControl === context);
        });
        cards.forEach((card) => {
            card.classList.toggle("is-selected", checkboxFor(card, context).checked);
        });
        contextHelp.textContent = contextDescriptions[context];
    }

    function updateAvailableMode() {
        const selected = cardPool.querySelector(
            'input[name="available_mode"]:checked'
        );
        cardPool.dataset.availableMode = selected ? selected.value : "all";
        updateAvailableLabel();
    }

    contextButtons.forEach((button) => {
        button.addEventListener("click", () => setContext(button.dataset.pickerContext));
    });

    availableModes.forEach((input) => {
        input.addEventListener("change", updateAvailableMode);
    });

    cards.forEach((card) => {
        card.addEventListener("click", (event) => {
            if (event.target.closest("input, label, button")) return;
            const checkbox = checkboxFor(card, activeContext);
            checkbox.checked = !checkbox.checked;
            checkbox.dispatchEvent(new Event("change", { bubbles: true }));
        });
        card.querySelectorAll('input[type="checkbox"]').forEach((input) => {
            input.addEventListener("change", () => {
                updateChips(input.name.replace("_ids", ""));
                card.classList.toggle(
                    "is-selected", checkboxFor(card, activeContext).checked
                );
            });
        });
    });

    cardPool.addEventListener("click", (event) => {
        const remove = event.target.closest("[data-remove-card]");
        if (!remove) return;
        const input = cardPool.querySelector(
            `input[name="${remove.dataset.removeCard}_ids"][value="${remove.dataset.cardId}"]`
        );
        if (input) {
            input.checked = false;
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }
    });

    search.addEventListener("input", () => {
        const query = search.value.trim().toLocaleLowerCase();
        cards.forEach((card) => {
            card.hidden = !card.dataset.cardName.includes(query);
        });
    });

    cardPool.querySelector("[data-select-all-available]")
        .addEventListener("click", () => {
            cardPool.querySelectorAll('input[name="available_ids"]')
                .forEach((input) => { input.checked = true; });
            updateChips("available");
            setContext("available");
        });

    cardPool.querySelector("[data-clear-available]")
        .addEventListener("click", () => {
            cardPool.querySelectorAll('input[name="available_ids"]')
                .forEach((input) => { input.checked = false; });
            updateChips("available");
            setContext("available");
        });

    contexts.forEach(updateChips);
    updateAvailableMode();
    setContext(activeContext);
});

"""Regression tests for the Heal Spirit exception and the approved R2 snapshot."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from randomizer import (CardType, ConstraintError, DeckConstraints, WildSlotMode,
    arrange_deck, card_type, get_random_deck, has_evolution, has_hero, is_champion)
from scripts.update_cards import validate_snapshot

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cards():
    return json.loads((ROOT / "cards.json").read_text(encoding="utf-8"))["items"]


def test_heal_spirit_is_a_troop(cards):
    heal = next(card for card in cards if card["id"] == 28000016)
    assert card_type(heal) is CardType.TROOP


@pytest.mark.parametrize("last_card,feasible", [("Zap", True), ("Minions", False)])
def test_required_heal_spirit_needs_a_real_spell(cards, last_card, feasible):
    names = {"Heal Spirit", "Knight", "Archers", "Goblins", "Skeletons", "Ice Spirit", "Bats", last_card}
    available = frozenset(card["id"] for card in cards if card["name"] in names)
    assert len(available) == 8
    constraints = DeckConstraints(available_ids=available, required_ids=frozenset({28000016}),
        spell_count=1, building_count=0, evolution_slot_enabled=False,
        hero_slot_enabled=False, wild_slot_mode=WildSlotMode.OFF)
    if not feasible:
        with pytest.raises(ConstraintError) as error:
            get_random_deck(cards, constraints)
        assert error.value.code == "not_enough_spells"
        return
    deck = get_random_deck(cards, constraints)
    assert len({card["id"] for card in deck}) == 8
    assert 28000016 in {card["id"] for card in deck}
    assert [card["name"] for card in deck if card_type(card) is CardType.SPELL] == ["Zap"]


def test_javascript_and_python_agree_for_the_complete_catalog(cards):
    script = """
        import fs from 'node:fs';
        import {cardType} from './static/randomizer.js';
        const cards=JSON.parse(fs.readFileSync('cards.json')).items;
        console.log(JSON.stringify(Object.fromEntries(cards.map(card=>[card.id,cardType(card)]))));
    """
    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT,
        env={"PATH":os.defpath}, capture_output=True, text=True, check=True, timeout=10)
    actual = json.loads(result.stdout)
    assert actual["28000016"] == "troop"
    assert actual == {str(card["id"]):card_type(card).value for card in cards}


def test_snapshot_contains_the_approved_new_card_and_forms(cards):
    validate_snapshot(json.loads((ROOT / "cards.json").read_text(encoding="utf-8")))
    by_id = {card["id"]:card for card in cards}
    assert by_id[26000107]["name"] == "Minion Giant"
    assert card_type(by_id[26000107]) is CardType.TROOP
    for card_id, bit, artwork in [(26000023, 2, "heroMedium"), (26000042, 2, "heroMedium"),
                                 (26000043, 1, "evolutionMedium"), (26000085, 1, "evolutionMedium")]:
        assert by_id[card_id]["maxEvolutionLevel"] & bit
        assert by_id[card_id]["iconUrls"][artwork]


@pytest.mark.parametrize("card_id,physical_slot,active_form", [
    (26000023, 1, "hero"), (26000042, 1, "hero"),
    (26000043, 0, "evolution"), (26000085, 0, "evolution"),
])
def test_new_forms_generate_in_physical_and_wild_slots(cards, card_id, physical_slot, active_form):
    ordinary = [card for card in cards if not has_evolution(card) and not has_hero(card) and not is_champion(card)][:7]
    available = frozenset([card_id, *(card["id"] for card in ordinary)])
    assert len(available) == 8
    for index in (physical_slot, 2):
        wild = (WildSlotMode.HERO_CHAMPION if active_form == "hero" else WildSlotMode.EVOLUTION) if index == 2 else WildSlotMode.OFF
        constraints = DeckConstraints(available_ids=available, required_ids=frozenset({card_id}),
            evolution_slot_enabled=index == 0, hero_slot_enabled=index == 1, wild_slot_mode=wild)
        for _ in range(2):
            arranged = arrange_deck(get_random_deck(cards, constraints), constraints)
            assert len({slot.card["id"] for slot in arranged}) == 8
            assert arranged[index].card["id"] == card_id
            assert arranged[index].active_form.value == active_form

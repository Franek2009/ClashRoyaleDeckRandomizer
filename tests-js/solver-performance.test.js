import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import {benchmarkCases, benchmarkConstraints, measureSolver} from "../scripts/benchmark_solver.mjs";

const source = fs.readFileSync(new URL("../static/randomizer.js", import.meta.url), "utf8");
const cards = JSON.parse(fs.readFileSync(new URL("../cards.json", import.meta.url))).items;

test("full-catalog regressions fit the 250ms browser responsiveness budget", async () => {
    // The worker deadline only prevents a regression from hanging the test runner.
    // The substantially smaller assertion is the actual performance requirement.
    for (const scenario of benchmarkCases) for (const seed of [123,124,125]) {
        const result = await measureSolver({source,cards,constraints:benchmarkConstraints(scenario,cards),seed,timeoutMs:1500});
        assert.notEqual(result.status,"timeout",`${scenario.name}: worker exceeded 1500ms`);
        assert.ok(result.elapsedMs < 250,`${scenario.name}: ${result.elapsedMs.toFixed(1)}ms exceeds 250ms`);
        const impossible = ["spells-2-low","spells-2-high","typed-no-integer-total"].includes(scenario.name);
        assert.equal(result.status,impossible ? "error" : "success",scenario.name);
        if (impossible) assert.equal(result.code,"constraints_not_feasible");
        if (scenario.name.startsWith("spells-2-")) {
            assert.equal(result.slotStates + result.fillerStates,0);
            assert.equal(result.boundChecks,1);
        }
        if (result.ids) assert.equal(new Set(result.ids).size,8);
    }
});

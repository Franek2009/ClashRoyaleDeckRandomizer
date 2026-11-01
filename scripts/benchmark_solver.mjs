// Bounded, seeded measurements. Instrument a private module copy, never production.
import fs from "node:fs";
import {performance} from "node:perf_hooks";
import {Worker, isMainThread, parentPort, workerData} from "node:worker_threads";
import {fileURLToPath, pathToFileURL} from "node:url";

export const benchmarkCases = [
    {name:"spells-2-low", constraints:{spellCount:2, minAverageElixir:0.1, maxAverageElixir:0.2}},
    {name:"spells-2-high", constraints:{spellCount:2, minAverageElixir:9.9, maxAverageElixir:10}},
    {name:"typed-exact-3.125", constraints:{spellCount:2, buildingCount:1, minAverageElixir:3.125, maxAverageElixir:3.125}},
    {name:"untyped-exact-3.125", constraints:{minAverageElixir:3.125, maxAverageElixir:3.125}},
    {name:"typed-no-integer-total", constraints:{spellCount:2, buildingCount:1, minAverageElixir:3.1, maxAverageElixir:3.1}},
    {name:"typed-edge-low", constraints:{spellCount:2, minAverageElixir:1.75, maxAverageElixir:1.75}},
    {name:"typed-edge-high", constraints:{spellCount:2, minAverageElixir:6.75, maxAverageElixir:6.75}},
    {name:"mirror-exact", constraints:{requiredIds:new Set([28000006]), spellCount:2, buildingCount:1, minAverageElixir:3.125, maxAverageElixir:3.125}},
    {name:"seven-locks", constraints:{lockedIds:[26000007,26000011,26000001,27000006,28000015,26000102,28000002,null], spellCount:2, buildingCount:1, minAverageElixir:3.125, maxAverageElixir:3.125}},
    {name:"eight-card-pool", constraints:{availableIds:new Set([26000007,26000011,26000001,27000006,28000015,26000102,28000002,26000064]), spellCount:2, buildingCount:1, minAverageElixir:3.125, maxAverageElixir:3.125}},
    {name:"eight-spells", constraints:{evolutionSlotEnabled:false, heroSlotEnabled:false, wildSlotMode:"off", spellCount:8}},
    {name:"eight-buildings", constraints:{evolutionSlotEnabled:false, heroSlotEnabled:false, wildSlotMode:"off", buildingCount:8}},
];

export function benchmarkConstraints(scenario, cards) {
    const constraints = {...scenario.constraints};
    if (["seven-locks","eight-card-pool"].includes(scenario.name)) {
        // Keep these exact-average witnesses valid after ordinary cost updates.
        const witness = [26000007,26000011,26000001,27000006,28000015,26000102,28000002,26000064];
        const byId = new Map(cards.map(card => [card.id,card]));
        const average = witness.reduce((total,id) => total + (id === 28000006 ? 1 : byId.get(id).elixirCost),0)/8;
        constraints.minAverageElixir = constraints.maxAverageElixir = average;
    }
    return constraints;
}

function instrument(source) {
    const replacements = [
        [/function search\([^)]*\) \{/g, 1],
        [/const chooseSlots = \([^)]*\) => \{/g, 0],
        [/function completeDeck\([^)]*\) \{/g, 2],
    ];
    for (const [pattern, counter] of replacements) {
        if (!pattern.test(source)) throw new Error("Unrecognized solver instrumentation point");
        pattern.lastIndex = 0;
        source = source.replace(pattern, match => `${match}\nAtomics.add(globalThis.__solverCounters, ${counter}, 1);`);
    }
    source = source.replace(/function canComplete\([^)]*\) \{/g,
        match => `${match}\nAtomics.add(globalThis.__solverCounters, 3, 1);`);
    return source;
}

export async function measureSolver({source, cards, constraints, seed = 123, timeoutMs = 2000}) {
    const shared = new SharedArrayBuffer(4 * Int32Array.BYTES_PER_ELEMENT);
    const counters = new Int32Array(shared);
    const worker = new Worker(new URL(import.meta.url), {workerData:{source, cards, constraints, seed, shared}});
    let started, timer;
    return new Promise((resolve, reject) => {
        const finish = async result => {
            clearTimeout(timer);
            await worker.terminate();
            resolve({...result, slotStates:counters[0], fillerStates:counters[1], completeDeckCalls:counters[2], boundChecks:counters[3]});
        };
        timer = setTimeout(() => { worker.terminate(); reject(new Error("Benchmark worker startup timed out")); }, 5000);
        worker.on("message", message => {
            if (message.started) {
                clearTimeout(timer); started = performance.now();
                timer = setTimeout(() => finish({status:"timeout", elapsedMs:performance.now() - started}), timeoutMs);
            } else finish(message);
        });
        worker.on("error", error => { clearTimeout(timer); reject(error); });
    });
}

if (!isMainThread) {
    globalThis.__solverCounters = new Int32Array(workerData.shared);
    let seed = workerData.seed;
    Math.random = () => ((seed = (1664525 * seed + 1013904223) >>> 0) / 2 ** 32);
    const source = instrument(workerData.source);
    const {generateDeck} = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
    parentPort.postMessage({started:true});
    const start = performance.now();
    try {
        const slots = generateDeck(workerData.cards, workerData.constraints);
        parentPort.postMessage({status:"success", elapsedMs:performance.now() - start, ids:slots.map(slot => slot.card.id)});
    } catch (error) {
        parentPort.postMessage({status:"error", code:error.code || error.name, elapsedMs:performance.now() - start});
    }
} else if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
    const args = process.argv.slice(2);
    const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
    const sourcePath = option("--source", fileURLToPath(new URL("../static/randomizer.js", import.meta.url)));
    const source = fs.readFileSync(sourcePath, "utf8");
    const cards = JSON.parse(fs.readFileSync(new URL("../cards.json", import.meta.url))).items;
    const runs = Number(option("--runs", 3)), timeoutMs = Number(option("--timeout-ms", 2000));
    if (!Number.isInteger(runs) || runs < 1 || runs > 10 || !Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 5000)
        throw new Error("Use 1–10 runs and a 1–5000ms benchmark deadline");
    for (const scenario of benchmarkCases) for (let run = 0; run < runs; run++) {
        const seed = 123 + run;
        const result = await measureSolver({source, cards, constraints:benchmarkConstraints(scenario,cards), seed, timeoutMs});
        console.log(JSON.stringify({case:scenario.name, seed, cards:cards.length, ...result}));
    }
}

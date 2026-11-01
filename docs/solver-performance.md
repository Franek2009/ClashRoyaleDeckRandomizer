# R3: complete solver pruning

The static generator remains a complete randomized depth-first search. No retry
limit, deadline or sampling-based rejection was added to the production solver.

## Cause and change

`completeDeck` previously checked average Elixir only at a complete typed fill.
It repeatedly explored combinations that could not meet the requested total.
`chooseFillers` had bounds/memoization, but sorted every suffix at every node.
`resolveDeck` retried those searches for physical slot triples and type targets.

The new checks use the existing integral total bounds for eight-card averages:

- Reject an average interval containing no integer total during validation.
- Before and during special-slot selection, count Required/Locked and selected
  IDs once. Reject when the remaining types/counts cannot be supplied or when
  even the cheapest/most expensive remaining cards cannot meet the total.
- For filler search, precompute suffix tables of minimum/maximum cost for exactly
  k cards, separately by type when exact type counts apply. Mirror contributes 1.
- Memoize failed typed states by suffix index, remaining type counts and total.
- Never put a card locked elsewhere into a special slot. Such branches could
  not previously complete, because the same ID must occupy its locked position.

The prefix bounds deliberately allow some impossible completions (e.g. too many
Champions). They are optimistic: this weakens pruning but cannot remove a valid
solution. Actual role restrictions are still applied when selecting the slots.

## Why pruning preserves completeness

For a fixed prefix, every valid completion must include its distinct required
and locked IDs and draw the missing cards from the remaining eligible pool.
Its cost cannot be below that pool's cheapest admissible sum or above its most
expensive sum. Types partition the pool, so their exact-count bounds add.

Suffix tables compute the exact extrema by considering both taking and skipping
each candidate. Insufficient supply has minimum Infinity. Only states outside the
requested interval, or with insufficient type supply, are rejected. Failed-state
memoization is local to the fixed slot assignment/candidate order: future choices
depend only on the suffix, remaining counts and accumulated total. It does not
reuse failures across different eligible pools or slot assignments.

Include/skip order and Fisher–Yates shuffling are retained. Skipping dead branches
can change subsequent RNG consumption, so a seed is not promised to reproduce
every historical deck. The previous solver also did not promise a uniform
distribution over valid decks. Catalog costs remain validated integer values;
the existing average rounding policy and Mirror policy are unchanged.

## Repeatable measurements

```bash
node scripts/benchmark_solver.mjs --runs 3
git show 30a3c84:static/randomizer.js > /tmp/crdr-solver-before.mjs
node scripts/benchmark_solver.mjs --source /tmp/crdr-solver-before.mjs --runs 1 --timeout-ms 2000
```

The script uses the current local catalog (123 cards for this comparison), seeds
123–125, isolated workers and a private instrumented copy of the selected module.
JSON lines report wall time inside the solver, result, slot states, filler states,
completeDeck calls and prefix bound checks. Module loading/worker startup is not
included in elapsed time. Instrumentation adds overhead to every visited state.

The worker deadline prevents an old/regressed solver from hanging measurement;
timeouts are reported as timeouts, never as evidence of infeasibility. It is not
a limit used by the application.

Representative local Node measurements, seed 123 (milliseconds; cold workers):

| Case | Before | After | Filler states before → after |
| --- | ---: | ---: | ---: |
| Spells 2, average 0.1–0.2 | timeout ~2000 | 5.95 | 8,514,604 → 0 |
| Spells 2, average 9.9–10 | timeout ~2000 | 2.48 | 8,555,931 → 0 |
| Spells 2, Buildings 1, average exactly 3.1 | timeout ~2000 | 2.91 | 8,651,889 → 0 |
| Spells 2, average exactly 1.75 (feasible) | timeout ~2000 | 7.08 | 8,930,348 → 122 |
| Spells 2, average exactly 6.75 (feasible) | timeout ~2000 | 8.41 | 7,864,155 → 194 |
| Spells 2, Buildings 1, average exactly 3.125 | 4.23 | 5.55 | 2,298 → 20 |
| Untyped, average exactly 3.125 | 4.06 | 7.47 | 132 → 132 |

Counts for timed-out runs are partial, not complete search sizes. Easy cases can
be slightly slower because they now build bounds; the gain is avoiding enormous
infeasible subtrees. Other cases cover eight Spells, eight Buildings, required
Mirror, seven locks and an exact eight-card pool. Three-seed post-change runs of
all 12 benchmark cases remained below 10ms locally; timings vary by hardware.

## Regression budget and limitations

The target is under 100ms on a desktop, with a **250ms hard regression budget** per
solve to keep synchronous browser interaction responsive. The Node performance
test checks all benchmark cases at three seeds against 250ms. Its separate
1500ms worker kill deadline is only test containment, not an accepted solve time.
Playwright checks the same 250ms threshold in desktop/mobile Chromium, including
both original impossible ranges and a feasible exact average, and attaches the
timings. Mobile emulation is not a measurement on a physical low-end phone.

Completeness tests independently enumerate all eight-card subsets and physical
slot triples of an eleven-card fixture. They cover all 12 slot settings, Required,
Banned, Available, locks, Champions, dual forms, Mirror, exact type counts, narrow
averages, and even-cost gaps with nearby feasible totals. Seeded mixed constraints
also compare existence and validate every returned deck against that oracle.

The solver is still synchronous and worst-case search can grow with adversarial
or substantially larger catalogs. The budget is a measured regression criterion,
not a mathematical runtime guarantee for every possible catalog. No valid deck
is rejected merely to satisfy a time budget. Python's retained solver is unchanged.

# Your Overall score averages two different scoring rules

**Alveera Munshi · October 2026**
Repo: `benchmarks-bio-audit` · reproduces 494/494 board scores and 38/38 Overall scores

---

## What I did

I pulled the public result files behind benchmarks.bio — `/data/v1/<board>.json`,
`/data/oncologybench/index.json` and `/results/v1/latest.json` — and rebuilt the
leaderboard from the per-evaluation counts. 13 capability boards, 1,228 evaluations,
38 model×harness rows, 147,182 graded runs, $231,697 of inference.

The first thing I did was check I could reproduce what the site shows. I can: all 494
board scores to within 0.005 points, and all 38 Overall scores to within 0.004. Getting
there is how I found the problem, because a large block of cells would not reproduce
under the rule the site documents.

## The finding

Eleven of the thirteen boards score a refused attempt as a **failure**. Two —
BioSecBench-Function and BioSecBench-Surveillance — **drop it from the denominator**.
I established this by fitting both rules to every published cell: the biosecurity boards
match *exclude* on 38 of 38 rows and *fail* on 9–10; every other board matches *fail*
exactly.

Overall is an evaluation-count-weighted mean of those thirteen boards. So a refusal costs
a model nothing on two boards and a full item on eleven, and the two currencies are then
averaged into the headline number.

Eleven of the thirteen boards also carry identical text saying *"Refusals are excluded
from the denominator."* That is true of two of them. MetagenomicsBench and OncologyBench
are the exceptions and both describe the failure rule accurately. Two boards getting it
right is why I read this as deliberate scoring with stale prose on the other **nine**,
rather than as a scoring mistake.

## Why it matters

It decides the top of the board.

| | as published | all *exclude* | all *fail* | min. coverage |
|---|---|---|---|---|
| **Opus 5.5** (Claude Code) | 42.1 → rank **22** | 58.8 → rank **1** | 33.9 | **2.7%** |
| **Opus 5.5\*** LSVP (Pi) | 58.1 → rank **1** | 58.5 → rank 2 | 58.1 | 95.8% |

Opus 5.5 moves 21 places depending on a rule nobody chose on purpose.

The LSVP pair is the control that makes this unambiguous. LSVP is the same model with the
safety filter off, so it attempts nearly the whole suite — and it scores ~58 under *every*
rule. The standard run of that same model swings 25 points, entirely on what it declined
to answer.

## What I checked and was wrong about

I assumed exclusion would inflate scores by dropping the hardest items. It does not.
Scoring each refused item against the 38-model consensus difficulty, across 65
model×board cells: mean gap **−0.58 points**, 95% bootstrap CI **[−1.93, +0.73]**,
Wilcoxon p = 0.61.

I'd stress the interval rather than the p-value. This isn't "we failed to detect an
effect" — the data **bounds** any difficulty-selection effect at under about a point.
The point estimates are close to right, so the fix belongs somewhere other than the
numbers themselves.

## A second thing, which is not the same problem

A cluster bootstrap over items turns each integer rank into the interval it supports.
Across all 494 board rows the **median 95% rank interval is 13 places**, on boards with
~38 rows.

What surprised me is that this is **not** mostly about refusals — the correlation between
coverage and interval width is 0.003. It is about **board size**. The three long-horizon
boards carry 21–25 items and have median intervals of 20–23 places; MetagenomicsBench
carries 100 items and has a median of 7. Low coverage compounds it only at the extreme,
which is where the worst single case sits: Opus 5.5 is ranked #1 on BioSecBench-Function
at 73.6% **from 12 of 111 items**, published CI `[47.5, 99.7]`.

The Overall board is the opposite — median interval **4 places**, because it pools 1,228
items. So the two defects are different and worth keeping apart: Overall's problem is its
*currency*; the per-board numbers' problem is their *precision*.

## What I propose

Implemented in `src/policy.py`, with the contract in `tests/`.

Not "pick one rule" — biosecurity has a real reason to exclude refusals, since refusing is
the desired behaviour there and you already score it separately on BioSecBench-Refusal.
Four changes:

1. **Each board declares its refusal rule in the data**, beside its score, instead of
   leaving it implicit in prose.
2. **The published number is tested against the declared rule**, so drift between the
   docs and the pipeline fails CI rather than shipping.
3. **Overall takes the rule as an argument** and refuses to average mixed currencies.
4. **A score ships with the rank interval it supports**, and the integer rank is withheld
   when the interval is too wide to mean anything.

On (4): I first proposed a coverage floor and then abandoned it, because the data says
coverage is not what drives width. Gating on the interval captures both causes — small
boards and heavy refusers — with coverage still reported, since on an `exclude` board the
model chooses its own denominator.

Two of the eight tests in `tests/test_scoring_contract.py` fail against today's data.
Those two failures are the finding; the other six show the harness is faithful, including
a guard that the Overall aggregation is evaluation-count weighted and not an unweighted
mean, so a silent change there would fail too.

## One more thing, while I was in there

Independent of the rule question, and relevant to where the next $230k goes:

- **171 items (14.2%) are never solved by any of the models**, costing $51,221.
  **121 have exactly zero passes across every model and every run** — that reads like
  broken graders rather than hard science. 8 of SpatialBench-Long's 21 items are dead,
  and 31 of EpiBench's 106.
- **37.7% of total spend ($87,433)** goes to items that cannot separate models.
- Keeping the **top 30% of items by discrimination** reproduces the full leaderboard at
  Spearman **0.986**, for **$61k instead of $229k**.
- The dead items **cluster by assay rather than by difficulty**: **12 of the 24
  ATAC-seq items are dead**, 8 of 18 exome-sequencing items, 10 of 31 wastewater items —
  and every therapeutics *stage* group has none at all. A failure that tracks the
  pipeline and not the science is a pipeline bug, which makes this a concrete place to
  start rather than a vague complaint.
- `mobilome_mge_class_abundance_illumina_wastewater_mgx` appears twice in
  BioSecBench-Surveillance under two ids. Both dead. $2,250.

If any of that is useful I'd happily take the dead-item list further — separating the
genuinely unsolved from the mis-graded is a concrete piece of work, and it would make the
next run both cheaper and sharper.

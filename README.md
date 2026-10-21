# benchmarks.bio — a scoring-rule audit

An independent, reproducible audit of the public result data behind
[benchmarks.bio](https://benchmarks.bio), LatchBio's agentic-biology benchmark suite.

Everything here comes from published endpoints (`/data/v1/<board>.json`,
`/data/oncologybench/index.json`, `/results/v1/latest.json`). Nothing is scraped from
the rendered page and no model was re-run — every number below is arithmetic on
LatchBio's own published counts.

**The data:** 13 capability boards · 1,228 evaluations · 46,414 model×evaluation cells ·
**147,182 graded runs** · 300B tokens · **$231,697** of inference.

**Fidelity:** this pipeline reproduces **494 of 494** published board scores (max error
0.005 pts) **and all 38 Overall scores** (max error 0.004 pts). That is the licence for
everything that follows.

---

## What this audits

benchmarks.bio is LatchBio's public measurement of how well AI agents handle real
biology data analysis. Each problem hands a model a snapshot of real experimental
data taken just before a decision point, and a deterministic grader checks whether it
recovered the right biological result. The tasks are built around traps — one of
their own examples: *"WT-style `n_genes >= 200` thresholds zero out a ~386-gene BD
Rhapsody panel; panel-aware floors retain ~14k PBMCs and correct monocyte counts."*
A standard quality filter silently deletes the dataset, and the model has to notice.

These are long agentic sessions, not questions: **31 turns and 2.1M tokens per
attempt at $1.74**, past $4 on the long-horizon boards.

Fourteen boards across four areas — Omics (7), Therapeutics (3), Biosecurity (3),
Applications (1). **Thirteen measure capability** and average into the headline
Overall score. The fourteenth, **BioSecBench-Refusal**, measures whether a model
blocks harmful requests while still answering benign ones, and is reported separately
as a safeguard. That distinction matters here: on dual-use biology refusing can be the
*right* behaviour, and LatchBio already grades it on its own board.

**Why audit it.** A benchmark's authority rests entirely on its numbers being computed
the way it says they are — for a measurement, the numbers *are* the product. So this
does the one test that matters: download the published numbers and try to reproduce
them from the published counts. Everything below follows from where that succeeded and
where it didn't.

---

## Finding 1 — Overall averages two different scoring rules

Eleven boards score a refused attempt as a **failure**. Two — BioSecBench-Function and
BioSecBench-Surveillance — **drop it from the denominator**. I recovered this by fitting
both rules to all 494 published cells: the biosecurity boards match *exclude* 38/38 and
*fail* 9–10/38; every other board matches *fail* exactly.

The Overall score is an evaluation-count-weighted mean of those thirteen boards. So the
same behaviour is free on two boards and fatal on eleven, and both are averaged into one
number.

**It is not documented.** Eleven of the thirteen boards carry identical boilerplate
saying *"Refusals are excluded from the denominator"*, which is true of two of them.
**MetagenomicsBench and OncologyBench are the exceptions** and describe what they
actually do — Metagenomics: *"Refusals and timeouts both count as failures and stay in
the denominator"*; Oncology: *"Refusals and the four timed-out slots remain in the
denominator"*. Two boards getting it right is good evidence the rule is deliberate and
the prose on the other **9 of 13** is stale.

**It decides the top of the leaderboard.**

| | as published | all *exclude* | all *fail* | min. coverage |
|---|---|---|---|---|
| Opus 5.5 (Claude Code) | 42.1 — rank **22** | 58.8 — rank **1** | 33.9 | **2.7%** |
| Opus 5.5 (Pi) | 42.3 — rank 19 | 58.2 — rank 4 | 33.1 | 4.4% |
| Opus 5.5* LSVP (Pi) | 58.1 — rank **1** | 58.5 — rank 2 | 58.1 | 95.8% |
| Opus 5.5* LSVP (CC) | 58.1 — rank 2 | 58.2 — rank 3 | 58.1 | 98.3% |

Apply the documented rule uniformly and Opus 5.5 moves **22nd → 1st**, a 21-place swing,
on a minimum per-board coverage of 2.7%.

**The data contains its own control.** `*` LSVP is Anthropic's safety-filter-exempt
variant, which refuses far less. The starred rows score ~58 under **every** rule, because
they attempted ~100% of the suite. The unstarred rows swing 25 points across rules on
nothing but what they declined to answer. The spread is a property of the scoring.

### A hypothesis I tested, bounded, and discarded

The obvious worry is that excluding refusals quietly drops the hardest items and inflates
the score. Measuring each refused item against the 38-model consensus difficulty, across
65 model×board cells with enough data on both sides:

> mean gap **−0.58 pts**, 95% bootstrap CI **[−1.93, +0.73]**, Wilcoxon p = 0.61

So this is not merely "not significant" — the data **bounds** any difficulty-selection
effect at under about one point of item difficulty. The point estimates are close to
right, and a fix aimed at correcting them would be solving the wrong problem.

---

## Finding 2 — A per-board rank is an interval about 13 places wide

A cluster bootstrap over items turns each integer rank into the interval it supports.
Across all 494 board rows the **median 95% rank interval is 13 places** on boards holding
~38 rows.

The driver is **board size, not refusals** — the Spearman correlation between coverage
and interval width is **0.003**. The three long-horizon boards carry 21–25 items and have
median intervals of 20–23 places; MetagenomicsBench carries 100 items and has a median of
7. Refusal-driven coverage loss compounds it at the extreme (rows scored on under a
quarter of a board have a median interval of 28), which is why the worst single cases sit
on the `exclude` boards: Opus 5.5 is ranked **#1 on BioSecBench-Function at 73.6% from 12
of 111 items**, published CI `[47.5, 99.7]`.

**The Overall board, by contrast, is well identified** — median interval **4 places** —
because it pools 1,228 items across thirteen boards. So the two problems are different
and should not be conflated: *Overall's* defect is its currency, *the per-board numbers'*
defect is their precision.

Scoring everyone on the items everyone attempted is not an available repair: that
intersection is 7% of BioSecBench-Function and 2% of TxBench-Oligo.

---

## Finding 3 — 37.7% of the spend buys no ranking information

- **171 items (14.2%) are never solved by any model** — $51,221. **121 have exactly zero
  passes across every model and every run** ($38,686), which reads as broken graders
  rather than hard science. 8 of SpatialBench-Long's 21 items are dead, and 31 of
  EpiBench's 106.
- **$87,433 (37.7%)** goes to items that cannot separate models.
- Keeping only the **top 30% of items by discrimination** reproduces the full leaderboard
  at Spearman **0.986**, for **$61k instead of $229k**.
- **They cluster by assay, not by difficulty**, which is the part that makes them
  actionable: **12 of the 24 ATAC-seq items (50%) are dead**, as are 8 of 18 exome-
  sequencing items and 10 of 31 wastewater items — while every therapeutics *stage*
  group (target hypothesis, assay design, preclinical de-risking, potency) has **zero**.
  A failure that tracks the pipeline rather than the science is a pipeline bug. The
  24 ATAC-seq items are where I would start.
- `mobilome_mge_class_abundance_illumina_wastewater_mgx` appears twice in
  BioSecBench-Surveillance under two ids. Both dead. $2,250.

---

## The proposed fix

In `src/policy.py`, with the contract in `tests/test_scoring_contract.py`.

Not "pick one rule". Biosecurity has a real reason to exclude refusals — refusing is the
*desired* behaviour there and is already scored separately on BioSecBench-Refusal.
Four changes instead:

1. **Every board declares its refusal rule in the data**, next to its score, rather than
   leaving it implicit in a prose string nothing validates.
2. **The published number is checked against the declared rule**, so drift between the
   docs and the pipeline fails CI instead of shipping.
3. **Overall takes the rule as an argument** and will not silently average mixed
   currencies. One Overall per rule is honest; one Overall across two is not.
4. **A score ships with the rank interval it supports**, and the integer rank is withheld
   when that interval is too wide to mean anything. *(This replaces a coverage floor I
   proposed first and then abandoned — see above: coverage does not drive width.)*

```
$ pytest tests/ -q
....FF..
FAILED test_methodology_text_matches_the_implementation
    9/13 boards contradict their own methodology string
    (MetagenomicsBench and OncologyBench document theirs correctly)
FAILED test_overall_does_not_average_boards_with_different_rules
    Overall averages 2 different refusal rules: {'exclude': 2, 'fail': 11}
2 failed, 6 passed
```

The six that pass show the harness is faithful — including that the Overall weighting is
evaluation-count weighted and **not** an unweighted mean, which is guarded explicitly so
a silent change to the aggregation would fail too. The two that fail are the finding.

---

## Deliverables

| | |
|---|---|
| **Report page** | https://alveeramunshi.github.io/benchmarks-bio-audit/ (also at https://claude.ai/artifact/5fg5zn61V7yTgcVsFTSDcF) |
| **Deck** | https://canva.link/d2426xpr24aae1r |
| **Memo** | [`MEMO.md`](MEMO.md) |
| **Proposed change** | [`src/policy.py`](src/policy.py) + [`tests/`](tests/) |
| **Pipeline** | `src/fetch.py` → `src/report.py` → `out/` |

## Run it

```bash
pip install pandas numpy scipy pyarrow pytest
python3 src/fetch.py      # pull the published result files
python3 src/explain.py    # how the method works, worked through on real numbers
python3 src/report.py     # reproduce every number above -> out/
pytest tests/ -v          # the scoring contract: 6 pass, 2 fail
```

### How it works, in short

The site publishes the raw counts *and* the score, so you can work backwards to
the formula joining them. There are only two sensible things to do with a refused
attempt — drop it (`correct / (runs - refused)`) or fail it (`correct / runs`) —
so apply both to every published cell and see which lands on their number. Those
score one *evaluation*; a board score is the average of the per-evaluation scores,
which is why an evaluation refused on all three attempts drops out of a Rule-A
average entirely.

When a model refuses nothing the two formulas are arithmetically identical, so
that cell is silent rather than evidence. Across all 494 cells: **148 discriminate
and pick a rule, 346 are silent, and 0 match neither.** No cell points the other
way, which is why the claim is "all of them" rather than "most of them".
`src/explain.py` prints this walkthrough from live data.

## Layout

| file | what it does |
|---|---|
| `src/fetch.py` | download the published JSON |
| `src/load.py` | flatten 13 boards to one tidy frame; board labels and Overall weights |
| `src/oncology.py` | OncologyBench, which ships in its own schema |
| `src/scoring.py` | the three scoring rules, and the weighted Overall |
| `src/policy.py` | **the proposed fix**: declared rules, interval-gated ranking |
| `src/bias.py` | is exclusion dropping harder items? bounded, not just tested |
| `src/stability.py` | cluster bootstrap over items → rank intervals, per board and Overall |
| `src/items.py` | item difficulty, discrimination, subset fidelity, dead-item profile |
| `src/explain.py` | **a runnable walkthrough of the method** — start here |
| `src/report.py` | runs everything, writes `out/` and the page's `figures.json` |
| `src/make_artifact.py` | strips the standalone doctype/meta lines for the Artifact copy |
| `docs/` | the published report page (GitHub Pages serves this folder) |

*Audit by Alveera Munshi, October 2026. Data as published 2026-10-20.*

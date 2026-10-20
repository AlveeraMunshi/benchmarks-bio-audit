# benchmarks.bio — a scoring-rule audit

An independent, reproducible audit of the public result data behind
[benchmarks.bio](https://benchmarks.bio), LatchBio's agentic-biology benchmark suite.

Everything here comes from published endpoints (`/data/v1/<bench>.json`,
`/results/v1/latest.json`). Nothing is scraped from the rendered page, and no model
was re-run — every number below is arithmetic on LatchBio's own published counts.

**The data:** 12 capability boards · 1,203 evaluations · 38 model×harness rows ·
45,539 model×evaluation cells · **144,557 graded runs** · 299B tokens ·
**$226,970** of inference.

**Fidelity:** this pipeline reproduces **459 of 459** published board scores to within
**0.005 points**. That is the licence for everything that follows.

---

## The finding

**The Overall score is the mean of twelve boards that do not price a refusal the same
way.**

Ten boards score a refused attempt as a failure. Two — BioSecBench-Function and
BioSecBench-Surveillance — drop it from the denominator entirely. I recovered this by
fitting both rules to all 459 published cells: the biosecurity boards match *exclude*
38/38 and *fail* 9/38; every other board matches *fail* exactly.

So the same behaviour is free on two boards and fatal on ten, and the twelve are then
averaged into one headline number.

**It is not documented.** Eleven of the twelve boards carry identical boilerplate
saying *"Refusals are excluded from the denominator"*, which is true of two of them.
MetagenomicsBench is the exception and says what it actually does — *"Refusals and
timeouts both count as failures and stay in the denominator"* — which is good
evidence the rule is deliberate and the text on the other **9 boards is stale**.

**It decides the top of the leaderboard.** Apply the documented rule uniformly and
Claude Opus 5.5 moves from **16th to 1st**, on a minimum per-board coverage of
**2.7%**. Apply refusal-as-failure uniformly and the current top is unchanged. The
number published today is neither.

| | as published (mixed) | all `exclude` | all `fail` |
|---|---|---|---|
| Opus 5.5 (Claude Code) | 37.6 — rank 16 | **56.2 — rank 1** | 29.8 — rank 23 |
| Opus 5.5* LSVP (Pi) | 55.3 — rank 1 | 55.6 — rank 2 | 55.3 — rank 1 |

`*` LSVP is Anthropic's safety-filter-exempt variant, which refuses far less. The
starred and unstarred runs of the same model are the control: the starred one scores
~55 under **every** rule, because it attempted ~100% of the suite. The unstarred one
swings 26 points across rules purely on what it declined to answer.

### Why this bites hardest exactly where it is used

On the two boards that exclude refusals, the denominator is chosen by the model.
Opus 5.5 is ranked **#1 on BioSecBench-Function at 73.6%, scored on 12 of 111 items**,
published CI `[47.5, 99.7]`. A cluster bootstrap over items puts the model *shown at
rank 2* anywhere in **[1, 27]**. Ranks are rendered as integers for quantities that
are intervals tens of places wide.

The obvious repair — score everyone on the items everyone attempted — is not
available: only **7%** of BioSecBench-Function and **2%** of TxBench-Oligo were
attempted by all 38 rows.

### One hypothesis I tested and discarded

I expected exclusion to *inflate* scores by quietly dropping the hardest items.
Measuring each refused item's difficulty against the 38-model consensus, across 64
model×board cells with enough data: **no significant effect** (Wilcoxon p = 0.58;
mean gap −0.6 pts). Refusals track topic sensitivity, not difficulty. So the defect
is inconsistency and precision, not bias — and a correction that only adjusts the
point estimate would be solving the wrong problem.

---

## The proposed fix

In `src/policy.py`, with the contract in `tests/test_scoring_contract.py`.

Not "pick one rule". Biosecurity has a real reason to exclude refusals — refusing is
the *desired* behaviour there and is scored separately on BioSecBench-Refusal.
Four changes instead:

1. **Every board declares its refusal rule in the data**, next to its score, rather
   than leaving it implicit in a prose string.
2. **The published number is checked against the declared rule**, so drift between
   the docs and the pipeline fails CI instead of shipping.
3. **Overall never silently averages mixed rules.** `policy.overall(df, rule)` takes
   the currency as an argument; publishing one Overall per rule is honest, and
   averaging two is not.
4. **Every score carries the coverage it rests on**, and a row below a coverage floor
   is reported but **not ranked** — because under `exclude`, a rank computed on 12 of
   111 items is not a rank.

```
$ pytest tests/ -q
..FF..
FAILED test_methodology_text_matches_the_implementation
    9/12 boards contradict their own methodology string
FAILED test_overall_does_not_average_boards_with_different_rules
    Overall averages 2 different refusal rules: {'exclude': 2, 'fail': 10}
2 failed, 4 passed
```

The four that pass show the harness is faithful and the proposed Overall is
well-defined. The two that fail are the finding.

---

## Supporting: what the suite spends on items that move nothing

Independent of the rule question, and relevant to where the next $227k goes:

- **166 items (14%) are never solved by any of the 38 models** — $50,319. **120 of
  them have exactly zero passes across every model and every run**, which reads as
  broken graders rather than hard science. 8 of SpatialBench-Long's 21 items are dead.
- **$85,785 (37.8%) of spend** goes to items that cannot separate models.
- Keeping only the **top 30% of items by discrimination** reproduces the full
  leaderboard at Spearman **0.984**, 10/10 top-10 overlap, for **$59k instead of
  $224k**.
- One duplicated item found: `mobilome_mge_class_abundance_illumina_wastewater_mgx`
  appears twice in SurveillanceBench under two ids, both dead, $2,250.

---

## Run it

```bash
pip install pandas numpy scipy pyarrow pytest
python3 src/fetch.py      # pull the published result files
python3 src/report.py     # reproduce every number above -> out/
pytest tests/ -v          # the scoring contract: 4 pass, 2 fail
```

## Layout

| file | what it does |
|---|---|
| `src/fetch.py` | download the published JSON |
| `src/load.py` | flatten to one tidy frame (one row per model × evaluation) |
| `src/scoring.py` | the three scoring rules, and which board uses which |
| `src/policy.py` | **the proposed fix**: declared rules, coverage-gated ranking |
| `src/items.py` | item difficulty, discrimination, subset fidelity |
| `src/stability.py` | cluster bootstrap over items → rank intervals |
| `src/report.py` | runs everything, writes `out/` |
| `tests/` | the scoring contract |

## Deliverables

| | |
|---|---|
| **Report page** | https://claude.ai/artifact/5fg5zn61V7yTgcVsFTSDcF — the finding with the four charts |
| **Memo** | [`MEMO.md`](MEMO.md) — two pages, the register of an internal eng note |
| **Proposed change** | [`src/policy.py`](src/policy.py) + [`tests/`](tests/) — declared rules, coverage-gated ranking, and the contract that catches the drift |
| **Pipeline** | `src/fetch.py` -> `src/report.py` -> `out/` |

*Audit by Alveera Munshi, October 2026. Data as published 2026-10-20.*

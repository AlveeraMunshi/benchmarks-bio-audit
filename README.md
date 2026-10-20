# benchmarks.bio — reliability audit

An independent, fully reproducible audit of the public result data behind
[benchmarks.bio](https://benchmarks.bio), LatchBio's agentic-biology benchmark suite.

Everything here is derived from published endpoints (`/data/v1/<bench>.json`,
`/results/v1/latest.json`). Nothing is scraped from the rendered page.

**Scale of the data:** 12 capability benchmarks · 1,203 evaluations · 38 model×harness
rows · 45,539 model×evaluation cells · **144,557 graded runs** · 299B tokens ·
**$226,970** of published inference spend.

**Fidelity check:** the pipeline reproduces **459 of 459** published board scores to
within 0.005 points, so every claim below is arithmetic on LatchBio's own numbers.

## Findings

**1. The Overall score averages boards that do not use the same scoring rule.**
Every board's own `methodology` string says *"Refusals are excluded from the
denominator."* Only the two biosecurity boards actually do that; the other ten score
a refusal as a failure. Applying the documented rule uniformly moves Claude Opus 5.5
from **16th to 1st** — on a minimum per-board coverage of **2.7%**. A refusal is free
on one board and fatal on another, and the two are averaged into one number.

**2. Where refusals are excluded, rank rests on a handful of items.**
Opus 5.5 (Pi) is ranked #1 on BioSecBench-Function at 73.6%, scored on **12 of 111**
items, published CI `[47.5, 99.7]`. The model shown at rank 2 has a bootstrap 95%
rank interval of **[1, 27]**. Ranks are rendered as integers but are intervals tens
of places wide, and the width is set by how much of the board the model declined.

**3. 38% of the suite's spend buys no ranking information.**
166 items (14%) are never solved by any of the 38 models — $50,319, and 120 of them
have *exactly zero* passes across every model and run, which reads as broken graders
rather than hard science. Keeping only the most discriminating 30% of items
reproduces the full leaderboard at Spearman **0.984** with 10/10 top-10 overlap, for
**$59k instead of $224k**.

## Run it

```bash
pip install pandas numpy scipy pyarrow
python3 src/fetch.py     # pull the public result files
python3 src/report.py    # reproduce every number above -> out/
```

## Layout

| file | what it does |
|---|---|
| `src/fetch.py` | download the published JSON |
| `src/load.py` | flatten to one tidy frame (one row per model × evaluation) |
| `src/scoring.py` | the three scoring rules, and which board uses which |
| `src/items.py` | item difficulty, discrimination, subset fidelity |
| `src/stability.py` | cluster bootstrap over items → rank intervals |
| `src/report.py` | runs everything, writes `out/` |

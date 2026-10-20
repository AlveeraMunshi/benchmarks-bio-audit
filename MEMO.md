# Your Overall score averages two different scoring rules

**Alveera Munshi · October 2026**
Repo: `benchmarks-bio-audit` · reproduces 459/459 published board scores to within 0.005 pts

---

## What I did

I pulled the public result files behind benchmarks.bio — `/data/v1/<bench>.json` and
`/results/v1/latest.json` — and rebuilt the leaderboard from the per-evaluation
counts. 12 capability boards, 1,203 evaluations, 38 model×harness rows, 144,557
graded runs, $226,970 of inference.

The first thing I did was check I could reproduce what the site shows. I can: all 459
published board scores, to within 0.005 points. Getting there is how I found the
problem, because 83 of those cells would not reproduce under the rule the site
documents.

## The finding

Ten of the twelve boards score a refused attempt as a **failure**. Two —
BioSecBench-Function and BioSecBench-Surveillance — **drop it from the denominator**.
I established this by fitting both rules to every published cell: the biosecurity
boards match *exclude* on 38 of 38 rows and *fail* on 9; every other board matches
*fail* exactly.

The Overall score is the unweighted mean of those twelve boards. So a refusal costs a
model nothing on two boards and a full item on ten, and the two currencies are then
averaged into the headline number.

Eleven of the twelve boards also carry identical text saying *"Refusals are excluded
from the denominator."* That is true of two of them. MetagenomicsBench is the
exception and describes what it actually does, which suggests the rule is deliberate
and the prose on the other nine boards is just stale.

## Why it matters

It decides the top of the board.

| | as published | all *exclude* | all *fail* |
|---|---|---|---|
| **Opus 5.5** (Claude Code) | 37.6 → rank **16** | 56.2 → rank **1** | 29.8 → rank **23** |
| **Opus 5.5\*** LSVP (Pi) | 55.3 → rank **1** | 55.6 → rank **2** | 55.3 → rank **1** |

Opus 5.5 moves 15 places depending on a rule nobody chose on purpose, and its minimum
per-board coverage is 2.7%.

The LSVP pair is the control that makes this unambiguous. LSVP is the same model with
the safety filter off, so it attempts ~100% of the suite — and it scores ~55 under
*every* rule. The unstarred run of the same model swings 26 points across rules,
entirely on what it declined to answer. The spread is a property of the scoring, not
of the model.

And it bites hardest exactly where the *exclude* rule is in force, because there the
model picks its own denominator. Opus 5.5 is ranked **#1 on BioSecBench-Function at
73.6%, scored on 12 of 111 items**, with a published CI of `[47.5, 99.7]`. A cluster
bootstrap over items puts the row *displayed at rank 2* anywhere in **[1, 27]**.

The obvious repair is not available: scoring everyone on the items everyone attempted
leaves 7% of BioSecBench-Function and 2% of TxBench-Oligo.

## What I checked and was wrong about

I assumed exclusion would inflate scores by dropping the hardest items. It does not.
Scoring each refused item against the 38-model consensus difficulty, across 64
model×board cells with enough data on both sides: Wilcoxon p = 0.58, mean gap
−0.6 points. Refusals track topic sensitivity, not difficulty.

That matters for the fix. The point estimates are roughly fine. The defects are that
the rule is inconsistent and that the precision behind each number varies by an order
of magnitude, so a correction aimed at the point estimate would miss.

## What I propose

Implemented in `src/policy.py`, with the contract in `tests/`.

Not "pick one rule" — biosecurity has a real reason to exclude refusals, since
refusing is the desired behaviour there and you already score it separately on
BioSecBench-Refusal. Four changes:

1. **Each board declares its refusal rule in the data**, beside its score, instead of
   leaving it implicit in prose.
2. **The published number is tested against the declared rule**, so drift between the
   docs and the pipeline fails CI rather than shipping.
3. **Overall takes the rule as an argument** and refuses to average mixed currencies.
   One Overall per rule is honest; one Overall across two is not.
4. **Every score carries its coverage**, and a row below a coverage floor is reported
   but not ranked. A rank computed on 12 of 111 items is not a rank.

Two of the six tests in `tests/test_scoring_contract.py` fail against today's data.
Those two failures are the finding; the other four show the harness is faithful and
the proposed Overall is well-defined.

## One more thing, while I was in there

Independent of the rule question, and relevant to where the next $227k goes:

- **166 items (14%) are never solved by any of the 38 models**, costing $50,319.
  **120 have exactly zero passes across every model and every run** — that reads like
  broken graders rather than hard science. 8 of SpatialBench-Long's 21 items are dead.
- **37.8% of total spend ($85,785)** goes to items that cannot separate models.
- Keeping the **top 30% of items by discrimination** reproduces the full leaderboard
  at Spearman **0.984** with 10/10 top-10 overlap, for **$59k instead of $224k**.
- `mobilome_mge_class_abundance_illumina_wastewater_mgx` appears twice in
  SurveillanceBench under two ids. Both dead. $2,250.

If any of that is useful I'd happily take the dead-item list further — working out
which of the 120 are genuinely unsolved and which are grader bugs is a concrete piece
of work and it would make the next run cheaper and sharper.

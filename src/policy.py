"""The proposed fix: make the refusal rule a declared property of a board, and
publish the interval a rank actually supports.

Today the rule is implicit. Eleven of the thirteen capability boards carry the
same sentence - "Refusals are excluded from the denominator" - and two of them
do it; the Overall score then averages both rules. Nothing in the data model
records which rule a board used, so nothing can catch the drift.

The proposal is NOT "pick one rule". Biosecurity has a real reason to exclude
refusals: refusing is the desired behaviour there, and it is already scored
separately on BioSecBench-Refusal. Four changes instead:

  1. every board DECLARES its rule, in the data, next to its score;
  2. the published number is checked against the declared rule, so drift
     becomes a failing test rather than a surprise;
  3. Overall takes the rule as an argument and will not silently average
     boards that priced a refusal differently;
  4. a score ships with the rank INTERVAL it supports, and an integer rank is
     withheld when that interval is too wide to mean anything.

(4) replaces an earlier coverage-floor idea. Coverage turned out not to drive
interval width - across all 494 board rows the Spearman correlation between
coverage and width is 0.003. Width is driven mainly by how many items a board
has: the three long-horizon boards carry 21-25 items and median intervals near
20 places, while MetagenomicsBench carries 100 items and a median of 7. So the
gate is the interval itself, which captures both causes, with coverage still
reported because on an `exclude` board the model chooses its own denominator.
"""
from dataclasses import dataclass
from typing import Literal

import pandas as pd

import load
import scoring

RefusalRule = Literal["exclude", "fail"]


@dataclass(frozen=True)
class ScoringPolicy:
    """What a board does with a refused attempt, and when a rank is publishable."""
    refusal: RefusalRule
    max_rank_interval: int = 10   # places; wider than this and no integer rank
    report_coverage: bool = True

    @property
    def fn(self):
        return (scoring.exclude_refusals if self.refusal == "exclude"
                else scoring.refusal_is_fail)


# Declared from what each board's published numbers actually do, recovered by
# fitting both rules to all 494 published cells (see tests/).
DECLARED = {
    "functionbench":            ScoringPolicy("exclude"),
    "biosecbench-surveillance": ScoringPolicy("exclude"),
    **{b: ScoringPolicy("fail") for b in [
        "spatialbench", "spatialbench-long", "scbench", "scbench-long",
        "epibench", "variantbench", "metagenomics",
        "txbench-ab", "txbench-pp", "txbench-od", "oncologybench"]},
}

# Boards whose published methodology string describes the rule they actually
# use. Every other board claims refusals are excluded when they are not.
DOCUMENTED_CORRECTLY = {"functionbench", "biosecbench-surveillance",
                        "metagenomics", "oncologybench"}


def infer_rule(df, bench, tol=0.01):
    """Which rule reproduces this board's published numbers?"""
    g = df[df.bench == bench]
    site = g.groupby("mid").published_pass.first()
    hits = {}
    for name, fn in (("exclude", scoring.exclude_refusals),
                     ("fail", scoring.refusal_is_fail)):
        v = g.groupby("mid").apply(fn, include_groups=False)
        hits[name] = int((v - site).abs().lt(tol).sum())
    return max(hits, key=hits.get), hits, len(site)


def score_board(df, bench, intervals=None):
    """A board score that carries its rule, its coverage, and its rank interval."""
    policy = DECLARED[bench]
    b = scoring.board(df[df.bench == bench], policy.fn)
    b["refusal_rule"] = policy.refusal
    if intervals is not None:
        iv = intervals[intervals.bench == bench].set_index("mid")
        b = b.join(iv[["rank_lo", "rank_hi", "interval_width"]], on="mid")
        b["rank"] = b.score.rank(ascending=False)
        b.loc[b.interval_width > policy.max_rank_interval, "rank"] = pd.NA
    return b


def overall(df, rule: RefusalRule, min_boards=11):
    """Overall on ONE declared currency.

    Averaging boards that priced a refusal differently is the defect this
    exists to prevent, so the rule is an argument and never an inference.
    Weighting matches the site: each board's configured evaluation count.
    """
    policy = ScoringPolicy(rule)
    out = scoring.overall(df, policy.fn, min_boards=min_boards).copy()
    out["refusal_rule"] = rule
    out["rank"] = out.score.rank(ascending=False)
    return out


def mixed_rule_overall(df, min_boards=11):
    """What the site publishes today: each board on its own rule, averaged."""
    return scoring.overall(df, scoring.as_published, min_boards=min_boards)


def rules_in_use():
    return pd.Series({b: p.refusal for b, p in sorted(DECLARED.items())},
                     name="refusal_rule")

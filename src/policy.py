"""The proposed fix: make the refusal rule a declared property of a board.

Today the rule is implicit. Every board's `methodology` string says refusals
leave the denominator; two boards do that and ten do the opposite, and the
Overall score averages both. Nothing in the data model records which rule a
board used, so nothing can catch the drift.

The proposal is not "pick one rule" - biosecurity has a real reason to exclude
refusals, because refusing is the desired behaviour there and is scored
separately on BioSecBench-Refusal. The proposal is:

  1. every board DECLARES its rule, in the data, next to its score;
  2. a board's published number is checked against its declared rule (drift
     becomes a failing test rather than a surprise);
  3. the Overall score refuses to silently average boards whose rules differ -
     it either converts them to one currency or reports one Overall per rule;
  4. every score carries the coverage it was computed on, because under
     `exclude` the denominator is chosen by the model.
"""
from dataclasses import dataclass
from typing import Literal

import pandas as pd

import scoring

RefusalRule = Literal["exclude", "fail"]


@dataclass(frozen=True)
class ScoringPolicy:
    """What a board does with a refused attempt."""
    refusal: RefusalRule
    # a score computed on less of the board than this is reported, not ranked
    coverage_floor: float = 80.0

    @property
    def fn(self):
        return (scoring.exclude_refusals if self.refusal == "exclude"
                else scoring.refusal_is_fail)


# Declared from what each board's published numbers actually do, recovered by
# fitting both rules to all 459 published cells (see tests/).
DECLARED = {
    "functionbench":     ScoringPolicy("exclude"),
    "surveillancebench": ScoringPolicy("exclude"),
    **{b: ScoringPolicy("fail") for b in [
        "spatialbench", "spatialbench-long", "scbench", "scbench-long",
        "epibench", "variantbench", "metagenomics",
        "txbench-pp", "txbench-od", "txbench-ad"]},
}


def infer_rule(df, bench, tol=0.01):
    """Which rule reproduces this board's published numbers?"""
    g = df[df.bench == bench]
    site = g.groupby("mid").published_pass.first()
    hits = {}
    for name, fn in (("exclude", scoring.exclude_refusals),
                     ("fail", scoring.refusal_is_fail)):
        v = g.groupby("mid").apply(fn, include_groups=False)
        hits[name] = int((v - site).abs().lt(tol).sum())
    best = max(hits, key=hits.get)
    return best, hits, len(site)


def score_board(df, bench):
    """A board score that carries its rule and its coverage."""
    policy = DECLARED[bench]
    b = scoring.board(df[df.bench == bench], policy.fn)
    b["refusal_rule"] = policy.refusal
    b["rankable"] = b.coverage >= policy.coverage_floor
    return b


def overall(df, rule: RefusalRule):
    """Overall on ONE declared currency, with the weakest coverage carried up.

    Averaging boards that priced a refusal differently is the defect this
    exists to prevent, so the rule is an argument and not an inference.
    """
    policy = ScoringPolicy(rule)
    b = scoring.board(df, policy.fn)
    out = b.groupby("mid").agg(score=("score", "mean"), boards=("bench", "size"),
                               min_coverage=("coverage", "min"),
                               mean_coverage=("coverage", "mean"))
    out = out[out.boards >= 12].copy()
    out["refusal_rule"] = rule
    out["rankable"] = out.min_coverage >= policy.coverage_floor
    # rank only the rows that earned a rank; the rest are reported unranked
    out["rank"] = out.score.where(out.rankable).rank(ascending=False)
    return out.sort_values("score", ascending=False)


def mixed_rule_overall(df):
    """What the site publishes today: each board on its own rule, averaged."""
    b = scoring.board(df, scoring.as_published)
    out = b.groupby("mid").agg(score=("score", "mean"), boards=("bench", "size"),
                               min_coverage=("coverage", "min"))
    return out[out.boards >= 12].sort_values("score", ascending=False)


def rules_in_use(df):
    return pd.Series({b: DECLARED[b].refusal for b in sorted(DECLARED)}, name="refusal_rule")

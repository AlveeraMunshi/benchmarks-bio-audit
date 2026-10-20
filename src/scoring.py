"""The scoring rules, and which board uses which.

Eleven of the thirteen capability boards carry the same methodology sentence -
"Refusals are excluded from the denominator" - and only the two biosecurity
boards do it. MetagenomicsBench and OncologyBench are the two that describe the
failure rule accurately, which is why the drift reads as stale prose rather
than a scoring mistake.

`as_published` reproduces what the site shows, board by board.
`exclude_refusals` / `refusal_is_fail` apply one rule uniformly so the thirteen
boards can be compared on a single currency.
"""
import numpy as np
import pandas as pd

import load

# boards whose published numbers are reproduced by dropping refusals
EXCLUDES_REFUSALS = {"functionbench", "biosecbench-surveillance"}


def exclude_refusals(g):
    """correct / gradeable, macro-mean over the evals the model attempted."""
    return 100 * (g.correct / g.gradeable).where(g.attempted).mean()


def refusal_is_fail(g):
    """correct / runs, macro-mean over every eval on the board."""
    return 100 * (g.correct / g.runs).mean()


def as_published(g):
    rule = exclude_refusals if g.name[0] in EXCLUDES_REFUSALS else refusal_is_fail
    return rule(g)


def board(df, rule):
    """Per (bench, model) score under one rule, plus the coverage it rests on."""
    score = df.groupby(["bench", "mid"]).apply(rule, include_groups=False).rename("score")
    cov = df.groupby(["bench", "mid"]).agg(
        n_items=("eval_id", "size"), items_scored=("attempted", "sum"),
        refusals=("refused", "sum"), runs=("runs", "sum"))
    cov["coverage"] = 100 * cov.items_scored / cov.n_items
    return pd.concat([score, cov], axis=1).reset_index()


def overall(df, rule, weights=None, min_boards=12):
    """Overall the way the site computes it: a mean across boards WEIGHTED by
    each board's configured evaluation count, over the boards a model has.

    Verified against the published capability leaderboard - an unweighted mean
    reproduces 0 of 38 rows, this reproduces 29 of 38 (see tests).
    """
    w = weights or load.overall_weights()
    b = board(df, rule)
    b["w"] = b.bench.map(w)
    out = (b.groupby("mid")
             .apply(lambda g: pd.Series({
                 "score": float(np.average(g.score, weights=g.w)),
                 "boards": len(g),
                 "min_coverage": g.coverage.min(),
                 "mean_coverage": float(np.average(g.coverage, weights=g.w)),
             }), include_groups=False))
    return out[out.boards >= min_boards].sort_values("score", ascending=False)

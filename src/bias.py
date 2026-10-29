"""Does excluding refusals inflate a score by dropping the harder items?

The worry is selection: if a model declines exactly the items it would have
failed, removing them from the denominator flatters it. This tests that
directly, and - more usefully than a p-value - puts an interval on how large
any such effect could be.

Item difficulty is estimated from the high-coverage rows only (models that
attempted essentially the whole board), so the yardstick is not itself
contaminated by refusals.
"""
import numpy as np
import pandas as pd
from scipy import stats

HIGH_COVERAGE = 0.95
MIN_CELL = 10          # need this many refused AND attempted items to compare


def consensus_difficulty(df):
    cov = (df.groupby(["mid", "bench"]).attempted.mean().rename("cov").reset_index())
    d = df.merge(cov, on=["mid", "bench"])
    hi = d[(d["cov"] >= HIGH_COVERAGE) & d.attempted]
    return (hi.groupby(["bench", "eval_id"])
              .agg(difficulty=("rate", "mean"), n_models=("rate", "size"))
              .reset_index())


def gap_table(df):
    """Per (model, board): mean consensus difficulty of the items it refused
    minus the items it attempted. Positive = it dropped the harder ones."""
    item = consensus_difficulty(df)
    d = df.merge(item, on=["bench", "eval_id"], how="left")
    rows = []
    for (mid, bench), g in d.groupby(["mid", "bench"]):
        g = g[g.difficulty.notna()]
        ref, att = g[~g.attempted], g[g.attempted]
        if len(ref) < MIN_CELL or len(att) < MIN_CELL:
            continue
        rows.append(dict(
            mid=mid, bench=bench, n_refused=len(ref), n_attempted=len(att),
            diff_refused=100 * ref.difficulty.mean(),
            diff_attempted=100 * att.difficulty.mean(),
            gap=100 * (att.difficulty.mean() - ref.difficulty.mean()),
            p=stats.mannwhitneyu(att.difficulty, ref.difficulty).pvalue))
    return pd.DataFrame(rows)


def bound(gaps, n_boot=20_000, seed=0):
    """A bootstrap interval on the mean gap.

    Failing to reject is weak; an interval says how big the effect could
    plausibly be, which is what decides whether the point estimate needs
    correcting at all.
    """
    rng = np.random.default_rng(seed)
    x = gaps.gap.to_numpy()
    means = np.array([rng.choice(x, len(x), replace=True).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(means, [2.5, 97.5])
    w = stats.wilcoxon(x)
    return dict(n_cells=len(x), mean_gap=x.mean(), ci_lo=lo, ci_hi=hi,
                median_gap=float(np.median(x)), share_positive=float((x > 0).mean()),
                wilcoxon_p=w.pvalue,
                # worst case: the largest inflation consistent with the data,
                # scaled by how much of a board a heavy refuser drops
                max_plausible_inflation=hi)

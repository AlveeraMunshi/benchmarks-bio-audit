"""How much of a leaderboard position is real?

The boards sort point estimates computed from between 12 and 195 items. A
cluster bootstrap over items turns each integer rank into the interval it
actually supports.
"""
import numpy as np
import pandas as pd


def rank_intervals(df, bench, n_boot=4000, seed=0):
    rng = np.random.default_rng(seed)
    s = df[(df.bench == bench) & df.attempted]
    rate = s.pivot_table(index="eval_id", columns="mid", values="rate")
    M, mids = rate.values, rate.columns.to_numpy()
    n = M.shape[0]
    observed = np.nanmean(M, axis=0)
    ranks = np.empty((n_boot, len(mids)))
    wins = np.zeros(len(mids))
    for b in range(n_boot):
        sc = np.nanmean(M[rng.integers(0, n, n), :], axis=0)
        order = (-sc).argsort()
        r = np.empty(len(mids)); r[order] = np.arange(1, len(mids) + 1)
        ranks[b] = r
        wins[np.nanargmax(sc)] += 1
    out = pd.DataFrame(dict(
        mid=mids, score=100 * observed,
        items_scored=(~np.isnan(M)).sum(axis=0),
        p_rank1=100 * wins / n_boot,
        rank_lo=np.percentile(ranks, 2.5, axis=0),
        rank_hi=np.percentile(ranks, 97.5, axis=0)))
    out["shown_rank"] = out.score.rank(ascending=False)
    return out.sort_values("score", ascending=False)

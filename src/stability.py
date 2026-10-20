"""How much of a leaderboard position is real?

Boards sort point estimates computed from between 12 and 195 items. A cluster
bootstrap over items turns each integer rank into the interval it supports, on
a single board or on the weighted Overall.
"""
import numpy as np
import pandas as pd

import load
import scoring


def _matrix(df, bench):
    s = df[(df.bench == bench) & df.attempted]
    return s.pivot_table(index="eval_id", columns="mid", values="rate")


def rank_intervals(df, bench, n_boot=4000, seed=0):
    rng = np.random.default_rng(seed)
    rate = _matrix(df, bench)
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
        bench=bench, mid=mids, score=100 * observed,
        items_scored=(~np.isnan(M)).sum(axis=0),
        coverage=100 * (~np.isnan(M)).sum(axis=0) / n,
        p_rank1=100 * wins / n_boot,
        rank_lo=np.percentile(ranks, 2.5, axis=0),
        rank_hi=np.percentile(ranks, 97.5, axis=0)))
    out["shown_rank"] = out.score.rank(ascending=False)
    out["interval_width"] = out.rank_hi - out.rank_lo
    return out.sort_values("score", ascending=False)


def overall_rank_intervals(df, n_boot=2000, seed=0, min_boards=11):
    """Resample items WITHIN each board, recompute every board score under the
    published rule, then re-weight into Overall. This is the interval behind
    the number on the front page."""
    rng = np.random.default_rng(seed)
    w = load.overall_weights()
    mats, rules = {}, {}
    for bench in df.bench.unique():
        s = df[df.bench == bench]
        rules[bench] = bench in scoring.EXCLUDES_REFUSALS
        if rules[bench]:
            v = s.assign(v=(s.correct / s.gradeable).where(s.attempted))
        else:
            v = s.assign(v=s.correct / s.runs)
        mats[bench] = v.pivot_table(index="eval_id", columns="mid", values="v")

    mids = sorted(set().union(*[set(m.columns) for m in mats.values()]))
    keep = [m for m in mids if sum(m in mats[b].columns for b in mats) >= min_boards]
    idx = {m: i for i, m in enumerate(keep)}
    draws = np.full((n_boot, len(keep)), np.nan)
    for b in range(n_boot):
        num = np.zeros(len(keep)); den = np.zeros(len(keep))
        for bench, M in mats.items():
            arr, cols = M.values, M.columns.to_numpy()
            samp = np.nanmean(arr[rng.integers(0, arr.shape[0], arr.shape[0]), :], axis=0)
            for j, m in enumerate(cols):
                if m in idx and not np.isnan(samp[j]):
                    num[idx[m]] += 100 * samp[j] * w[bench]
                    den[idx[m]] += w[bench]
        draws[b] = np.where(den > 0, num / den, np.nan)
    order = (-draws).argsort(axis=1)
    ranks = np.empty_like(draws)
    for b in range(n_boot):
        ranks[b, order[b]] = np.arange(1, len(keep) + 1)
    obs = scoring.overall(df, scoring.as_published, min_boards=min_boards)
    out = pd.DataFrame(dict(
        mid=keep,
        rank_lo=np.percentile(ranks, 2.5, axis=0),
        rank_hi=np.percentile(ranks, 97.5, axis=0),
        p_rank1=100 * (ranks == 1).mean(axis=0))).set_index("mid")
    out = obs.join(out)
    out["shown_rank"] = out.score.rank(ascending=False)
    out["interval_width"] = out.rank_hi - out.rank_lo
    return out.sort_values("score", ascending=False)

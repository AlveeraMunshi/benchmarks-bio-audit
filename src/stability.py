"""How much of a leaderboard position is real?

Boards sort point estimates computed from between 12 and 195 items. A cluster
bootstrap over items turns each integer rank into the interval it supports, on
a single board or on the weighted Overall.
"""
import warnings

import numpy as np
import pandas as pd

import load
import scoring


def _rank_one_draw(sc):
    """Ranks for a single bootstrap draw, 1 = best, NaN where undefined.

    A model can come out of a draw with NO estimate: if it attempted only a
    handful of the board's items, a resample can miss all of them. That is not
    hypothetical - Opus 5.5 (Claude Code) attempted 3 of TxBench-Oligo's 113
    items, so about 5% of draws leave it with nothing.

    Such a model ABSTAINS from that draw rather than being ranked. Letting
    argsort handle the NaN instead would silently sort it last, which reads as
    "worst model in this draw" when the truth is "no measurement in this
    draw" - and it would widen that model's interval to the bottom of the
    board for free. Abstaining keeps the interval over draws that measured it,
    which is the same population the point estimate is computed over.
    """
    r = np.full(len(sc), np.nan)
    have = np.flatnonzero(~np.isnan(sc))
    order = have[(-sc[have]).argsort(kind="stable")]
    r[order] = np.arange(1, len(order) + 1)
    return r, (order[0] if len(order) else None)


def _matrix(df, bench):
    s = df[(df.bench == bench) & df.attempted]
    return s.pivot_table(index="eval_id", columns="mid", values="rate")


# 10,000 resamples puts the Monte Carlo error on a 2.5th/97.5th percentile
# below a tenth of a rank place, which is well under the quantity being
# reported (whole rank positions). Lower counts make the published interval
# itself jitter between runs, which is the one thing an interval must not do.
N_BOOT = 10_000


def rank_intervals(df, bench, n_boot=N_BOOT, seed=0):
    """95% rank interval for every model on ONE board.

    Items are the unit of independence - the three runs inside an item are
    correlated, so the bootstrap resamples items and never runs.
    """
    rng = np.random.default_rng(seed)
    rate = _matrix(df, bench)
    M, mids = rate.values, rate.columns.to_numpy()
    n = M.shape[0]
    observed = np.nanmean(M, axis=0)
    ranks = np.full((n_boot, len(mids)), np.nan)
    wins = np.zeros(len(mids))
    # A draw that misses every item a model attempted makes nanmean warn on an
    # empty slice. That case is expected here and handled in _rank_one_draw,
    # so the warning is noise rather than a signal.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for b in range(n_boot):
            sc = np.nanmean(M[rng.integers(0, n, n), :], axis=0)
            ranks[b], winner = _rank_one_draw(sc)
            if winner is not None:
                wins[winner] += 1
    out = pd.DataFrame(dict(
        bench=bench, mid=mids, score=100 * observed,
        items_scored=(~np.isnan(M)).sum(axis=0),
        coverage=100 * (~np.isnan(M)).sum(axis=0) / n,
        p_rank1=100 * wins / n_boot,
        # nanpercentile, not percentile: the abstentions above are NaN, and
        # counting them as a value would drag the interval toward last place.
        rank_lo=np.nanpercentile(ranks, 2.5, axis=0),
        rank_hi=np.nanpercentile(ranks, 97.5, axis=0),
        # Reported rather than hidden: a model measured in only some draws has
        # a correspondingly weaker interval, and the reader should see that.
        draws_undefined=np.isnan(ranks).sum(axis=0)))
    out["shown_rank"] = out.score.rank(ascending=False)
    out["interval_width"] = out.rank_hi - out.rank_lo
    return out.sort_values("score", ascending=False)


def overall_rank_intervals(df, n_boot=N_BOOT, seed=0, min_boards=11):
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
    # Expected empty slices again, same reason as the per-board loop.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for b in range(n_boot):
            # num/den accumulate the weighted sum and the weight actually
            # present for each model, so a model missing a board is normalised
            # over the boards it HAS rather than scored zero on the ones it
            # lacks - which is what the site's own coverage rule does.
            num = np.zeros(len(keep)); den = np.zeros(len(keep))
            for bench, M in mats.items():
                arr, cols = M.values, M.columns.to_numpy()
                # Resample this board's items, independently per board: the
                # boards are separate item pools, so one shared draw would
                # correlate them artificially.
                samp = np.nanmean(
                    arr[rng.integers(0, arr.shape[0], arr.shape[0]), :], axis=0)
                for j, m in enumerate(cols):
                    if m in idx and not np.isnan(samp[j]):
                        num[idx[m]] += 100 * samp[j] * w[bench]
                        den[idx[m]] += w[bench]
            draws[b] = np.where(den > 0, num / den, np.nan)
    # Same abstention rule as the per-board intervals above. It almost never
    # fires here - min_boards=11 means a model needs eleven boards to appear
    # at all, so a draw that leaves it with no estimate anywhere is rare - but
    # the handling is explicit so a thin model cannot quietly rank last.
    ranks = np.full_like(draws, np.nan)
    for b in range(n_boot):
        ranks[b], _ = _rank_one_draw(draws[b])
    obs = scoring.overall(df, scoring.as_published, min_boards=min_boards)
    out = pd.DataFrame(dict(
        mid=keep,
        rank_lo=np.nanpercentile(ranks, 2.5, axis=0),
        rank_hi=np.nanpercentile(ranks, 97.5, axis=0),
        p_rank1=100 * (ranks == 1).mean(axis=0))).set_index("mid")
    out = obs.join(out)
    out["shown_rank"] = out.score.rank(ascending=False)
    out["interval_width"] = out.rank_hi - out.rank_lo
    return out.sort_values("score", ascending=False)

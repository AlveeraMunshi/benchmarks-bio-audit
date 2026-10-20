"""Item-level information: does an evaluation help separate models at all?

Difficulty      = mean pass rate across the models that attempted it.
Discrimination  = point-biserial correlation between the per-model rate on this
                  item and that model's overall ability.

An item every model passes, an item no model passes, and an item uncorrelated
with ability all cost money and move no ranking.
"""
import numpy as np
import pandas as pd

DEAD = 0.02           # mean pass rate at or below this: nobody solves it
SATURATED = 0.98      # at or above this: everybody solves it
WEAK_DISCRIMINATION = 0.05


def item_table(df, min_models=20):
    s = df[df.attempted].copy()
    s["ability"] = s.mid.map(s.groupby("mid").rate.mean())
    rows = []
    for (bench, ev), g in s.groupby(["bench", "eval_id"]):
        if len(g) < min_models:
            continue
        r = g.rate.values
        disc = np.corrcoef(r, g.ability.values)[0, 1] if r.std() > 0 else 0.0
        rows.append(dict(bench=bench, eval_id=ev, n_models=len(g),
                         difficulty=r.mean(), sd=r.std(), discrimination=disc,
                         runs=int(g.runs.sum()), cost=g.costSum.sum(),
                         zero_passes=int(g.correct.sum()) == 0))
    it = pd.DataFrame(rows)
    it["dead"] = it.difficulty <= DEAD
    it["saturated"] = it.difficulty >= SATURATED
    it["uninformative"] = (it.dead | it.saturated | (it.sd < 1e-9)
                           | (it.discrimination <= WEAK_DISCRIMINATION))
    return it


def subset_fidelity(df, items, keep_fractions=(1.0, .6, .4, .3, .2)):
    """Does a high-discrimination subset of items reproduce the full ranking?"""
    from scipy.stats import spearmanr
    s = df[df.attempted].merge(items[["bench", "eval_id", "discrimination"]],
                               on=["bench", "eval_id"])
    full = s.groupby("mid").rate.mean()
    per_item = s.groupby(["bench", "eval_id"]).discrimination.first()
    out = []
    for f in keep_fractions:
        sub = s[s.discrimination >= per_item.quantile(1 - f)]
        sc = sub.groupby("mid").rate.mean()
        common = full.index.intersection(sc.index)
        out.append(dict(keep_frac=f,
                        n_items=sub.groupby(["bench", "eval_id"]).ngroups,
                        cost=sub.costSum.sum(),
                        spearman=spearmanr(full[common], sc[common]).statistic,
                        top10_overlap=len(set(full.nlargest(10).index)
                                          & set(sc.nlargest(10).index))))
    return pd.DataFrame(out)


def dead_item_profile(df, items):
    """Where the never-solved items cluster. A board-wide pattern points at a
    grader or a task spec rather than at the science being hard."""
    dead = items[items.dead][["bench", "eval_id"]]
    f = [c for c in df.columns if c.startswith("facet_")]
    d = df.merge(dead.assign(is_dead=True), on=["bench", "eval_id"], how="left")
    d["is_dead"] = d.is_dead.fillna(False).astype(bool)
    per_item = d.groupby(["bench", "eval_id"]).first().reset_index()
    out = []
    for col in f:
        if per_item[col].notna().sum() < 20:
            continue
        g = per_item.dropna(subset=[col]).groupby([col.replace("facet_", "facet_")])
        for val, grp in per_item.dropna(subset=[col]).groupby(col):
            if len(grp) < 5:
                continue
            # `n_items`, not `items`: a column named `items` shadows
            # DataFrame.items and breaks attribute access downstream.
            out.append(dict(facet=col.replace("facet_", ""), value=val,
                            n_items=len(grp), dead=int(grp.is_dead.sum()),
                            dead_pct=100 * grp.is_dead.mean()))
    return pd.DataFrame(out).sort_values("dead_pct", ascending=False)

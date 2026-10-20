"""The three scoring rules.

Each benchmark's own `methodology` string on benchmarks.bio says refusals are
excluded from the denominator. Only the two biosecurity boards actually do it;
the other ten score a refusal as a failure. `as_published` reproduces what the
site shows, board by board; `exclude_refusals` and `refusal_is_fail` apply one
rule uniformly so the boards can be compared on a single currency.
"""
import pandas as pd

# boards whose published numbers are reproduced by dropping refusals
EXCLUDES_REFUSALS = {"functionbench", "surveillancebench"}


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
    out = df.groupby(["bench", "mid"]).apply(rule, include_groups=False).rename("score")
    cov = df.groupby(["bench", "mid"]).agg(
        n_items=("eval_id", "size"), items_scored=("attempted", "sum"),
        refusals=("refused", "sum"), runs=("runs", "sum"))
    cov["coverage"] = 100 * cov.items_scored / cov.n_items
    return pd.concat([out, cov], axis=1).reset_index()


def overall(df, rule, require_full=True):
    """Unweighted mean across boards — every V1 benchmark carries weight 1."""
    b = board(df, rule)
    g = b.groupby("mid").agg(score=("score", "mean"), boards=("bench", "size"),
                             min_coverage=("coverage", "min"),
                             mean_coverage=("coverage", "mean"))
    return g[g.boards >= 12].sort_values("score", ascending=False) if require_full else g

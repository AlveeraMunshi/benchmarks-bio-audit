"""Flatten the per-evaluation JSON into one tidy frame.

One row = one (model x harness) x (benchmark x evaluation) cell, holding the
counts over that cell's `runsPerEval` attempts.
"""
import json, pathlib
import pandas as pd

RAW = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw" / "v1"
CAPABILITY = ["spatialbench", "spatialbench-long", "scbench", "scbench-long",
              "epibench", "variantbench", "metagenomics", "txbench-pp",
              "txbench-od", "txbench-ad", "surveillancebench", "functionbench"]


def _bench_rows(bench):
    d = json.loads((RAW / f"{bench}.json").read_text())
    schema, facets = d["perEvalSchema"], d.get("evalFacets", {})
    for m in d["models"]:
        for ev, vals in m["perEval"].items():
            row = dict(zip(schema, vals))
            row.update(bench=bench, eval_id=ev, mid=m["id"], model=m["name"],
                       harness=m["harness"], org=m["organization"],
                       published_pass=m["passRate"], ci_lo=m["ci"][0], ci_hi=m["ci"][1])
            row.update({f"facet_{k}": v for k, v in facets.get(ev, {}).items()})
            yield row


def tidy():
    df = pd.DataFrame(r for b in CAPABILITY for r in _bench_rows(b))
    # gradeable = attempts that reached the grader; refusals leave the denominator
    df["gradeable"] = df.runs - df.refused
    df["attempted"] = df.gradeable > 0
    df["rate"] = (df.correct / df.gradeable).where(df.attempted)
    return df


def published_scores(df):
    """Reproduce the site's metric: macro-mean of per-eval rates over the evals
    a model actually attempted."""
    g = df[df.attempted].groupby(["bench", "mid"])
    return g.rate.mean().mul(100).rename("published").reset_index()

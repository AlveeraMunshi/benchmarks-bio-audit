"""Flatten the published per-evaluation records into one tidy frame.

One row = one (model x harness) x (benchmark x evaluation) cell, holding the
counts over that cell's attempts. Twelve boards ship under /data/v1/<id>.json;
OncologyBench has its own schema and is folded in from src/oncology.py.
"""
import json, pathlib
import pandas as pd

import oncology

RAW = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"
V1 = RAW / "v1"

# the twelve boards under /data/v1/; OncologyBench is the thirteenth
V1_BOARDS = ["spatialbench", "spatialbench-long", "scbench", "scbench-long",
             "epibench", "variantbench", "metagenomics", "txbench-pp",
             "txbench-od", "txbench-ad", "surveillancebench", "functionbench"]

# the site's own board ids, which differ from the per-eval filenames
FILE_TO_BOARD = {"txbench-ad": "txbench-ab", "surveillancebench": "biosecbench-surveillance"}
BOARD_TO_FILE = {v: k for k, v in FILE_TO_BOARD.items()}

LABEL = {
    "spatialbench": "SpatialBench", "spatialbench-long": "SpatialBench-Long",
    "scbench": "scBench", "scbench-long": "scBench-Long", "epibench": "EpiBench",
    "variantbench": "VariantBench", "metagenomics": "MetagenomicsBench",
    "txbench-ab": "TxBench-Antibody", "txbench-pp": "TxBench-Preclinical",
    "txbench-od": "TxBench-Oligo", "biosecbench-surveillance": "BioSecBench-Surveillance",
    "functionbench": "BioSecBench-Function", "oncologybench": "OncologyBench",
}


def _v1_rows(fname):
    d = json.loads((V1 / f"{fname}.json").read_text())
    bench = FILE_TO_BOARD.get(fname, fname)
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
    rows = [r for f in V1_BOARDS for r in _v1_rows(f)]
    rows += list(oncology.rows())
    df = pd.DataFrame(rows)
    df["timeout"] = df.timeout.fillna(0)
    df["gradeable"] = df.runs - df.refused      # attempts that reached a grader
    df["attempted"] = df.gradeable > 0
    df["rate"] = (df.correct / df.gradeable).where(df.attempted)
    df["label"] = df.bench.map(LABEL)
    return df


def methodology_text():
    """Each board's published methodology string, by board id."""
    out = {}
    for f in V1_BOARDS:
        out[FILE_TO_BOARD.get(f, f)] = json.loads((V1 / f"{f}.json").read_text())["methodology"]
    out["oncologybench"] = oncology.methodology()
    return out


def overall_weights():
    """The weights the site uses for Overall: configured evaluation counts."""
    d = json.loads((RAW / "results" / "v1" / "latest.json").read_text())
    return {b["id"]: b["overallWeightEvaluationCount"] for b in d["benchmarks"]}


def published_overall():
    """The site's Overall capability leaderboard, for checking against."""
    d = json.loads((RAW / "results" / "v1" / "latest.json").read_text())
    return pd.DataFrame([
        dict(mid=r["id"], model=r["model"], harness=r["harness"],
             overall=r["overallScorePct"], coverage=r["benchmarkCoverage"],
             missing=",".join(r.get("missingBenchmarks") or []))
        for r in d["capabilitiesLeaderboard"]])

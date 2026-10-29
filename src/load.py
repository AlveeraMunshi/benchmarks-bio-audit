"""Flatten the published per-evaluation records into one tidy frame.

One row = one (model x harness) x (benchmark x evaluation) cell, holding the
counts over that cell's attempts. Twelve boards ship under /data/v1/<id>.json;
OncologyBench has its own schema and is folded in from src/oncology.py.
"""
import json, pathlib
import pandas as pd

import oncology
import schema

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


def _read(path):
    """Read one published file, or say which command would create it."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is not here. Run `python3 src/fetch.py` to download the "
            "published files this audit reads.")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise schema.SchemaDrift(f"{path}: not valid JSON ({e}). Re-fetch it.") from e


def _v1_rows(fname):
    d = _read(V1 / f"{fname}.json")
    schema.check_v1_board(fname, d)
    bench = FILE_TO_BOARD.get(fname, fname)
    # `fields`, not `schema`: the module of that name is imported above, and a
    # local shadowing it turns every schema call in here into UnboundLocalError.
    fields, facets = d["perEvalSchema"], d.get("evalFacets", {})
    for m in d["models"]:
        for ev, vals in m["perEval"].items():
            # perEval ships bare count arrays; the board's own perEvalSchema
            # names the columns, so zip rather than hardcode the order.
            row = dict(zip(fields, vals))
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
    if df.label.isna().any():
        raise schema.SchemaDrift(
            f"boards with no display label: {sorted(df[df.label.isna()].bench.unique())}. "
            "A board id changed, or a new board shipped; update LABEL.")
    schema.check_tidy(df)
    return df


def methodology_text():
    """Each board's published methodology string, by board id."""
    out = {}
    for f in V1_BOARDS:
        out[FILE_TO_BOARD.get(f, f)] = _read(V1 / f"{f}.json")["methodology"]
    out["oncologybench"] = oncology.methodology()
    return out


# RefusalBench is the SAFEGUARDS board, not a capability board: it scores
# whether a model declines what it should, so it carries a weight in
# latest.json but takes no part in the capability Overall. Dropping it here
# keeps the unknown-id guard below meaningful - anything else new really is a
# capability board this audit has not accounted for.
NON_CAPABILITY = {"biosecbench-refusal"}


def overall_weights():
    """The weights the site uses for the capability Overall: each board's
    configured evaluation count. These are what make the published Overall
    reproducible - an unweighted mean of the thirteen boards matches nothing.
    """
    d = _read(RAW / "results" / "v1" / "latest.json")
    schema.check_results(d)
    w = {b["id"]: b["overallWeightEvaluationCount"]
         for b in d["benchmarks"] if b["id"] not in NON_CAPABILITY}
    # A board id we have no label for means the suite gained a capability
    # board. Failing here is the point: silently averaging twelve of fourteen
    # would still produce a plausible-looking number.
    unknown = set(w) - set(LABEL)
    if unknown:
        raise schema.SchemaDrift(
            f"Overall is weighted over board ids this audit does not know: "
            f"{sorted(unknown)}. A new capability board joined the Overall score.")
    return w


def published_overall():
    """The site's Overall capability leaderboard, for checking against."""
    d = _read(RAW / "results" / "v1" / "latest.json")
    schema.check_results(d)
    return pd.DataFrame([
        dict(mid=r["id"], model=r["model"], harness=r["harness"],
             overall=r["overallScorePct"], coverage=r["benchmarkCoverage"],
             missing=",".join(r.get("missingBenchmarks") or []))
        for r in d["capabilitiesLeaderboard"]])

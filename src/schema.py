"""What this audit assumes about benchmarks.bio's published shape.

Every claim here rests on files someone else publishes and can change without
telling us. Left unchecked, a renamed key surfaces as a KeyError three modules
away, or worse, as a plausible wrong number. So the assumptions are written
down once, checked at the boundary, and reported as what moved.
"""


class SchemaDrift(Exception):
    """The published files no longer have the shape this audit was built on."""


# per-evaluation counts, in the order the boards' `perEvalSchema` lists them
V1_PER_EVAL = ["correct", "refused", "timeout", "apiError", "runs"]
# "methodology" is in here because the central finding is a comparison against it
V1_BOARD_KEYS = ["perEvalSchema", "models", "evals", "methodology"]
V1_MODEL_KEYS = ["id", "name", "harness", "organization", "passRate", "ci", "perEval"]
ONCOLOGY_KEYS = ["metadata", "models", "modelResults"]
ONCOLOGY_PER_EVAL = ["attempts", "passed", "refused", "timeout"]
RESULTS_KEYS = ["benchmarks", "capabilitiesLeaderboard"]
BENCHMARK_KEYS = ["id", "overallWeightEvaluationCount"]


def _missing(where, got, want):
    gap = [k for k in want if k not in got]
    if gap:
        raise SchemaDrift(
            f"{where}: missing {gap}. Present: {sorted(got)[:12]}. "
            "The published shape changed; re-read the file before trusting any number.")


def check_v1_board(bench, doc):
    """One of the twelve boards under /data/v1/."""
    _missing(f"{bench}.json", doc, V1_BOARD_KEYS)
    _missing(f"{bench}.json perEvalSchema", doc["perEvalSchema"], V1_PER_EVAL)
    if not doc["models"]:
        raise SchemaDrift(f"{bench}.json: no models")
    _missing(f"{bench}.json models[0]", doc["models"][0], V1_MODEL_KEYS)
    width = len(doc["perEvalSchema"])
    for m in doc["models"][:3]:
        for ev, vals in list(m["perEval"].items())[:3]:
            if len(vals) != width:
                raise SchemaDrift(
                    f"{bench}.json {m['id']}/{ev}: {len(vals)} values for a "
                    f"{width}-field perEvalSchema")


def check_oncology(doc):
    _missing("oncologybench.json", doc, ONCOLOGY_KEYS)
    if not doc["models"]:
        raise SchemaDrift("oncologybench.json: no models")
    first = next(iter(doc["models"][0]["perEval"].values()))
    _missing("oncologybench.json perEval entry", first, ONCOLOGY_PER_EVAL)


def check_results(doc):
    """/results/v1/latest.json — the published Overall board and its weights."""
    _missing("results/v1/latest.json", doc, RESULTS_KEYS)
    if not doc["benchmarks"]:
        raise SchemaDrift("results/v1/latest.json: no benchmarks")
    _missing("results/v1/latest.json benchmarks[0]", doc["benchmarks"][0], BENCHMARK_KEYS)


def check_tidy(df, expect_boards=13):
    """The frame every downstream module reads."""
    want = ["bench", "eval_id", "mid", "runs", "refused", "correct",
            "gradeable", "attempted", "rate", "published_pass"]
    _missing("tidy frame", df.columns, want)
    if df.bench.nunique() != expect_boards:
        raise SchemaDrift(
            f"tidy frame: {df.bench.nunique()} boards, expected {expect_boards} "
            f"({sorted(df.bench.unique())})")
    bad = df[(df.correct > df.runs) | (df.refused > df.runs) | (df.runs <= 0)]
    if len(bad):
        raise SchemaDrift(
            f"tidy frame: {len(bad)} rows where counts are impossible "
            f"(correct or refused exceeds runs). First: {bad.iloc[0].to_dict()}")

"""The schema guards must FIRE, not merely exist.

src/schema.py exists to make an upstream shape change fail loudly at the
boundary instead of surfacing as a KeyError three modules deep - or, worse, as
a plausible wrong number. A guard nobody has ever seen reject anything is
decoration, so each test here hands it a deliberately broken copy of a real
published file and asserts it refuses.

Paired with the baseline test: the same guards must stay silent on the real
files, or they would be useless noise. Both directions are needed - one test
proves the guard can reject, the other proves it does not reject everything.
"""
import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import load                                                    # noqa: E402
import schema                                                  # noqa: E402

RAW = ROOT / "data" / "raw"


def _read(rel):
    return json.loads((RAW / rel).read_text())


@pytest.fixture(scope="module")
def board():
    # scBench is an ordinary v1 capability board, representative of the twelve.
    return _read("v1/scbench.json")


@pytest.fixture(scope="module")
def oncology():
    # OncologyBench ships its own schema, so it needs its own checker.
    return _read("oncologybench.json")


@pytest.fixture(scope="module")
def results():
    # latest.json carries the published Overall board and the weights.
    return _read("results/v1/latest.json")


def test_real_files_pass_every_guard(board, oncology, results):
    """The guards stay silent on the files as published. If this fails, the
    guards are too strict and will block an honest re-fetch."""
    schema.check_v1_board("scbench", board)
    schema.check_oncology(oncology)
    schema.check_results(results)
    schema.check_tidy(load.tidy())


def test_board_missing_methodology_is_caught(board):
    """The central finding compares behaviour against this string, so losing
    it must stop the run rather than silently skip the comparison."""
    d = copy.deepcopy(board)
    del d["methodology"]
    with pytest.raises(schema.SchemaDrift, match="methodology"):
        schema.check_v1_board("scbench", d)


def test_board_missing_a_count_column_is_caught(board):
    """Every score in this audit is built from these counts; a renamed one
    would otherwise read as a zero."""
    d = copy.deepcopy(board)
    d["perEvalSchema"] = [c for c in d["perEvalSchema"] if c != "runs"]
    with pytest.raises(schema.SchemaDrift, match="runs"):
        schema.check_v1_board("scbench", d)


def test_perval_row_width_mismatch_is_caught(board):
    """perEval rows are bare arrays zipped against perEvalSchema, so a width
    change would silently shift every count into the wrong column."""
    d = copy.deepcopy(board)
    first = next(iter(d["models"][0]["perEval"]))
    d["models"][0]["perEval"][first] = [1, 2, 3]
    with pytest.raises(schema.SchemaDrift, match="values for a"):
        schema.check_v1_board("scbench", d)


def test_empty_board_is_caught(board):
    """An empty models list would produce an empty frame and a clean run."""
    d = copy.deepcopy(board)
    d["models"] = []
    with pytest.raises(schema.SchemaDrift, match="no models"):
        schema.check_v1_board("scbench", d)


def test_model_missing_passrate_is_caught(board):
    """passRate is the published number the whole audit checks against."""
    d = copy.deepcopy(board)
    del d["models"][0]["passRate"]
    with pytest.raises(schema.SchemaDrift, match="passRate"):
        schema.check_v1_board("scbench", d)


def test_oncology_missing_refused_is_caught(oncology):
    """Refusals are the subject of the finding; losing the column would make
    both scoring rules collapse into one and the finding disappear."""
    d = copy.deepcopy(oncology)
    first = next(iter(d["models"][0]["perEval"]))
    del d["models"][0]["perEval"][first]["refused"]
    with pytest.raises(schema.SchemaDrift, match="refused"):
        schema.check_oncology(d)


def test_results_missing_leaderboard_is_caught(results):
    """Without it there is nothing to reproduce the Overall score against."""
    d = copy.deepcopy(results)
    del d["capabilitiesLeaderboard"]
    with pytest.raises(schema.SchemaDrift, match="capabilitiesLeaderboard"):
        schema.check_results(d)


def test_results_missing_a_weight_is_caught(results):
    """The weights are what make Overall reproducible at all - an unweighted
    mean of the thirteen boards matches none of the 38 published rows."""
    d = copy.deepcopy(results)
    del d["benchmarks"][0]["overallWeightEvaluationCount"]
    with pytest.raises(schema.SchemaDrift, match="overallWeightEvaluationCount"):
        schema.check_results(d)


def test_a_new_board_is_caught():
    """Thirteen boards is load-bearing: the finding is '9 of 13', and a
    fourteenth would change the claim without changing any code."""
    with pytest.raises(schema.SchemaDrift, match="expected 14"):
        schema.check_tidy(load.tidy(), expect_boards=14)


def test_impossible_counts_are_caught():
    """correct > runs cannot happen in honest data, so it means the columns
    have been misread - exactly the failure the width check above guards."""
    df = load.tidy().copy()
    df.loc[df.index[0], "correct"] = df.loc[df.index[0], "runs"] + 5
    with pytest.raises(schema.SchemaDrift, match="impossible"):
        schema.check_tidy(df)


def test_refusalbench_is_excluded_from_the_overall_weights():
    """RefusalBench is the SAFEGUARDS board: it scores whether a model declines
    what it should, and takes no part in the capability Overall even though
    latest.json gives it a weight. Including it would silently change every
    Overall score."""
    w = load.overall_weights()
    assert "biosecbench-refusal" not in w
    assert len(w) == 13, f"expected 13 capability weights, got {sorted(w)}"

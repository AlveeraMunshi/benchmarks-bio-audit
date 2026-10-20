"""The contract a benchmark suite should be able to state about its own scores.

Two of these pass and two fail against the data published on 2026-10-20. The
failures are the finding: they are what a CI job would have caught.

    pytest tests/ -v
"""
import json, pathlib, re

import pytest

import policy
import scoring

RAW = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw" / "v1"
TOL = 0.01


def test_published_scores_are_reproducible(df):
    """Baseline: our harness agrees with every number on the site."""
    got = scoring.board(df, scoring.as_published).set_index(["bench", "mid"]).score
    want = df.groupby(["bench", "mid"]).published_pass.first()
    err = (got - want).abs()
    assert err.max() < TOL, f"{int((err >= TOL).sum())} cells disagree"


def test_each_board_declares_the_rule_it_actually_uses(df):
    """A board's declared refusal rule must be the one its numbers imply."""
    wrong = {}
    for bench in sorted(policy.DECLARED):
        inferred, hits, n = policy.infer_rule(df, bench)
        if inferred != policy.DECLARED[bench].refusal:
            wrong[bench] = (policy.DECLARED[bench].refusal, inferred, hits, n)
    assert not wrong, f"declared rule does not match published numbers: {wrong}"


def test_methodology_text_matches_the_implementation(df):
    """FAILS TODAY on 9 of 12 boards.

    Eleven of the twelve boards carry identical boilerplate saying refusals
    are excluded from the denominator; only the two biosecurity boards do it.
    MetagenomicsBench is the counter-example and carries a bespoke, accurate
    string ("Refusals and timeouts both count as failures and stay in the
    denominator"), which is good evidence the rule is deliberate and the text
    on the other boards is simply stale.
    """
    says_excluded = re.compile(r"refusals are excluded from the denominator", re.I)
    mismatched = []
    for bench in sorted(policy.DECLARED):
        text = json.loads((RAW / f"{bench}.json").read_text())["methodology"]
        documented = "exclude" if says_excluded.search(text) else "fail"
        actual, _, _ = policy.infer_rule(df, bench)
        if documented != actual:
            mismatched.append(f"{bench}: documented={documented} actual={actual}")
    assert not mismatched, (
        f"{len(mismatched)}/12 boards contradict their own methodology string "
        "(MetagenomicsBench is the one that documents it correctly):\n  "
        + "\n  ".join(mismatched))


def test_overall_does_not_average_boards_with_different_rules(df):
    """FAILS TODAY.

    The Overall score is the mean of twelve boards. Two price a refusal at
    zero cost and ten price it as a wrong answer, so the mean is taken over
    two different currencies.
    """
    rules = {b: policy.infer_rule(df, b)[0] for b in policy.DECLARED}
    distinct = sorted(set(rules.values()))
    counts = {r: sum(v == r for v in rules.values()) for r in distinct}
    assert len(distinct) == 1, (
        f"Overall averages {len(distinct)} different refusal rules: {counts}. "
        "A refusal is free on the 'exclude' boards and fatal on the 'fail' boards.")


@pytest.mark.parametrize("rule", ["exclude", "fail"])
def test_single_rule_overall_is_well_defined(df, rule):
    """The proposed fix: one declared currency, coverage carried up, and rows
    below the coverage floor reported but not ranked."""
    o = policy.overall(df, rule)
    assert o.refusal_rule.nunique() == 1
    assert o[o.rankable]["rank"].notna().all()
    assert o[~o.rankable]["rank"].isna().all()

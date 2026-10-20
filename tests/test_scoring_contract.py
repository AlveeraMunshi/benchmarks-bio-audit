"""The contract a benchmark suite should be able to state about its own scores.

Five of these pass and two fail against the data published on 2026-10-20. The
failures are the finding: they are what a CI job would have caught.

    pytest tests/ -v
"""
import json, pathlib, re

import numpy as np
import pytest

import load
import policy
import scoring

RAW = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"
TOL = 0.01


def test_published_board_scores_are_reproducible(df):
    """Baseline: our harness agrees with every per-board number on the site."""
    got = scoring.board(df, scoring.as_published).set_index(["bench", "mid"]).score
    want = df.groupby(["bench", "mid"]).published_pass.first()
    err = (got - want).abs()
    assert err.max() < TOL, f"{int((err >= TOL).sum())} of {len(err)} board cells disagree"


def test_published_overall_is_reproducible(df):
    """And with the Overall column, which is an evaluation-count WEIGHTED mean
    across the thirteen capability boards, not an unweighted one."""
    got = scoring.overall(df, scoring.as_published, min_boards=1).score
    want = load.published_overall().set_index("mid").overall
    common = got.index.intersection(want.index)
    assert len(common) == len(want), "some published rows are missing from the rebuild"
    err = (got[common] - want[common]).abs()
    assert err.max() < TOL, f"{int((err >= TOL).sum())} of {len(err)} Overall rows disagree"


def test_overall_weighting_is_not_unweighted(df):
    """Guard the weighting itself: an unweighted mean must NOT reproduce the
    site, or someone has quietly changed the aggregation."""
    b = scoring.board(df, scoring.as_published)
    unweighted = b.groupby("mid").score.mean()
    want = load.published_overall().set_index("mid").overall
    common = unweighted.index.intersection(want.index)
    exact = int(((unweighted[common] - want[common]).abs() < TOL).sum())
    assert exact == 0, f"unweighted mean unexpectedly reproduces {exact} rows"


def test_each_board_declares_the_rule_it_actually_uses(df):
    """A board's declared refusal rule must be the one its numbers imply."""
    wrong = {b: (policy.DECLARED[b].refusal, policy.infer_rule(df, b)[0])
             for b in sorted(policy.DECLARED)
             if policy.infer_rule(df, b)[0] != policy.DECLARED[b].refusal}
    assert not wrong, f"declared rule does not match published numbers: {wrong}"


def test_methodology_text_matches_the_implementation(df):
    """FAILS TODAY on 9 of 13 boards.

    Eleven of the thirteen boards carry identical boilerplate saying refusals
    are excluded from the denominator; only the two biosecurity boards do it.
    MetagenomicsBench and OncologyBench are the counter-examples and describe
    the failure rule accurately, which is good evidence the rule is deliberate
    and the text on the other nine is simply stale.
    """
    says_excluded = re.compile(r"refusals are excluded from the denominator", re.I)
    texts = load.methodology_text()
    mismatched = []
    for bench in sorted(policy.DECLARED):
        documented = "exclude" if says_excluded.search(texts[bench]) else "fail"
        actual, _, _ = policy.infer_rule(df, bench)
        if documented != actual:
            mismatched.append(f"{bench}: documented={documented} actual={actual}")
    assert not mismatched, (
        f"{len(mismatched)}/13 boards contradict their own methodology string "
        f"(MetagenomicsBench and OncologyBench document theirs correctly):\n  "
        + "\n  ".join(mismatched))


def test_overall_does_not_average_boards_with_different_rules(df):
    """FAILS TODAY.

    Overall is a weighted mean of thirteen boards. Two price a refusal at zero
    cost and eleven price it as a wrong answer, so the mean is taken over two
    different currencies.
    """
    rules = {b: policy.infer_rule(df, b)[0] for b in policy.DECLARED}
    counts = {r: sum(v == r for v in rules.values()) for r in sorted(set(rules.values()))}
    assert len(counts) == 1, (
        f"Overall averages {len(counts)} different refusal rules: {counts}. "
        "A refusal is free on the 'exclude' boards and fatal on the rest.")


@pytest.mark.parametrize("rule", ["exclude", "fail"])
def test_single_rule_overall_is_well_defined(df, rule):
    """The proposed fix: one declared currency, coverage carried up, and a rank
    for every row that earns one."""
    o = policy.overall(df, rule)
    assert o.refusal_rule.nunique() == 1
    assert o["rank"].notna().all()
    assert o.score.between(0, 100).all()

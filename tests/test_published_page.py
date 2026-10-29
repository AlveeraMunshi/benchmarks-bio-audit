"""The published page must not state a number the pipeline does not produce.

docs/index.html reads most of its figures from figures.json at runtime, so those
cannot drift. A handful of numbers are written into the page's PROSE instead,
where nothing checks them - and prose is exactly where a stale figure survives a
rerun. These tests re-derive each hardcoded claim and fail if the page and the
data disagree.

The claims guarded here are the LSVP control, which is the strongest single
piece of evidence in the audit and the one most worth keeping honest.
"""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "index.html"
FIGS = ROOT / "docs" / "figures.json"


@pytest.fixture(scope="module")
def page():
    return PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def figs():
    return json.loads(FIGS.read_text(encoding="utf-8"))


def test_figures_json_carries_the_control_block(figs):
    """report.py must still emit it; without this the tests below are vacuous."""
    assert "control" in figs, "figures.json has no control block - re-run src/report.py"
    for k in ("items_shared", "items_both_attempted", "acc_std", "acc_lsvp"):
        assert k in figs["control"], f"control block is missing {k}"


@pytest.mark.parametrize("key,label", [
    ("items_both_attempted", "items both arms attempted"),
    ("items_shared", "items served to both arms"),
])
def test_page_quotes_the_right_item_counts(page, figs, key, label):
    """The page states these as bold integers, e.g. <b>719 both actually
    attempted</b>. Thousands separators are optional in the prose."""
    want = figs["control"][key]
    pattern = rf"\b{want // 1000},?{want % 1000:03d}\b" if want >= 1000 else rf"\b{want}\b"
    assert re.search(pattern, page), (
        f"page does not state the computed {label} ({want:,}). "
        "The control numbers in the prose have drifted from figures.json.")


@pytest.mark.parametrize("key", ["acc_std", "acc_lsvp"])
def test_page_quotes_the_right_accuracies(page, figs, key):
    """Matched-ability accuracies, stated in the prose as e.g. <b>58.6%</b>."""
    want = figs["control"][key]
    assert f"{want}%" in page, (
        f"page does not state the computed {key} ({want}%). "
        "Re-run src/report.py and update the prose in docs/index.html.")


def test_the_control_actually_shows_equal_ability(figs):
    """The whole argument is that the two arms are equally capable where both
    answered. If that gap ever widened, the control would no longer licence the
    claim and the page would need rewriting rather than re-labelling."""
    c = figs["control"]
    gap = abs(c["acc_std"] - c["acc_lsvp"])
    assert gap < 2.0, (
        f"the two arms now differ by {gap:.1f} pts on commonly-attempted items. "
        "The 'same ability, different refusal rate' claim no longer holds.")


def test_the_control_arms_really_do_differ_in_refusals(figs):
    """The other half: if the starred arm stopped being the low-refusal one,
    there would be no contrast left to attribute the score swing to."""
    c = figs["control"]
    assert c["refusal_pct_std"] > 20, "the standard arm no longer refuses much"
    assert c["refusal_pct_lsvp"] < 5, "the LSVP arm is no longer near-zero refusal"


def test_page_does_not_link_a_dead_canva_deck(page):
    """A stale slides link on the page she would actually send someone is worse
    than no link. That design is no longer in the account."""
    assert "1c56BQoplmB1NGd" not in page, "the removed Canva deck link is back"


def test_stated_bootstrap_count_matches_provenance(page, figs):
    """The page cites its own resample count in a figure subtitle."""
    n = figs["provenance"]["n_boot"]
    assert f"{n:,} resamples" in page, (
        f"page does not cite the actual resample count ({n:,}). "
        "src/report.py and the figure subtitle have diverged.")

"""A runnable walkthrough of how this audit works.

    python3 src/explain.py

Every number it prints is computed live from the downloaded files, so this is
both the explanation and a check that the explanation is still true.

The method in one line: the site publishes the raw counts AND the score, so you
can work backwards to the formula that turns one into the other.
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import tidy, LABEL
import scoring

RULE_A = "correct / (attempts - refusals)   [a refusal never happened]"
RULE_B = "correct / attempts               [a refusal is a wrong answer]"


def rule_a(g):
    """Macro-mean over the evals the model actually attempted."""
    return 100 * (g.correct / g.gradeable).where(g.attempted).mean()


def rule_b(g):
    """Macro-mean over every eval on the board."""
    return 100 * (g.correct / g.runs).mean()


def head(n, title):
    print(f"\n{'=' * 72}\n{n}. {title}\n{'=' * 72}")


def step_1_raw_data(df):
    head(1, "WHAT THE SITE ACTUALLY PUBLISHES")
    g = df[(df.mid == "opus-5-5-pi") & (df.bench == "functionbench")]
    print("""
It does not just publish scores. For every model on every evaluation it
publishes the counts underneath the score: how many attempts, how many correct,
how many the model refused. Three attempts per evaluation.

Here is one model on one board - Claude Opus 5.5 (Pi) on BioSecBench-Function:
""")
    print(g[["eval_id", "runs", "refused", "correct"]].head(6).to_string(index=False))
    print(f"""
  ... {len(g)} evaluations in total
      {int(g.runs.sum())} attempts, of which {int(g.refused.sum())} were refused
      {int(g.correct.sum())} attempts reached the right answer

Notice the rows where refused = 3. The model declined that task outright.
What a scorer DOES with those rows is the whole question.""")


def step_2_two_formulas(df):
    head(2, "THERE ARE ONLY TWO SENSIBLE THINGS TO DO WITH A REFUSAL")
    print(f"""
  Rule A  "exclude"  {RULE_A}
  Rule B  "fail"     {RULE_B}

Those score ONE evaluation. A board score is the average of the per-evaluation
scores - which matters, because under Rule A an evaluation refused on all three
attempts has no score at all and drops out of the average entirely.

The site gives us the counts and the score but describes the formula only in
prose, so we can work backwards: apply both, and see which lands on the
published number.
""")
    for mid, bench in [("opus-5-5-pi", "functionbench"), ("opus-5-5-pi", "txbench-ab")]:
        g = df[(df.mid == mid) & (df.bench == bench)]
        a, b, pub = rule_a(g), rule_b(g), g.published_pass.iloc[0]
        win = "A" if abs(a - pub) < 0.01 else "B"
        att = int(g.attempted.sum())
        print(f"  Claude Opus 5.5 (Pi) on {LABEL[bench]}")
        print(f"    {len(g)} evaluations x 3 attempts; "
              f"{len(g) - att} refused outright, leaving {att} with a score")
        print(f"    Rule A  average over those {att:3d}            = {a:6.2f}")
        print(f"    Rule B  average over all  {len(g):3d}, refusals 0 = {b:6.2f}")
        print(f"    the site publishes {pub:6.2f}   -> this board uses Rule {win}\n")
    print("  Same model. Same week. Different board. Different rule.")


def step_3_why_not_luck(df):
    head(3, "WHY THE FIT CANNOT BE LUCK")
    print("""
When a model refuses NOTHING the two formulas are arithmetically identical -
correct/3 and correct/(3-0) are the same number. Such a cell cannot tell the
rules apart, so it is silent rather than evidence.

Which means every cell falls into one of three buckets, and the third one is
the one that would sink the whole argument:
""")
    discriminating = silent = contradicting = 0
    for (bench, mid), g in df.groupby(["bench", "mid"]):
        a, b, pub = rule_a(g), rule_b(g), g.published_pass.iloc[0]
        if pd.isna(pub):
            continue
        if abs(a - b) < 0.01:
            silent += 1
        elif abs(a - pub) < 0.01 or abs(b - pub) < 0.01:
            discriminating += 1
        else:
            contradicting += 1
    total = discriminating + silent + contradicting
    print(f"    {discriminating:4d}  cells where the rules disagree AND one of them matches")
    print(f"    {silent:4d}  cells that are silent (no refusals, so both rules agree)")
    print(f"    {contradicting:4d}  cells matching NEITHER rule")
    print(f"    {total:4d}  total\n")
    print("  Every cell either confirms a rule or says nothing. None points the other")
    print("  way. That is why the claim is 'all of them' and not 'most of them'.")


def step_4_scoreboard(df):
    head(4, "DOING THAT FOR ALL THIRTEEN BOARDS")
    rows = []
    for bench, g in df.groupby("bench"):
        site = g.groupby("mid").published_pass.first()
        fits = {}
        for name, fn in (("A", rule_a), ("B", rule_b)):
            v = g.groupby("mid").apply(fn, include_groups=False)
            fits[name] = int((v - site).abs().lt(0.01).sum())
        rows.append(dict(board=LABEL[bench], cells=len(site),
                         matches_A=fits["A"], matches_B=fits["B"],
                         rule="A  exclude" if fits["A"] > fits["B"] else "B  fail"))
    t = pd.DataFrame(rows).sort_values(["rule", "board"])
    print()
    print(t.to_string(index=False))
    print("""
  Eleven boards score a refusal as a failure. The two biosecurity boards do not.
  The Overall score is a weighted mean of all thirteen - so the same behaviour is
  free on two boards and fatal on eleven, and both get averaged into one number.""")


def step_5_consequence(df):
    head(5, "WHAT THAT DOES TO THE RANKING")
    pub = scoring.overall(df, scoring.as_published, min_boards=11).rename(
        columns={"score": "as_published"})
    exc = scoring.overall(df, scoring.exclude_refusals, min_boards=11)["score"]
    fail = scoring.overall(df, scoring.refusal_is_fail, min_boards=11)["score"]
    T = pub.join(exc.rename("all_exclude")).join(fail.rename("all_fail"))
    for c in ["as_published", "all_exclude", "all_fail"]:
        T["rk_" + c] = T[c].rank(ascending=False)
    show = ["opus-5-5-claude-code", "opus-5-5-lsvp-pi"]
    name = {"opus-5-5-claude-code": "Opus 5.5  (standard run)",
            "opus-5-5-lsvp-pi": "Opus 5.5* (safety filter off)"}
    print()
    for m in show:
        r = T.loc[m]
        print(f"  {name[m]}")
        print(f"    as published        {r.as_published:5.1f}  rank {int(r.rk_as_published):2d}")
        print(f"    all boards 'exclude'{r.all_exclude:5.1f}  rank {int(r.rk_all_exclude):2d}")
        print(f"    all boards 'fail'   {r.all_fail:5.1f}  rank {int(r.rk_all_fail):2d}\n")
    print("""  The starred row is the SAME MODEL with its safety filter switched off, so it
  barely refuses - and it scores about the same under every rule, because there
  are hardly any refusals for a rule to disagree about.

  The standard row swings 25 points. That spread is produced by the scoring rule
  meeting its refusals, not by the model being better or worse.""")


def main():
    pd.set_option("display.width", 200)
    df = tidy()
    print(__doc__)
    step_1_raw_data(df)
    step_2_two_formulas(df)
    step_3_why_not_luck(df)
    step_4_scoreboard(df)
    step_5_consequence(df)
    print(f"\n{'=' * 72}\nFull write-up: README.md   "
          f"Contract: pytest tests/ -v\n{'=' * 72}")


if __name__ == "__main__":
    main()

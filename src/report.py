"""Run every check and write the tables behind the findings."""
import pathlib, sys
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import tidy
import scoring, items as items_mod, stability

OUT = pathlib.Path(__file__).resolve().parents[1] / "out"


def main():
    OUT.mkdir(exist_ok=True)
    df = tidy()
    log = []
    def say(s=""):
        print(s); log.append(s)

    say("## 0. Reproduction")
    pub = scoring.board(df, scoring.as_published)
    site = df.groupby(["bench", "mid"]).published_pass.first().rename("site").reset_index()
    chk = pub.merge(site, on=["bench", "mid"]); chk["err"] = (chk.score - chk.site).abs()
    say(f"reproduced {int((chk.err < 0.01).sum())}/{len(chk)} published board scores "
        f"(max error {chk.err.max():.4f} pts)")
    say(f"runs={int(df.runs.sum()):,}  refusals={int(df.refused.sum()):,} "
        f"({100*df.refused.sum()/df.runs.sum():.2f}%)  spend=${df.costSum.sum():,.0f}  "
        f"tokens={df.tokSum.sum()/1e9:.0f}B")

    say("\n## 1. The scoring rule is not the documented one on 10 of 12 boards")
    rules = {"exclude_refusals": scoring.exclude_refusals,
             "refusal_is_fail": scoring.refusal_is_fail}
    rows = []
    for b, g in df.groupby("bench"):
        s = site[site.bench == b].set_index("mid").site
        rec = {"bench": b}
        for name, f in rules.items():
            v = g.groupby("mid").apply(f, include_groups=False)
            rec[name] = int((v - s).abs().lt(0.01).sum())
        rec["cells"] = g.mid.nunique()
        rec["rule_in_use"] = max(rules, key=lambda k: rec[k])
        rows.append(rec)
    R = pd.DataFrame(rows); R.to_csv(OUT / "01_rule_per_board.csv", index=False)
    say(R.to_string(index=False))

    ov = scoring.overall(df, scoring.as_published).rename(columns={"score": "as_published"})
    ov = ov.join(scoring.overall(df, scoring.exclude_refusals)["score"].rename("all_exclude"))
    ov = ov.join(scoring.overall(df, scoring.refusal_is_fail)["score"].rename("all_fail"))
    ov["rank_published"] = ov.as_published.rank(ascending=False)
    ov["rank_all_exclude"] = ov.all_exclude.rank(ascending=False)
    ov["move"] = ov.rank_published - ov.rank_all_exclude
    ov.sort_values("as_published", ascending=False).to_csv(OUT / "02_overall_by_rule.csv")
    say("\nbiggest rank move when the documented rule is applied uniformly:")
    say(ov.reindex(ov.move.abs().sort_values(ascending=False).index).head(4)[
        ["as_published", "all_exclude", "min_coverage", "rank_published",
         "rank_all_exclude", "move"]].to_string(float_format=lambda x: "%.1f" % x))

    say("\n## 2. On the two refusal-excluding boards, rank rests on a handful of items")
    frames = []
    for b in ["functionbench", "surveillancebench", "scbench"]:
        st = stability.rank_intervals(df, b); st["bench"] = b; frames.append(st)
        say(f"\n{b}:")
        say(st.head(6)[["mid", "score", "items_scored", "shown_rank",
                        "rank_lo", "rank_hi", "p_rank1"]]
            .to_string(index=False, float_format=lambda x: "%.1f" % x))
    pd.concat(frames).to_csv(OUT / "03_rank_intervals.csv", index=False)

    say("\n## 3. Item information and what the suite spends on items that move nothing")
    it = items_mod.item_table(df); it.to_csv(OUT / "04_items.csv", index=False)
    tot = df.costSum.sum()
    say(f"items analysed: {len(it)}")
    say(f"  never solved by any model : {int(it.dead.sum()):4d} ({100*it.dead.mean():.1f}%)  "
        f"${it.loc[it.dead,'cost'].sum():,.0f}")
    say(f"  solved by nearly all      : {int(it.saturated.sum()):4d} ({100*it.saturated.mean():.1f}%)  "
        f"${it.loc[it.saturated,'cost'].sum():,.0f}")
    say(f"  uninformative overall     : {int(it.uninformative.sum()):4d} "
        f"({100*it.uninformative.mean():.1f}%)  ${it.loc[it.uninformative,'cost'].sum():,.0f} "
        f"= {100*it.loc[it.uninformative,'cost'].sum()/tot:.1f}% of spend")
    fid = items_mod.subset_fidelity(df, it); fid.to_csv(OUT / "05_subset_fidelity.csv", index=False)
    say("\nkeeping only the most discriminating items:")
    say(fid.to_string(index=False, float_format=lambda x: "%.3f" % x))

    (OUT / "findings.txt").write_text("\n".join(log))
    say(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

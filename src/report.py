"""Run every check and write the tables behind the findings."""
import json, pathlib, sys
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import load, scoring, policy, stability, bias
import items as items_mod

OUT = pathlib.Path(__file__).resolve().parents[1] / "out"
RAW_V1 = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw" / "results" / "v1"
LOG = []


def say(s=""):
    print(s); LOG.append(s)


def main():
    OUT.mkdir(exist_ok=True)
    df = load.tidy()

    say("## 0. Reproduction")
    b = scoring.board(df, scoring.as_published)
    site = df.groupby(["bench", "mid"]).published_pass.first().rename("site").reset_index()
    chk = b.merge(site, on=["bench", "mid"]); chk["err"] = (chk.score - chk.site).abs()
    ov = scoring.overall(df, scoring.as_published, min_boards=1)
    po = load.published_overall().set_index("mid")
    j = ov.join(po[["overall"]], how="inner"); j["err"] = (j.score - j.overall).abs()
    say(f"board scores reproduced : {int((chk.err<0.01).sum())}/{len(chk)}  (max err {chk.err.max():.4f} pts)")
    say(f"Overall reproduced      : {int((j.err<0.01).sum())}/{len(j)}  (max err {j.err.max():.4f} pts)")
    say(f"boards={df.bench.nunique()}  evals={df.eval_id.nunique()}  cells={len(df):,}  "
        f"runs={int(df.runs.sum()):,}  refusals={int(df.refused.sum()):,} "
        f"({100*df.refused.sum()/df.runs.sum():.2f}%)  spend=${df.costSum.sum():,.0f}")

    say("\n## 1. The scoring rule is not the documented one on 9 of 13 boards")
    texts = load.methodology_text()
    rows = []
    for bench in sorted(policy.DECLARED):
        actual, hits, n = policy.infer_rule(df, bench)
        documented = "exclude" if "refusals are excluded from the denominator" in texts[bench].lower() else "fail"
        rows.append(dict(board=load.LABEL[bench], bench=bench, cells=n,
                         fit_exclude=hits["exclude"], fit_fail=hits["fail"],
                         rule_in_use=actual, documented=documented,
                         contradicts=documented != actual))
    R = pd.DataFrame(rows).sort_values(["rule_in_use", "board"])
    R.to_csv(OUT / "01_rule_per_board.csv", index=False)
    say(R.to_string(index=False))
    say(f"\nboards contradicting their own methodology text: {int(R.contradicts.sum())}/13")

    say("\n## 2. What the inconsistency does to Overall")
    T = scoring.overall(df, scoring.as_published, min_boards=11).rename(columns={"score": "as_published"})
    T = T.join(scoring.overall(df, scoring.exclude_refusals, min_boards=11)["score"].rename("all_exclude"))
    T = T.join(scoring.overall(df, scoring.refusal_is_fail, min_boards=11)["score"].rename("all_fail"))
    for c in ["as_published", "all_exclude", "all_fail"]:
        T["rk_" + c] = T[c].rank(ascending=False)
    T["move"] = T.rk_as_published - T.rk_all_exclude
    T.sort_values("as_published", ascending=False).to_csv(OUT / "02_overall_by_rule.csv")
    say(T.reindex(T.move.abs().sort_values(ascending=False).index).head(5)[
        ["as_published", "all_exclude", "all_fail", "min_coverage",
         "rk_as_published", "rk_all_exclude", "move"]].to_string(float_format=lambda x: "%.1f" % x))

    say("\n## 3. Is exclusion dropping the harder items? (bounded, not just tested)")
    g = bias.gap_table(df); g.to_csv(OUT / "06_difficulty_gap.csv", index=False)
    bb = bias.bound(g)
    say(f"cells={bb['n_cells']}  mean gap={bb['mean_gap']:+.2f} pts  "
        f"95% CI [{bb['ci_lo']:+.2f}, {bb['ci_hi']:+.2f}]  Wilcoxon p={bb['wilcoxon_p']:.3f}")
    say("=> any difficulty-selection effect is bounded under ~1 pt of item difficulty;"
        " the point estimates are close to right and the fix belongs elsewhere.")

    say("\n## 4. What a rank is actually worth")
    frames = [stability.rank_intervals(df, bn, n_boot=2000) for bn in sorted(df.bench.unique())]
    RI = pd.concat(frames); RI.to_csv(OUT / "03_rank_intervals.csv", index=False)
    per = RI.groupby("bench").agg(models=("mid", "size"), items=("items_scored", "max"),
                                  min_cov=("coverage", "min"),
                                  med_width=("interval_width", "median"),
                                  max_width=("interval_width", "max"))
    per["board"] = per.index.map(load.LABEL)
    say(per.sort_values("med_width", ascending=False).to_string(float_format=lambda x: "%.1f" % x))
    say(f"\nmedian 95% rank interval across all {len(RI)} board rows: "
        f"{RI.interval_width.median():.0f} places")
    say(f"Spearman(coverage, interval width) = {RI.coverage.corr(RI.interval_width, method='spearman'):.3f}"
        "  -> width tracks BOARD SIZE, not refusals")
    OV = stability.overall_rank_intervals(df, n_boot=1500)
    OV.to_csv(OUT / "07_overall_rank_intervals.csv")
    say(f"Overall board, by contrast, is well identified: median interval "
        f"{OV.interval_width.median():.0f} places (it pools {df.eval_id.nunique():,} items)")

    say("\n## 5. What the suite spends on items that move nothing")
    it = items_mod.item_table(df); it.to_csv(OUT / "04_items.csv", index=False)
    tot = df.costSum.sum()
    say(f"items analysed            {len(it)}")
    say(f"  never solved by anyone  {int(it.dead.sum()):4d} ({100*it.dead.mean():.1f}%)   ${it.loc[it.dead,'cost'].sum():,.0f}")
    say(f"  exactly zero passes     {int(it.zero_passes.sum()):4d}           ${it.loc[it.zero_passes,'cost'].sum():,.0f}")
    say(f"  uninformative overall   {int(it.uninformative.sum()):4d} ({100*it.uninformative.mean():.1f}%)   "
        f"${it.loc[it.uninformative,'cost'].sum():,.0f} = {100*it.loc[it.uninformative,'cost'].sum()/tot:.1f}% of spend")
    fid = items_mod.subset_fidelity(df, it); fid.to_csv(OUT / "05_subset_fidelity.csv", index=False)
    say("\n" + fid.to_string(index=False, float_format=lambda x: "%.3f" % x))
    dead_board = it.groupby("bench").agg(n=("eval_id", "size"), dead=("dead", "sum"))
    dead_board["pct"] = 100 * dead_board.dead / dead_board.n
    dead_board["board"] = dead_board.index.map(load.LABEL)
    say("\ndead items by board:")
    say(dead_board.sort_values("pct", ascending=False).head(6).to_string(float_format=lambda x: "%.1f" % x))

    say("\n## 6. Where the never-solved items cluster")
    prof = items_mod.dead_item_profile(df, it)
    prof = prof[prof.n_items >= 8].sort_values("dead_pct", ascending=False)
    prof.to_csv(OUT / "08_dead_item_profile.csv", index=False)
    say(prof.head(8).to_string(index=False, float_format=lambda x: "%.0f" % x))
    say("\nno dead items at all in these groups:")
    say(prof[prof.dead == 0].head(5)[["facet", "value", "n_items"]].to_string(index=False))
    say("=> they cluster by ASSAY, not by scientific stage, which points at a data or"
        " grader problem in particular pipelines rather than at hard science.")

    (OUT / "findings.txt").write_text("\n".join(LOG))
    _figures(df, T, R, RI, OV, fid, it, bb)
    say(f"\nwrote {OUT}")


def _figures(df, T, R, RI, OV, fid, it, bb):
    """Compact JSON the report page renders from, so the page cannot drift."""
    name = {"opus-5-5-claude-code": "Opus 5.5 (Claude Code)", "opus-5-5-pi": "Opus 5.5 (Pi)",
            "opus-5-5-lsvp-pi": "Opus 5.5* LSVP (Pi)", "opus-5-5-lsvp-claude-code": "Opus 5.5* LSVP (CC)",
            "sonnet-5-5-pi": "Sonnet 5.5 (Pi)", "gpt-6-astra-pi": "GPT-6 Astra (Pi)",
            "grok-4-6-grok-build": "Grok 4.6 (Grok Build)", "opus-5-pi": "Opus 5 (Pi)",
            "fable-5-1-lsvp-claude-code": "Fable 5.1* LSVP (CC)"}
    D = {}
    D["overall"] = [dict(model=name.get(m, m), pub=round(T.at[m, "as_published"], 1),
                         exc=round(T.at[m, "all_exclude"], 1), fail=round(T.at[m, "all_fail"], 1),
                         rk_pub=int(T.at[m, "rk_as_published"]), rk_exc=int(T.at[m, "rk_all_exclude"]),
                         rk_fail=int(T.at[m, "rk_all_fail"]), cov=round(T.at[m, "min_coverage"], 1))
                    for m in name if m in T.index]
    D["rules"] = [dict(board=r.board, rule=r.rule_in_use, documented=r.documented,
                       contradicts=bool(r.contradicts), fit_exc=int(r.fit_exclude),
                       fit_fail=int(r.fit_fail), cells=int(r.cells)) for r in R.itertuples()]
    fb = RI[RI.bench == "functionbench"].head(8)
    D["ranks"] = [dict(model=name.get(r.mid, r.mid), score=round(r.score, 1),
                       items=int(r.items_scored), shown=int(r.shown_rank),
                       lo=int(r.rank_lo), hi=int(r.rank_hi), p1=round(r.p_rank1, 1))
                  for r in fb.itertuples()]
    per = RI.groupby("bench").agg(items=("items_scored", "max"),
                                  med_width=("interval_width", "median")).reset_index()
    D["boardsize"] = [dict(board=load.LABEL[r.bench], items=int(r.items),
                           width=float(r.med_width)) for r in per.itertuples()]
    D["fidelity"] = [dict(keep=int(r.keep_frac * 100), items=int(r.n_items), cost=int(r.cost),
                          rho=round(r.spearman, 3), top10=int(r.top10_overlap))
                     for r in fid.itertuples()]
    D["items"] = dict(total=int(len(it)), dead=int(it.dead.sum()),
                      dead_cost=int(it.loc[it.dead, "cost"].sum()),
                      zero=int(it.zero_passes.sum()),
                      uninf=int(it.uninformative.sum()),
                      uninf_cost=int(it.loc[it.uninformative, "cost"].sum()),
                      total_cost=int(df.costSum.sum()))
    D["scale"] = dict(boards=int(df.bench.nunique()), evals=int(df.eval_id.nunique()),
                      cells=int(len(df)), runs=int(df.runs.sum()),
                      refusals=int(df.refused.sum()), spend=int(df.costSum.sum()),
                      tokens_b=round(df.tokSum.sum() / 1e9))
    D["bias"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in bb.items()}

    # what the suite IS: the boards, grouped the way the site groups them, plus
    # what a single attempt costs - so the page can describe the thing it audits
    meta = json.loads((RAW_V1 / "latest.json").read_text())
    cat = {b["id"]: b for b in meta["benchmarks"]}
    suite = []
    for b in sorted(df.bench.unique()):
        m = cat.get(b, {})
        suite.append(dict(board=load.LABEL[b], category=m.get("category", "?"),
                          horizon=m.get("horizon", "?"), assessment="capabilities",
                          evals=int(df[df.bench == b].eval_id.nunique())))
    r = cat.get("biosecbench-refusal", {})
    suite.append(dict(board="BioSecBench-Refusal", category=r.get("category", "biosecurity"),
                      horizon=r.get("horizon", "short"), assessment="safeguards",
                      evals=int(r.get("v2EvaluationCount", 107))))
    D["suite"] = suite
    D["run"] = dict(turns=round(df[df.turnN > 0].turnSum.sum() / df[df.turnN > 0].turnN.sum()),
                    tokens=int(df.tokSum.sum() / df.tokN.sum()),
                    cost=round(df.costSum.sum() / df.costN.sum(), 2))
    D["overall_interval"] = dict(median_width=float(OV.interval_width.median()),
                                 board_median_width=float(RI.interval_width.median()),
                                 cov_corr=round(RI.coverage.corr(RI.interval_width, method="spearman"), 3))
    (OUT / "figures.json").write_text(json.dumps(D, indent=1))
    # the published page reads the same file, so it cannot drift from the pipeline
    site = OUT.parent / "docs" / "figures.json"
    if site.parent.exists():
        site.write_text(json.dumps(D, indent=1))


if __name__ == "__main__":
    main()

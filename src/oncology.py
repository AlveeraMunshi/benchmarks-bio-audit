"""OncologyBench is the thirteenth capability board and ships in its own schema.

It is not under /data/v1/<board>.json like the other twelve; its per-evaluation
records live at /data/oncologybench/index.json with `attempts / passed / refused
/ timeout` per eval. Its published methodology states the rule plainly -
"Refusals and the four timed-out slots remain in the denominator" - which makes
it the second board, with MetagenomicsBench, to document the failure rule
correctly.
"""
import json, pathlib

RAW = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"
BENCH = "oncologybench"


def rows():
    d = json.loads((RAW / "oncologybench.json").read_text())
    meta = {m["id"]: m for m in d["modelResults"]}
    for m in d["models"]:
        pub = meta.get(m["id"], {})
        for ev, r in m["perEval"].items():
            yield dict(
                bench=BENCH, eval_id=ev, mid=m["id"], model=m["name"],
                harness=m["harness"], org=m["organization"],
                correct=r["passed"], refused=r["refused"], timeout=r["timeout"],
                runs=r["attempts"],
                # the per-eval export carries no cost/token breakdown; the board
                # only publishes per-configuration averages, so spread those.
                costSum=(pub.get("avgCost") or 0.0) * r["attempts"] / 3,
                tokSum=(pub.get("avgTokens") or 0.0) * r["attempts"] / 3,
                turnSum=(pub.get("avgTurns") or 0.0) * r["attempts"] / 3,
                costN=r["attempts"], tokN=r["attempts"], turnN=r["attempts"],
                published_pass=pub.get("passRate"),
                ci_lo=(pub.get("ci") or [None, None])[0],
                ci_hi=(pub.get("ci") or [None, None])[1],
            )


def methodology():
    return json.loads((RAW / "oncologybench.json").read_text())["metadata"]["methodology"]

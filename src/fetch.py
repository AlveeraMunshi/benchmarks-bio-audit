"""Pull the public benchmarks.bio result files. Nothing here is scraped from the
rendered page: every path below is a published JSON endpoint referenced by the
site's own asset bundle and by results/versions.json."""
import json, pathlib, urllib.request

RAW = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"
BASE = "https://benchmarks.bio"

# 12 capability benchmarks carry per-evaluation records; refusalbench is the
# safeguards board and uses a different schema.
CAPABILITY = ["spatialbench", "spatialbench-long", "scbench", "scbench-long",
              "epibench", "variantbench", "metagenomics", "txbench-pp",
              "txbench-od", "txbench-ad", "surveillancebench", "functionbench"]
OTHER = {"oncologybench/index.json": "oncologybench.json",
         "v1/refusalbench.json": "v1/refusalbench.json",
         "aggregate-leaderboard.json": "aggregate-leaderboard.json",
         "../results/versions.json": "results/versions.json",
         "../results/v1/latest.json": "results/v1/latest.json"}


def get(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r:
        dest.write_bytes(r.read())
    return dest.stat().st_size


def main():
    for b in CAPABILITY:
        n = get(f"{BASE}/data/v1/{b}.json", RAW / "v1" / f"{b}.json")
        print(f"  {b:20s} {n:>8,} B")
    for src, dst in OTHER.items():
        url = f"{BASE}/data/{src}" if not src.startswith("..") else f"{BASE}/{src[3:]}"
        print(f"  {dst:28s} {get(url, RAW / dst):>8,} B")


if __name__ == "__main__":
    main()

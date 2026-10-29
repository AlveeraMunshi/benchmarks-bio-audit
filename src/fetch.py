"""Pull the public benchmarks.bio result files. Nothing here is scraped from the
rendered page: every path below is a published JSON endpoint referenced by the
site's own asset bundle and by results/versions.json.

Each file is checked against src/schema.py before it is written, so a shape
change upstream fails here, named, rather than downstream as a KeyError. A
download that fails validation is still saved as <name>.rejected so you can
look at what arrived.
"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import schema

RAW = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"
BASE = "https://benchmarks.bio"
TIMEOUT = 30

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

# which checker guards which destination; anything unlisted is stored unchecked
CHECK = {"oncologybench.json": lambda d: schema.check_oncology(d),
         "results/v1/latest.json": lambda d: schema.check_results(d)}


def get(url, dest, check=None):
    """Download, validate, then write. Returns the byte count."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            if r.status != 200:
                raise RuntimeError(f"{url}: HTTP {r.status}")
            body = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{url}: HTTP {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"{url}: unreachable ({e.reason})") from e

    try:
        doc = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{url}: served {len(body)} bytes that are not JSON "
                           f"({e}). An HTML error page is the usual cause.") from e

    dest.parent.mkdir(parents=True, exist_ok=True)
    if check is not None:
        try:
            check(doc)
        except schema.SchemaDrift:
            dest.with_suffix(dest.suffix + ".rejected").write_bytes(body)
            raise

    dest.write_bytes(body)
    return len(body)


def main():
    bad = []
    for b in CAPABILITY:
        try:
            n = get(f"{BASE}/data/v1/{b}.json", RAW / "v1" / f"{b}.json",
                    lambda d, b=b: schema.check_v1_board(b, d))
            print(f"  {b:20s} {n:>8,} B")
        except (RuntimeError, schema.SchemaDrift) as e:
            bad.append(str(e))
            print(f"  {b:20s} FAILED")
    for src, dst in OTHER.items():
        url = f"{BASE}/data/{src}" if not src.startswith("..") else f"{BASE}/{src[3:]}"
        try:
            print(f"  {dst:28s} {get(url, RAW / dst, CHECK.get(dst)):>8,} B")
        except (RuntimeError, schema.SchemaDrift) as e:
            bad.append(str(e))
            print(f"  {dst:28s} FAILED")

    if bad:
        print("\n" + "=" * 72)
        print(f"{len(bad)} file(s) did not pass. Nothing downstream should be")
        print("trusted until these are understood:\n")
        for b in bad:
            print(f"  - {b}\n")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

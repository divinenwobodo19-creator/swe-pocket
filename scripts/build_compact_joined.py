#!/usr/bin/env python3
"""Join the compact stratum's tasks with its graph structure (compact twin of
merge_gold_structure.py).

Reads:   resources/compact_tasks.json, data/compact_structure.csv
Writes:  data/compact_joined.json, data/compact_joined.csv

    python3 scripts/stratify.py --gdir data/compact_graphs \
        --out data/compact_structure.csv --summary resources/compact_stratification_raw.json
    python3 scripts/build_compact_joined.py
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_tests import parse_ftl  # noqa: E402
from merge_gold_structure import churn  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COLS = ["instance_id", "repo", "stratum", "nodes", "edges", "density",
        "isolated_ratio", "max_depth", "gold_churn_total", "f2p_count",
        "test_churn", "problem_words", "graph_key"]


def main() -> int:
    tasks = json.load(open(ROOT / "resources/compact_tasks.json"))
    struct = {r["instance"]: r for r in csv.DictReader(open(ROOT / "data/compact_structure.csv"))}
    out = []
    for t in tasks:
        repo = t["repo"].split("/")[-1]
        key = f"{repo}_{t['base_commit']}"
        s = struct[key]
        a, d = churn(t["patch"])
        ta, td = churn(t["test_patch"])
        out.append({
            "instance_id": t["instance_id"], "repo": repo, "stratum": "compact",
            "nodes": int(s["nodes"]), "edges": int(s["edges"]),
            "density": float(s["density"]), "isolated_ratio": float(s["isolated_ratio"]),
            "max_depth": int(s["max_depth"]), "gold_churn_total": a + d,
            "f2p_count": len(parse_ftl(t["test_patch"])["fail_to_pass"]),
            "test_churn": ta + td, "problem_words": len(t["problem_statement"].split()),
            "graph_key": key,
        })
    json.dump(out, open(ROOT / "data/compact_joined.json", "w"), indent=1)
    with open(ROOT / "data/compact_joined.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(out)} compact tasks -> data/compact_joined.json/.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())

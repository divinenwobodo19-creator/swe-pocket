#!/usr/bin/env python3
"""Merge tasks.jsonl gold-patch metadata with structural stratification.

Reads:
  resources/tasks.jsonl                       (132 tasks, authoritative)
  data/stratification.csv                     (structural metrics, 127 graph keys)
Writes:
  data/task_metadata.csv                      (per-task gold-patch features)
  resources/task_metadata.json
  data/joined_structure_gold.csv              (structure + gold-patch joined)
  resources/size_vs_difficulty.json           (correlations, medians)
"""
from __future__ import annotations
import csv
import json
import math
import re
import statistics
import sys
from collections.abc import Iterable

ROOT = __file__.rsplit("/", 2)[0]

def files_of(patch: str) -> list[str]:
    out = []
    for line in (patch or "").splitlines():
        if line.startswith("+++ b/"):
            p = line[6:].strip()
            if p != "/dev/null":
                out.append(p)
    return out

def is_test(p: str) -> bool:
    return (
        re.search(r"(^|/)(tests?|testing)/", "/" + p)
        or p.endswith("_test.py")
        or p.startswith("test_")
        or p.endswith("conftest.py")
    )

def churn(patch: str) -> tuple[int, int]:
    add = dele = 0
    for line in (patch or "").splitlines():
        if line.startswith("+"):
            add += 1
        elif line.startswith("-") and not line.startswith("---"):
            dele += 1
    return add, dele

def task_metadata() -> list[dict]:
    rows = [json.loads(l) for l in open(f"{ROOT}/resources/tasks.jsonl")]
    out = []
    for r in rows:
        repo = r["repo"].split("/")[-1]
        gp = files_of(r["patch"])
        tp = files_of(r["test_patch"])
        src = [f for f in gp if not is_test(f)]
        a, d = churn(r["patch"])
        ta, td = churn(r["test_patch"])
        new_tests = re.findall(
            r"^\+\s*(?:async\s+)?def\s+(test_\w+)", r["test_patch"], flags=re.M
        )
        out.append({
            "instance_id": r["instance_id"],
            "repo": repo,
            "base_commit": r["base_commit"],
            "problem_words": len(r["problem_statement"].split()),
            "gold_files": len(src),
            "gold_churn_add": a,
            "gold_churn_del": d,
            "gold_churn_total": a + d,
            "test_files": len(tp),
            "test_patch_churn": ta + td,
            "new_test_functions": len(new_tests),
            "has_hints": int(bool((r.get("hints_text") or "").strip())),
            "graph_key": f"{repo}_{r['base_commit']}",
        })
    return out

def pearson(xs: Iterable[float], ys: Iterable[float]) -> float:
    xl, yl = list(xs), list(ys)
    n = len(xl)
    mx, my = sum(xl) / n, sum(yl) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xl, yl))
    vx = sum((a - mx) ** 2 for a in xl)
    vy = sum((b - my) ** 2 for b in yl)
    return cov / math.sqrt(vx * vy) if vx * vy else 0.0

def main() -> int:
    meta = task_metadata()
    with open(f"{ROOT}/data/task_metadata.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(meta[0]))
        w.writeheader()
        w.writerows(meta)
    json.dump(meta, open(f"{ROOT}/resources/task_metadata.json", "w"), indent=1)

    strat = list(csv.DictReader(open(f"{ROOT}/data/stratification.csv")))
    s_map = {r["instance"]: r for r in strat}
    tsets = {t["instance_id"]: t for t in
             json.load(open(f"{ROOT}/resources/test_sets.json"))}
    joined = []
    for m in meta:
        s = s_map.get(m["graph_key"])
        if not s:
            continue
        ts = tsets.get(m["instance_id"], {})
        joined.append({
            **m,
            "test_file_count": len(ts.get("files", [])),
            "f2p_count": len(ts.get("fail_to_pass", [])),
            "p2p_count": len(ts.get("pass_to_pass", [])),
            "nodes": int(s["nodes"]),
            "edges": int(s["edges"]),
            "density": float(s["density"]),
            "max_depth": int(s["max_depth"]),
            "isolated_ratio": float(s["isolated_ratio"]),
        })
    with open(f"{ROOT}/data/joined_structure_gold.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(joined[0]))
        w.writeheader()
        w.writerows(joined)

    corrs = {
        "nodes_vs_churn": pearson((j["nodes"] for j in joined),
                                  (j["gold_churn_total"] for j in joined)),
        "nodes_vs_files": pearson((j["nodes"] for j in joined),
                                  (j["gold_files"] for j in joined)),
        "nodes_vs_problem_words": pearson((j["nodes"] for j in joined),
                                          (j["problem_words"] for j in joined)),
        "max_depth_vs_churn": pearson((j["max_depth"] for j in joined),
                                      (j["gold_churn_total"] for j in joined)),
    }
    medians = {
        repo: int(statistics.median(  # type: ignore[arg-type]
            j["gold_churn_total"] for j in joined if j["repo"] == repo))
        for repo in ("fastapi", "rich", "requests", "httpx")
    }
    json.dump({
        "joined": len(joined), "tasks": len(meta),
        "pearson": corrs, "median_gold_churn": medians,
    }, open(f"{ROOT}/resources/size_vs_difficulty.json", "w"), indent=1)

    print(f"tasks: {len(meta)}  joined: {len(joined)}")
    print("pearson:", {k: round(v, 3) for k, v in corrs.items()})
    print("median gold churn:", medians)
    return 0

if __name__ == "__main__":
    sys.exit(main())
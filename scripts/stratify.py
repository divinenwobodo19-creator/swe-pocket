#!/usr/bin/env python3
"""Difficulty stratification across all provided SWE-Pocket instances.

Produces the Section 3.3 table: per-instance structural difficulty metrics,
used to make repository size the controlled variable in the paper.

Metrics per instance (from the code graph, no model required):
  - nodes, edges        : raw repository scale
  - files, symbols/file : structure breadth
  - mean/median fan-in  : coupling
  - max fan-in          : hotspot concentration
  - isolated nodes      : dead/leafy code ratio
  - density             : edges / nodes

Outputs:
  data/stratification.csv   one row per instance
  resources/stratification.json  summary stats + repo-level rollup

Usage:
    python3 scripts/stratify.py
    python3 scripts/stratify.py --graphs-only     # skip .npz reads
"""
import argparse
import csv
import json
import os
from collections import Counter
from statistics import mean, median

GDIR = "data/graphs"


def instance_metrics(g: dict) -> dict:
    nodes, edges = g["nodes"], g["edges"]
    ids = [n["id"] for n in nodes]
    files = {i.split(".")[0] for i in ids}
    n, e = len(nodes), len(edges)

    fan_in = Counter(edge["target"] for edge in edges)
    fan_out = Counter(edge["source"] for edge in edges)
    targets = set(fan_in)
    sources = set(fan_out)
    isolated = len(set(ids) - targets - sources)

    return {
        "nodes": n,
        "edges": e,
        "files": len(files),
        "symbols_per_file": round(n / max(len(files), 1), 2),
        "mean_fan_in": round(e / max(n, 1), 3),
        "median_fan_in": round(float(median(fan_in.values())) if fan_in else 0.0, 2),
        "max_fan_in": max(fan_in.values()) if fan_in else 0,
        "isolated_nodes": isolated,
        "isolated_ratio": round(isolated / max(n, 1), 4),
        "density": round(e / max(n, 1), 3),
        # Structural reach: longest acyclic call chain (cycles broken).
        "max_depth": call_depth(nodes, edges),
    }


def call_depth(nodes: list, edges: list) -> int:
    """Longest acyclic call-chain length, cycle-safe.

    Iterative post-order over the call graph: an explicit stack replaces the
    naive recursive DFS, which copied a frozenset per node and did not scale to
    multi-thousand-node graphs.
    """
    succ: dict[str, list[str]] = {}
    ids = [n["id"] for n in nodes]
    for nid in ids:
        succ.setdefault(nid, [])
    for e in edges:
        succ.setdefault(e["source"], []).append(e["target"])

    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(ids, WHITE)
    memo: dict[str, int] = {}

    for root in ids:
        if color[root] != WHITE:
            continue
        stack = [(root, iter(succ[root]))]
        path: list[str] = [root]
        color[root] = GREY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                c = color.get(nxt, WHITE)
                if c == GREY:
                    continue  # back edge: cycle, stop descending
                if c == WHITE:
                    color[nxt] = GREY
                    path.append(nxt)
                    stack.append((nxt, iter(succ.get(nxt, ()))))
                    advanced = True
                    break
                # BLACK: already resolved
                memo[node] = max(memo.get(node, 0), 1 + memo[nxt])
            if not advanced:
                color[node] = BLACK
                stack.pop()
                depth = memo.setdefault(node, 0)
                # Propagate the resolved depth to the parent frame
                if stack:
                    parent = stack[-1][0]
                    memo[parent] = max(memo.get(parent, 0), 1 + depth)

    return max(memo.values(), default=0)




def pct(values, q):
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graphs-only", action="store_true")
    ap.add_argument("--gdir", default=GDIR)
    ap.add_argument("--out", default="data/stratification.csv",
                    help="CSV output path (use a distinct name per stratum)")
    ap.add_argument("--summary", default="resources/stratification.json")
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(args.gdir) if f.endswith(".json"))
    if not files:
        print(f"No graphs found in {args.gdir} — run scripts/download_all.py first.")
        return 1
    print(f"Found {len(files)} graphs in {args.gdir}")
    if len(files) < 127:
        print(f"NOTE: partial data ({len(files)}/127). Re-run download_all.py to resume.\n")

    rows = []
    for fname in files:
        stem = fname[:-5]
        repo = stem.split("_")[0]
        with open(os.path.join(args.gdir, fname)) as fh:
            g = json.load(fh)
        m = instance_metrics(g)
        m.update({"instance": stem, "repo": repo})
        rows.append(m)

    rows.sort(key=lambda r: r["nodes"])

    os.makedirs("data", exist_ok=True)
    cols = ["instance", "repo", "nodes", "edges", "files", "symbols_per_file",
            "mean_fan_in", "median_fan_in", "max_fan_in", "isolated_nodes",
            "isolated_ratio", "density", "max_depth"]
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    by_repo = {}
    for r in rows:
        by_repo.setdefault(r["repo"], []).append(r)

    repo_summary = {}
    for repo, rs in sorted(by_repo.items(), key=lambda kv: -len(kv[1])):
        repo_summary[repo] = {
            "instances": len(rs),
            "nodes_min": min(x["nodes"] for x in rs),
            "nodes_max": max(x["nodes"] for x in rs),
            "nodes_mean": round(mean(x["nodes"] for x in rs), 1),
            "edges_mean": round(mean(x["edges"] for x in rs), 1),
            "density_mean": round(mean(x["density"] for x in rs), 3),
        }

    all_nodes = [r["nodes"] for r in rows]
    summary = {
        "generated_from": len(rows),
        "repos": repo_summary,
        "size_distribution": {
            "nodes_min": min(all_nodes),
            "nodes_p10": pct(all_nodes, 0.10),
            "nodes_p25": pct(all_nodes, 0.25),
            "nodes_p50": pct(all_nodes, 0.50),
            "nodes_p75": pct(all_nodes, 0.75),
            "nodes_p90": pct(all_nodes, 0.90),
            "nodes_max": max(all_nodes),
        },
    }

    with open(args.summary, "w") as fh:
        json.dump(summary, fh, indent=2)

    print(f"Instances analysed: {len(rows)}\n")
    print(f"{'repo':<12}{'n':>4}{'nodes min':>11}{'nodes mean':>12}{'nodes max':>11}{'edges mean':>12}")
    for repo, s in repo_summary.items():
        print(f"{repo:<12}{s['instances']:>4}{s['nodes_min']:>11}{s['nodes_mean']:>12}{s['nodes_max']:>11}{s['edges_mean']:>12}")
    print("\nSize distribution (nodes):")
    for k, v in summary["size_distribution"].items():
        print(f"  {k:<14}{v}")
    print(f"\nWrote {args.out} and {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
#!/usr/bin/env python3
"""Inspect one provided SWE-Pocket instance: code graph + embeddings.

Verified output shape (Sept 2026):
  graph JSON : NetworkX multigraph
               nodes: [{name, text, id}]  id = "<file_stem>.<symbol>"
               edges: [{type: "calls", source, target, key}]
  embedding  : .npz, float32, 256-dim, keyed by the same node ids

Usage:
    python3 scripts/inspect_instance.py graphs/rich_9f620dc50c0008c35e9f8493f198e6e593574a70.json

Paths are resolved against data/graphs/ and data/embeddings/.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np


def main(path: str) -> int:
    name = path.rsplit("/", 1)[-1]
    stem = name[:-5] if name.endswith(".json") else name
    graph_path = f"data/graphs/{stem}.json"
    emb_path = f"data/embeddings/{stem}.npz"
    for p in (graph_path, emb_path):
        if not Path(p).exists():
            print(f"missing: {p}\nRun scripts/download_all.py first.")
            return 1

    print("=" * 60)
    print("GRAPH")
    print("=" * 60)
    with open(graph_path) as fh:
        g = json.load(fh)
    nodes, edges = g["nodes"], g["edges"]
    print(f"repo        : {g['graph'].get('repo_name')}")
    print(f"nodes       : {len(nodes)}")
    print(f"edges       : {len(edges)}")
    print(f"edge types  : {Counter(e['type'] for e in edges).most_common()}")

    files = {n['id'].split('.')[0] for n in nodes}
    print(f"files       : {len(files)}")
    print(f"symbols/file: {len(nodes)/max(len(files),1):.1f} avg")

    fan_in = Counter(e["target"] for e in edges)
    top = fan_in.most_common(5)
    print("\nhighest fan-in (most-called symbols):")
    for nid, c in top:
        print(f"  {c:>4}  {nid[:80]}")

    depths = fan_in
    print(f"\nmean fan-in: {sum(depths.values())/max(len(nodes),1):.2f}")

    print("\n" + "=" * 60)
    print("EMBEDDINGS")
    print("=" * 60)
    z = np.load(emb_path, allow_pickle=True)
    keys = list(z.keys())
    shapes = {z[k].shape for k in keys[:50]}
    dtypes = {str(z[k].dtype) for k in keys[:50]}
    print(f"vectors     : {len(keys)}")
    print(f"shape       : {shapes}")
    print(f"dtype       : {dtypes}")

    covered = sum(1 for n in nodes if n["id"] in set(keys))
    print(f"node coverage: {covered}/{len(nodes)} ({covered/max(len(nodes),1):.1%})")

    a = np.stack([z[k] for k in keys[:2000]])
    norms = np.linalg.norm(a, axis=1)
    print(f"norm mean   : {norms.mean():.4f} (sd {norms.std():.4f})")
    if norms.std() > 1e-3:
        a = a / norms[:, None]
        sim = a[:500] @ a[:500].T
        off = sim[~np.eye(500, dtype=bool)]
        print(f"cosine sim  : mean {off.mean():.4f}  max {off.max():.4f}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    raise SystemExit(main(sys.argv[1]))
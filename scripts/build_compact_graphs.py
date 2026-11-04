#!/usr/bin/env python3
"""Build call graphs for the compact stratum, matching the provided schema.

The competition's code graphs use node ids of the form
`<module.path>.<Symbol>` (dots, no slashes) and `calls` edges between symbols
referenced in a function body. We reproduce that schema for the mined compact
repos so they can be stratified with the exact same metrics code.

Source of truth: the repo tree at each task's base_commit, fetched via the
GitHub API (no clone, no snapshots needed). For each .py file we parse with
`ast`, collect:
  nodes: every top-level + nested def/class (id = module.symbol)
  edges: resolved bare-name / attribute calls from a symbol body to a known symbol

Writes one graph per base_commit under data/compact_graphs/<repo>_<base>.json
(so scripts/stratify.py can run with --gdir data/compact_graphs).

Usage:
  export GH_TOKEN=$(gh auth token)
  python3 -u scripts/build_compact_graphs.py
"""
from __future__ import annotations
import ast
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict

API = "https://api.github.com"
ROOT = __file__.rsplit("/", 2)[0]
OUT = f"{ROOT}/data/compact_graphs"
HDR = {"Accept": "application/vnd.github+json", "User-Agent": "nlib-compact-graphs"}

def token() -> str:
    return os.environ.get("GH_TOKEN") or subprocess.check_output(["gh", "auth", "token"], text=True).strip()

def api(url: str, retries: int = 3):
    HDR["Authorization"] = f"Bearer {token()}"
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                time.sleep(5 * (i + 1)); continue
            if e.code == 404:
                return None
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return None

def module_path(repo: str, path: str) -> str:
    """path 'src/packaging/version.py' -> 'packaging.version'."""
    p = path[:-3] if path.endswith(".py") else path
    parts = p.split("/")
    for strip in ("src", "lib"):
        if parts and parts[0] == strip:
            parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)

def collect_symbols(tree: ast.AST, mod: str) -> tuple[list[dict], dict[str, str]]:
    """Return (nodes, defined_symbols) where defined maps bare name -> full id."""
    nodes, defined = [], {}

    class V(ast.NodeVisitor):
        def __init__(self, prefix: str):
            self.prefix = prefix

        def visit_FunctionDef(self, node): self._fn(node)
        def visit_AsyncFunctionDef(self, node): self._fn(node)

        def _fn(self, node):
            full = f"{self.prefix}.{node.name}"
            text = f"def {node.name}(...)"
            nodes.append({"name": full, "text": text, "id": full})
            defined.setdefault(node.name, full)
            V(full).visit_many(node.body)

        def visit_ClassDef(self, node):
            full = f"{self.prefix}.{node.name}"
            nodes.append({"name": full, "text": f"class {node.name}", "id": full})
            defined.setdefault(node.name, full)
            V(full).visit_many(node.body)

        def visit_many(self, body):
            for b in body:
                self.visit(b)

    V(mod).visit_many(tree.body)
    return nodes, defined

def calls_of(tree: ast.AST) -> list[tuple[str, str]]:
    """(enclosing_symbol_id_hint, called_bare_name) pairs, from Call nodes."""
    out = []

    def walk(node, cur):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = child.name
                walk(child, name)
            elif isinstance(child, ast.Call):
                fn = child.func
                nm = None
                if isinstance(fn, ast.Name):
                    nm = fn.id
                elif isinstance(fn, ast.Attribute):
                    nm = fn.attr
                if nm:
                    out.append((cur, nm))
                walk(child, cur)
            else:
                walk(child, cur)

    walk(tree, "")
    return out

def build_one(slug: str, base: str) -> dict | None:
    tree = api(f"{API}/repos/{slug}/git/trees/{base}?recursive=1")
    if not tree or "tree" not in tree:
        return None
    py = [t for t in tree["tree"] if t.get("type") == "blob" and t["path"].endswith(".py")
          and not re.search(r"(^|/)(tests?|docs?|examples?|benchmarks?)/", t["path"])]
    nodes, defined_by_mod, edges = [], {}, []
    per_mod_src = {}
    for t in py:
        blob = api(f"{API}/repos/{slug}/git/blobs/{t['sha']}")
        if not blob or "content" not in blob:
            continue
        try:
            src = base64.b64decode(blob["content"]).decode("utf-8", "replace")
        except Exception:
            continue
        mod = module_path(slug, t["path"])
        per_mod_src[mod] = src
        try:
            tree_ast = ast.parse(src)
        except SyntaxError:
            continue
        ns, dfn = collect_symbols(tree_ast, mod)
        nodes += ns
        defined_by_mod[mod] = dfn
    # global bare-name -> candidate ids
    global_def: dict[str, list[str]] = defaultdict(list)
    for mod, dfn in defined_by_mod.items():
        for name, full in dfn.items():
            global_def[name].append(full)
    # edges: resolve each call's bare name to the unique defined symbol
    id_set = {n["id"] for n in nodes}
    for mod, src in per_mod_src.items():
        try:
            tree_ast = ast.parse(src)
        except SyntaxError:
            continue
        for enclosing_name, called in calls_of(tree_ast):
            src_id = f"{mod}.{enclosing_name}" if enclosing_name else mod
            if src_id not in id_set and enclosing_name:
                continue
            cands = global_def.get(called, [])
            if len(cands) == 1:
                edges.append({"type": "calls", "source": src_id, "target": cands[0], "key": 0})
    return {"directed": True, "multigraph": True, "graph": {}, "nodes": nodes, "edges": edges}

def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    tasks = json.load(open(f"{ROOT}/resources/compact_tasks.json"))
    done = 0
    for t in tasks:
        key = f"{t['repo'].split('/')[-1]}_{t['base_commit']}"
        dest = f"{OUT}/{key}.json"
        if os.path.exists(dest):
            done += 1; continue
        g = build_one(t["repo"], t["base_commit"])
        if not g or not g["nodes"]:
            print(f"  FAIL {key}", file=sys.stderr); continue
        json.dump(g, open(dest, "w"))
        print(f"  {key}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")
        done += 1
    print(f"\nbuilt {done}/{len(tasks)} compact graphs -> {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
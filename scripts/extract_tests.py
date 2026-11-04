#!/usr/bin/env python3
"""Extract FAIL_TO_PASS / PASS_TO_PASS tests from tasks.jsonl test_patches.

Each task's `test_patch` is a unified diff of the test file(s) the maintainer
added/changed for the PR. Newly added non-trivial test functions
(`+ def test_...`) are FAIL_TO_PASS candidates; context lines that keep existing
test names are PASS_TO_PASS candidates. Writes:
  data/test_sets.csv          (task x test-function-level rows)
  resources/test_sets.json    (task -> {task_id, repo, files, fail_to_pass, pass_to_pass})
"""
from __future__ import annotations
import csv
import json
import re
import sys
from collections import OrderedDict

ROOT = __file__.rsplit("/", 2)[0]

DIFF_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
FUNC = re.compile(r"^def\s+(test_\w+|async\s+def\s+test_\w+)")

def parse_ftl(test_patch: str) -> dict:
    """Parse a test_file diff -> {'fail_to_pass': [...], 'pass_to_pass': [...], 'files': [...]}."""
    fail_to_pass: list[str] = []
    pass_to_pass: list[str] = []
    files: list[str] = []
    func_stack: list[str] = []

    def current_func() -> str | None:
        for f in reversed(func_stack):
            if f:
                return f
        return None

    in_patch = False
    for line in test_patch.splitlines():
        if line.startswith("+++ b/"):
            p = line[6:].strip()
            if p != "/dev/null":
                files.append(p)
            func_stack = []
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        if DIFF_HUNK.match(line):
            func_stack.append(None)
            continue
        if in_patch and func_stack:
            func_stack[-1] = None
            in_patch = False
        if line.startswith("+"):
            in_patch = True
            m = FUNC.match(line[1:].strip())
            if m:
                name = re.sub(r"^def\s+", "", line[1:].strip()).split("(")[0].strip()
                if "async" in line[1:line.find("(")]:
                    pass
                func_stack[-1] = name
                if current_func() and current_func() not in fail_to_pass:
                    fail_to_pass.append(current_func())
        elif line.startswith(" "):
            m = FUNC.match(line[1:].strip())
            if m:
                name = line[1:].strip().split("(")[0].split("def ")[-1].strip()
                if func_stack:
                    func_stack[-1] = name
                if name not in pass_to_pass:
                    pass_to_pass.append(name)
        elif line.startswith("-"):
            if func_stack:
                func_stack[-1] = None
    return {"fail_to_pass": fail_to_pass, "pass_to_pass": pass_to_pass, "files": files}

def main() -> int:
    rows = [json.loads(l) for l in open(f"{ROOT}/resources/tasks.jsonl")]
    out, csv_rows = [], []
    for r in rows:
        fs = parse_ftl(r["test_patch"])
        out.append({
            "instance_id": r["instance_id"], "repo": r["repo"],
            "base_commit": r["base_commit"], "graph_key":
                f"{r['repo'].split('/')[-1]}_{r['base_commit']}",
            **fs,
        })
        for f in fs["fail_to_pass"]:
            csv_rows.append({"instance_id": r["instance_id"], "type": "F2P",
                             "test": f, "file": "; ".join(fs["files"])})
        for f in fs["pass_to_pass"]:
            csv_rows.append({"instance_id": r["instance_id"], "type": "P2P",
                             "test": f, "file": "; ".join(fs["files"])})

    json.dump(out, open(f"{ROOT}/resources/test_sets.json", "w"), indent=1)
    with open(f"{ROOT}/data/test_sets.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["instance_id", "type", "test", "file"])
        w.writeheader()
        w.writerows(csv_rows)

    n_f2p = sum(1 for o in out if o["fail_to_pass"])
    n_p2p = sum(1 for o in out if o["pass_to_pass"])
    print(f"tasks: {len(out)} | with F2P tests: {n_f2p} | with P2P tests: {n_p2p}")
    import collections
    c = collections.Counter(o["repo"] for o in out if not o["fail_to_pass"])
    print("tasks with NO F2P by repo:", dict(c))
    return 0

if __name__ == "__main__":
    sys.exit(main())
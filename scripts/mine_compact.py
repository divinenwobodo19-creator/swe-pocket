#!/usr/bin/env python3
"""Mine a compact stratum of SWE tasks from small repos, same schema as tasks.jsonl.

For each seed repo, pull merged PRs and build task rows:
  instance_id, repo, base_commit (= PR base sha), problem_statement (PR title+body),
  patch (unified diff of SOURCE files), test_patch (unified diff of TEST files).

Filters to small, verifiable PRs so the compact stratum stays compact and each
task has a real test patch (so it is gradeable by pytest, like the large stratum).

Writes: resources/compact_tasks.json  (list of task dicts)
        data/compact_structure.csv    (per-task structural metrics from a fresh
                                       checkout via GitHub API tree+content)
Usage:
  export GH_TOKEN=$(gh auth token)
  python3 -u scripts/mine_compact.py
"""
from __future__ import annotations
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

SEED = [
    "pypa/packaging",
    "jazzband/prettytable",
    "davidhalter/parso",
    "theskumar/python-dotenv",
]

# Compact-stratum selection criteria (deliberately small).
MAX_FILES = 6            # total changed files in the PR
MIN_CHURN = 4            # at least this many add+del lines (avoid no-op/docs)
MAX_CHURN = 160          # keep fixes small — compact means small fixes
TARGET_PER_REPO = 6      # aim for ~6 tasks/repo -> ~24 total

def token() -> str:
    return os.environ.get("GH_TOKEN") or subprocess.check_output(["gh", "auth", "token"], text=True).strip()

HDR = {"Authorization": "", "Accept": "application/vnd.github+json", "User-Agent": "nlib-compact-mine"}

def api(url: str, retries: int = 3):
    HDR["Authorization"] = f"Bearer {token()}"
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 403 and "rate limit" in str(e).lower():
                time.sleep(5 * (i + 1)); continue
            if e.code == 404:
                return None
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return None

def is_test_path(p: str) -> bool:
    return bool(re.search(r"(^|/)(tests?|testing)/", "/" + p)
                or p.endswith("_test.py") or p.startswith("test_")
                or p.endswith("conftest.py"))

def split_patch(files: list[dict]) -> tuple[str, str, int, int]:
    """Split a PR's file list into (source_patch, test_patch, src_files, test_files)."""
    src_lines, test_lines = [], []
    src_n = test_n = 0
    for f in files:
        if f.get("status") == "removed":
            continue
        patch = f.get("patch")
        if not patch:
            continue  # binary or truncated -> skip file
        name = f["filename"]
        header = [f"--- a/{name}", f"+++ b/{name}"]
        body = patch.splitlines()
        block = header + body
        if is_test_path(name):
            test_lines += block + [""]
            test_n += 1
        else:
            src_lines += block + [""]
            src_n += 1
    return "\n".join(src_lines), "\n".join(test_lines), src_n, test_n

def mine_repo(slug: str) -> list[dict]:
    out: list[dict] = []
    pulls = api(f"{API}/repos/{slug}/pulls?state=closed&per_page=100&sort=updated&direction=desc")
    if not pulls:
        print(f"  {slug}: no pulls returned", file=sys.stderr); return out
    merged = [p for p in pulls if p.get("merged_at")]
    print(f"  {slug}: {len(pulls)} closed, {len(merged)} merged (recent 100)")
    for p in merged:
        if len(out) >= TARGET_PER_REPO:
            break
        num = p["number"]
        files = api(f"{API}/repos/{slug}/pulls/{num}/files?per_page=100")
        if not files:
            continue
        churn = sum(f.get("additions", 0) + f.get("deletions", 0) for f in files)
        if len(files) > MAX_FILES or not (MIN_CHURN <= churn <= MAX_CHURN):
            continue
        src_patch, test_patch, src_n, test_n = split_patch(files)
        if not src_patch or not test_patch:
            continue  # need both a source change and a test change
        iid = f"{slug.split('/')[-1]}_{num}"
        out.append({
            "instance_id": iid,
            "repo": slug,
            "base_commit": p["base"]["sha"],
            "problem_statement": (p.get("title") or "") + "\n\n" + (p.get("body") or "")[:2000],
            "patch": src_patch,
            "test_patch": test_patch,
            "hints_text": "",
            "created_at": p["merged_at"],
            "source": "mined-compact",
            "n_source_files": src_n,
            "n_test_files": test_n,
            "churn": churn,
        })
    return out

def main() -> int:
    tasks: list[dict] = []
    for slug in SEED:
        got = mine_repo(slug)
        print(f"  -> mined {len(got)} tasks from {slug}")
        tasks += got
    json.dump(tasks, open(f"{ROOT}/resources/compact_tasks.json", "w"), indent=1)
    by = defaultdict(int)
    for t in tasks:
        by[t["repo"]] += 1
    print(f"\ntotal compact tasks: {len(tasks)}  {dict(by)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
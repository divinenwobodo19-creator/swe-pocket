#!/usr/bin/env python3
"""Map each provided instance's base_commit back to its GitHub origin.

Each provided filename is `<repo>_<40-hex base_commit>`, e.g.
    fastapi_016ab760faba1813ba235d5582a014a58bd2f417.json

This script resolves every commit to its canonical repo and records commit date,
subject line, and the PR that contains it. That gives us the provenance needed
to (a) attach issue statements and (b) verify the harness's base commits are
real upstream commits rather than synthetic ones.

Findings recorded so far (do not re-derive):
  - All 127/127 filenames parse as `<repo>_<40-hex>`.
  - The four repos are NOT the SWE-bench repos. SWE-bench (princeton-nlp) covers
    astropy, django, matplotlib, seaborn, flask, requests, xarray, pylint,
    pytest, scikit-learn, sphinx, sympy. Zero of our 127 base_commits appear in
    SWE-bench's 2,294 rows. Only `requests` overlaps by name (psf/requests, 41
    rows) and even there the commits are disjoint. These instances come from a
    different source corpus.
  - Spot checks: rich 9f620dc5 -> 200, httpx 4acf5c2c -> 200,
    requests 0b401c76 -> 200, fastapi 016ab760 -> 200 (after following the
    tiangolo/fastapi -> repositories/160919119 redirect, i.e. a repo rename).
  - rich 9f620dc5 is a merge commit for PR #3191 ("Various docstring fixes,
    removing unused variables", merged 2023-11-07).

Usage:
    python3 scripts/map_provenance.py                # all 127, writes CSV+JSON
    python3 scripts/map_provenance.py --limit 10      # quick spot check
"""
import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import re

GDIR = Path("data/graphs")
OUT_CSV = Path("resources/provenance.csv")
OUT_JSON = Path("resources/provenance.json")

# The competition ships a short repo name; these are the upstream slugs.
# tiangolo/fastapi now redirects (repo was renamed/transferred), so we follow it.
REPO_SLUGS = {
    "fastapi": "tiangolo/fastapi",
    "rich": "Textualize/rich",
    "requests": "psf/requests",
    "httpx": "encode/httpx",
}

FILENAME_RE = re.compile(r"^(?P<repo>[a-z]+)_(?P<commit>[0-9a-f]{40})$")


def api_get(url: str, token: str, tries: int = 3) -> dict | list | None:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "N-Library-SWE-Pocket",
        },
    )
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90) as fh:
                return json.loads(fh.read())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < tries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            if e.code == 404:
                return None
            raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < tries - 1:
                time.sleep(3)
                continue
            return None
    return None


def resolve(stem: str, token: str) -> dict:
    m = FILENAME_RE.match(stem)
    rec = {"instance": stem, "repo": None, "commit": None}
    if not m:
        rec["error"] = "unparseable filename"
        return rec
    rec["repo"] = m["repo"]
    rec["commit"] = m["commit"]
    slug = REPO_SLUGS.get(m["repo"])
    if not slug:
        rec["error"] = f"no upstream slug for {m['repo']}"
        return rec
    rec["upstream"] = slug

    commit = api_get(f"https://api.github.com/repos/{slug}/commits/{m['commit']}", token)
    if not commit:
        rec["error"] = "commit not found upstream"
        return rec
    rec["commit_date"] = commit["commit"]["author"]["date"]
    rec["commit_subject"] = commit["commit"]["message"].splitlines()[0]
    rec["is_merge"] = len(commit["parents"]) > 1

    pulls = api_get(
        f"https://api.github.com/repos/{slug}/commits/{m['commit']}/pulls", token
    )
    if isinstance(pulls, list) and pulls:
        p = pulls[0]
        rec["pr_number"] = p["number"]
        rec["pr_title"] = p["title"]
        rec["pr_state"] = p["state"]
        rec["pr_merged_at"] = p.get("merged_at")
        rec["pr_head_sha"] = p["head"]["sha"]
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only the first N instances")
    ap.add_argument("--out-prefix", default="")
    args = ap.parse_args()

    token = ""
    tok_path = Path.home() / ".config" / "gh" / "hosts.yml"
    if tok_path.exists():
        for line in tok_path.read_text().splitlines():
            if "oauth_token:" in line:
                token = line.split("oauth_token:")[1].strip()
                break
    if not token:
        import subprocess

        try:
            token = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, check=True
            ).stdout.strip()
        except Exception:
            print("No GitHub token found (gh auth token failed).")
            return 1

    stems = sorted(p.stem for p in GDIR.glob("*.json"))
    if args.limit:
        stems = stems[: args.limit]
    print(f"Resolving {len(stems)} instances via GitHub API...")

    rows = []
    for i, stem in enumerate(stems, 1):
        rows.append(resolve(stem, token))
        if i % 15 == 0 or i == len(stems):
            print(f"  [{i}/{len(stems)}]")

    prefix = args.out_prefix
    csv_path = Path(f"{prefix}{OUT_CSV}")
    json_path = Path(f"{prefix}{OUT_JSON}")
    cols = [
        "instance", "repo", "upstream", "commit", "commit_date", "commit_subject",
        "is_merge", "pr_number", "pr_title", "pr_state", "pr_merged_at", "pr_head_sha", "error",
    ]
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    json_path.write_text(json.dumps(rows, indent=2))

    ok = sum(1 for r in rows if not r.get("error"))
    with_pr = sum(1 for r in rows if r.get("pr_number"))
    print(f"\nresolved {ok}/{len(rows)}; {with_pr} linked to a PR")
    print(f"wrote {csv_path} and {json_path}")
    if ok < len(rows):
        for r in rows:
            if r.get("error"):
                print(f"  FAIL {r['instance']}: {r['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

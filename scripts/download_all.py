#!/usr/bin/env python3
"""Bulk-download the provided SWE-Pocket data: 127 graphs + 127 embeddings.

Uses the Kaggle API directly (not one CLI call per file) with a thread pool,
so ~1.2GB completes in minutes rather than hours. Resumable: existing,
non-empty files are skipped.

Usage:
    python3 scripts/download_all.py                # everything
    python3 scripts/download_all.py --graphs-only
    python3 scripts/download_all.py --workers 8
"""
import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

COMP = "gemma-4-developer-agent"
GDIR = Path("data/graphs")
EDIR = Path("data/embeddings")


def api_get(path: str, params: dict) -> dict:
    import urllib.parse
    import urllib.request

    token = os.environ["KAGGLE_API_TOKEN"]
    qs = urllib.parse.urlencode(params)
    url = f"https://www.kaggle.com/api/v1{path}"
    if qs:
        url += f"?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def list_files() -> list[str]:
    """Page through the competition file index via the Kaggle CLI.

    The REST endpoint shape differs across API versions, so we shell out to the
    CLI (already authenticated) and parse its table output.
    """
    import re
    import subprocess

    names: list[str] = []
    page_token = None
    while True:
        cmd = ["kaggle", "competitions", "files", "-c", COMP]
        if page_token:
            cmd += ["--page-token", page_token]
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = line.split()
            if parts and parts[0].startswith(("embeddings/", "graphs/")):
                names.append(parts[0])
        m = re.search(r"Next Page Token = (\S+)", out)
        if not m:
            break
        page_token = m.group(1)
    return sorted(set(names))


def fetch(ref: str) -> tuple[str, bool, str]:
    """Download one file via the Kaggle CLI (verified working; the REST
    download URL shape varies by API version and returned 404 here)."""
    dest = (EDIR if ref.startswith("embeddings/") else GDIR) / Path(ref).name
    if dest.exists() and dest.stat().st_size > 0:
        return ref, True, "cached"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["kaggle", "competitions", "download", "-c", COMP, "-f", ref, "-p", str(dest.parent), "-q"],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            return ref, False, (r.stderr or r.stdout).strip()[:120]
        if not dest.exists() or dest.stat().st_size == 0:
            return ref, False, "empty after download"
        return ref, True, f"{dest.stat().st_size/1e6:.1f}MB"
    except Exception as e:  # noqa: BLE001
        return ref, False, str(e)[:120]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graphs-only", action="store_true")
    ap.add_argument("--embeddings-only", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    GDIR.mkdir(parents=True, exist_ok=True)
    EDIR.mkdir(parents=True, exist_ok=True)

    refs = list_files()
    if args.graphs_only:
        refs = [r for r in refs if r.startswith("graphs/")]
    elif args.embeddings_only:
        refs = [r for r in refs if r.startswith("embeddings/")]

    total = len(refs)
    print(f"Discovered {total} files. Downloading with {args.workers} workers...\n")
    t0 = time.time()

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(fetch, r): r for r in refs}
        for fut in as_completed(futs):
            ref, good, msg = fut.result()
            ok += good
            fail += not good
            n = ok + fail
            if not good:
                print(f"  [{n}/{total}] FAIL {Path(ref).name}: {msg}")
            elif n % 10 == 0 or n == total:
                print(f"  [{n}/{total}] ok={ok} fail={fail}  ({time.time()-t0:.0f}s)")

    have_g = len(list(GDIR.glob("*.json")))
    have_e = len(list(EDIR.glob("*.npz")))
    print(f"\nDone in {time.time()-t0:.0f}s. graphs {have_g}/127  embeddings {have_e}/127")
    if have_g != 127 or have_e != 127:
        print("Some files missing — rerun to resume.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
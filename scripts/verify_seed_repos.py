#!/usr/bin/env python3
"""Verify a curated seed list of compact, real Python libraries.

Replaces naive GitHub search (its open_issues index is stale/noisy) with an
explicit seed list checked against the REST API on: activity, size, open issues,
and archived state. Stdlib only.

Usage:
    python3 scripts/verify_seed_repos.py
"""
import json
import subprocess
import urllib.request

API = "https://api.github.com"

# Curated: compact, actively-used Python libraries/tools with real issue streams.
SEED = [
    "mjhea0/python-frontmatter",
    "tox-dev/platformdirs",
    "jazzband/prettytable",
    "pallets/click",
    "python-dateutil/dateutil",
    "theskumar/python-dotenv",
    "arrow-py/arrow",
    "pypa/packaging",
    "pallets/jinja",
    "psf/blackdoc",
    "hynek/environ-config",
    "davidhalter/parso",
]


def gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def repo(slug: str) -> dict:
    req = urllib.request.Request(
        f"{API}/repos/{slug}",
        headers={
            "Authorization": f"Bearer {gh_token()}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "nlibrary-swe-pocket-verify",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def main() -> int:
    print(f"{'repo':<34} {'★':>6} {'size':>7} {'open':>6} {'pushed':>10}  archived")
    for slug in SEED:
        try:
            r = repo(slug)
            print(
                f"{r['full_name']:<34} {r['stargazers_count']:>6} "
                f"{r['size']:>7}KB {r['open_issues_count']:>6} "
                f"{r['pushed_at'][:10]:>10}  {str(r['archived'])}"
            )
        except Exception as e:
            print(f"{slug:<34} ERROR {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
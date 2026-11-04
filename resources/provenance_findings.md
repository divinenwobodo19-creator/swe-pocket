# Provenance findings — the 129 provided tasks

**STATUS: CORRECTED (supersedes the first version of this file).**

The first pass tried to reconstruct task metadata from graph filenames and
concluded the tasks were unrecoverable. **That conclusion was wrong.** The
competition's full data listing (524 files, 22.4 GB) includes `tasks.jsonl`,
which contains the actual task definitions (not redistributed here).

## What `tasks.jsonl` provides (129 tasks, all verified)

Each row has `instance_id`, `repo`, `base_commit`, `patch` (gold), `test_patch`,
`problem_statement`, `hints_text`, `created_at`.

Verified against the GitHub API (`scripts/map_provenance.py` plus a 129/129
pull check on 2026-10-08):

- **129/129** `instance_id`s correspond to real, **merged** upstream pull
  requests (e.g. `fastapi_15661` → fastapi/fastapi PR #15661).
- **129/129** `base_commit`s equal the PR's base branch SHA exactly.
- **129/129** graph+embedding pairs cover a task (`graph_key = repo_base_commit`);
  127 unique keys cover 129 tasks because 2 pairs share a base commit
  (`rich_3882/3894`, `requests_6629/6589`).

So every provided instance is a genuine SWE-bench-style task with recoverable
provenance and complete grading material (gold patch + test patch). The graphs
and embeddings are navigation aids, exactly as the harness describes.

## Distribution (from tasks.jsonl, authoritative)

| repo | tasks | PRs merged | base==PR.base |
|---|---|---|---|
| `fastapi/fastapi` | 67 | 67 | 67 |
| `Textualize/rich` | 48 | 48 | 48 |
| `psf/requests` | 13 | 13 | 13 |
| `encode/httpx` | 1 | 1 | 1 |
| **total** | **129** | **129** | **129** |

(Note: the earlier graph-filename count of fastapi 67 / rich 47 / requests 12 /
httpx 1 was an artifact of 127 graph files; `tasks.jsonl` defines 129 tasks.)

## Full competition inventory (524 files, 22.4 GB)

| component | count | size | role |
|---|---|---|---|
| `snapshots/*.tgz` | 129 | 21.5 GB | frozen repo at base_commit |
| `embeddings/*.npz` | 127 | 468 MB | node embeddings, 256-d |
| `graphs/*.json` | 127 | 422 MB | code call graphs |
| `wheels/*.whl` | 124 | 28 MB | hermetic dependency cache |
| `tasks.jsonl` | 1 | 2 MB | the 129 task definitions |
| `sample_submission/` | 10 | 0.4 MB | starter agent (LoRA adapters, prompts) |
| docker, sandbox, README | 6 | — | harness support |

## What this changes for the paper

- §2 must **never** claim we reconstruct tasks or that the corpus cannot be
  documented. We now have gold patches, so difficulty can be measured directly.
- §2/§3 can report verified provenance: all 129 tasks are merged upstream PRs,
  frozen at base_commit, graded by the maintainers' own tests.
- A **new, useful negative result**: repository-level structure does **not**
  predict gold-patch size. Across all 129 tasks:
    - corr(nodes, gold_churn) = **−0.014**
    - corr(max_depth, gold_churn) = **+0.102**
  Median gold churn is tiny (fastapi 19 lines, rich 10, requests 5). So the
  *structural* cost of large repos is NOT the token count of the fix — it is the
  cost of *finding* the right file in a large, fragmented graph. That separation
  (fix-size vs search-cost) is the empirical spine of Option A.
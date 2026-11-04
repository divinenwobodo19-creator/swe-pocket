# Test-set extraction from `tasks.jsonl`

**Status:** done — `data/test_sets.csv`, `resources/test_sets.json`,
`resources/task_metadata.json` (17 cols, 129 tasks).

## Method
`scripts/extract_tests.py` parses each task's provided `test_patch` (a unified
diff of the test files the maintainer changed for the PR):

- **FAIL_TO_PASS candidates** — test functions newly *added* (`+ def test_…`)
  or whose body lines are modified; these fail before the gold patch and pass
  after it.
- **PASS_TO_PASS candidates** — test functions that appear on unchanged
  context lines; they pass before and after.

Handles `async def`, class-scoped methods (e.g. requests'
`def test_content_length_for_bytes_data(self, httpbin)`), and multi-file
patches.

## Counts (129 tasks)

| repo | tasks | with F2P | total F2P tests | total P2P tests |
|---|---|---|---|---|
| `fastapi` | 67 | 53 | 280 | 87 |
| `rich` | 48 | 41 | 170 | 32 |
| `requests` | 13 | 12 | 14 | 5 |
| `httpx` | 1 | 1* | 0 | 0 |
| **total** | **129** | **107** | **464** | **124** |

## Caveats
- **Heuristic lower bound.** F2P names come from *added* test functions.
  Tasks that only *modify* an existing test (e.g. `httpx_3672` renames
  `p.complete()` → `p.reset()` on the pre-existing `test_parser*` tests) are
  caught by `test_patch_churn > 0`, but their exact test names still require a
  real pytest run against the snapshot.
- **Difficulty proxy.** F2P count is a task-level difficulty proxy, usable
  *now*; the ground-truth pass/fail classification needs the harness run
  (`--skip-agent-patch` gold-patch check) against snapshots.

## Use in paper
- §4.1 setup can stratify by F2P count as a *task-intrinsic* difficulty, held
  constant across size strata.
- Combined with `data/joined_structure_gold.csv` it gives the three-way table
  the writeup's headline: structural axis × gold churn × F2P size.
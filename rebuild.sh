#!/usr/bin/env bash
# Rebuild every derived table from the competition data.
# Requires: joined https://www.kaggle.com/competitions/gemma-4-developer-agent,
#           kaggle CLI authenticated (KAGGLE_API_TOKEN or ~/.kaggle/access_token).
set -euo pipefail
cd "$(dirname "$0")"
export KAGGLE_API_TOKEN="${KAGGLE_API_TOKEN:-$(cat ~/.kaggle/access_token)}"

[ -s resources/tasks.jsonl ] || kaggle competitions download -c gemma-4-developer-agent -f tasks.jsonl -p resources
[ -f resources/tasks.jsonl.zip ] && unzip -o -q resources/tasks.jsonl.zip -d resources && rm resources/tasks.jsonl.zip
python3 -u scripts/download_all.py --graphs-only

# Large stratum
python3 scripts/stratify.py --graphs-only
python3 scripts/extract_tests.py
python3 scripts/merge_gold_structure.py

# Compact stratum
python3 scripts/stratify.py --gdir data/compact_graphs \
    --out data/compact_structure.csv --summary resources/compact_stratification.json
python3 scripts/build_compact_joined.py

echo "Done. Verify: notebooks/reproduce.ipynb"

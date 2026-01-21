#!/usr/bin/env bash
set -euo pipefail

# Run unit tests and a simple import verification.
# Place this file in `python/tools/` and run from the repo root:
#   bash python/tools/test.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[test.sh] Running pytest on all tests under python/tools..."
if pytest -q python/tools -q; then
    echo "[test.sh] TESTS: PASS"
    TEST_RC=0
else
    echo "[test.sh] TESTS: FAIL"
    TEST_RC=1
fi

echo "[test.sh] Running import verification..."
python3 - <<'PY'
import sys
sys.path.insert(0, "")
ok = True
errs = []
for mod in ("python.transports", "python.connection_organiser_adapter"):
    try:
        __import__(mod)
    except Exception as e:
        ok = False
        errs.append((mod, str(e)))

if ok:
    print("[test.sh] IMPORTS: OK")
    sys.exit(0)
else:
    print("[test.sh] IMPORTS: FAIL")
    for m,e in errs:
        print(f" - {m}: {e}")
    sys.exit(2)
PY

exit $TEST_RC

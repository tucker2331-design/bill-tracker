#!/bin/bash
# Fetch LIS bill-details pages via headless Chrome, 8x parallel.
#
# Usage: bash tools/crossover_audit/fetch_bills.sh /tmp/lis_audit/to_fetch.txt
#
# Outputs /tmp/lis_audit/<BILL>.html for each bill ID.
# Skips bills that already have a valid dump (≥15KB). Retries undersized dumps
# with a longer virtual-time-budget.

set -u

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LIST="${1:-/tmp/lis_audit/to_fetch.txt}"
OUTDIR="/tmp/lis_audit"
PARALLEL=8
MIN_SIZE=15000

if [ ! -f "$LIST" ]; then
    echo "ERROR: bill list not found: $LIST" >&2
    echo "Run: python3 tools/crossover_audit/build_universe.py" >&2
    exit 1
fi

mkdir -p "$OUTDIR"

fetch_one() {
    local bill="$1"
    local out="$OUTDIR/${bill}.html"
    # Skip if already have a good dump
    if [ -f "$out" ]; then
        local existing
        existing=$(wc -c < "$out")
        if [ "$existing" -ge "$MIN_SIZE" ]; then
            echo "  ${bill}: skip (${existing}B cached)"
            return 0
        fi
    fi
    "$CHROME" --headless=new --disable-gpu --virtual-time-budget=15000 \
        --dump-dom "https://lis.virginia.gov/bill-details/20261/${bill}" \
        > "$out" 2>/dev/null
    local size
    size=$(wc -c < "$out")
    if [ "$size" -lt "$MIN_SIZE" ]; then
        "$CHROME" --headless=new --disable-gpu --virtual-time-budget=25000 \
            --dump-dom "https://lis.virginia.gov/bill-details/20261/${bill}" \
            > "$out" 2>/dev/null
        size=$(wc -c < "$out")
    fi
    echo "  ${bill}: ${size}B"
}

export -f fetch_one
export OUTDIR CHROME MIN_SIZE

echo "Fetching $(wc -l < "$LIST") bills with ${PARALLEL}x parallelism..."
xargs -P "$PARALLEL" -I {} bash -c 'fetch_one "$@"' _ {} < "$LIST"
echo "Done."

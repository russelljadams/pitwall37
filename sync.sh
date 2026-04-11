#!/bin/bash
# Sync IBT telemetry files from GPU box via Tailscale SSH
# Usage: ./sync.sh [car_filter]
# Default: superformulalights324

CAR="${1:-superformulalights324}"
GPU="gpu"
IBT_SRC='C:\Users\russell\Documents\iRacing\telemetry'
IBT_DST="/home/gh0st/projects/pitwall37/data/ibt"

echo "=== PitWall37 Sync ==="
echo "Car filter: ${CAR}_*"

# Test connectivity
if ! ssh -o ConnectTimeout=5 "$GPU" "echo ok" > /dev/null 2>&1; then
    echo "ERROR: Cannot reach GPU box via SSH"
    exit 1
fi

# Get list of remote files
echo "Scanning remote files..."
REMOTE_FILES=$(ssh "$GPU" "powershell -Command \"(Get-ChildItem ${IBT_SRC}\\${CAR}_*.ibt).Name\"" 2>/dev/null)
REMOTE_COUNT=$(echo "$REMOTE_FILES" | grep -c '.ibt')
LOCAL_COUNT=$(ls -1 "${IBT_DST}/${CAR}_"*.ibt 2>/dev/null | wc -l)

echo "Remote: ${REMOTE_COUNT} files, Local: ${LOCAL_COUNT} files"

# Find new files (not yet in local dir)
NEW=0
FAILED=0
while IFS= read -r fname; do
    [ -z "$fname" ] && continue
    fname=$(echo "$fname" | tr -d '\r')
    [[ "$fname" != *.ibt ]] && continue
    if [ ! -f "${IBT_DST}/${fname}" ]; then
        echo "  Copying: ${fname}"
        scp "${GPU}:C:/Users/russell/Documents/iRacing/telemetry/${fname}" "${IBT_DST}/" 2>/dev/null
        if [ $? -eq 0 ]; then
            NEW=$((NEW + 1))
        else
            echo "  WARN: Failed to copy ${fname}"
            FAILED=$((FAILED + 1))
        fi
    fi
done <<< "$REMOTE_FILES"

echo ""
echo "Sync complete: ${NEW} new files copied, ${FAILED} failed"
echo "Total local: $(ls -1 "${IBT_DST}/${CAR}_"*.ibt 2>/dev/null | wc -l) files"

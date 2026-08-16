#!/usr/bin/env bash
# Pause vps_promote_7y_marts after collective commercial marts, before land.
LOG="${1:-/var/backups/ch2/promote_7y_20260810_025946.log}"
PAUSE_LOG=/var/backups/ch2/promote_pause.log
MARKER='collective_commercial_region_annual_stats upserted'

echo "watcher start $(date -Is) log=$LOG" >> "$PAUSE_LOG"

while true; do
  if [[ -f "$LOG" ]] && grep -q '==> land V2 marts' "$LOG"; then
    echo "land already started $(date -Is)" >> "$PAUSE_LOG"
    exit 2
  fi
  if [[ -f "$LOG" ]] && grep -q "$MARKER" "$LOG"; then
    sleep 2
    pkill -f 'build_stats_v2.py' 2>/dev/null || true
    pkill -f 'build_upper_stats_v2.py' 2>/dev/null || true
    pkill -f 'vps_promote_7y_marts.sh' 2>/dev/null || true
    pkill -f 'build_collective' 2>/dev/null || true
    echo "stopped after commercial $(date -Is)" >> "$PAUSE_LOG"
    grep -E 'commercial.*upserted|market_stats upserted|==> land' "$LOG" | tail -8 >> "$PAUSE_LOG"
    exit 0
  fi
  sleep 20
done

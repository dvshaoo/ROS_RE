#!/usr/bin/env bash
# E2E-006 reply-ID offset/width sweep driver.
# Runs a series of (offset,width,endian) candidates against the live client,
# capturing logcat for each, so the client's own retry-vs-proceed behavior
# can be used as the pass/fail oracle (no root/Frida needed).
set -u
ADB="/c/LDPlayer/LDPlayer9/adb.exe"
PY="/c/Python314/python.exe"
REPO="/c/Users/Raysoo/Downloads/ROS_RE"
OUT="$REPO/scratch/sweep_results"
mkdir -p "$OUT"

PLAY_X=952
PLAY_Y=800
CONFIRM_X=952
CONFIRM_Y=701

run_variant() {
  offset=$1; width=$2; endian=$3
  tag="o${offset}_w${width}_${endian}"
  echo "=== [$tag] starting ==="
  cd "$REPO"
  SWEEP_OFFSET=$offset SWEEP_WIDTH=$width SWEEP_ENDIAN=$endian SWEEP_ACTIVE=1 \
    "$PY" mitm/local_baseapp_capture.py > "$OUT/server_${tag}.log" 2>&1 &
  SERVER_PID=$!
  sleep 1.5
  $ADB -s emulator-5554 logcat -c
  $ADB -s emulator-5554 shell input tap $PLAY_X $PLAY_Y
  sleep 11
  $ADB -s emulator-5554 logcat -d > "$OUT/logcat_${tag}.txt"
  kill $SERVER_PID 2>/dev/null
  sleep 0.5
  # dismiss any resulting error dialog + relaunch to title, best-effort
  $ADB -s emulator-5554 shell input tap $CONFIRM_X $CONFIRM_Y
  sleep 1
  # classify result
  if grep -q "onLoginReply" "$OUT/logcat_${tag}.txt"; then
    result="REACHED_ONLOGINREPLY"
  elif grep -q "Couldn't find handler for reply id" "$OUT/logcat_${tag}.txt"; then
    result="FAIL_NO_HANDLER"
  elif grep -q "logOnComplete" "$OUT/logcat_${tag}.txt"; then
    result="FAIL_LOGONCOMPLETE_OTHER"
  else
    result="UNKNOWN_NO_SIGNAL"
  fi
  echo "[$tag] RESULT=$result"
  echo "$tag,$result" >> "$OUT/SUMMARY.csv"
}

echo "tag,result" > "$OUT/SUMMARY.csv"

# Candidate list, in priority order (most PC-launcher-analogous first):
run_variant 5 4 little   # PC-analogous: uint32 at offset 5 (vs current default u16)
run_variant 6 2 little   # PC's ORIGINAL WRONG assumption, tested for completeness
run_variant 6 4 little
run_variant 5 4 big
run_variant 3 4 little
run_variant 7 4 little
run_variant 9 4 little
run_variant 5 2 big      # current default's width but big-endian

echo "=== SWEEP DONE ==="
cat "$OUT/SUMMARY.csv"

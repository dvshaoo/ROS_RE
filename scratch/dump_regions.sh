#!/usr/bin/env bash
# Dump all libc_malloc / [heap] regions of a target PID to local files via
# adb exec-out (binary-safe, avoids CRLF mangling that plain `adb shell`
# redirection risks on Windows), for an offline vtable-pointer scan.
set -u
ADB="/c/LDPlayer/LDPlayer9/adb.exe"
PID="$1"
OUTDIR="$2"
mkdir -p "$OUTDIR"
$ADB -s emulator-5554 shell "su 0 cat /proc/$PID/maps" > "$OUTDIR/maps.txt"
grep -E "libc_malloc|\[heap\]" "$OUTDIR/maps.txt" | while read -r line; do
  range=$(echo "$line" | awk '{print $1}')
  start_hex=${range%-*}
  end_hex=${range#*-}
  start=$((16#$start_hex))
  end=$((16#$end_hex))
  size=$((end - start))
  outfile="$OUTDIR/region_${start_hex}.bin"
  echo "Dumping $start_hex-$end_hex (${size} bytes) -> $outfile"
  $ADB -s emulator-5554 exec-out "su 0 dd if=/proc/$PID/mem bs=4096 skip=$((start/4096)) count=$((size/4096)) 2>/dev/null" > "$outfile"
done
echo "DONE"

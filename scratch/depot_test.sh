#!/bin/bash
# usage: depot_test.sh <label>   (hall must be showing). Opens Depot, tries X, then Android Back; logs SCRIPT ERRORs.
export MSYS_NO_PATHCONV=1
A="/c/LDPlayer/LDPlayer9/adb.exe -s emulator-5554"
L=$1; D=/c/Users/Raysoo/Downloads/ROS_RE/scratch
$A logcat -c
$A logcat > $D/depot_${L}_logcat.txt &
LP=$!
shot(){ $A shell screencap -p /sdcard/c.png; $A pull /sdcard/c.png $D/depot_${L}_$1.png >/dev/null; }
sleep 2; $A shell input tap 70 820; sleep 8; shot 1_open
$A shell input keyevent 4; sleep 6; shot 2_back
kill $LP
echo "errors after depot open+back: $(grep -ac 'SCRIPT ERROR' $D/depot_${L}_logcat.txt)"
grep -a -A25 'SCRIPT ERROR' $D/depot_${L}_logcat.txt | grep -aE 'File "|Error' | sed -E 's/^.*<SCRIPT> : *//' | cut -c1-140

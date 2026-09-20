#!/bin/bash
# fresh login -> guide -> SUPPLY -> FIREARMS tab -> Skip -> DRAW 1x -> screenshots + server draw log. usage: draw_test.sh <label>  (hands off!)
export MSYS_NO_PATHCONV=1
D=/c/Users/Raysoo/Downloads/ROS_RE; cd $D; L=$1
A="/c/LDPlayer/LDPlayer9/adb.exe -s emulator-5554"
$A shell am force-stop com.netease.chiji
rm -f scratch/fresh_${L}_*; (scratch/fresh_run.sh $L > scratch/fresh_${L}_summary.txt 2>&1 &)
sleep 25; N0=$(grep -ac "STAGE 3: loaded" scratch/server_redpoints.out)
for i in 1 2 3 4 5 6; do N=$(grep -ac "STAGE 3: loaded" scratch/server_redpoints.out); [ "$N" -gt "$N0" ] && break; $A shell input tap 815 230; sleep 4; $A shell input tap 960 790; sleep 10; done
until grep -q "SCRIPT ERROR count" scratch/fresh_${L}_summary.txt 2>/dev/null; do sleep 4; done
sleep 8; $A shell input tap 100 45; sleep 2; $A shell input tap 1620 980; sleep 4
$A shell input tap 70 380; sleep 8
$A shell input tap 85 695; sleep 14; $A shell input tap 1680 990; sleep 6
$A shell screencap -p /sdcard/c.png; $A pull /sdcard/c.png scratch/${L}_before.png >/dev/null
$A logcat -c
$A shell input tap 1320 990; sleep 10
$A shell screencap -p /sdcard/c.png; $A pull /sdcard/c.png scratch/${L}_after1.png >/dev/null
sleep 6; $A shell screencap -p /sdcard/c.png; $A pull /sdcard/c.png scratch/${L}_after2.png >/dev/null
grep -aE "openSupplyBox|prizes=" scratch/server_redpoints.out | tail -4 | cut -c1-200
timeout 30 $A logcat -d | grep -a -A25 "SCRIPT ERROR" | grep -aE 'File "(ui|entities|common)|Error' | sed -E 's/^.*<SCRIPT> : *//' | cut -c1-150 | tail -8
echo DONE

#!/bin/bash
# fresh login -> guide -> SUPPLY -> each tab: screenshot after 18 s (VEHICLE also after one Skip tap). Hands off! usage: tab_test.sh <label>
export MSYS_NO_PATHCONV=1
D=/c/Users/Raysoo/Downloads/ROS_RE; cd $D; L=$1
A="/c/LDPlayer/LDPlayer9/adb.exe -s emulator-5554"
$A shell am force-stop com.netease.chiji
rm -f scratch/fresh_${L}_*; (scratch/fresh_run.sh $L > scratch/fresh_${L}_summary.txt 2>&1 &)
sleep 25; N0=$(grep -ac "STAGE 3: loaded" scratch/server_redpoints.out)
for i in 1 2 3 4 5 6; do N=$(grep -ac "STAGE 3: loaded" scratch/server_redpoints.out); [ "$N" -gt "$N0" ] && break; $A shell input tap 815 230; sleep 4; $A shell input tap 960 790; sleep 10; done
until grep -q "SCRIPT ERROR count" scratch/fresh_${L}_summary.txt 2>/dev/null; do sleep 4; done
sleep 8; $A shell input tap 100 45; sleep 2; $A shell input tap 1620 980; sleep 4
$A logcat -c
$A shell input tap 70 380; sleep 8
for t in 280 385 485 590 695; do
  $A shell input tap 85 $t; sleep 18; $A shell screencap -p /sdcard/c.png; $A pull /sdcard/c.png scratch/${L}_tab$t.png >/dev/null
  if [ $t = 590 ]; then $A shell input tap 1680 990; sleep 8; $A shell screencap -p /sdcard/c.png; $A pull /sdcard/c.png scratch/${L}_tab590skip.png >/dev/null; fi
done
timeout 30 $A logcat -d | grep -a -A25 "SCRIPT ERROR" | grep -aE 'File "(ui|entities|common)|Error' | sed -E 's/^.*<SCRIPT> : *//' | cut -c1-150 | tail -8
grep -a "SUPPLEMENT:" scratch/server_redpoints.out | tail -1 | cut -c1-160
echo DONE

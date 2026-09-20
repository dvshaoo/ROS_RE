#!/bin/bash
# usage: fresh_run.sh <label>  -- fresh login, tap controls Confirm, capture hall + full SCRIPT ERROR list
export MSYS_NO_PATHCONV=1 ADB_PATH='C:\LDPlayer\LDPlayer9\adb.exe' ROS_SERVER_LOG='C:\Users\Raysoo\Downloads\ROS_RE\scratch\server_redpoints.out'
D=/c/Users/Raysoo/Downloads/ROS_RE/scratch; L=$1
A="/c/LDPlayer/LDPlayer9/adb.exe -s emulator-5554"
$A logcat -c; $A logcat > $D/fresh_${L}_logcat.txt & LP=$!
cd /c/Users/Raysoo/Downloads/ROS_RE; python scratch/drive_login.py scratch/fresh_${L}_drive.txt > $D/fresh_${L}_drive.out 2>&1
sleep 15; $A shell input tap 960 953
sleep 75
$A shell screencap -p /sdcard/c.png; $A pull /sdcard/c.png $D/fresh_${L}_hall.png >/dev/null
kill $LP
echo "SCRIPT ERROR count: $(grep -ac 'SCRIPT ERROR' $D/fresh_${L}_logcat.txt)"
grep -a -A25 'SCRIPT ERROR' $D/fresh_${L}_logcat.txt | grep -aE 'File "(ui|entities|extconfigs)|Error' | sed -E 's/^.*<SCRIPT> : *//' | cut -c1-140

@echo off
REM Launch ROS.
REM
REM HISTORY (2026-09-26, Checkpoint 23): the "Invalid login. Please log in again."
REM dialog this script used to spam-dismiss is RESOLVED -- it was stale/corrupted
REM local session state left over from patch-testing, not a client code bug or a
REM timing race. See CLAUDE.md section 0.2. It no longer appears on a clean
REM device, so this script no longer looks for it.
REM
REM REMAINING KNOWN ISSUE (still open, separate bug): after login succeeds,
REM MpayActivity sometimes does not call finish() and is left as the resumed
REM activity showing only its own loading spinner -- a blank, button-less
REM overlay that swallows all touches meant for the game underneath, which is
REM already fully loaded and rendering behind it. This is NOT a dialog asking
REM for a decision; there is nothing to read or agree to, nothing a real
REM interactive tap would ever land on. Pressing the Android BACK button once
REM finishes the stuck activity and hands control straight back to the game
REM (confirmed live, works every time). This script automates exactly that one
REM BACK press, and only after MpayActivity has been the resumed activity for
REM longer than any real login round-trip should take -- it does not touch,
REM confirm, or dismiss anything inside an actual dialog.
REM
REM IMPORTANT: do NOT delete com.netease.mpay.*.xml shared_prefs to "fix" this --
REM that is an unrelated, separate bug that guarantees a different cold-start
REM dialog (see reapply_env_setup.sh comment). Do NOT run `pm clear` as part of
REM normal launching either -- it wipes patchVersion (see CLAUDE.md 0.1) and
REM should only be used deliberately to recover from a suspected corrupted
REM session state, with OBB + patchVersion restored immediately after.

setlocal enabledelayedexpansion
set "ADB=C:\LDPlayer\LDPlayer9\adb.exe"
set SER=-s emulator-5554

REM Tap coordinates below are in the CURRENT (rotated, landscape) input space,
REM i.e. the same 1920x1080 space screencap/screenshots show -- NOT the portrait
REM "Physical size" that `wm size` reports for this device.
set CONTROLS_CONFIRM_X=960
set CONTROLS_CONFIRM_Y=955

echo [1/4] Force-stopping any running instance...
%ADB% %SER% shell am force-stop com.netease.chiji
timeout /t 1 /nobreak >nul

echo [2/4] Launching ROS...
%ADB% %SER% shell am start -n com.netease.chiji/com.netease.neox.Launcher

echo [3/4] Watching for a stuck MpayActivity overlay (up to 60s)...
REM MpayActivity legitimately appears for a few seconds during real login
REM traffic -- only treat it as "stuck" once it has been resumed continuously
REM for MPAY_STUCK_THRESHOLD seconds, then send exactly one BACK press.
set ELAPSED=0
set MPAY_STREAK=0
set MPAY_STUCK_THRESHOLD=10
set BACK_SENT=0

:WAIT_LOOP
%ADB% %SER% shell "dumpsys activity activities 2>/dev/null | grep mResumedActivity" > "%TEMP%\ros_resumed.txt" 2>nul
findstr /c:"MpayActivity" "%TEMP%\ros_resumed.txt" >nul
if %ERRORLEVEL%==0 (
    set /a MPAY_STREAK+=2
    if !MPAY_STREAK! GEQ %MPAY_STUCK_THRESHOLD% (
        if "!BACK_SENT!"=="0" (
            echo       MpayActivity stuck for ~!MPAY_STREAK!s with no dialog visible -- sending one BACK press...
            %ADB% %SER% shell input keyevent KEYCODE_BACK
            set BACK_SENT=1
            timeout /t 2 /nobreak >nul
        )
    )
) else (
    set MPAY_STREAK=0
    findstr /c:"neox.Client" "%TEMP%\ros_resumed.txt" >nul
    if !ERRORLEVEL!==0 (
        echo       Game activity resumed -- login flow clear.
        goto :TITLE_REACHED
    )
)
timeout /t 2 /nobreak >nul
set /a ELAPSED+=2
if %ELAPSED% LSS 60 goto :WAIT_LOOP

echo       Timed out waiting -- continuing anyway, check screen manually.

:TITLE_REACHED
echo [4/4] Waiting for "Please select controls" confirm countdown, then confirming...
timeout /t 17 /nobreak >nul
%ADB% %SER% shell input tap %CONTROLS_CONFIRM_X% %CONTROLS_CONFIRM_Y%

timeout /t 5 /nobreak >nul
echo Final state:
%ADB% %SER% shell dumpsys activity activities 2>nul | find "mResumedActivity"

echo.
echo Done.
goto :DONE

:DONE
pause

@echo off
REM Launch ROS and auto-dismiss the "Invalid login. Please log in again." popup.
REM
REM Root cause (2026-09-25, scratch/HANDOFF_PROMPT_CLAUDE.md): the MPay SDK's
REM shouldAutoLogin() check fails on every cold start (no/expired saved session),
REM which shows this dialog via com.netease.mpay.oversea.ui.l$c ~50% into the
REM patch-check loading bar. Tapping "Confirm" switches to a fresh guest/channel
REM login and the game proceeds cleanly -- our server handles that login fine.
REM
REM IMPORTANT: do NOT delete com.netease.mpay.*.xml shared_prefs to "fix" this --
REM that guarantees the dialog fires every launch instead (see reapply_env_setup.sh).

setlocal enabledelayedexpansion
set "ADB=C:\LDPlayer\LDPlayer9\adb.exe"
set SER=-s emulator-5554

echo [1/5] Force-stopping any running instance...
%ADB% %SER% shell am force-stop com.netease.chiji
timeout /t 1 /nobreak >nul

echo [2/5] Detecting screen resolution...
set WIDTH=1080
set HEIGHT=1920
for /f "tokens=3 delims=: " %%A in ('%ADB% %SER% shell wm size ^| find "Physical size"') do set RES=%%A
if defined RES (
    for /f "tokens=1,2 delims=x" %%A in ("%RES%") do (
        set WIDTH=%%A
        set HEIGHT=%%B
    )
)
echo       Resolution: %WIDTH%x%HEIGHT%

REM Confirm button bounds measured at 1080x1920: [780,646][1125,757] -> center (952, 701).
REM Scale that reference point to whatever resolution wm size reports.
set /a TAP_X=(%WIDTH% * 952) / 1080
set /a TAP_Y=(%HEIGHT% * 701) / 1920
echo       Confirm button tap point: (%TAP_X%, %TAP_Y%)

echo [3/5] Launching ROS...
%ADB% %SER% shell am start -n com.netease.chiji/com.netease.neox.Launcher
echo       Waiting for the "Invalid login" dialog (MpayActivity)...

REM Poll for MpayActivity; it typically appears ~15-25s after launch (~50% into
REM the patch-check progress bar), well before the 3D intro video / title screen.
set ATTEMPTS=0
:WAIT_MPAY
timeout /t 2 /nobreak >nul
set /a ATTEMPTS+=1
if %ATTEMPTS% GTR 30 (
    echo [!] Timed out waiting for MpayActivity after 60s. It may not have appeared this run.
    goto :DONE
)
%ADB% %SER% shell "dumpsys activity activities 2>/dev/null | grep -c MpayActivity" > "%TEMP%\ros_mpay_check.txt" 2>nul
set /p MPAY_COUNT=<"%TEMP%\ros_mpay_check.txt"
if "%MPAY_COUNT%"=="" set MPAY_COUNT=0
if "%MPAY_COUNT%"=="0" (
    echo       ... waiting (%ATTEMPTS%/30)
    goto :WAIT_MPAY
)

echo [4/5] MpayActivity detected! Auto-tapping Confirm at (%TAP_X%, %TAP_Y%)...
%ADB% %SER% shell input tap %TAP_X% %TAP_Y%

echo [5/5] Verifying dismissal...
timeout /t 2 /nobreak >nul
%ADB% %SER% shell "dumpsys activity activities 2>/dev/null | grep -c MpayActivity" > "%TEMP%\ros_mpay_check.txt" 2>nul
set /p MPAY_COUNT2=<"%TEMP%\ros_mpay_check.txt"
if "%MPAY_COUNT2%"=="0" (
    echo [OK] MpayActivity dismissed! Game proceeding to title screen...
) else (
    echo [!] MpayActivity still active. Retrying tap...
    %ADB% %SER% shell input tap %TAP_X% %TAP_Y%
    timeout /t 2 /nobreak >nul
)

echo.
echo Done! Game should reach the title screen / PLAY button cleanly.

:DONE
pause

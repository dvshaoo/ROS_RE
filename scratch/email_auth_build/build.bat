@echo off
set "ANDROID_JAR=C:\Users\Raysoo\AppData\Local\Android\Sdk\platforms\android-34\android.jar"
set "D8=C:\Users\Raysoo\AppData\Local\Android\Sdk\build-tools\34.0.0\d8.bat"
set "APKTOOL=C:\Users\Raysoo\Downloads\ROS_RE\tools\apktool.jar"
set "BUILD_DIR=C:\Users\Raysoo\Downloads\ROS_RE\scratch\email_auth_build"

echo [1/4] Compiling Java...
javac -source 8 -target 8 -cp "%ANDROID_JAR%" -d "%BUILD_DIR%\out" "%BUILD_DIR%\src\EmailAuthActivity.java" "%BUILD_DIR%\src\MpayWatcherService.java"
if errorlevel 1 exit /b 1

echo [2/4] Compiling BaksmaliDriver...
javac -cp "%APKTOOL%" -d "%BUILD_DIR%\driver_out" "%BUILD_DIR%\BaksmaliDriver.java"
if errorlevel 1 exit /b 1

echo [3/4] Dexing classes...
del /q "%BUILD_DIR%\dex_out\*.dex" 2>nul
call "%D8%" --output "%BUILD_DIR%\dex_out" "%BUILD_DIR%\out\com\netease\chiji\*.class"
if errorlevel 1 exit /b 1

echo [4/4] Disassembling to smali...
rmdir /s /q "%BUILD_DIR%\smali_out" 2>nul
mkdir "%BUILD_DIR%\smali_out" 2>nul
java -cp "%BUILD_DIR%\driver_out;%APKTOOL%" BaksmaliDriver "%BUILD_DIR%\dex_out\classes.dex" "%BUILD_DIR%\smali_out"
if errorlevel 1 exit /b 1

echo Done!

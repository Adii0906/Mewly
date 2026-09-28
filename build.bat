@echo off
setlocal EnableExtensions
cd /d "%~dp0"
:: ===========================================================================
:: Mewly - Windows build script
::
:: Produces dist\Mewly.exe: ONE self-contained 64-bit executable. Python,
:: PyQt6 + Qt (with the Windows platform plugin), the Microsoft C++ runtime
:: and all assets are bundled, so end users need nothing installed.
::
:: The build never uses the developer's global Python packages: it creates a
:: fresh virtual environment, runs with a minimal PATH, verifies the
:: environment, builds from Mewly.spec and finally self-tests the .exe in a
:: clean environment.
::
:: Usage:  build.bat          (asks to run Mewly at the end)
::         build.bat /norun   (for CI / scripted builds)
:: ===========================================================================

set "VENV=%~dp0.build-venv"
set "PY=%VENV%\Scripts\python.exe"

echo [Mewly] 1/7  Looking for 64-bit Python 3.10+ ...
set "BASEPY="
set "PYCHECK=import sys; raise SystemExit(0 if sys.version_info >= (3, 10) and sys.maxsize > 2**32 else 1)"
where py >nul 2>nul && py -3 -c "%PYCHECK%" >nul 2>nul && set "BASEPY=py -3"
if not defined BASEPY python -c "%PYCHECK%" >nul 2>nul && set "BASEPY=python"
if not defined BASEPY (
    echo [Mewly] ERROR: 64-bit Python 3.10 or newer was not found.
    echo         Install it from https://www.python.org/downloads/ ^(tick "Add to PATH"^).
    goto :fail
)
echo         using: %BASEPY%

echo [Mewly] 2/7  Removing previous build artifacts ...
taskkill /IM Mewly.exe /F >nul 2>nul
taskkill /IM CodingCat.exe /F >nul 2>nul
if exist "build"     rmdir /s /q "build"
if exist "dist"      rmdir /s /q "dist"
if exist "%VENV%"    rmdir /s /q "%VENV%"
if exist "CodingCat.spec" del /q "CodingCat.spec"
if exist "main.spec"      del /q "main.spec"
for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"

echo [Mewly] 3/7  Creating a clean, isolated build environment ...
%BASEPY% -m venv "%VENV%" || goto :fail
:: From here on nothing from the developer machine may leak into the build:
:: PATH only contains Windows itself (PyInstaller searches PATH for DLLs, so a
:: stray old msvcp140.dll / Qt folder on PATH would otherwise get bundled),
:: and Python/Qt variables that redirect imports or plugins are cleared.
set "PATH=%VENV%\Scripts;%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0"
set "PYTHONPATH="
set "PYTHONHOME="
set "PYTHONNOUSERSITE=1"
set "QT_PLUGIN_PATH="
set "QT_QPA_PLATFORM_PLUGIN_PATH="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
"%PY%" -m pip install --upgrade pip || goto :fail
"%PY%" -m pip install --upgrade -r requirements-build.txt || goto :fail

echo [Mewly] 4/7  Verifying the build environment ...
"%PY%" tools\check_build_env.py || goto :fail

echo [Mewly] 5/7  Generating icon (if missing) ...
"%PY%" utils\icon_gen.py

echo [Mewly] 6/7  Building dist\Mewly.exe ...
"%PY%" -m PyInstaller --noconfirm --clean --log-level WARN Mewly.spec || goto :fail
if not exist "dist\Mewly.exe" (
    echo [Mewly] ERROR: dist\Mewly.exe was not produced.
    goto :fail
)

echo [Mewly] 7/7  Self-testing dist\Mewly.exe in a clean environment ...
:: Only Windows on PATH, no Python/Qt variables: like a fresh user machine.
set "SELFTEST=%TEMP%\mewly-selftest-%RANDOM%.txt"
setlocal
set "PATH=%SystemRoot%\System32;%SystemRoot%"
set "VIRTUAL_ENV="
start "" /wait "%~dp0dist\Mewly.exe" --self-test "%SELFTEST%"
endlocal & set "SELFTEST_RC=%ERRORLEVEL%"
if exist "%SELFTEST%" type "%SELFTEST%"
if not "%SELFTEST_RC%"=="0" (
    echo [Mewly] SELF-TEST FAILED ^(exit code %SELFTEST_RC%^). See the report above and %USERPROFILE%\.coding_cat\cat.log
    goto :fail
)
if not exist "%SELFTEST%" (
    echo [Mewly] SELF-TEST FAILED: the exe produced no report.
    goto :fail
)
del /q "%SELFTEST%" >nul 2>nul

echo.
echo [Mewly] Build complete and verified: dist\Mewly.exe
echo         Share just that one file - no Python, Qt or DLL setup needed.
if /I "%~1"=="/norun" exit /b 0

:askrun
set /p runNow=Run Mewly now? (Y/N): 
if /I "%runNow%"=="Y" goto run_cat
if /I "%runNow%"=="N" goto end
echo Please enter Y or N.
goto askrun

:run_cat
echo Starting Mewly...
start "" "%~dp0dist\Mewly.exe"

:monitor
echo.
echo Options: (C)lose Mewly  (Q)uit
set /p action=Enter choice: 
if /I "%action%"=="C" (
	echo Closing Mewly...
	taskkill /IM Mewly.exe /F 2>nul || echo Could not kill process. Try running this script as Administrator.
	goto end
)
if /I "%action%"=="Q" goto end
echo Invalid choice.
goto monitor

:fail
echo.
echo [Mewly] BUILD FAILED - see the messages above.
if /I not "%~1"=="/norun" pause
exit /b 1

:end
rem Overwrite stop script with robust stop + cleanup logic
>"%~dp0stop_codingcat.bat" echo @echo off
>>"%~dp0stop_codingcat.bat" echo powershell -NoProfile -ExecutionPolicy Bypass -Command "^\
$ErrorActionPreference = 'SilentlyContinue'; Write-Output 'Stopping CodingCat processes...'; ^\
$names = @('CodingCat','codingcat','coding-cat','coding_cat','Mewly'); ^\
for ($i=0; $i -lt 8; $i++) { ^\
	$procs = Get-Process | Where-Object { $names -contains $_.ProcessName }; ^\
	if (-not $procs) { break } ^\
	$procs | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } ^\
	Start-Sleep -Milliseconds 400 ^\
} ^\
$remaining = Get-Process | Where-Object { $names -contains $_.ProcessName }; ^\
if ($remaining) { Write-Output 'Some CodingCat processes remain. Try running this script as Administrator.'; $remaining | Format-Table Id, ProcessName, MainWindowTitle -AutoSize } else { Write-Output 'Stopped all CodingCat processes.' } ; ^\
Write-Output 'Removing CodingCat/Mewly scheduled tasks (exact names only)...'; ^\
Get-ScheduledTask | Where-Object { $names -contains $_.TaskName } | ForEach-Object { Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false -ErrorAction SilentlyContinue } ; ^\
Write-Output 'Removing CodingCat/Mewly Run registry entries (HKCU, exact names only)...'; ^\
Get-ItemProperty -Path HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run -ErrorAction SilentlyContinue | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name | Where-Object { $names -contains $_ } | ForEach-Object { Remove-ItemProperty -Path HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run -Name $_ -ErrorAction SilentlyContinue } ; ^\
Write-Output 'Removing CodingCat/Mewly startup shortcuts...'; ^\
$startup = [Environment]::GetFolderPath('Startup'); Get-ChildItem -Path $startup -Filter 'CodingCat*' -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue } ; ^\
$common = [Environment]::GetFolderPath('CommonStartup'); Get-ChildItem -Path $common -Filter 'CodingCat*' -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue } ; ^\
Write-Output 'Done.'; pause"

rem Create a Desktop shortcut named "Cancel CodingCat" with hotkey Ctrl+Alt+C
powershell -NoProfile -Command "
$ws = New-Object -ComObject WScript.Shell;
$desk = [Environment]::GetFolderPath('Desktop');
$lnk = $ws.CreateShortcut($desk + '\\Cancel CodingCat.lnk');
$lnk.TargetPath = '%~dp0stop_codingcat.bat';
$lnk.WorkingDirectory = '%~dp0';
$lnk.Hotkey = 'Ctrl+Alt+C';
$lnk.WindowStyle = 1;
$lnk.Save();
" 2>nul

echo Created cancel shortcut on your Desktop (Ctrl+Alt+C).
pause

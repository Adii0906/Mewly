@echo off
:: =========================================================
:: CodingCat Build Script for Windows
:: Run from the project root:  build.bat
:: =========================================================

echo [CodingCat] Installing dependencies...
pip install -r requirements.txt

echo [CodingCat] Generating icon...
python utils/icon_gen.py

echo [CodingCat] Building executable...
pyinstaller --noconfirm coding_cat.spec

echo [CodingCat] Build complete!
echo Output: dist\CodingCat.exe
echo [CodingCat] Build complete!
echo Output: dist\CodingCat.exe

:askrun
set /p runNow=Run CodingCat now? (Y/N): 
if /I "%runNow%"=="Y" goto run_cat
if /I "%runNow%"=="N" goto end
echo Please enter Y or N.
goto askrun

:run_cat
echo Starting CodingCat...
start "" "%~dp0dist\CodingCat.exe"

:monitor
echo.
echo Options: (C)lose CodingCat  (R)elaunch  (Q)uit
set /p action=Enter choice: 
if /I "%action%"=="C" (
	echo Closing CodingCat...
	taskkill /IM CodingCat.exe /F 2>nul || echo Could not kill process. Try running this script as Administrator.
	goto end
)
if /I "%action%"=="C" (
	echo Closing CodingCat...
	call "%~dp0stop_codingcat.bat"
	goto end
)
if /I "%action%"=="Q" goto end
echo Invalid choice.
goto monitor

:end
rem Overwrite stop script with robust stop + cleanup logic
>"%~dp0stop_codingcat.bat" echo @echo off
>>"%~dp0stop_codingcat.bat" echo powershell -NoProfile -ExecutionPolicy Bypass -Command "^\
$ErrorActionPreference = 'SilentlyContinue'; Write-Output 'Stopping CodingCat processes...'; ^\
$names = @('CodingCat','codingcat','coding-cat','coding_cat'); ^\
for ($i=0; $i -lt 8; $i++) { ^\
	$procs = Get-Process | Where-Object { $names -contains $_.ProcessName -or ($_.MainWindowTitle -and $_.MainWindowTitle -match 'Coding') }; ^\
	if (-not $procs) { break } ^\
	$procs | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } ^\
	Start-Sleep -Milliseconds 400 ^\
} ^\
$remaining = Get-Process | Where-Object { $names -contains $_.ProcessName -or ($_.MainWindowTitle -and $_.MainWindowTitle -match 'Coding') }; ^\
if ($remaining) { Write-Output 'Some CodingCat processes remain. Try running this script as Administrator.'; $remaining | Format-Table Id, ProcessName, MainWindowTitle -AutoSize } else { Write-Output 'Stopped all CodingCat processes.' } ; ^\
Write-Output 'Removing scheduled tasks named like Coding/Cat (if any)...'; ^\
Get-ScheduledTask | Where-Object { $_.TaskName -match 'Coding|Cat' } | ForEach-Object { Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false -ErrorAction SilentlyContinue } ; ^\
Write-Output 'Removing Run registry entries (HKCU/HKLM) that match Coding/Cat...'; ^\
Get-ItemProperty -Path HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run -ErrorAction SilentlyContinue | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name | Where-Object { $_ -match 'Coding|Cat' } | ForEach-Object { Remove-ItemProperty -Path HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run -Name $_ -ErrorAction SilentlyContinue } ; ^\
Get-ItemProperty -Path HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run -ErrorAction SilentlyContinue | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name | Where-Object { $_ -match 'Coding|Cat' } | ForEach-Object { Remove-ItemProperty -Path HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run -Name $_ -ErrorAction SilentlyContinue } ; ^\
Write-Output 'Removing startup shortcuts named like Coding/Cat...'; ^\
$startup = [Environment]::GetFolderPath('Startup'); Get-ChildItem -Path $startup -Filter '*Coding*' -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue } ; ^\
$common = [Environment]::GetFolderPath('CommonStartup'); Get-ChildItem -Path $common -Filter '*Coding*' -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue } ; ^\
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

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
pause

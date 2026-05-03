@echo off
chcp 65001 > nul
echo Building zapret-optimizer.exe...

:: Check Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    exit /b 1
)

:: Check if running in venv
if defined VIRTUAL_ENV (
    echo [OK] Using existing venv: %VIRTUAL_ENV%
) else (
    :: Check for existing .venv
    if exist ".venv\Scripts\activate.bat" (
        echo [OK] Activating existing .venv...
        call ".venv\Scripts\activate.bat"
    ) else (
        :: Create new venv
        echo Creating virtual environment...
        python -m venv .venv
        if errorlevel 1 (
            echo [ERROR] Failed to create venv
            exit /b 1
        )
        call ".venv\Scripts\activate.bat"
    )
)

:: Install dependencies if needed
echo Installing dependencies...
pip install -r requirements.txt

:: Build with PyInstaller
echo Building with PyInstaller...
python -m PyInstaller ^
    --onefile ^
    --name zapret-optimizer ^
    --clean ^
    --noconfirm ^
    --hidden-import cryptography ^
    --hidden-import cryptography.hazmat.primitives.asymmetric.x25519 ^
    --hidden-import cryptography.hazmat.primitives.serialization ^
    main.py

if errorlevel 1 (
    echo [ERROR] Build failed
    exit /b 1
)

echo.
echo [OK] Build complete!
echo Output: dist\zapret-optimizer.exe
echo.
echo To use:
echo   1. Place zapret-optimizer.exe next to your zapret folder
echo   2. Run: zapret-optimizer.exe init
echo   3. Run: zapret-optimizer.exe optimize
echo   4. Run: zapret-optimizer.exe run-best

pause

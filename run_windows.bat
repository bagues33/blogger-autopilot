@echo off
REM Double-click launcher for Windows
cd /d "%~dp0"

echo ==============================================
echo     Blogger Auto-Pilot & SEO Dashboard       
echo ==============================================
echo.

IF NOT EXIST ".venv" (
    echo [INFO] Menyiapkan virtual environment Python pertama kali...
    python -m venv .venv
    call .venv\Scripts\pip install -r requirements.txt
)

IF NOT EXIST "data.db" (
    echo [INFO] Menginisialisasi basis data...
    call .venv\Scripts\python db.py
    call .venv\Scripts\python migrate_multi_blog.py
)

echo [INFO] Membuka browser ke http://localhost:8090 ...
timeout /t 2 /nobreak >nul
start http://localhost:8090

echo.
echo Server aktif di http://localhost:8090
echo Tutup jendela ini untuk menghentikan aplikasi.
echo.

call .venv\Scripts\uvicorn app:app --host 0.0.0.0 --port 8090
pause

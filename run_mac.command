#!/usr/bin/env bash
# Double-click launcher for macOS
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=============================================="
echo "    Blogger Auto-Pilot & SEO Dashboard       "
echo "=============================================="
echo ""

# Auto setup virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "⚡ Menyiapkan lingkungan virtual environment Python..."
    if command -v uv &> /dev/null; then
        uv venv .venv
        uv pip install -r requirements.txt
    else
        python3 -m venv .venv
        .venv/bin/pip install -r requirements.txt
    fi
fi

# Auto initialize database if missing
if [ ! -f "data.db" ]; then
    echo "⚡ Menginisialisasi basis data..."
    .venv/bin/python db.py
    .venv/bin/python migrate_multi_blog.py
fi

echo "🚀 Membuka Web Dashboard di browser Anda..."
sleep 1 && open "http://localhost:8090" &

echo "🌐 Server aktif di http://localhost:8090"
echo "Tekan [CTRL + C] di jendela ini untuk mematikan aplikasi kapan saja."
echo ""
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8090

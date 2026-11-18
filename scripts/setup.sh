#!/usr/bin/env bash
# Installation & Dependency Setup Script for Blogger Auto-Pilot
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "⚡ Installing Blogger Auto-Pilot dependencies..."
if command -v uv &> /dev/null; then
    uv pip install -r requirements.txt
else
    pip install -r requirements.txt
fi

echo "✅ All dependencies installed successfully!"


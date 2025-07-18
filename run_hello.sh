#!/bin/bash
# Script to run hello.py with proper virtual environment activation

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Running hello.py with virtual environment..."
echo "📁 Working directory: $SCRIPT_DIR"

# Change to the script directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run:"
    echo "   python -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if hello.py exists
if [ ! -f "hello.py" ]; then
    echo "❌ hello.py not found in the current directory"
    exit 1
fi

# Run hello.py
echo "🎵 Starting audio generation..."
python hello.py

echo "✅ Script completed!" 
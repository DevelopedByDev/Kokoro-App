#!/bin/bash
# Convenience script to run Kokoro in the virtual environment

echo "Activating virtual environment..."
source venv/bin/activate

echo "Running Kokoro test..."
cd examples
PYTORCH_ENABLE_MPS_FALLBACK=1 python test.py

echo "Done! Audio files generated in examples/ directory" 
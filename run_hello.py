#!/usr/bin/env python3
"""
Script to run hello.py with proper virtual environment activation
"""
import subprocess
import sys
import os

def main():
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Change to the script directory
    os.chdir(script_dir)
    
    # Activate virtual environment and run hello.py
    venv_python = os.path.join(script_dir, "venv", "bin", "python")
    
    if not os.path.exists(venv_python):
        print("❌ Virtual environment not found. Please run:")
        print("   python -m venv venv")
        print("   source venv/bin/activate")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    
    print("🚀 Running hello.py with virtual environment...")
    print(f"📁 Working directory: {script_dir}")
    print(f"🐍 Using Python: {venv_python}")
    
    try:
        # Run hello.py using the virtual environment's Python
        result = subprocess.run([venv_python, "hello.py"], 
                              cwd=script_dir, 
                              check=True)
        print("✅ Script completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Script failed with exit code: {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("❌ Could not find hello.py in the current directory")
        sys.exit(1)

if __name__ == "__main__":
    main() 
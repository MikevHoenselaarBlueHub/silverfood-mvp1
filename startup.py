
#!/usr/bin/env python3
"""
Startup script voor Silverfood API
Zorgt ervoor dat alle dependencies geïnstalleerd zijn voordat de app start
"""

import subprocess
import sys
import os

def install_requirements():
    """Installeer requirements.txt als deze bestaat"""
    if os.path.exists('requirements.txt'):
        print("🔧 Installing Python dependencies via UPM...")
        try:
            # Use Replit's Universal Package Manager instead of pip
            subprocess.check_call(['upm', 'add', '-r', 'requirements.txt'])
            print("✅ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            print("ℹ️  Continuing without fresh install - dependencies might already be installed")
            # Don't fail if UPM fails - dependencies might already be installed
    return True

def start_server():
    """Start de FastAPI server"""
    print("🚀 Starting Silverfood API server...")
    try:
        # Check if uvicorn is available
        subprocess.check_call([sys.executable, '-c', 'import uvicorn'])
        subprocess.check_call([
            sys.executable, '-m', 'uvicorn', 
            'api:app', 
            '--host', '0.0.0.0', 
            '--port', '5000',
            '--reload'
        ])
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start server: {e}")
        print("ℹ️  Try running: upm add fastapi uvicorn")
        return False
    return True

if __name__ == "__main__":
    print("🍽️ Silverfood API - Startup Script")
    print("=" * 40)
    
    # Installeer dependencies
    if not install_requirements():
        sys.exit(1)
    
    # Start server
    if not start_server():
        sys.exit(1)

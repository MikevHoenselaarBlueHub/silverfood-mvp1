
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
        print("🔧 Installing Python dependencies...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
            print("✅ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    return True

def start_server():
    """Start de FastAPI server"""
    print("🚀 Starting Silverfood API server...")
    try:
        subprocess.check_call([
            sys.executable, '-m', 'uvicorn', 
            'api:app', 
            '--host', '0.0.0.0', 
            '--port', '5000',
            '--reload'
        ])
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start server: {e}")
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

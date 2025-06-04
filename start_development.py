
#!/usr/bin/env python3
"""
Quick start voor Silverfood development
GRATIS - Geen Replit Core nodig
"""

import subprocess
import sys

def main():
    print("🍽️  Silverfood - Quick Development Start")
    print("💰 GRATIS MODE - Geen Core membership nodig!")
    print("=" * 50)
    
    print("🚀 Starting development server...")
    print("📡 Je server wordt automatisch beschikbaar op je .repl.co URL")
    print("🔧 Chrome extensie kan tegen deze URL testen")
    print("")
    print("💡 Om extensie te testen:")
    print("   1. Run: python test_extension_local.py")
    print("   2. Of build handmatig: python build_extension.py")
    print("")
    print("⏹️  Druk Ctrl+C om te stoppen")
    print("")
    
    # Start server direct
    try:
        subprocess.run([
            sys.executable, '-m', 'uvicorn',
            'api:app',
            '--host', '0.0.0.0',  # Belangrijk voor Replit
            '--port', '5000',
            '--reload'
        ])
    except KeyboardInterrupt:
        print("\n✅ Server gestopt")

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Test Chrome Extension tegen lokale development server
Geen Replit Core nodig - werkt met gratis account
"""

import subprocess
import sys
import time
import requests
import webbrowser
import os

def start_local_server():
    """Start lokale development server"""
    print("🚀 Starting local development server...")
    print("   Port 5000 wordt automatisch doorgestuurd naar je replit.dev URL")
    print("   Geen Core membership nodig!")
    
    # Start uvicorn server in background
    try:
        process = subprocess.Popen([
            sys.executable, '-m', 'uvicorn', 
            'api:app', 
            '--host', '0.0.0.0',  # Belangrijk voor Replit
            '--port', '5000',
            '--reload'
        ])
        
        # Wacht tot server opstart
        time.sleep(3)
        
        # Test of server draait
        try:
            response = requests.get('http://localhost:5000/health', timeout=5)
            if response.status_code == 200:
                print("✅ Server is running!")
                return process
            else:
                print("❌ Server start failed")
                return None
        except:
            print("❌ Server not responding")
            return None
            
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return None

def build_extension():
    """Build Chrome extension met development configuratie"""
    print("\n🔧 Building Chrome extension for development...")
    
    try:
        result = subprocess.run([sys.executable, 'build_extension.py'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Extension built successfully!")
            return True
        else:
            print(f"❌ Extension build failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error building extension: {e}")
        return False

def get_replit_dev_url():
    """Get the current replit.dev URL"""
    # In Replit, de REPL_SLUG en REPL_OWNER environment variables zijn beschikbaar
    repl_slug = os.environ.get('REPL_SLUG', 'silverfood-analyzer')
    repl_owner = os.environ.get('REPL_OWNER', 'unknown')
    
    # Replit.dev URLs zijn gratis beschikbaar tijdens development
    dev_url = f"https://{repl_slug}.{repl_owner}.repl.co"
    
    return dev_url

def show_extension_instructions():
    """Toon instructies voor Chrome extensie installatie"""
    dev_url = get_replit_dev_url()
    
    print("\n📋 Chrome Extension Installatie (GRATIS):")
    print("=" * 50)
    print("1. Open Chrome en ga naar: chrome://extensions/")
    print("2. Schakel 'Developer mode' in (rechtsboven)")
    print("3. Klik 'Load unpacked'")
    print("4. Selecteer deze project folder")
    print("5. Extensie is nu geladen!")
    print("")
    print("🌐 API URLs die de extensie zal proberen:")
    print(f"   - Development: {dev_url} (GRATIS)")
    print(f"   - Localhost: http://localhost:5000 (fallback)")
    print("")
    print("💡 Tips:")
    print("   - Je server draait op port 5000")
    print("   - Replit stuurt dit automatisch door naar je .repl.co URL")
    print("   - Geen Core membership nodig voor development!")
    print("   - Test op verschillende recipe websites")
    print("")
    print("🧪 Test de extensie op:")
    print("   - https://www.ah.nl/allerhande/recept/...")
    print("   - https://www.jumbo.com/recepten/...")
    print("   - Andere recipe websites")

def main():
    """Main functie voor lokale extensie testing"""
    print("🍽️  Silverfood Chrome Extension - Development Testing")
    print("💰 GRATIS - Geen Replit Core nodig!")
    print("=" * 60)
    
    # Start lokale server
    server_process = start_local_server()
    if not server_process:
        print("❌ Cannot continue without server")
        return False
    
    # Build extensie
    if not build_extension():
        print("❌ Cannot continue without extension build")
        server_process.terminate()
        return False
    
    # Toon instructies
    show_extension_instructions()
    
    print("\n🎉 Setup complete!")
    print("📝 Je server draait nu en extensie is klaar voor installatie")
    print("⏹️  Druk Ctrl+C om server te stoppen")
    
    try:
        # Houd server draaiende
        server_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        server_process.terminate()
        print("✅ Server stopped")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


#!/usr/bin/env python3
"""
Health check script voor Silverfood API
Controleert of alle dependencies en componenten werken
"""

import sys
import importlib
import subprocess
import os

def check_python_version():
    """Check Python versie"""
    print(f"🐍 Python version: {sys.version}")
    return sys.version_info >= (3, 8)

def check_dependencies():
    """Check of alle benodigde packages geïnstalleerd zijn"""
    required_packages = [
        'fastapi', 'uvicorn', 'requests', 'beautifulsoup4',
        'rapidfuzz', 'selenium', 'lxml', 'aiofiles', 'openai'
    ]
    
    missing = []
    for package in required_packages:
        try:
            if package == 'beautifulsoup4':
                importlib.import_module('bs4')
            else:
                importlib.import_module(package)
            print(f"✅ {package} - OK")
        except ImportError:
            print(f"❌ {package} - MISSING")
            missing.append(package)
    
    return len(missing) == 0, missing

def check_chrome_selenium():
    """Check Selenium en Chrome setup"""
    try:
        import shutil
        chrome = shutil.which('chromium') or shutil.which('chrome') or shutil.which('google-chrome')
        chromedriver = shutil.which('chromedriver')
        
        print(f"🌐 Chrome binary: {'✅' if chrome else '❌'} {chrome or 'Not found'}")
        print(f"🔧 ChromeDriver: {'✅' if chromedriver else '❌'} {chromedriver or 'Not found'}")
        
        return bool(chrome and chromedriver)
    except Exception as e:
        print(f"❌ Selenium check failed: {e}")
        return False

def check_config_files():
    """Check of configuratiebestanden bestaan"""
    files = ['config.json', 'health_tips.json', 'substitutions.json']
    all_exist = True
    
    for file in files:
        exists = os.path.exists(file)
        print(f"📁 {file}: {'✅' if exists else '❌'}")
        if not exists:
            all_exist = False
    
    return all_exist

def check_port_availability():
    """Check of poort 5000 beschikbaar is"""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', 5000))
            print("🔌 Port 5000: ✅ Available")
            return True
    except OSError:
        print("🔌 Port 5000: ❌ In use")
        return False

def check_api_endpoints():
    """Test of de API endpoints bereikbaar zijn"""
    try:
        import requests
        response = requests.get('http://localhost:5000/health', timeout=5)
        if response.status_code == 200:
            print("🌐 API Health endpoint: ✅ Responding")
            return True
        else:
            print(f"🌐 API Health endpoint: ❌ Status {response.status_code}")
            return False
    except Exception as e:
        print(f"🌐 API Health endpoint: ❌ Not responding ({e})")
        return False

def main():
    print("🍽️ Silverfood API - Health Check")
    print("=" * 40)
    
    issues = []
    
    # Check Python
    if not check_python_version():
        issues.append("Python version too old (need 3.8+)")
    
    # Check dependencies
    deps_ok, missing = check_dependencies()
    if not deps_ok:
        issues.append(f"Missing packages: {', '.join(missing)}")
    
    # Check Selenium (optional)
    selenium_ok = check_chrome_selenium()
    if not selenium_ok:
        print("⚠️  Selenium/Chrome not available - will use fallback scraping")
    
    # Check config files
    if not check_config_files():
        issues.append("Missing configuration files")
    
    # Check port
    if not check_port_availability():
        issues.append("Port 5000 not available")
    
    print("\n" + "=" * 40)
    if issues:
        print("❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n🔧 To fix, run: python startup.py")
        return False
    else:
        print("✅ All checks passed! API should work correctly.")
        print("\n🚀 To start the server: python startup.py")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

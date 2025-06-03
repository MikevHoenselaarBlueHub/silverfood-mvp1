
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
        chrome = shutil.which('chromium') or shutil.which('chrome')
        chromedriver = shutil.which('chromedriver')
        
        print(f"🌐 Chrome binary: {'✅' if chrome else '❌'} {chrome or 'Not found'}")
        print(f"🔧 ChromeDriver: {'✅' if chromedriver else '❌'} {chromedriver or 'Not found'}")
        
        return bool(chrome and chromedriver)
    except:
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
    
    # Check Selenium
    if not check_chrome_selenium():
        issues.append("Chrome/ChromeDriver not properly configured")
    
    # Check config files
    if not check_config_files():
        issues.append("Missing configuration files")
    
    print("\n" + "=" * 40)
    if issues:
        print("❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n🔧 To fix, run: python startup.py")
        return False
    else:
        print("✅ All checks passed! API should work correctly.")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

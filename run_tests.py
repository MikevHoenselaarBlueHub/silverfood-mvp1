
#!/usr/bin/env python3
"""
Silverfood Test Runner
Run this script to execute all automated tests for the Silverfood application.
"""

import subprocess
import sys
import os
import time
import webbrowser

def run_api_tests():
    """Run API functionality tests"""
    print("🔧 Running API Tests...")
    try:
        result = subprocess.run([sys.executable, "test_functionality.py"], 
                              capture_output=True, text=True, timeout=120)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ API tests timed out after 120 seconds")
        return False
    except Exception as e:
        print(f"❌ Error running API tests: {e}")
        return False

def run_ui_tests():
    """Open UI test page in browser"""
    print("🌐 Opening UI Tests in browser...")
    try:
        # Check if server is running
        import requests
        test_urls = [
            "http://127.0.0.1:5000",
            "http://localhost:5000"
        ]
        
        server_running = False
        for test_url in test_urls:
            try:
                response = requests.get(test_url, timeout=5)
                if response.status_code == 200:
                    webbrowser.open(f"{test_url}/static/test_ui_functionality.html")
                    print("✅ UI test page opened. Please run tests manually in browser.")
                    server_running = True
                    break
            except:
                continue
        
        if not server_running:
            print("❌ Server not responding. Please start the server first:")
            print("   uvicorn api:app --host 0.0.0.0 --port 5000")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Could not open UI tests: {e}")
        print("   Make sure the server is running on port 5000")
        return False

def main():
    print("🧪 Silverfood Test Suite")
    print("=" * 40)
    
    # Check if we're in the right directory
    required_files = ["api.py", "analyse.py", "static/script.js"]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        print("   Please run this script from the Silverfood project root directory")
        return False
    
    print("✅ Project files found")
    
    # Run API tests
    api_success = run_api_tests()
    
    print("\n" + "=" * 40)
    
    # Open UI tests
    ui_opened = run_ui_tests()
    
    print("\n" + "=" * 40)
    print("📋 Test Summary:")
    print(f"   API Tests: {'✅ PASSED' if api_success else '❌ FAILED'}")
    print(f"   UI Tests: {'✅ OPENED' if ui_opened else '❌ FAILED TO OPEN'}")
    
    if api_success and ui_opened:
        print("\n🎉 All automated tests completed successfully!")
        print("   Don't forget to run the UI tests manually in your browser.")
        return True
    else:
        print("\n⚠️  Some tests failed or could not be run.")
        if not api_success:
            print("   - Check if the API server is running")
            print("   - Review any error messages above")
        if not ui_opened:
            print("   - Make sure the server is running on port 5000")
            print("   - Check your default browser settings")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

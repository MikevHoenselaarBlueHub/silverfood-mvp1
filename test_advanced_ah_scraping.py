
#!/usr/bin/env python3
"""
Advanced AH scraping test with all evasion techniques
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyse import (
    scrape_ah_with_proxy_rotation, 
    scrape_ah_via_api_endpoints,
    scrape_ah_with_browser_automation_evasion,
    get_advanced_user_agents,
    get_free_proxy_list
)
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_all_ah_methods():
    """Test all advanced AH scraping methods"""
    url = "https://www.ah.nl/allerhande/recept/R-R1201256/orzosalade-met-asperges-nectarines-en-burrata"
    
    print("🍽️  ADVANCED AH SCRAPING TEST")
    print("=" * 80)
    print(f"🔗 URL: {url}")
    
    methods = [
        ("🔄 Proxy Rotation", lambda: scrape_ah_with_proxy_rotation(url)),
        ("🔌 API Endpoints", lambda: scrape_ah_via_api_endpoints(url)),
        ("🤖 Browser Evasion", lambda: scrape_ah_with_browser_automation_evasion(url)),
    ]
    
    results = {}
    
    for method_name, method_func in methods:
        print(f"\n{method_name}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            ingredients, title = method_func()
            duration = time.time() - start_time
            
            print(f"✅ SUCCESS: {len(ingredients)} ingredients in {duration:.2f}s")
            print(f"📝 Title: {title}")
            print("🥬 First 5 ingredients:")
            for i, ing in enumerate(ingredients[:5], 1):
                print(f"   {i}. {ing}")
            
            results[method_name] = {
                'success': True,
                'ingredients': len(ingredients),
                'title': title,
                'duration': duration
            }
            
            # If one method works, we can stop
            print(f"\n🎉 Method {method_name} works! Stopping here.")
            break
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            results[method_name] = {
                'success': False,
                'error': str(e)
            }
    
    # Summary
    print(f"\n📊 SUMMARY")
    print("=" * 40)
    
    successful_methods = [name for name, result in results.items() if result.get('success')]
    
    if successful_methods:
        print(f"✅ Working methods: {', '.join(successful_methods)}")
        print("💡 Recommendation: Use the first working method as primary")
    else:
        print("❌ All methods failed")
        print("💡 Recommendations:")
        print("   - Try different times of day (AH may have rate limiting)")
        print("   - Check if AH has updated their blocking mechanisms")
        print("   - Consider manual copy-paste as instructed to users")

def test_proxy_connectivity():
    """Test if our proxy list is working"""
    print("\n🌐 TESTING PROXY CONNECTIVITY")
    print("=" * 40)
    
    proxies = get_free_proxy_list()
    
    for i, proxy in enumerate(proxies, 1):
        try:
            import requests
            response = requests.get("http://httpbin.org/ip", 
                                  proxies=proxy, 
                                  timeout=10)
            if response.status_code == 200:
                ip_data = response.json()
                print(f"✅ Proxy {i}: {ip_data.get('origin')} - Working")
            else:
                print(f"❌ Proxy {i}: Status {response.status_code}")
        except Exception as e:
            print(f"❌ Proxy {i}: Failed - {e}")

def test_user_agents():
    """Test user agent diversity"""
    print("\n🕵️  TESTING USER AGENTS")
    print("=" * 40)
    
    user_agents = get_advanced_user_agents()
    
    print(f"📊 Total user agents: {len(user_agents)}")
    print("🔍 Sample user agents:")
    
    for i, ua in enumerate(user_agents[:5], 1):
        browser = "Chrome" if "Chrome" in ua else "Firefox" if "Firefox" in ua else "Safari" if "Safari" in ua else "Unknown"
        mobile = "Mobile" if "Mobile" in ua else "Desktop"
        print(f"   {i}. {browser} ({mobile})")

if __name__ == "__main__":
    print("🧪 Starting Advanced AH Scraping Tests...")
    
    # Test components first
    test_proxy_connectivity()
    test_user_agents()
    
    # Then test scraping
    test_all_ah_methods()
    
    print("\n✅ Testing completed!")

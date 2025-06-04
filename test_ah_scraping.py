
#!/usr/bin/env python3
"""
Test script specifically for AH website scraping with comprehensive debugging
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyse import scrape_ah_advanced, scrape_ah_specific, smart_ingredient_scraping
import logging
import requests
from bs4 import BeautifulSoup
import time

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def basic_url_test(url):
    """Basic test to see if URL is accessible"""
    print(f"\n🔍 Basic URL accessibility test...")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"✅ Status Code: {response.status_code}")
        print(f"📊 Content Length: {len(response.content)} bytes")
        print(f"🔗 Final URL: {response.url}")
        print(f"📋 Content Type: {response.headers.get('content-type', 'Unknown')}")
        
        # Check for common blocking indicators
        if 'captcha' in response.text.lower():
            print("⚠️  Warning: CAPTCHA detected")
        if 'blocked' in response.text.lower():
            print("⚠️  Warning: Blocking detected")
        if response.status_code == 403:
            print("🚫 403 Forbidden - Site is blocking requests")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ URL not accessible: {e}")
        return False

def analyze_page_structure(url):
    """Analyze the page structure to understand why scraping might fail"""
    print(f"\n🔬 Analyzing page structure...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Save HTML for manual inspection
        with open('debug/page_structure.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("💾 Page HTML saved to debug/page_structure.html")
        
        # Look for script tags that might load content dynamically
        scripts = soup.find_all('script')
        print(f"📜 Found {len(scripts)} script tags")
        
        # Look for JSON-LD
        json_scripts = soup.find_all('script', type='application/ld+json')
        print(f"📊 Found {len(json_scripts)} JSON-LD scripts")
        
        # Look for common ingredient selectors
        selectors = [
            '.ingredient', '[data-testid*="ingredient"]', '.ingredients li',
            '.recipe-ingredient', '[data-ingredient]', '.ingredient-item'
        ]
        
        print("🔍 Testing selectors:")
        for selector in selectors:
            elements = soup.select(selector)
            print(f"   {selector}: {len(elements)} elements")
            
        # Look for data attributes that might contain recipe info
        elements_with_data = soup.find_all(attrs={"data-testid": True})
        print(f"🏷️  Found {len(elements_with_data)} elements with data-testid")
        
        # Sample some data-testid values
        testids = list(set([elem.get('data-testid') for elem in elements_with_data[:20]]))
        print(f"📝 Sample data-testid values: {testids[:10]}")
        
    except Exception as e:
        print(f"❌ Page analysis failed: {e}")

def test_different_methods(url):
    """Test different scraping methods"""
    print(f"\n🧪 Testing different scraping methods...")
    
    methods = [
        ("Smart Scraping", lambda: smart_ingredient_scraping(url)),
        ("Advanced AH", lambda: scrape_ah_advanced(url)),
        ("Original AH", lambda: scrape_ah_specific(url))
    ]
    
    results = {}
    
    for method_name, method_func in methods:
        print(f"\n🔧 Testing {method_name}...")
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
                'ingredients': ingredients,
                'title': title,
                'duration': duration
            }
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            results[method_name] = {
                'success': False,
                'error': str(e)
            }
    
    return results

def test_ah_scraping():
    """Main test function"""
    url = "https://www.ah.nl/allerhande/recept/R-R442446/thaise-beef-salad-met-mango-en-komkommer"
    
    print("🍽️  AH RECIPE SCRAPING TEST")
    print("=" * 80)
    print(f"🔗 URL: {url}")
    
    # Ensure debug directory exists
    os.makedirs('debug', exist_ok=True)
    
    # Step 1: Basic URL test
    if not basic_url_test(url):
        print("❌ Cannot proceed - URL not accessible")
        return
    
    # Step 2: Analyze page structure
    analyze_page_structure(url)
    
    # Step 3: Test different methods
    results = test_different_methods(url)
    
    # Step 4: Summary
    print(f"\n📊 SUMMARY")
    print("=" * 40)
    
    successful_methods = [name for name, result in results.items() if result.get('success')]
    failed_methods = [name for name, result in results.items() if not result.get('success')]
    
    if successful_methods:
        print(f"✅ Successful methods: {', '.join(successful_methods)}")
        
        # Find best method (most ingredients)
        best_method = max(
            [name for name in successful_methods],
            key=lambda name: len(results[name]['ingredients'])
        )
        best_result = results[best_method]
        print(f"🏆 Best method: {best_method} ({len(best_result['ingredients'])} ingredients)")
        
    else:
        print("❌ All methods failed")
    
    if failed_methods:
        print(f"❌ Failed methods: {', '.join(failed_methods)}")
        print("\n🔍 Error details:")
        for method in failed_methods:
            print(f"   {method}: {results[method]['error']}")
    
    print(f"\n💡 Recommendations:")
    if not successful_methods:
        print("   - Check if the website blocks automated requests")
        print("   - Try using a VPN or different IP address")
        print("   - Consider using browser automation with longer delays")
        print("   - Check debug/page_structure.html for manual analysis")
    else:
        print(f"   - Use {best_method} for best results")
        print("   - Consider implementing fallback chain for reliability")
    
    print(f"\n📁 Debug files saved in debug/ directory")

if __name__ == "__main__":
    test_ah_scraping()

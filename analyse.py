import requests
import json
import logging
import time
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from urllib.parse import urlparse, urljoin
import asyncio
from debug_helper import debug
import random
import base64
import hashlib
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Selenium imports with error handling
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
    logger.info("Selenium is available")
except ImportError as e:
    SELENIUM_AVAILABLE = False
    logger.warning(f"Selenium not available - fallback to requests only: {e}")
except Exception as e:
    SELENIUM_AVAILABLE = False
    logger.warning(f"Selenium setup failed - fallback to requests only: {e}")

# Load configuration files
try:
    with open("config.json", encoding="utf-8") as f:
        CONFIG = json.load(f)
    logger.info("Configuration loaded successfully")
except FileNotFoundError:
    CONFIG = {
        "health_scoring": {"default_unknown_score": 5},
        "api": {"rate_limit_requests": 8, "rate_limit_window_seconds": 60},
        "ui": {"max_url_length": 500}
    }
    logger.warning("Config file not found, using defaults")

try:
    with open("substitutions.json", encoding="utf-8") as f:
        SUBSTITUTIONS = json.load(f)
    logger.info("Substitutions database loaded successfully")
except FileNotFoundError:
    SUBSTITUTIONS = {}
    logger.warning("Substitutions file not found")

def smart_ingredient_scraping(url: str) -> Tuple[List[str], str]:
    """
    Smart ingredient scraping with multiple fallback methods.

    Args:
        url (str): Recipe URL to scrape

    Returns:
        Tuple[List[str], str]: List of ingredients and recipe title
    """
    logger.info(f"Starting smart scraping for {url}")

    # Try different scraping methods in order of preference
    methods = []
    
    # Add AH-specific method if it's an AH URL
    if 'ah.nl' in url.lower():
        methods.append(("ah_specific", scrape_ah_specific))
    
    # Always try these methods
    methods.extend([
        ("requests_json_ld", scrape_with_requests_json_ld),
        ("requests_patterns", scrape_with_requests_patterns),
    ])
    
    # Add Selenium as last resort only if available
    if SELENIUM_AVAILABLE:
        methods.append(("selenium", scrape_with_selenium))

    for method_name, method_func in methods:
        try:
            logger.info(f"Trying method: {method_name}")
            ingredients, title = method_func(url)

            if ingredients and len(ingredients) >= 3:
                logger.info(f"Success with {method_name}: {len(ingredients)} ingredients found")
                debug.log_scraping_attempt(url, method_name, True, len(ingredients))
                return ingredients, title
            else:
                logger.warning(f"Method {method_name} found insufficient ingredients: {len(ingredients) if ingredients else 0}")

        except Exception as e:
            debug.log_scraping_attempt(url, method_name, False, 0)
            logger.warning(f"Method {method_name} failed: {e}")

            # For AH URLs, provide more specific debugging
            if 'ah.nl' in url.lower() and method_name == 'ah_specific':
                logger.info("AH advanced method failed, check debug/ folder for detailed logs")

            continue

    # Final fallback: suggest manual copy-paste for AH.nl
    if 'ah.nl' in url.lower():
        raise Exception("AH.nl blokkeert automatische toegang. Kopieer de ingrediënten handmatig van de receptpagina en plak ze in het tekstveld voor analyse.")
    
    raise Exception("Geen ingrediënten gevonden met alle beschikbare methoden")

def scrape_with_requests_json_ld(url: str) -> Tuple[List[str], str]:
    """Scrape using requests and JSON-LD structured data."""
    # Enhanced headers to bypass AH.nl blocking
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }

    debug.log_request(url, "GET", headers)
    start_time = time.time()

    # Try multiple request approaches for AH.nl
    session = requests.Session()
    session.headers.update(headers)

    response = session.get(url, timeout=15, allow_redirects=True)
    debug.log_response(response, time.time() - start_time)

    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    # Save debug HTML
    debug.save_debug_html(str(soup), url, "requests_json_ld")

    # Try JSON-LD structured data
    json_scripts = soup.find_all('script', type='application/ld+json')

    for script in json_scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0]

            if data.get('@type') == 'Recipe' or 'Recipe' in str(data.get('@type', [])):
                ingredients = []
                recipe_ingredients = data.get('recipeIngredient', [])

                for ingredient in recipe_ingredients:
                    if isinstance(ingredient, dict):
                        ingredient_text = ingredient.get('name', ingredient.get('text', ''))
                    else:
                        ingredient_text = str(ingredient)

                    if ingredient_text:
                        ingredients.append(ingredient_text.strip())

                title = data.get('name', 'Onbekend recept')

                if ingredients:
                    return ingredients, title

        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"JSON-LD parsing failed: {e}")
            continue

    raise Exception("Geen JSON-LD receptdata gevonden")

def scrape_with_requests_patterns(url: str) -> Tuple[List[str], str]:
    """Scrape using requests and pattern matching."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    session = requests.Session()
    session.headers.update(headers)
    response = session.get(url, timeout=15, allow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    # AH-specific selectors first, then common ones
    selectors = [
        '.recipe-ingredient',
        '.ingredient',
        '.ingredients li',
        '[data-ingredient]',
        '.recipe-ingredients li',
        '.ingredient-list li',
        '.ingredients-list li',
        # AH-specific selectors
        '[data-testid="ingredient"]',
        '.ingredient-item',
        '.recipe-ingredients-list li',
        'ul[data-testid="ingredients"] li',
        '.ingredients-section li'
    ]

    ingredients = []

    for selector in selectors:
        elements = soup.select(selector)
        if elements:
            for element in elements:
                text = element.get_text().strip()
                if text and len(text) > 2:
                    ingredients.append(text)

            if len(ingredients) >= 3:
                break

    # Try to find title
    title = "Onbekend recept"
    title_selectors = ['h1', '.recipe-title', '.entry-title', 'title']
    for selector in title_selectors:
        title_elem = soup.select_one(selector)
        if title_elem:
            title = title_elem.get_text().strip()
            break

    if not ingredients:
        raise Exception("Geen ingrediënten gevonden met patroonherkenning")

    return ingredients, title

def get_advanced_user_agents():
    """Get realistic user agents with current browser versions."""
    return [
        # Chrome Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        
        # Chrome macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        
        # Firefox
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
        
        # Safari
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
        
        # Edge
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        
        # Mobile Chrome
        'Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
    ]

def get_free_proxy_list():
    """Get list of free proxies - basic implementation."""
    # Deze proxies zijn vaak tijdelijk en kunnen uitvallen
    return [
        # Nederlandse proxies (vaak beter voor AH.nl)
        {'http': 'http://185.93.3.123:8080', 'https': 'http://185.93.3.123:8080'},
        {'http': 'http://31.220.109.82:80', 'https': 'http://31.220.109.82:80'},
        
        # Duitse proxies (dichtbij Nederland)
        {'http': 'http://217.182.170.87:80', 'https': 'http://217.182.170.87:80'},
        {'http': 'http://46.101.13.77:80', 'https': 'http://46.101.13.77:80'},
        
        # Belgische proxies
        {'http': 'http://195.244.25.51:80', 'https': 'http://195.244.25.51:80'},
    ]

def create_session_with_retries():
    """Create session with retry strategy."""
    session = requests.Session()
    
    # Retry strategy
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS"],
        backoff_factor=1
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def generate_realistic_headers(user_agent: str):
    """Generate realistic headers based on user agent."""
    is_mobile = 'Mobile' in user_agent or 'iPhone' in user_agent
    is_firefox = 'Firefox' in user_agent
    is_safari = 'Safari' in user_agent and 'Chrome' not in user_agent
    
    headers = {
        'User-Agent': user_agent,
        'Accept-Language': random.choice([
            'nl-NL,nl;q=0.9,en;q=0.8',
            'en-US,en;q=0.9,nl;q=0.8',
            'nl,en-US;q=0.9,en;q=0.8'
        ]),
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': random.choice(['max-age=0', 'no-cache']),
    }
    
    if is_firefox:
        headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
    elif is_safari:
        headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    else:  # Chrome/Edge
        headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': random.choice(['none', 'same-origin', 'cross-site']),
            'Sec-Fetch-User': '?1',
            'Sec-Ch-Ua': f'"Chromium";v="120", "Not(A:Brand";v="24", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?1' if is_mobile else '?0',
            'Sec-Ch-Ua-Platform': random.choice(['"Windows"', '"macOS"', '"Linux"']),
        })
    
    # Add random extra headers sometimes
    if random.choice([True, False]):
        headers['X-Requested-With'] = 'XMLHttpRequest'
    
    return headers

def scrape_ah_with_proxy_rotation(url: str) -> Tuple[List[str], str]:
    """Advanced AH scraping with proxy rotation."""
    logger.info("Trying advanced proxy rotation method for AH.nl")
    
    user_agents = get_advanced_user_agents()
    proxies_list = get_free_proxy_list()
    
    # Add no-proxy as first option
    proxies_list.insert(0, None)
    
    for attempt in range(len(proxies_list)):
        try:
            user_agent = random.choice(user_agents)
            headers = generate_realistic_headers(user_agent)
            proxies = proxies_list[attempt] if attempt < len(proxies_list) else None
            
            session = create_session_with_retries()
            session.headers.update(headers)
            
            # Random delay to appear human
            time.sleep(random.uniform(2, 6))
            
            logger.info(f"Attempt {attempt + 1}: Using {'proxy' if proxies else 'direct connection'}")
            
            # Try to access homepage first (cookie collection)
            try:
                session.get("https://www.ah.nl", 
                           proxies=proxies, 
                           timeout=15, 
                           allow_redirects=True)
                time.sleep(random.uniform(1, 3))
            except:
                pass
            
            # Now try the recipe page
            response = session.get(url, 
                                 proxies=proxies, 
                                 timeout=25, 
                                 allow_redirects=True)
            
            if response.status_code == 200:
                logger.info(f"Success with attempt {attempt + 1}")
                return parse_ah_response(response, url)
            elif response.status_code == 403:
                logger.warning(f"Attempt {attempt + 1} blocked (403)")
                continue
            else:
                logger.warning(f"Attempt {attempt + 1} failed with status {response.status_code}")
                continue
                
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            continue
    
    raise Exception("Alle proxy pogingen gefaald voor AH.nl")

def scrape_ah_via_api_endpoints(url: str) -> Tuple[List[str], str]:
    """Try to find AH API endpoints for recipe data."""
    logger.info("Trying AH API endpoint method")
    
    # Extract recipe ID from URL
    recipe_id_match = re.search(r'/recept/(R-R\d+)/', url)
    if not recipe_id_match:
        raise Exception("Could not extract recipe ID from URL")
    
    recipe_id = recipe_id_match.group(1)
    
    # Try different API endpoints
    api_endpoints = [
        f"https://www.ah.nl/zoeken/api/products/recipe/{recipe_id}",
        f"https://api.ah.nl/mobile-services/recipe/v2/{recipe_id}",
        f"https://www.ah.nl/service/rest/delegate?url=/zoeken/api/products/recipe/{recipe_id}",
        f"https://ah.nl/allerhande/api/recipe/{recipe_id}",
    ]
    
    user_agent = random.choice(get_advanced_user_agents())
    headers = {
        'User-Agent': user_agent,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'nl-NL,nl;q=0.9',
        'Referer': 'https://www.ah.nl/',
        'Origin': 'https://www.ah.nl',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    session = create_session_with_retries()
    
    for endpoint in api_endpoints:
        try:
            logger.info(f"Trying API endpoint: {endpoint}")
            response = session.get(endpoint, headers=headers, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    ingredients = extract_ingredients_from_api_data(data)
                    if ingredients:
                        title = data.get('name', 'AH Recept')
                        logger.info(f"API success: {len(ingredients)} ingredients")
                        return ingredients, title
                except:
                    continue
            
        except Exception as e:
            logger.debug(f"API endpoint {endpoint} failed: {e}")
            continue
    
    raise Exception("Geen werkende AH API endpoints gevonden")

def extract_ingredients_from_api_data(data: Dict) -> List[str]:
    """Extract ingredients from AH API response."""
    ingredients = []
    
    # Try different possible structures
    possible_paths = [
        ['ingredients'],
        ['recipe', 'ingredients'],
        ['data', 'ingredients'],
        ['recipeIngredient'],
        ['recipe', 'recipeIngredient'],
        ['ingredientLines'],
        ['recipe', 'ingredientLines'],
    ]
    
    for path in possible_paths:
        current = data
        try:
            for key in path:
                current = current[key]
            
            if isinstance(current, list):
                for item in current:
                    if isinstance(item, str):
                        ingredients.append(item)
                    elif isinstance(item, dict):
                        # Try to get text from various fields
                        text = item.get('name') or item.get('text') or item.get('description') or str(item)
                        if text:
                            ingredients.append(text)
                            
                if len(ingredients) >= 3:
                    return ingredients
                    
        except (KeyError, TypeError):
            continue
    
    return ingredients

def scrape_ah_with_browser_automation_evasion(url: str) -> Tuple[List[str], str]:
    """Advanced browser automation with anti-detection."""
    if not SELENIUM_AVAILABLE:
        raise Exception("Selenium niet beschikbaar voor geavanceerde methode")
    
    logger.info("Using advanced browser automation with anti-detection")
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--disable-javascript')  # Sometimes helps with detection
    
    # Anti-detection measures
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Random window size
    width = random.randint(1200, 1920)
    height = random.randint(800, 1080)
    options.add_argument(f'--window-size={width},{height}')
    
    # Random user agent
    user_agent = random.choice(get_advanced_user_agents())
    options.add_argument(f'--user-agent={user_agent}')
    
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        
        # Execute script to hide automation markers
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Random delays and human-like behavior
        time.sleep(random.uniform(2, 5))
        
        # Visit AH homepage first
        driver.get("https://www.ah.nl")
        time.sleep(random.uniform(3, 7))
        
        # Now visit recipe page
        driver.get(url)
        time.sleep(random.uniform(5, 10))
        
        # Try multiple selectors
        selectors = [
            '.recipe-ingredients li',
            '[data-testid="ingredient"]',
            '.ingredient-item',
            '.ingredient',
            'ul[class*="ingredient"] li',
            '.recipe-ingredient-list li'
        ]
        
        ingredients = []
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 2:
                            ingredients.append(text)
                    
                    if len(ingredients) >= 3:
                        break
            except:
                continue
        
        # Get title
        title = "AH Recept"
        try:
            title_element = driver.find_element(By.TAG_NAME, "h1")
            title = title_element.text.strip()
        except:
            try:
                title = driver.title
            except:
                pass
        
        if not ingredients:
            raise Exception("Geen ingrediënten gevonden met geavanceerde browser methode")
        
        return ingredients, title
        
    finally:
        if driver:
            driver.quit()

def parse_ah_response(response, url: str) -> Tuple[List[str], str]:
    """Parse successful AH response."""
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Save debug HTML
    debug.save_debug_html(str(soup), url, "proxy_success")
    
    ingredients = []
    title = "AH Recept"
    
    # Get title
    title_selectors = [
        'h1[data-testid="recipe-title"]',
        'h1.recipe-title',
        '.recipe-header h1',
        'h1'
    ]
    
    for selector in title_selectors:
        title_elem = soup.select_one(selector)
        if title_elem:
            title = title_elem.get_text().strip()
            break
    
    # Get ingredients with extended selectors
    ah_selectors = [
        '[data-testid="ingredient"]',
        '[data-testid="ingredients"] li',
        '.recipe-ingredients li',
        '.ingredients-list li',
        '.ingredient-item',
        'ul[class*="ingredient"] li',
        '[class*="ingredient-list"] li',
        '.recipe-ingredient-list li',
        'li[class*="ingredient"]',
        '[data-ingredient]',
        '.recipe-content ul li',
        '.ingredients ul li',
        # More specific AH selectors
        '.ah-ingredient',
        '.allerhande-ingredient',
        '[data-qa="ingredient"]',
        '.recipe-ingredients .ingredient'
    ]
    
    for selector in ah_selectors:
        try:
            elements = soup.select(selector)
            if elements:
                temp_ingredients = []
                for element in elements:
                    text = element.get_text().strip()
                    if text and len(text) > 2:
                        text = text.replace('\n', ' ').replace('\t', ' ')
                        text = ' '.join(text.split())
                        temp_ingredients.append(text)
                
                if len(temp_ingredients) >= 3:
                    ingredients = temp_ingredients
                    break
        except:
            continue
    
    if not ingredients:
        raise Exception("Geen ingrediënten gevonden in response")
    
    return ingredients, title

def scrape_ah_specific(url: str) -> Tuple[List[str], str]:
    """AH-specific scraping method with all advanced techniques."""
    logger.info("Starting advanced AH scraping with all techniques")
    
    # Try methods in order of preference
    methods = [
        ("Proxy Rotation", lambda: scrape_ah_with_proxy_rotation(url)),
        ("API Endpoints", lambda: scrape_ah_via_api_endpoints(url)),
        ("Browser Evasion", lambda: scrape_ah_with_browser_automation_evasion(url)),
        ("Original Method", lambda: scrape_ah_original_method(url))
    ]
    
    for method_name, method_func in methods:
        try:
            logger.info(f"Trying {method_name}")
            ingredients, title = method_func()
            if ingredients and len(ingredients) >= 3:
                logger.info(f"Success with {method_name}: {len(ingredients)} ingredients")
                return ingredients, title
        except Exception as e:
            logger.warning(f"{method_name} failed: {e}")
            continue
    
    raise Exception("Alle geavanceerde AH scraping methoden gefaald")

def scrape_ah_original_method(url: str) -> Tuple[List[str], str]:
    """Original AH scraping method as fallback."""
    user_agents = get_advanced_user_agents()
    
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"'
    }

    session = requests.Session()
    session.headers.update(headers)

    # Add random delay to appear more human-like
    time.sleep(random.uniform(2, 5))

    try:
        # Try with different approaches
        attempts = [
            # Attempt 1: Direct request
            lambda: session.get(url, timeout=25, allow_redirects=True),
            # Attempt 2: With referer
            lambda: session.get(url, timeout=25, allow_redirects=True, headers={**headers, 'Referer': 'https://www.ah.nl/allerhande'}),
            # Attempt 3: Simulated navigation
            lambda: _simulate_ah_navigation(session, url, headers)
        ]
        
        response = None
        last_error = None
        
        for i, attempt in enumerate(attempts):
            try:
                logger.info(f"AH scraping attempt {i+1}/3")
                response = attempt()
                if response.status_code == 200:
                    break
                elif response.status_code == 403:
                    logger.warning(f"Attempt {i+1} blocked with 403, trying next method")
                    time.sleep(random.uniform(3, 7))  # Longer delay after being blocked
                    continue
                else:
                    logger.warning(f"Attempt {i+1} failed with status {response.status_code}")
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {i+1} failed: {e}")
                time.sleep(random.uniform(2, 4))
                continue
        
        if not response or response.status_code != 200:
            if response and response.status_code == 403:
                raise Exception("AH.nl blokkeert automatische toegang. Probeer een ander recept of kopieer de ingrediënten handmatig.")
            elif last_error:
                raise last_error
            else:
                raise Exception("Alle AH scraping pogingen gefaald")
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Save debug HTML for AH
        debug.save_debug_html(str(soup), url, "ah_specific")

        ingredients = []
        title = "AH Recept"

        # Try to get title first
        title_selectors = [
            'h1[data-testid="recipe-title"]',
            'h1.recipe-title',
            '.recipe-header h1',
            'h1',
            '[data-testid="recipe-name"]'
        ]

        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text().strip()
                break

        # AH-specific ingredient selectors with multiple strategies
        ah_selectors = [
            '[data-testid="ingredient"]',
            '[data-testid="ingredients"] li',
            '.recipe-ingredients li',
            '.ingredients-list li',
            '.ingredient-item',
            'ul[class*="ingredient"] li',
            '[class*="ingredient-list"] li',
            '.recipe-ingredient-list li',
            # Fallback selectors
            'li[class*="ingredient"]',
            '[data-ingredient]',
            '.recipe-content ul li',
            '.ingredients ul li'
        ]

        for selector in ah_selectors:
            try:
                elements = soup.select(selector)
                logger.debug(f"AH selector '{selector}' found {len(elements)} elements")

                if elements:
                    temp_ingredients = []
                    for element in elements:
                        text = element.get_text().strip()
                        if text and len(text) > 2:
                            # Clean up common AH formatting
                            text = text.replace('\n', ' ').replace('\t', ' ')
                            text = ' '.join(text.split())  # Remove extra whitespace
                            temp_ingredients.append(text)

                    if len(temp_ingredients) >= 3:
                        ingredients = temp_ingredients
                        logger.info(f"AH scraping successful with selector '{selector}': {len(ingredients)} ingredients")
                        break

            except Exception as e:
                logger.debug(f"AH selector '{selector}' failed: {e}")
                continue

        # If still no ingredients found, try text-based extraction from page content
        if not ingredients:
            logger.info("Trying text-based extraction for AH recipe")
            page_text = soup.get_text()

            # Look for ingredient patterns in the full text
            lines = page_text.split('\n')
            potential_ingredients = []

            for line in lines:
                line = line.strip()
                if not line or len(line) < 3:
                    continue

                # Look for lines that contain measurements (likely ingredients)
                if re.search(r'\d+\s*(gram|g|kg|ml|l|el|tl|stuks?|blik|pak)', line, re.IGNORECASE):
                    potential_ingredients.append(line)

            if len(potential_ingredients) >= 3:
                ingredients = potential_ingredients[:15]  # Limit to reasonable amount

        if not ingredients:
            raise Exception("Geen ingrediënten gevonden met AH-specifieke methode")

        return ingredients, title

    except requests.exceptions.RequestException as e:
        raise Exception(f"AH scraping request failed: {e}")

def _simulate_ah_navigation(session, url, headers):
    """Simulate human navigation to AH recipe page"""
    try:
        # First visit AH homepage
        logger.debug("Simulating visit to AH homepage")
        session.get("https://www.ah.nl/allerhande", headers=headers, timeout=15)
        time.sleep(random.uniform(1, 3))
        
        # Then visit the recipe page
        logger.debug("Navigating to recipe page")
        return session.get(url, headers={**headers, 'Referer': 'https://www.ah.nl/allerhande'}, timeout=25)
    except Exception as e:
        logger.warning(f"Navigation simulation failed: {e}")
        # Fallback to direct request
        return session.get(url, headers=headers, timeout=25)

def scrape_with_selenium(url: str) -> Tuple[List[str], str]:
    """Scrape using Selenium for dynamic content."""
    if not SELENIUM_AVAILABLE:
        raise Exception("Selenium niet beschikbaar")

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-logging')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    options.add_argument('--window-size=1920,1080')
    # Add longer page load timeout
    options.add_argument('--page-load-strategy=normal')

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        debug.log_selenium_action("Driver created", "Headless Chrome")

        driver.get(url)
        debug.log_selenium_action("Page loaded", url)

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Try to find ingredients
        selectors = [
            '.recipe-ingredient',
            '.ingredient',
            '.ingredients li',
            '[data-ingredient]'
        ]

        ingredients = []
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 2:
                            ingredients.append(text)

                    if len(ingredients) >= 3:
                        break
            except Exception as e:
                logger.debug(f"Selenium selector {selector} failed: {e}")

        # Get title
        title = "Onbekend recept"
        try:
            title_element = driver.find_element(By.TAG_NAME, "h1")
            title = title_element.text.strip()
        except:
            try:
                title = driver.title
            except:
                pass

        if not ingredients:
            raise Exception("Geen ingrediënten gevonden met Selenium")

        return ingredients, title

    finally:
        if driver:
            driver.quit()
            debug.log_selenium_action("Driver closed", "Cleanup completed")

def extract_ingredients_from_text(text: str) -> List[str]:
    """Extract ingredients from direct text input with smart duplicate handling."""
    logger.info("Extracting ingredients from text")

    # Check if the text contains HTML tags (likely not a recipe)
    if '<' in text and '>' in text:
        # Count HTML tags vs potential ingredients
        html_tag_count = text.count('<')
        lines_count = len([line for line in text.split('\n') if line.strip()])

        # If more than 30% of lines contain HTML tags, try to extract text from HTML
        if html_tag_count > (lines_count * 0.3):
            logger.info("Text appears to be HTML, attempting to extract text content")
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(text, 'html.parser')

                # Extract all text content and split into lines
                extracted_text = soup.get_text(separator='\n')
                potential_ingredients = []

                for line in extracted_text.split('\n'):
                    line = line.strip()
                    if line and len(line) > 2:
                        # Check if line looks like an ingredient
                        if any(pattern in line.lower() for pattern in ['gram', 'g', 'kg', 'ml', 'l', 'el', 'tl', 'stuks', 'blik', 'pak', 'uien', 'gehakt', 'tomaten', 'room']):
                            potential_ingredients.append(line)

                if len(potential_ingredients) >= 2:
                    logger.info(f"Extracted {len(potential_ingredients)} ingredients from HTML")
                    # Continue with these extracted ingredients
                    text = '\n'.join(potential_ingredients)
                else:
                    logger.warning("No clear ingredients found in HTML content")
                    raise Exception("Geen duidelijke ingrediënten gevonden in de HTML-code. Plak alleen de recept tekst zonder HTML-opmaak.")

            except ImportError:
                logger.warning("BeautifulSoup not available for HTML parsing")
                raise Exception("Deze tekst bevat HTML-code. Plak alleen de recept ingrediënten of instructies, geen HTML-code.")

    # Check for common HTML elements that indicate this is still HTML after processing
    html_indicators = ['<div', '<input', '<button', '<label', '<textarea', '<span', 'class=', 'id=', 'aria-']
    html_indicator_count = sum(1 for indicator in html_indicators if indicator.lower() in text.lower())

    if html_indicator_count >= 3:
        logger.warning("Text still contains multiple HTML indicators after processing")
        raise Exception("Deze tekst bevat nog steeds HTML-code. Plak alleen de recept ingrediënten of instructies, geen HTML-code.")

    # Split text into lines and filter for potential ingredients
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Clean and deduplicate lines
    cleaned_lines = []
    seen_ingredients = set()

    for line in lines:
        if not line or len(line) < 3:
            continue

        # Fix common copy-paste formatting issues from AH and other recipe sites
        cleaned_line = clean_ingredient_line(line)

        if cleaned_line:
            # Check for duplicates - if this is just the ingredient name without amounts,
            # and we already have a line with amounts for this ingredient, skip it
            ingredient_name = extract_ingredient_name_only(cleaned_line)

            # Skip if we already have this ingredient name with measurements
            skip_duplicate = False
            for seen_name in seen_ingredients:
                if ingredient_name.lower() in seen_name.lower() and has_measurements(seen_name):
                    skip_duplicate = True
                    break

            if not skip_duplicate:
                cleaned_lines.append(cleaned_line)
                seen_ingredients.add(cleaned_line)

    # Patterns that suggest ingredient lines
    ingredient_patterns = [
        r'^\d+(?:\.\d+)?\s*(gram|g|kg|ml|l|el|tl|stuks?|blik|pak)',  # Amount + unit
        r'^½\d*\.?\d*\s*\w+',  # Fractions like ½ or ½0.5
        r'^\d+(?:\.\d+)?\s*[^\d\s]',  # Number followed by text
        r'^-\s*\d*\s*[^\d]',  # Dash lists
        r'^\*\s*\d*\s*[^\d]',  # Bullet lists
        r'^\d+\.\s*\d*\s*[^\d]',  # Numbered lists
    ]

    ingredients = []
    for line in cleaned_lines:
        # Check if line matches ingredient patterns
        is_ingredient = any(re.match(pattern, line, re.IGNORECASE) for pattern in ingredient_patterns)

        # Also include lines that contain common ingredient words
        ingredient_words = ['gram', 'g', 'kg', 'ml', 'l', 'liter', 'eetlepel', 'el', 'theelepel', 'tl', 'stuks', 'blik', 'pak', 'snufje', 'snufjes', 'takje', 'takjes']
        contains_ingredient_word = any(word in line.lower() for word in ingredient_words)

        if is_ingredient or contains_ingredient_word:
            ingredients.append(line)

    # If no pattern matches found, use all cleaned lines
    if len(ingredients) < 3:
        ingredients = cleaned_lines

    # Final validation - ensure we have reasonable ingredients
    if len(ingredients) == 0:
        raise Exception("Geen ingrediënten gevonden in de tekst.")

    # Check if all "ingredients" are suspiciously similar (like HTML attributes)
    if len(ingredients) > 10:
        # Count how many contain common HTML patterns
        html_like_count = sum(1 for ing in ingredients if any(pattern in ing.lower() for pattern in ['class=', 'id=', 'data-', 'aria-', '</', 'div>', 'button>', 'input>', 'onclick', 'style=']))

        if html_like_count > (len(ingredients) * 0.3):
            logger.warning(f"Found {html_like_count} HTML-like ingredients out of {len(ingredients)} total")
            raise Exception("De tekst lijkt nog steeds HTML-code te bevatten in plaats van ingrediënten. Plak alleen de recept tekst.")

    # Additional check for reasonable ingredient content
    valid_ingredients = []
    for ing in ingredients:
        ing_lower = ing.lower()
        # Skip obvious HTML artifacts
        if any(html_pattern in ing_lower for html_pattern in ['onclick', 'javascript:', 'return false', 'class=', 'id=', 'data-', 'aria-']):
            continue
        # Skip very short or suspicious entries
        if len(ing) < 3 or ing.isdigit():
            continue
        valid_ingredients.append(ing)

    if len(valid_ingredients) < len(ingredients) * 0.5 and len(ingredients) > 5:
        logger.warning(f"Only {len(valid_ingredients)} valid ingredients out of {len(ingredients)} total")
        # Use only the valid ingredients if we have at least 2
        if len(valid_ingredients) >= 2:
            ingredients = valid_ingredients
        else:
            raise Exception("Geen geldige ingrediënten gevonden. Controleer of u echte recept-ingrediënten heeft geplakt.")

    logger.info(f"Extracted {len(ingredients)} ingredients from text after cleaning")
    return ingredients

def clean_ingredient_line(line: str) -> str:
    """Clean ingredient line from copy-paste formatting issues."""
    # Fix common AH.nl copy-paste issues like "500g500 gram" -> "500 gram"

    # Pattern: aantal+eenheid+aantal+spatie+eenheid (bijv. "500g500 gram")
    line = re.sub(r'(\d+(?:\.\d+)?)\s*(g|kg|ml|l|el|tl|gram|kilogram|liter|eetlepel|theelepel)\d+\s+(gram|kilogram|liter|eetlepel|theelepel)', r'\1 \3', line)

    # Pattern: aantal+eenheid+aantal+eenheid (bijv. "3el3 eetlepel")
    line = re.sub(r'(\d+(?:\.\d+)?)(el|tl|g|kg|ml|l)\d+\s+(eetlepel|theelepel|gram|kilogram|liter)', r'\1 \3', line)

    # Pattern: ½aantal -> ½ aantal
    line = re.sub(r'½(\d+(?:\.\d+)?)', r'0.5', line)

    # Clean up multiple spaces
    line = re.sub(r'\s+', ' ', line).strip()

    return line

def extract_ingredient_name_only(line: str) -> str:
    """Extract just the ingredient name without measurements."""
    # Remove common measurement patterns to get just the ingredient name
    clean_line = re.sub(r'^\d+(?:\.\d+)?\s*(gram|g|kg|ml|l|el|tl|eetlepel|theelepel|stuks?|blik|pak)\s*', '', line, flags=re.IGNORECASE)
    clean_line = re.sub(r'^½\d*\.?\d*\s*', '', clean_line)
    clean_line = re.sub(r'^\d+(?:\.\d+)?\s*', '', clean_line)
    return clean_line.strip()

def has_measurements(line: str) -> bool:
    """Check if line contains measurements."""
    measurement_pattern = r'\d+(?:\.\d+)?\s*(gram|g|kg|ml|l|el|tl|eetlepel|theelepel|stuks?|blik|pak)'
    return bool(re.search(measurement_pattern, line, re.IGNORECASE))

def translate_ingredient_to_dutch(ingredient_name):
    """Vertaal ingrediënt naar Nederlands"""
    translations = {
        # Basis ingrediënten
        'flour': 'bloem',
        'all-purpose flour': 'bloem (patent)',
        'sugar': 'suiker',
        'granulated sugar': 'kristalsuiker',
        'brown sugar': 'bruine suiker',
        'butter': 'boter',
        'eggs': 'eieren',
        'egg': 'ei',
        'milk': 'melk',
        'salt': 'zout',
        'baking powder': 'bakpoeder',
        'baking soda': 'zuiveringszout',
        'vanilla': 'vanille',
        'vanilla extract': 'vanille-extract',
        'oil': 'olie',
        'vegetable oil': 'plantaardige olie',
        'olive oil': 'olijfolie',
        'water': 'water',
        'cream': 'room',
        'heavy cream': 'slagroom',
        'sour cream': 'zure room',
        'cream cheese': 'roomkaas',
        'cheese': 'kaas',
        'cheddar cheese': 'cheddar kaas',
        'parmesan cheese': 'parmezaanse kaas',

        # Fruit
        'banana': 'banaan',
        'bananas': 'bananen',
        'apple': 'appel',
        'apples': 'appels',
        'orange': 'sinaasappel',
        'lemon': 'citroen',
        'lime': 'limoen',
        'pineapple': 'ananas',
        'strawberry': 'aardbei',
        'strawberries': 'aardbeien',
        'blueberry': 'bosbes',
        'blueberries': 'bosbessen',
        'raspberry': 'framboos',
        'raspberries': 'frambozen',
        'peach': 'perzik',
        'peaches': 'perziken',
        'pear': 'peer',
        'pears': 'peren',

        # Groenten
        'onion': 'ui',
        'onions': 'uien',
        'garlic': 'knoflook',
        'tomato': 'tomaat',
        'tomatoes': 'tomaten',
        'carrot': 'wortel',
        'carrots': 'wortels',
        'potato': 'aardappel',
        'potatoes': 'aardappels',
        'bell pepper': 'paprika',
        'red bell pepper': 'rode paprika',
        'green bell pepper': 'groene paprika',
        'cucumber': 'komkommer',
        'lettuce': 'sla',
        'spinach': 'spinazie',
        'broccoli': 'broccoli',
        'cauliflower': 'bloemkool',
        'mushroom': 'champignon',
        'mushrooms': 'champignons',

        # Vlees en vis
        'chicken': 'kip',
        'chicken breast': 'kipfilet',
        'beef': 'rundvlees',
        'ground beef': 'gehakt',
        'pork': 'varkensvlees',
        'bacon': 'spek',
        'ham': 'ham',
        'fish': 'vis',
        'salmon': 'zalm',
        'tuna': 'tonijn',
        'shrimp': 'garnalen',

        # Noten en zaden
        'nuts': 'noten',
        'almonds': 'amandelen',
        'walnuts': 'walnoten',
        'peanuts': 'pinda\'s',
        'cashews': 'cashewnoten',
        'pine nuts': 'pijnboompitten',
        'sunflower seeds': 'zonnebloempitten',
        'pumpkin seeds': 'pompoenpitten',

        # Kruiden en specerijen
        'pepper': 'peper',
        'black pepper': 'zwarte peper',
        'paprika': 'paprikapoeder',
        'cumin': 'komijn',
        'oregano': 'oregano',
        'basil': 'basilicum',
        'thyme': 'tijm',
        'rosemary': 'rozemarijn',
        'parsley': 'peterselie',
        'cilantro': 'koriander',
        'dill': 'dille',
        'sage': 'salie',
        'cinnamon': 'kaneel',
        'nutmeg': 'nootmuskaat',
        'ginger': 'gember',
        'turmeric': 'kurkuma',

        # Granen en pasta
        'rice': 'rijst',
        'bread': 'brood',
        'pasta': 'pasta',
        'spaghetti': 'spaghetti',
        'noodles': 'noedels',
        'oats': 'haver',
        'quinoa': 'quinoa',
        'barley': 'gerst',

        # Peulvruchten
        'beans': 'bonen',
        'black beans': 'zwarte bonen',
        'kidney beans': 'kidneybonen',
        'chickpeas': 'kikkererwten',
        'lentils': 'linzen',
        'peas': 'erwten',

        # Overig
        'chocolate': 'chocolade',
        'cocoa powder': 'cacaopoeder',
        'honey': 'honing',
        'maple syrup': 'ahornsiroop',
        'vinegar': 'azijn',
        'wine': 'wijn',
        'beer': 'bier',
        'stock': 'bouillon',
        'broth': 'bouillon',
        'chicken stock': 'kippenbouillon',
        'vegetable stock': 'groentebouillon',
        'soy sauce': 'sojasaus',
        'worcestershire sauce': 'worcestersaus',
        'hot sauce': 'hete saus',
        'ketchup': 'ketchup',
        'mayonnaise': 'mayonaise',
        'mustard': 'mosterd',
        'jam': 'jam',
        'jelly': 'gelei',
        'peanut butter': 'pindakaas',
    }

    # Maak lowercase voor matching
    name_lower = ingredient_name.lower().strip()

    # Directe match
    if name_lower in translations:
        return translations[name_lower]

    # Probeer gedeeltelijke matches voor samengestelde ingrediënten
    for eng_term, dutch_term in translations.items():
        if eng_term in name_lower:
            return ingredient_name.lower().replace(eng_term, dutch_term)

    # Als geen vertaling gevonden, return origineel
    return ingredient_name

def normalize_ingredient_name(name):
    """Normalize ingredient name."""
    name = name.lower()
    # Remove plurals and special characters
    name = re.sub(r's$', '', name)
    name = re.sub(r'[^a-z\s]', '', name)
    return name.strip()

def find_substitution(ingredient_name: str, substitutions_db: Dict[str, Any]) -> Dict[str, Any]:
    """Find ingredient substitution in the database."""
    # Fuzzy search for the ingredient
    best_match = None
    best_score = 0

    for key in substitutions_db.keys():
        score = fuzz.ratio(ingredient_name, key)
        if score > best_score:
            best_score = score
            best_match = key

    if best_score > 70:
        return substitutions_db[best_match]
    else:
        return {}

def calculate_health_score(ingredient_name: str, substitution_data: Dict[str, Any]) -> int:
    """Calculate health score for an ingredient."""
    if substitution_data:
        return substitution_data.get('health_score', 5)
    else:
        # Implement simple keyword-based scoring
        if 'groente' in ingredient_name or 'fruit' in ingredient_name:
            return 8
        elif 'suiker' in ingredient_name or 'vet' in ingredient_name:
            return 3
        else:
            return 5

def process_recipe_ingredients(ingredients: List[str], substitutions_db: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process recipe ingredients, normalize names, and calculate health scores."""
    processed_ingredients = []

    # Verwerk elk ingredient
    for ingredient in ingredients:
        try:
            # Vertaal eerst naar Nederlands als het Engels lijkt te zijn
            translated_name = translate_ingredient_to_dutch(ingredient)

            # Normaliseer de naam
            normalized_name = normalize_ingredient_name(translated_name)

            # Skip als leeg
            if not normalized_name:
                continue

            # Zoek in substitutie database
            substitution_data = find_substitution(normalized_name, substitutions_db)

            # Bereken health score
            health_score = calculate_health_score(normalized_name, substitution_data)

            # Force translation to Dutch
            dutch_name = translate_to_dutch(normalized_name)

            # Create ingredient object with health score
            ingredient_obj = {
                "name": dutch_name,
                "health_score": health_score,
                "details": substitution_data.get('details', ''),
                "health_fact": substitution_data.get('health_fact', ''),
                "substitution": substitution_data.get('substitution', '')
            }

            processed_ingredients.append(ingredient_obj)

        except Exception as e:
            logger.warning(f"Error processing ingredient '{ingredient}': {e}")
            continue

    return processed_ingredients

def analyze_ingredient(ingredient_text: str) -> Dict[str, Any]:
    """Analyze a single ingredient for health scoring with structured parsing."""
    if not ingredient_text or not isinstance(ingredient_text, str):
        return {
            'name': 'Onbekend ingrediënt',
            'original_text': str(ingredient_text) if ingredient_text else '',
            'health_score': 5,
            'category': 'unknown',
            'quantity': None,
            'unit': None,
            'nutrition': {}
        }

    # Basic ingredient analysis - verbeterd voor duplicate text
    original_text = ingredient_text.strip()

    # Verwijder duplicaten (bijv. "½0.5 afbakciabatta\n\nafbakciabatta")
    lines = [line.strip() for line in original_text.split('\n') if line.strip()]
    if len(lines) > 1:
        # Neem de langste/meest complete regel
        ingredient_text = max(lines, key=len)
    else:
        ingredient_text = lines[0] if lines else original_text

    # Parse quantity and unit
    quantity, unit, clean_ingredient = parse_ingredient_components(ingredient_text)

    # Get nutrition data from multiple sources
    nutrition_data = get_enhanced_nutrition_data(clean_ingredient, quantity, unit)

    # Simple health scoring based on keywords
    healthy_keywords = ['groente', 'fruit', 'volkoren', 'noten', 'vis', 'olijfolie', 'avocado', 'asperges', 'sperziebonen', 'spinazie', 'peterselie', 'radijs', 'nectarine', 'granaatappel']
    unhealthy_keywords = ['suiker', 'boter', 'room', 'spek', 'worst', 'gebak', 'friet', 'chips']

    health_score = 5  # Default neutral score

    ingredient_lower = clean_ingredient.lower()

    # Check for healthy keywords
    for keyword in healthy_keywords:
        if keyword in ingredient_lower:
            health_score = min(10, health_score + 2)
            break

    # Check for unhealthy keywords
    for keyword in unhealthy_keywords:
        if keyword in ingredient_lower:
            health_score = max(1, health_score - 2)
            break

    # Special cases
    if 'burrata' in ingredient_lower or 'kaas' in ingredient_lower:
        health_score = 6  # Moderate score for cheese
    elif 'olijfolie' in ingredient_lower:
        health_score = 8  # High score for olive oil
    elif any(veg in ingredient_lower for veg in ['asperges', 'sperziebonen', 'spinazie', 'radijs']):
        health_score = 9  # Very high for vegetables
    elif any(fruit in ingredient_lower for fruit in ['nectarine', 'granaatappel']):
        health_score = 8  # High for fruits

    return {
        'name': clean_ingredient,
        'original_text': original_text,
        'health_score': health_score,
        'category': 'unknown',
        'quantity': quantity,
        'unit': unit,
        'nutrition': nutrition_data
    }

def get_enhanced_nutrition_data(ingredient_name: str, quantity: Optional[float] = None, unit: Optional[str] = None) -> Dict[str, Any]:
    """Get nutrition data using multiple sources with fallbacks."""
    
    # Try Open Food Facts first (works better for European products)
    nutrition_data = get_nutrition_from_openfoodfacts_api(ingredient_name)
    
    # If that fails, try USDA API
    if not nutrition_data or all(v == 0 for v in nutrition_data.values()):
        nutrition_data = get_ingredient_nutrition_usda(ingredient_name)
    
    # If both fail, use basic estimations
    if not nutrition_data or all(v == 0 for v in nutrition_data.values()):
        nutrition_data = get_basic_nutrition_estimates(ingredient_name)
    
    # Apply quantity multiplier if available
    if nutrition_data and quantity and unit:
        multiplier = calculate_nutrition_multiplier(quantity, unit)
        for key in nutrition_data:
            if isinstance(nutrition_data[key], (int, float)):
                nutrition_data[key] = round(nutrition_data[key] * multiplier, 1)
    
    return nutrition_data

def get_nutrition_from_openfoodfacts_api(ingredient_name: str) -> Dict[str, Any]:
    """Get nutrition data from Open Food Facts API (better for European foods)."""
    try:
        # Clean ingredient name for search
        clean_name = ingredient_name.lower().strip()
        
        # Try both Dutch and English names
        search_terms = [clean_name]
        
        # Add English translation
        dutch_to_english = {
            'ui': 'onion', 'uien': 'onions', 'knoflook': 'garlic',
            'tomaat': 'tomato', 'tomaten': 'tomatoes', 'wortel': 'carrot',
            'aardappel': 'potato', 'kip': 'chicken', 'rundvlees': 'beef',
            'gehakt': 'ground beef', 'vis': 'fish', 'spinazie': 'spinach',
            'paprika': 'bell pepper', 'komkommer': 'cucumber', 'rijst': 'rice',
            'pasta': 'pasta', 'bloem': 'flour', 'suiker': 'sugar',
            'boter': 'butter', 'melk': 'milk', 'kaas': 'cheese',
            'olijfolie': 'olive oil', 'peterselie': 'parsley', 'koriander': 'coriander',
            'basterdsuiker': 'brown sugar', 'burrata': 'burrata cheese'
        }
        
        english_name = dutch_to_english.get(clean_name, clean_name)
        if english_name != clean_name:
            search_terms.append(english_name)
        
        for search_term in search_terms:
            search_url = f"https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                'search_terms': search_term,
                'search_simple': 1,
                'action': 'process',
                'json': 1,
                'page_size': 1
            }
            
            response = requests.get(search_url, params=params, timeout=8)
            if response.status_code == 200:
                data = response.json()
                
                if data.get('products') and len(data['products']) > 0:
                    product = data['products'][0]
                    nutriments = product.get('nutriments', {})
                    
                    nutrition = {
                        'calories': nutriments.get('energy-kcal_100g', 0),
                        'protein': nutriments.get('proteins_100g', 0),
                        'carbs': nutriments.get('carbohydrates_100g', 0),
                        'fat': nutriments.get('fat_100g', 0),
                        'fiber': nutriments.get('fiber_100g', 0),
                        'sodium': nutriments.get('sodium_100g', 0),
                        'sugar': nutriments.get('sugars_100g', 0)
                    }
                    
                    # Check if we got meaningful data
                    if any(v > 0 for v in nutrition.values()):
                        logger.debug(f"Found nutrition data via Open Food Facts for {ingredient_name}")
                        return nutrition
        
        return {}
        
    except Exception as e:
        logger.debug(f"Open Food Facts API error for {ingredient_name}: {e}")
        return {}

def get_ingredient_nutrition_usda(ingredient_name: str) -> Dict[str, Any]:
    """Get nutrition data using USDA FoodData Central API."""
    try:
        clean_name = ingredient_name.lower().strip()
        
        # Translate Dutch to English for USDA API
        dutch_to_english = {
            'ui': 'onion', 'uien': 'onions', 'knoflook': 'garlic',
            'tomaat': 'tomato', 'tomaten': 'tomatoes', 'wortel': 'carrot',
            'aardappel': 'potato', 'kip': 'chicken', 'rundvlees': 'beef',
            'gehakt': 'ground beef', 'vis': 'fish', 'spinazie': 'spinach',
            'paprika': 'bell pepper', 'komkommer': 'cucumber', 'rijst': 'rice',
            'pasta': 'pasta', 'bloem': 'flour', 'suiker': 'sugar',
            'boter': 'butter', 'melk': 'milk', 'kaas': 'cheese',
            'olijfolie': 'olive oil', 'peterselie': 'parsley'
        }
        
        english_name = dutch_to_english.get(clean_name, clean_name)
        
        search_url = f"https://api.nal.usda.gov/fdc/v1/foods/search"
        params = {
            'query': english_name,
            'dataType': ['Foundation', 'SR Legacy'],
            'pageSize': 1,
            'api_key': 'DEMO_KEY'
        }
        
        response = requests.get(search_url, params=params, timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('foods') and len(data['foods']) > 0:
                food = data['foods'][0]
                food_nutrients = food.get('foodNutrients', [])
                
                nutrition = {
                    'calories': 0,
                    'protein': 0,
                    'carbs': 0,
                    'fat': 0,
                    'fiber': 0,
                    'sodium': 0,
                    'sugar': 0
                }
                
                nutrient_map = {
                    1008: 'calories',  # Energy (kcal)
                    1003: 'protein',   # Protein
                    1005: 'carbs',     # Carbohydrate
                    1004: 'fat',       # Total fat
                    1079: 'fiber',     # Fiber
                    1093: 'sodium',    # Sodium
                    2000: 'sugar'      # Total sugars
                }
                
                for nutrient in food_nutrients:
                    nutrient_id = nutrient.get('nutrientId')
                    if nutrient_id in nutrient_map:
                        value = nutrient.get('value', 0)
                        nutrition[nutrient_map[nutrient_id]] = round(value, 1)
                
                if any(v > 0 for v in nutrition.values()):
                    logger.debug(f"Found nutrition data via USDA for {ingredient_name}")
                    return nutrition
                
    except Exception as e:
        logger.debug(f"USDA API error for {ingredient_name}: {e}")
    
    return {}

def get_basic_nutrition_estimates(ingredient_name: str) -> Dict[str, Any]:
    """Provide basic nutrition estimates for common ingredients when APIs fail."""
    clean_name = ingredient_name.lower().strip()
    
    # Basic nutrition estimates per 100g for common ingredients
    nutrition_estimates = {
        # Vegetables
        'ui': {'calories': 40, 'protein': 1.1, 'carbs': 9.3, 'fat': 0.1, 'fiber': 1.7},
        'uien': {'calories': 40, 'protein': 1.1, 'carbs': 9.3, 'fat': 0.1, 'fiber': 1.7},
        'knoflook': {'calories': 149, 'protein': 6.4, 'carbs': 33, 'fat': 0.5, 'fiber': 2.1},
        'tomaat': {'calories': 18, 'protein': 0.9, 'carbs': 3.9, 'fat': 0.2, 'fiber': 1.2},
        'tomaten': {'calories': 18, 'protein': 0.9, 'carbs': 3.9, 'fat': 0.2, 'fiber': 1.2},
        'wortel': {'calories': 41, 'protein': 0.9, 'carbs': 9.6, 'fat': 0.2, 'fiber': 2.8},
        'paprika': {'calories': 31, 'protein': 1, 'carbs': 7, 'fat': 0.3, 'fiber': 2.5},
        'spinazie': {'calories': 23, 'protein': 2.9, 'carbs': 3.6, 'fat': 0.4, 'fiber': 2.2},
        'peterselie': {'calories': 36, 'protein': 3, 'carbs': 6.3, 'fat': 0.8, 'fiber': 3.3},
        'koriander': {'calories': 23, 'protein': 2.1, 'carbs': 3.7, 'fat': 0.5, 'fiber': 2.8},
        
        # Proteins
        'kip': {'calories': 165, 'protein': 31, 'carbs': 0, 'fat': 3.6, 'fiber': 0},
        'gehakt': {'calories': 250, 'protein': 26, 'carbs': 0, 'fat': 15, 'fiber': 0},
        'burrata': {'calories': 330, 'protein': 17, 'carbs': 3, 'fat': 28, 'fiber': 0},
        
        # Oils and fats
        'olijfolie': {'calories': 884, 'protein': 0, 'carbs': 0, 'fat': 100, 'fiber': 0},
        'boter': {'calories': 717, 'protein': 0.9, 'carbs': 0.1, 'fat': 81, 'fiber': 0},
        
        # Sugars
        'suiker': {'calories': 387, 'protein': 0, 'carbs': 100, 'fat': 0, 'fiber': 0},
        'basterdsuiker': {'calories': 380, 'protein': 0, 'carbs': 98, 'fat': 0, 'fiber': 0},
        
        # Grains
        'rijst': {'calories': 130, 'protein': 2.7, 'carbs': 28, 'fat': 0.3, 'fiber': 0.4},
        'pasta': {'calories': 131, 'protein': 5, 'carbs': 25, 'fat': 1.1, 'fiber': 1.8},
    }
    
    # Try to find exact match first
    if clean_name in nutrition_estimates:
        base_nutrition = nutrition_estimates[clean_name].copy()
        base_nutrition.update({'sodium': 0, 'sugar': 0})  # Add missing keys
        logger.debug(f"Using nutrition estimates for {ingredient_name}")
        return base_nutrition
    
    # Try partial matches
    for key, nutrition in nutrition_estimates.items():
        if key in clean_name or clean_name in key:
            base_nutrition = nutrition.copy()
            base_nutrition.update({'sodium': 0, 'sugar': 0})
            logger.debug(f"Using partial match nutrition estimates for {ingredient_name}")
            return base_nutrition
    
    # Default values if no match
    return {
        'calories': 50,
        'protein': 2,
        'carbs': 10,
        'fat': 1,
        'fiber': 1,
        'sodium': 0,
        'sugar': 0
    }

def calculate_nutrition_multiplier(quantity: float, unit: str) -> float:
    """Calculate multiplier to convert from 100g base to actual quantity."""
    # Convert different units to grams, then get ratio to 100g
    unit_to_grams = {
        'gram': 1,
        'g': 1,
        'kilogram': 1000,
        'kg': 1000,
        'eetlepel': 15,  # approx 15g
        'el': 15,
        'theelepel': 5,  # approx 5g
        'tl': 5,
        'stuks': 100,    # assume average piece is 100g
        'stuk': 100,
        'blik': 400,     # average can
        'pak': 250,      # average package
        'teen': 5,       # garlic clove
        'takje': 2,      # herb sprig
        'snufje': 0.5    # pinch
    }
    
    grams = quantity * unit_to_grams.get(unit.lower(), 100)
    return grams / 100  # Convert to per-100g basis

def parse_ingredient_components(ingredient_text: str) -> Tuple[Optional[float], Optional[str], str]:
    """Parse ingredient text into quantity, unit, and name components."""

    # Normalize fractions first
    text = ingredient_text.replace('½', '0.5')

    # Common unit mappings
    unit_mappings = {
        'g': 'gram',
        'kg': 'kilogram', 
        'l': 'liter',
        'ml': 'milliliter',
        'el': 'eetlepel',
        'tl': 'theelepel',
        'stuks': 'stuks',
        'stuk': 'stuks',
        'blik': 'blik',
        'pak': 'pak',
        'teen': 'teen',
        'takje': 'takje',
        'takjes': 'takje',
        'snufje': 'snufje',
        'snufjes': 'snufje'
    }

    # Try to match quantity and unit patterns
    patterns = [
        # Pattern: "500 gram verse witte asperges"
        r'^(\d+(?:\.\d+)?)\s+(gram|kilogram|liter|milliliter|eetlepel|theelepel|stuks?|blik|pak|teen|takjes?|snufjes?)\s+(.+)',
        # Pattern: "500g verse witte asperges" 
        r'^(\d+(?:\.\d+)?)(g|kg|l|ml|el|tl)\s+(.+)',
        # Pattern: "3 el extra vierge olijfolie"
        r'^(\d+(?:\.\d+)?)\s+(el|tl|g|kg|ml|l)\s+(.+)',
        # Pattern: "22 nectarines" (just number + name)
        r'^(\d+(?:\.\d+)?)\s+(.+)',
    ]

    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            if len(match.groups()) == 3:
                quantity_str, unit_str, name = match.groups()
                # Normalize unit
                unit = unit_mappings.get(unit_str.lower(), unit_str.lower())
                try:
                    quantity = float(quantity_str)
                    return quantity, unit, name.strip()
                except ValueError:
                    pass
            elif len(match.groups()) == 2:
                quantity_str, name = match.groups()
                try:
                    quantity = float(quantity_str)
                    return quantity, 'stuks', name.strip()
                except ValueError:
                    pass

    # If no pattern matches, return just the clean name
    clean_name = re.sub(r'^\d+(?:\.\d+)?\s*', '', text).strip()
    clean_name = re.sub(r'^(g|kg|l|ml|el|tl|gram|kilogram|liter|milliliter|eetlepel|theelepel)\s*', '', clean_name, flags=re.IGNORECASE).strip()

    return None, None, clean_name if clean_name else text.strip()

def calculate_total_nutrition(ingredients: List[Dict]) -> Dict[str, float]:
    """Calculate total nutrition from ingredients."""
    return {
        'calories': sum(ing.get('calories', 50) for ing in ingredients),
        'protein': sum(ing.get('protein', 2) for ing in ingredients),
        'carbs': sum(ing.get('carbs', 5) for ing in ingredients),
        'fat': sum(ing.get('fat', 1) for ing in ingredients),
        'fiber': sum(ing.get('fiber', 1) for ing in ingredients)
    }

def calculate_health_goals_scores(ingredients: List[Dict], nutrition: Dict) -> Dict[str, int]:
    """Calculate health goal scores."""
    avg_health_score = sum(ing['health_score'] for ing in ingredients) / len(ingredients) if ingredients else 5

    return {
        'weight_loss': int(avg_health_score * 0.8),
        'muscle_gain': int(avg_health_score * 0.9),
        'heart_health': int(avg_health_score),
        'energy_boost': int(avg_health_score * 0.85)
    }

def generate_health_explanation(ingredients: List[Dict], health_scores: Dict) -> List[str]:
    """Generate health explanations with OpenAI for specific ingredient reasons."""
    explanations = []

    if not ingredients:
        explanations.append("ℹ️ Geen ingrediënten beschikbaar voor analyse.")
        return explanations

    avg_score = sum(ing.get('health_score', 5) for ing in ingredients) / len(ingredients)

    if avg_score >= 7:
        explanations.append("🌱 Dit recept bevat voornamelijk gezonde ingrediënten!")
    elif avg_score >= 5:
        explanations.append("⚖️ Dit recept heeft een gemiddelde gezondheidscore.")
    else:
        explanations.append("⚠️ Dit recept bevat veel minder gezonde ingrediënten.")

    # Voeg specifieke uitleg toe over ingrediënten
    healthy_ingredients = [ing for ing in ingredients if ing.get('health_score', 5) >= 7]
    unhealthy_ingredients = [ing for ing in ingredients if ing.get('health_score', 5) <= 3]

    # Get OpenAI explanations for healthy ingredients
    if healthy_ingredients:
        healthy_names = [ing.get('name', 'Onbekend') for ing in healthy_ingredients[:3]]
        try:
            # Filter out hidden goals for active goals context
            active_goals = {k: v for k, v in health_scores.items() if v > 3}  # Only include goals with decent scores
            healthy_explanation = get_openai_ingredient_explanation(healthy_names, True, active_goals)
            explanations.append(f"✅ {healthy_explanation}")
            logger.info(f"OpenAI healthy explanation generated successfully for {len(healthy_names)} ingredients")
        except Exception as e:
            logger.warning(f"OpenAI explanation failed for healthy ingredients: {e}")
            explanations.append(f"✅ Gezonde ingrediënten (score 7-10): {', '.join(healthy_names)} - Deze ingrediënten zijn rijk aan vitamines, mineralen en andere gezonde voedingsstoffen.")

    # Get OpenAI explanations for unhealthy ingredients
    if unhealthy_ingredients:
        unhealthy_names = [ing.get('name', 'Onbekend') for ing in unhealthy_ingredients[:3]]
        try:
            # Filter out hidden goals for active goals context
            active_goals = {k: v for k, v in health_scores.items() if v > 3}
            unhealthy_explanation = get_openai_ingredient_explanation(unhealthy_names, False, active_goals)
            explanations.append(f"❌ {unhealthy_explanation}")
            logger.info(f"OpenAI unhealthy explanation generated successfully for {len(unhealthy_names)} ingredients")
        except Exception as e:
            logger.warning(f"OpenAI explanation failed for unhealthy ingredients: {e}")
            explanations.append(f"❌ Minder gezonde ingrediënten (score 1-3): {', '.join(unhealthy_names)} - Deze ingrediënten bevatten veel suiker, verzadigde vetten of geraffineerde koolhydraten. Gebruik ze in beperkte hoeveelheden.")

    return explanations

def get_openai_ingredient_explanation(ingredient_names: List[str], is_healthy: bool, active_health_goals: Dict[str, int]) -> str:
    """Get OpenAI explanation for why ingredients are healthy or unhealthy."""
    import os
    
    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OpenAI API key not found in environment")
        raise Exception("OpenAI API key niet gevonden - stel OPENAI_API_KEY in bij Secrets")

    # Filter out hidden goals and translate keys
    visible_goals = []
    goal_translations = {
        "Algemene gezondheid": "algemene gezondheid",
        "Hart- en vaatziekten": "hart- en vaatziekten", 
        "Diabetes preventie": "diabetes preventie",
        "Gewichtsbeheersing": "gewichtsbeheersing",
        "Spijsvertering": "spijsvertering",
        "Immuunsysteem": "immuunsysteem",
        "Botgezondheid": "botgezondheid",
        "Energieniveau": "energieniveau",
        "Huidgezondheid": "huidgezondheid",
        "Hersengezondheid": "hersengezondheid",
        "weight_loss": "gewichtsverlies",
        "muscle_gain": "spieropbouw",
        "heart_health": "hartgezondheid",
        "energy_boost": "energie boost"
    }
    
    for goal, score in active_health_goals.items():
        if score > 3:  # Only include goals with decent scores
            translated_goal = goal_translations.get(goal, goal.replace('_', ' '))
            visible_goals.append(translated_goal)
    
    ingredients_text = ", ".join(ingredient_names)
    health_status = "gezond" if is_healthy else "minder gezond"
    goals_context = f"Relevante gezondheidsdoelen: {', '.join(visible_goals[:5])}" if visible_goals else ""
    
    if is_healthy:
        prompt = f"""Leg in 1-2 zinnen uit waarom deze ingrediënten gezond zijn: {ingredients_text}

{goals_context}

Focus op voedingsstoffen, vitamines en gezondheidsvoordelen. Antwoord in het Nederlands."""
    else:
        prompt = f"""Leg in 1-2 zinnen uit waarom deze ingrediënten minder gezond zijn: {ingredients_text}

{goals_context}

Focus op waarom ze minder gezond zijn (suiker, verzadigde vetten, etc.) en geef een kort advies. Antwoord in het Nederlands."""

    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "Je bent een voedingsdeskundige die korte, accurate uitleg geeft over ingrediënten in recepten."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 120,
            "temperature": 0.3
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            explanation = result['choices'][0]['message']['content'].strip()
            
            # Format the response properly
            status_prefix = "Gezonde ingrediënten (score 7-10)" if is_healthy else "Minder gezonde ingrediënten (score 1-3)"
            return f"{status_prefix}: {ingredients_text} - {explanation}"
        else:
            logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
            raise Exception(f"OpenAI API fout: HTTP {response.status_code}")
        
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        # Re-raise to be handled by calling function
        raise Exception(f"OpenAI API aanroep mislukt: {str(e)}")

def generate_healthier_swaps(ingredients: List[Dict]) -> List[Dict]:
    """Generate healthier ingredient swaps."""
    swaps = []

    for ingredient in ingredients:
        if ingredient['health_score'] < 6:
            # Simple swap suggestions
            name_lower = ingredient['name'].lower()
            if 'boter' in name_lower:
                swaps.append({
                    'original': ingredient['name'],
                    'suggestion': 'Olijfolie of avocado',
                    'reason': 'Gezonderevetten'
                })
            elif 'suiker' in name_lower:
                swaps.append({
                    'original': ingredient['name'],
                    'suggestion': 'Honing of dadels',
                    'reason': 'Natuurlijke zoetstof'
                })

    return swaps

async def validate_ingredients_with_openai(ingredients_list: List[str]) -> List[str]:
    """Validate ingredients using OpenAI (placeholder for now)."""
    # For now, just return the original list
    # In the future, this could use OpenAI API to filter out non-food items
    return ingredients_list

def analyse_text_directly(text: str) -> Dict[str, Any]:
    """Analyse function for direct text input."""
    logger.info("Starting text analysis")

    try:
        # Extract ingredients from text using patterns
        ingredients = extract_ingredients_from_text(text)

        if not ingredients:
            raise Exception("Geen ingrediënten gevonden in de tekst. Controleer of de tekst ingrediënten bevat.")

        logger.info(f"Found {len(ingredients)} ingredients in text")

        # Process ingredients the same way as URL analysis
        all_ingredients = []
        for ingredient_text in ingredients:
            ingredient_data = analyze_ingredient(ingredient_text.strip())
            if ingredient_data:
                all_ingredients.append(ingredient_data)

        # Calculate nutrition and health scores
        total_nutrition = calculate_total_nutrition(all_ingredients)
        health_goals_scores = calculate_health_goals_scores(all_ingredients, total_nutrition)
        health_explanation = generate_health_explanation(all_ingredients, health_goals_scores)
        swaps = generate_healthier_swaps(all_ingredients)

        result = {
            "success": True,
            "recipe_title": "Tekst Analyse",
            "source": "direct_text",
            "all_ingredients": all_ingredients,
            "total_nutrition": total_nutrition,
            "health_goals_scores": health_goals_scores,
            "health_explanation": health_explanation,
            "swaps": swaps,
            "ingredient_count": len(all_ingredients)
        }

        logger.info("Text analysis completed successfully")
        return result

    except Exception as e:
        logger.error(f"Text analysis failed: {e}")
        raise

def analyse(url_or_text: str) -> Dict[str, Any]:
    """
    Main analysis function that coordinates the entire recipe analysis process.

    Args:
        url_or_text (str): URL of the recipe page or direct text to analyze

    Returns:
        Dict[str, Any]: Complete analysis results including ingredients, 
                       nutrition, health scores, and recommendations
    """
    logger.info(f"Starting analysis for {url_or_text[:50]}...")

    # Check if input is URL or direct text
    if url_or_text.startswith(('http://', 'https://')):
        # Extract ingredients from URL
        ingredients_list, recipe_title = smart_ingredient_scraping(url_or_text)
    else:
        # Extract ingredients from direct text
        logger.info("Processing direct text input")
        ingredients_list = extract_ingredients_from_text(url_or_text)
        recipe_title = "Tekst Analyse"

    if not ingredients_list or len(ingredients_list) < 3:
        raise Exception("Geen ingrediënten gevonden. Controleer of dit een receptpagina is of dat de tekst ingrediënten bevat.")

    # Process each ingredient
    all_ingredients = []
    for ingredient_text in ingredients_list:
        ingredient_data = analyze_ingredient(ingredient_text.strip())
        if ingredient_data:
            all_ingredients.append(ingredient_data)

    # Calculate overall metrics
    total_nutrition = calculate_total_nutrition(all_ingredients)
    health_goals_scores = calculate_health_goals_scores(all_ingredients, total_nutrition)

    # Ensure all standard health goals are present
    standard_goals = {
        "Algemene gezondheid": 5,
        "Hart- en vaatziekten": 5,
        "Diabetes preventie": 5,
        "Gewichtsbeheersing": 5,
        "Spijsvertering": 5,
        "Immuunsysteem": 5,
        "Botgezondheid": 5,
        "Energieniveau": 5,
        "Huidgezondheid": 5,
        "Hersengezondheid": 5
    }

    # Update with calculated scores, keeping standard goals that weren't calculated
    for goal, default_score in standard_goals.items():
        if goal not in health_goals_scores:
            health_goals_scores[goal] = default_score

    # Ensure Algemene gezondheid is first
    ordered_goals = {"Algemene gezondheid": health_goals_scores.pop("Algemene gezondheid", 5)}
    ordered_goals.update(health_goals_scores)
    health_goals_scores = ordered_goals

    # Calculate overall health score
    health_score = sum(health_goals_scores[goal] * 0.1 for goal in health_goals_scores)

    # Get health explanation
    health_explanation = generate_health_explanation(all_ingredients, health_goals_scores)

    # Generate health score explanation
    health_score_explanation = generate_health_score_explanation(
        health_score, total_nutrition, all_ingredients, health_goals_scores
    )

    swaps = generate_healthier_swaps(all_ingredients)

    result = {
        "success": True,
        "recipe_title": recipe_title or "Recept Analyse",
        "source": "url" if url_or_text.startswith(('http://', 'https://')) else "text",
        "all_ingredients": all_ingredients or [],
        "total_nutrition": total_nutrition or {},
        "health_goals_scores": health_goals_scores or {},
        "swaps": swaps or [],
        "health_explanation": health_explanation,
        "health_score_explanation": health_score_explanation,
        "ingredient_count": len(all_ingredients),
        "health_score": round(health_score, 1) if health_score else 5.0
    }

    logger.info(f"Analysis completed successfully: {len(all_ingredients)} ingredients, health score: {health_score:.1f}")
    return result

if __name__ == "__main__":
    """
    Command line interface for testing recipe analysis.

    Usage:
        python analyse.py <recipe_url>
    """
    import sys
    import pprint
    import os
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY")

    if len(sys.argv) != 2:
        print("Usage: python analyse.py <recipe_url>")
        sys.exit(1)

    try:
        result = analyse(sys.argv[1])
        pprint.pprint(result)
    except Exception as e:
        print(f"Analysis failed: {e}")
        sys.exit(1)


def calculate_portions(ingredients: List[Dict], target_portions: int, original_portions: int = 4) -> List[Dict]:
    """
    Calculate ingredient quantities for different number of portions.

    Args:
        ingredients: List of ingredient dictionaries with quantity and unit
        target_portions: Target number of portions
        original_portions: Original recipe portions (default 4)

    Returns:
        List of ingredients with adjusted quantities
    """
    if target_portions <= 0 or original_portions <= 0:
        return ingredients

    portion_multiplier = target_portions / original_portions
    adjusted_ingredients = []

    for ingredient in ingredients:
        adjusted_ingredient = ingredient.copy()

        if ingredient.get('quantity') is not None:
            original_quantity = ingredient['quantity']
            new_quantity = original_quantity * portion_multiplier

            # Round to reasonable precision
            if new_quantity < 1:
                # For small amounts, round to 1 decimal place
                adjusted_ingredient['quantity'] = round(new_quantity, 1)
            elif new_quantity < 10:
                # For medium amounts, round to nearest 0.5
                adjusted_ingredient['quantity'] = round(new_quantity * 2) / 2
            else:
                # For large amounts, round to nearest whole number
                adjusted_ingredient['quantity'] = round(new_quantity)

            # Update display text
            if adjusted_ingredient['quantity'] and adjusted_ingredient.get('unit'):
                adjusted_ingredient['display_text'] = f"{adjusted_ingredient['quantity']} {adjusted_ingredient['unit']} {adjusted_ingredient['name']}"
            else:
                adjusted_ingredient['display_text'] = adjusted_ingredient['name']
        else:
            # No quantity info, keep as-is
            adjusted_ingredient['display_text'] = adjusted_ingredient['name']

        adjusted_ingredients.append(adjusted_ingredient)

    return adjusted_ingredients

def detect_recipe_portions(ingredients: List[Dict]) -> int:
    """
    Try to detect how many portions a recipe is for based on ingredient quantities.

    Args:
        ingredients: List of ingredient dictionaries

    Returns:
        Estimated number of portions (default 4 if unclear)
    """
    # Look for clues in quantities - this is a simple heuristic
    protein_quantities = []

    for ingredient in ingredients:
        name_lower = ingredient.get('name', '').lower()
        quantity = ingredient.get('quantity')
        unit = ingredient.get('unit', '').lower()

        # Look for main protein sources and their typical quantities
        if quantity and unit in ['gram', 'g']:
            if any(protein in name_lower for protein in ['vlees', 'kip', 'vis', 'gehakt', 'burrata', 'kaas']):
                protein_quantities.append(quantity)

    if protein_quantities:
        avg_protein = sum(protein_quantities) / len(protein_quantities)

        # Rough estimation based on protein amounts
        if avg_protein < 150:
            return 2
        elif avg_protein < 300:
            return 4  
        elif avg_protein < 500:
            return 6
        else:
            return 8

    # Default to 4 portions if we can't determine
    return 4

def translate_to_dutch(text):
    """Translate text to Dutch using OpenAI"""
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Je bent een professionele vertaler voor voedingsingrediënten. Vertaal de gegeven ingrediëntnaam naar het Nederlands. Gebruik Nederlandse culinaire termen. Geef alleen de Nederlandse naam terug, geen uitleg of extra tekst."},
                {"role": "user", "content": f"Vertaal deze ingrediëntnaam naar het Nederlands: {text}"}
            ],
            max_tokens=50,
            temperature=0
        )
        translation = response.choices[0].message.content.strip()

        # Ensure we got a valid translation
        if translation and translation.lower() != text.lower():
            return translation
        else:
            # Fallback to simple dictionary for common ingredients
            simple_translations = {
                'flour': 'bloem',
                'sugar': 'suiker', 
                'butter': 'boter',
                'eggs': 'eieren',
                'milk': 'melk',
                'oil': 'olie',
                'salt': 'zout',
                'pepper': 'peper',
                'chicken': 'kip',
                'beef': 'rundvlees',
                'pork': 'varkensvlees',
                'onion': 'ui',
                'garlic': 'knoflook',
                'tomato': 'tomaat',
                'carrot': 'wortel',
                'potato': 'aardappel'
            }
            return simple_translations.get(text.lower(), text)

    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text

def calculate_overall_health_score(health_goals_scores: Dict[str, int]) -> float:
    """Calculate an overall health score from health goal scores."""
    try:
        # Define weights for each health goal
        weights = {
            "Algemene gezondheid": 0.25,
            "Hart- en vaatziekten": 0.15,
            "Diabetes preventie": 0.15,
            "Gewichtsbeheersing": 0.10,
            "Spijsvertering": 0.05,
            "Immuunsysteem": 0.05,
            "Botgezondheid": 0.05,
            "Energieniveau": 0.10,
            "Huidgezondheid": 0.05,
            "Hersengezondheid": 0.05
        }

        # Calculate weighted sum of health goal scores
        weighted_sum = sum(health_goals_scores[goal] * weights.get(goal, 0) for goal in health_goals_scores)

        # Normalize to a 1-10 scale
        overall_health_score = weighted_sum / sum(weights.values()) if weights else 5

        return round(overall_health_score, 1)

    except Exception as e:
        logger.error(f"Error calculating overall health score: {e}")
        return 5.0

def get_health_explanation(ingredients: List[Dict]) -> List[str]:
    """Get health explanations with safety net."""
    try:
        # Placeholder implementation to avoid errors
        healthy_ingredients = [ing for ing in ingredients if ing.get('health_score', 5) >= 7]
        unhealthy_ingredients = [ing for ing in ingredients if ing.get('health_score', 5) <= 3]

        explanation = []
        if healthy_ingredients:
            explanation.append(f"Dit recept bevat {len(healthy_ingredients)} gezonde ingrediënten.")
        if unhealthy_ingredients:
            explanation.append(f"Dit recept bevat {len(unhealthy_ingredients)} minder gezonde ingrediënten.")
        return explanation
    except Exception as e:
        logger.error(f"Error getting health explanation: {e}")
        return ["Geen uitleg beschikbaar"]

def generate_health_score_explanation(health_score, total_nutrition, all_ingredients, health_goals_scores):
    """Generate explanation for how the health score was calculated"""
    try:
        # Prepare nutrition summary
        calories = total_nutrition.get('calories', 0)
        protein = total_nutrition.get('protein', 0)
        carbs = total_nutrition.get('carbs', 0)
        fat = total_nutrition.get('fat', 0)
        fiber = total_nutrition.get('fiber', 0)

        # Count healthy vs unhealthy ingredients
        healthy_ingredients = len([i for i in all_ingredients if i.get('health_score', 0) >= 7])
        total_ingredients = len(all_ingredients)

        # Get top health goal scores and translate keys to Dutch
        health_goals_translations = {
            "Algemene gezondheid": "Algemene gezondheid",
            "Hart- en vaatziekten": "Hart- en vaatziekten", 
            "Diabetes preventie": "Diabetes preventie",
            "Gewichtsbeheersing": "Gewichtsbeheersing",
            "Spijsvertering": "Spijsvertering",
            "Immuunsysteem": "Immuunsysteem",
            "Botgezondheid": "Botgezondheid",
            "Energieniveau": "Energieniveau",
            "Huidgezondheid": "Huidgezondheid",
            "Hersengezondheid": "Hersengezondheid",
            "weight_loss": "Gewichtsverlies",
            "muscle_gain": "Spieropbouw",
            "heart_health": "Hartgezondheid",
            "energy_boost": "Energie boost"
        }
        
        top_goals = sorted(health_goals_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        translated_goals = []
        for goal_key, score in top_goals:
            translated_name = health_goals_translations.get(goal_key, goal_key)
            translated_goals.append((translated_name, score))

        explanation = f"""De gezondheidsscore van {health_score}/10 is berekend op basis van een uitgebreide analyse van alle ingrediënten en hun voedingswaarden. 

Per portie bevat dit recept ongeveer {calories} calorieën, {protein}g eiwitten, {carbs}g koolhydraten, {fat}g vetten en {fiber}g vezels. Van de {total_ingredients} ingrediënten werden er {healthy_ingredients} als gezond beoordeeld (score 7+/10). 

De dagelijkse hoeveelheid voedingsstoffen werd vergeleken met aanbevolen dagelijkse waarden, waarbij rekening werd gehouden met de hoeveelheid vezels (goed voor spijsvertering), het type vetten (verzadigd vs onverzadigd), en de aanwezigheid van vitamines en mineralen. 

De hoogste scores werden behaald voor {translated_goals[0][0]} ({translated_goals[0][1]}/10), {translated_goals[1][0]} ({translated_goals[1][1]}/10) en {translated_goals[2][0]} ({translated_goals[2][1]}/10). Deze score geeft een indicatie van hoe goed dit recept past binnen een gezond voedingspatroon."""

        return explanation.strip()

    except Exception as e:
        logger.error(f"Error generating health score explanation: {e}")
        return "Er kon geen uitleg gegenereerd worden voor de gezondheidsscore."
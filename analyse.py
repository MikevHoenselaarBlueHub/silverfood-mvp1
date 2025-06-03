"""
Silverfood Recipe Analysis Module
=================================

This module provides comprehensive recipe analysis functionality with adaptive ingredient detection,
health scoring, and nutrition calculation. It supports all major recipe websites through intelligent
pattern recognition and Selenium fallback for dynamic content.

Features:
    - Universal recipe website support through adaptive pattern detection
    - Intelligent ingredient extraction with fuzzy matching
    - Health scoring based on nutrition data and predefined scores
    - Nutrition calculation using OpenFoodFacts API
    - Website pattern learning and caching
    - Chrome extension compatibility
    - Rate limiting and error handling

Dependencies:
    - requests: HTTP requests for web scraping
    - beautifulsoup4: HTML parsing
    - selenium: Dynamic content scraping
    - rapidfuzz: Fuzzy string matching
    - json: Configuration and data handling

Author: Silverfood Team
Version: 3.1.0
License: MIT
"""

import json
import re
import time
import os
import random
import logging
import shutil
from typing import Dict, List, Tuple, Optional, Any, Union
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz

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
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium not available - fallback to requests only")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Website patterns cache
WEBSITE_PATTERNS_FILE = "website_patterns.json"
try:
    with open(WEBSITE_PATTERNS_FILE, encoding="utf-8") as f:
        WEBSITE_PATTERNS = json.load(f)
    logger.info(f"Loaded {len(WEBSITE_PATTERNS)} website patterns")
except FileNotFoundError:
    WEBSITE_PATTERNS = {}
    logger.info("No existing website patterns found, starting fresh")

# Health scores database for common ingredients
HEALTH_SCORES = {
    # Vegetables (7-9)
    'ui': 7, 'uien': 7, 'tomaat': 8, 'tomaten': 8, 'paprika': 8,
    'courgette': 8, 'wortel': 9, 'aardappel': 6, 'spinazie': 9,
    'sla': 8, 'rucola': 8, 'andijvie': 8, 'broccoli': 9,
    'bloemkool': 8, 'prei': 7, 'asperges': 9, 'doperwten': 8,

    # Herbs and spices (8-9)
    'knoflook': 8, 'peterselie': 9, 'basilicum': 9, 'oregano': 8,
    'tijm': 8, 'rozemarijn': 8, 'munt': 8, 'dille': 8,

    # Grains and starches (4-6)
    'rijst': 5, 'pasta': 4, 'couscous': 5, 'quinoa': 7,
    'haver': 6, 'bloem': 3, 'brood': 4,

    # Proteins (5-8)
    'vlees': 5, 'kip': 6, 'vis': 8, 'zalm': 8, 'tonijn': 7,
    'ei': 6, 'eieren': 6, 'bonen': 7, 'linzen': 8,

    # Dairy (3-5)
    'melk': 5, 'room': 3, 'boter': 2, 'kaas': 4, 'yoghurt': 6,
    'feta': 4, 'ricotta': 5, 'burrata': 4,

    # Fruits (7-8)
    'appel': 8, 'banaan': 7, 'citroen': 8, 'limoen': 8,
    'nectarine': 8, 'perzik': 8, 'aardbei': 8,

    # Fats and oils (2-7)
    'olie': 3, 'olijfolie': 7, 'extra vierge olijfolie': 7,
    'zonnebloemolie': 3, 'boter': 2, 'margarine': 2,

    # Condiments and seasonings (1-6)
    'suiker': 1, 'zout': 2, 'peper': 6, 'azijn': 6,
    'wittewijnazijn': 6, 'balsamico': 5,

    # Nuts and seeds (6-8)
    'noten': 7, 'amandelen': 8, 'walnoten': 8, 'pijnboompitten': 7,
    'zonnebloempitten': 7, 'sesamzaad': 7
}


def get_domain(url: str) -> str:
    """
    Extract domain from URL for pattern matching.

    Args:
        url (str): The URL to extract domain from

    Returns:
        str: Clean domain name without www prefix

    Example:
        >>> get_domain("https://www.example.com/recipe")
        'example.com'
    """
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc.replace('www.', '')
        logger.debug(f"Extracted domain: {domain} from {url}")
        return domain
    except Exception as e:
        logger.error(f"Failed to extract domain from {url}: {e}")
        return ""


def get_random_user_agent() -> str:
    """
    Get a random user agent string to avoid detection.

    Returns:
        str: Random user agent string

    Note:
        Rotates between common browser user agents to appear more human-like
    """
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
    ]
    selected_agent = random.choice(user_agents)
    logger.debug(f"Selected user agent: {selected_agent[:50]}...")
    return selected_agent


def setup_selenium_driver() -> Optional[webdriver.Chrome]:
    """
    Setup Selenium Chrome driver with anti-detection options.

    Returns:
        Optional[webdriver.Chrome]: Configured Chrome driver or None if setup fails

    Note:
        Optimized for Replit/Nix environment with comprehensive anti-detection measures
    """
    if not SELENIUM_AVAILABLE:
        logger.error("Selenium not available")
        return None

    try:
        chrome_options = Options()

        # Replit/container optimizations
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--no-first-run')

        # Anti-detection measures
        chrome_options.add_argument(f'--user-agent={get_random_user_agent()}')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Find Chrome binary
        chrome_binary = shutil.which('chromium') or shutil.which('chrome') or shutil.which('google-chrome')
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info(f"Chrome binary found at: {chrome_binary}")
        else:
            logger.warning("Chrome binary not found in PATH")

        # Find ChromeDriver
        chromedriver_path = shutil.which('chromedriver')

        if chromedriver_path:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info(f"ChromeDriver found at: {chromedriver_path}")
        else:
            driver = webdriver.Chrome(options=chrome_options)
            logger.info("Using default ChromeDriver")

        # Additional anti-detection
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": get_random_user_agent()
        })

        logger.info("Selenium driver setup successful")
        return driver

    except Exception as e:
        logger.error(f"Failed to setup Selenium driver: {e}")
        return None


def save_website_patterns() -> None:
    """
    Save learned website patterns to file for future use.

    Note:
        Patterns are automatically learned and saved when successful selectors are found
    """
    try:
        with open(WEBSITE_PATTERNS_FILE, 'w', encoding="utf-8") as f:
            json.dump(WEBSITE_PATTERNS, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved {len(WEBSITE_PATTERNS)} website patterns")
    except Exception as e:
        logger.error(f"Failed to save website patterns: {e}")


def clean_ingredient_text(text: str) -> Optional[str]:
    """
    Clean and normalize ingredient text by removing quantities and formatting.

    Args:
        text (str): Raw ingredient text from webpage

    Returns:
        Optional[str]: Cleaned ingredient name or None if invalid

    Example:
        >>> clean_ingredient_text("200 gram tomaten, in blokjes")
        'tomaten'
    """
    if not text:
        return None

    # Handle encoding issues
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8', errors='ignore')
        except:
            try:
                text = text.decode('latin-1', errors='ignore')
            except:
                return None

    # Remove non-printable characters
    text = ''.join(char for char in text if char.isprintable() or char.isspace())

    # Filter out garbled text
    if any(ord(char) > 1000 for char in text):
        return None

    # Check for control characters
    if any(ord(char) < 32 and char not in '\t\n\r' for char in text):
        return None

    # Check for reasonable text composition
    if len(text) > 0:
        alpha_ratio = sum(c.isalpha() or c.isspace() or c in ',-().' for c in text) / len(text)
        if alpha_ratio < 0.5:
            return None

    # More aggressive cleaning for duplicates
    original_text = text
    
    # Remove leading quantities and measurements with better pattern
    text = re.sub(r'^[gG]\s*\d+\s*[gG]ram\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^[eE][lL]\s*\d+\s*[eE]etlepels?\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^[tT]een\s*\d+\s*[tT]een\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\d+\s*[.,]?\s*', '', text)
    text = re.sub(r'^\d+\s*(gram|g|ml|eetlepel|el|theelepel|tl|stuks?|teen|liter|l|kopje|blik)\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^[\W\d\s]*', '', text)

    # Remove trailing quantities in parentheses
    text = re.sub(r'\s*\(\d+.*?\)$', '', text)

    # Remove common descriptors
    text = re.sub(r',?\s*(fijngehakt|grof gehakt|in blokjes|gesneden|geraspt).*$', '', text, flags=re.IGNORECASE)

    text = text.strip()

    # Minimum length check
    if len(text) < 3:
        return None

    logger.debug(f"Cleaned ingredient: '{original_text}' -> '{text}'")
    return text


def is_likely_ingredient(text: str) -> bool:
    """
    Determine if text is likely an ingredient based on content analysis.

    Args:
        text (str): Text to analyze

    Returns:
        bool: True if text appears to be an ingredient

    Note:
        Uses multiple heuristics including quantity indicators, common ingredients,
        and exclusion patterns
    """
    if not text or len(text) < 3 or len(text) > 100:
        return False

    text_lower = text.lower()

    # Skip obvious non-ingredients
    skip_words = [
        'recept', 'stap', 'bereiding', 'instructie', 'minuten', 'uur',
        'serveren', 'bakken', 'koken', 'snijden', 'mixen', 'roeren',
        'toevoegen', 'verhitten', 'laten', 'bereidingstijd', 'porties',
        'moeilijkheid', 'voorbereiding', 'ingrediënten', 'benodigdheden',
        'tips', 'variaties', 'reviews', 'rating', 'sterren'
    ]

    if any(skip in text_lower for skip in skip_words):
        return False

    # Check for quantity indicators
    quantity_indicators = [
        'gram', 'g ', 'ml', 'liter', 'l ', 'eetlepel', 'el', 'theelepel', 'tl',
        'stuks', 'stuk', 'teen', 'teentje', 'kopje', 'blik', 'pak', 'zakje'
    ]
    has_quantity = any(indicator in text_lower for indicator in quantity_indicators)

    # Check for common ingredients
    common_ingredients = list(HEALTH_SCORES.keys())
    has_common_ingredient = any(ingredient in text_lower for ingredient in common_ingredients)

    # Check digit ratio
    digit_ratio = sum(c.isdigit() for c in text) / len(text) if text else 0

    # Check for HTML/URL content
    has_html = '<' in text or 'http' in text

    result = (has_quantity or has_common_ingredient) and digit_ratio < 0.3 and not has_html
    logger.debug(f"Ingredient check for '{text[:30]}...': {result}")
    return result


def selenium_scrape_ingredients(url: str) -> Tuple[List[str], str]:
    """
    Scrape ingredients using Selenium for dynamic content.

    Args:
        url (str): URL to scrape

    Returns:
        Tuple[List[str], str]: (ingredients list, page title)

    Note:
        Used as fallback when requests-based scraping fails
    """
    if not SELENIUM_AVAILABLE:
        logger.warning("Selenium not available for dynamic scraping")
        return [], ""

    driver = None
    try:
        driver = setup_selenium_driver()
        if not driver:
            return [], ""

        logger.info(f"Using Selenium for {url}")

        # Load page with timeout
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)

        try:
            driver.get(url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            logger.warning("Page load timeout, continuing anyway")

        # Wait for dynamic content
        time.sleep(3)

        # Get page data
        html = driver.page_source
        title = driver.title or "Recept"

        soup = BeautifulSoup(html, 'html.parser')
        domain = get_domain(url)
        ingredients = []

        # Try multiple selector strategies
        selectors = [
            # Domain specific
            '.recipe-ingredients-ingredient-list_name__YX7Rl',
            '[data-testhook="ingredients"] td:last-child p',
            '.ingredient-line', '.ingredients-list li',
            # Generic
            '[class*="ingredient"]', '.ingredient', '.ingredients li',
            'ul li', 'ol li', 'table td'
        ]

        for selector in selectors:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(strip=True)
                    if text and is_likely_ingredient(text):
                        clean_text = clean_ingredient_text(text)
                        if clean_text and clean_text not in ingredients:
                            ingredients.append(clean_text)

                if len(ingredients) >= 5:
                    logger.info(f"Selenium success with selector: {selector}")
                    break
            except Exception:
                continue

        return ingredients[:20], title

    except Exception as e:
        logger.error(f"Selenium scraping failed: {e}")
        return [], ""
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def extract_ingredients_from_soup(soup: BeautifulSoup, domain: str) -> List[str]:
    """
    Extract ingredients from BeautifulSoup object using known patterns.

    Args:
        soup (BeautifulSoup): Parsed HTML content
        domain (str): Website domain for pattern matching

    Returns:
        List[str]: List of found ingredients

    Note:
        Uses cached patterns first, falls back to generic selectors
    """
    ingredients = []

    # Try known patterns first
    if domain in WEBSITE_PATTERNS:
        pattern = WEBSITE_PATTERNS[domain]
        for selector in pattern.get('ingredient_selectors', []):
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if is_likely_ingredient(text):
                    clean_text = clean_ingredient_text(text)
                    if clean_text and clean_text not in ingredients:
                        ingredients.append(clean_text)
        logger.info(f"Used cached pattern for {domain}: {len(ingredients)} ingredients")

    # Generic selectors fallback
    if not ingredients:
        generic_selectors = [
            '.ingredient', '.ingredients li', '.recipe-ingredients li',
            '[class*="ingredient"]', '[data-ingredient]', '.recipe-ingredient',
            'ul.ingredients li', 'ol.ingredients li', '.ingredient-list li'
        ]

        for selector in generic_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if is_likely_ingredient(text):
                    clean_text = clean_ingredient_text(text)
                    if clean_text and clean_text not in ingredients:
                        ingredients.append(clean_text)

            if ingredients:
                # Save successful pattern
                if domain not in WEBSITE_PATTERNS:
                    WEBSITE_PATTERNS[domain] = {
                        'ingredient_selectors': [selector],
                        'auto_detected': True,
                        'success_count': 1
                    }
                    save_website_patterns()
                    logger.info(f"Learned new pattern for {domain}: {selector}")
                break

    return ingredients[:20]


def smart_ingredient_scraping(url: str) -> Tuple[List[str], str]:
    """
    Intelligent ingredient scraping with multiple fallback strategies.

    Args:
        url (str): URL to scrape ingredients from

    Returns:
        Tuple[List[str], str]: (ingredients list, page title)

    Raises:
        Exception: When no ingredients can be found after all attempts

    Note:
        Primary function for ingredient extraction, tries requests first,
        then Selenium, then pattern matching as fallbacks
    """
    session = requests.Session()
    domain = get_domain(url)
    ingredients = []
    title = "Recept"

    # Multiple header strategies for anti-detection
    headers_options = [
        {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        },
        {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Referer': 'https://www.google.com/'
        }
    ]

    # Try requests-based scraping first
    for attempt, headers in enumerate(headers_options):
        try:
            logger.info(f"Requests attempt {attempt + 1} for {url}")

            session.headers.update(headers)
            time.sleep(random.uniform(1, 3))

            response = session.get(url, timeout=30, allow_redirects=True)

            # Handle blocked responses
            if response.status_code == 403:
                logger.warning("403 Forbidden - website blocking access")
                continue
            elif response.status_code == 429:
                logger.warning("429 Rate limited - waiting")
                time.sleep(10)
                continue

            response.raise_for_status()

            if len(response.content) < 100:
                logger.warning(f"Response too short: {len(response.content)} bytes")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            for title_selector in ['h1', 'title', '.recipe-title', '[class*="title"]']:
                title_elem = soup.select_one(title_selector)
                if title_elem and title_elem.get_text(strip=True):
                    title = title_elem.get_text(strip=True)
                    break

            # Extract ingredients
            ingredients = extract_ingredients_from_soup(soup, domain)

            if len(ingredients) >= 3:
                logger.info(f"Requests successful: {len(ingredients)} ingredients found")
                break

        except requests.RequestException as e:
            logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
            time.sleep(5)
            continue
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            continue

    # Selenium fallback
    if len(ingredients) < 3:
        logger.info("Requests failed, trying Selenium...")
        selenium_ingredients, selenium_title = selenium_scrape_ingredients(url)
        if selenium_ingredients and len(selenium_ingredients) >= 3:
            ingredients = selenium_ingredients
            if selenium_title:
                title = selenium_title
            logger.info(f"Selenium successful: {len(ingredients)} ingredients found")

    # Final validation
    if len(ingredients) < 3:
        domain = get_domain(url)
        if domain in ['ah.nl', 'jumbo.com']:
            raise Exception(f"Deze website ({domain}) blokkeert automatische toegang. Probeer de ingrediënten handmatig te kopiëren.")
        else:
            raise Exception(f"Kon geen ingrediënten detecteren op {domain}. Website gebruikt mogelijk anti-bot bescherming.")

    logger.info(f"Scraping complete: {len(ingredients)} ingredients from {domain}")
    return ingredients, title


def get_nutrition_data(ingredient_name: str) -> Optional[Dict[str, Union[int, float]]]:
    """
    Fetch nutrition data from OpenFoodFacts API.

    Args:
        ingredient_name (str): Name of ingredient to look up

    Returns:
        Optional[Dict[str, Union[int, float]]]: Nutrition data or None if not found

    Note:
        Returns comprehensive nutrition information per 100g including
        calories, macronutrients, minerals, and NOVA processing group
    """
    try:
        search_url = "https://world.openfoodfacts.org/cgi/search.pl"
        params = {
            'search_terms': ingredient_name,
            'search_simple': 1,
            'action': 'process',
            'json': 1,
            'page_size': 1
        }

        response = requests.get(search_url, params=params, timeout=10)
        data = response.json()

        if data.get('products') and len(data['products']) > 0:
            product = data['products'][0]
            nutriments = product.get('nutriments', {})

            nutrition_data = {
                'calories': nutriments.get('energy-kcal_100g', 0),
                'fat': nutriments.get('fat_100g', 0),
                'saturated_fat': nutriments.get('saturated-fat_100g', 0),
                'sugar': nutriments.get('sugars_100g', 0),
                'fiber': nutriments.get('fiber_100g', 0),
                'protein': nutriments.get('proteins_100g', 0),
                'salt': nutriments.get('salt_100g', 0),
                'sodium': nutriments.get('sodium_100g', 0),
                'carbohydrates': nutriments.get('carbohydrates_100g', 0),
                'nova_group': product.get('nova_group', 1),
                'potassium': nutriments.get('potassium_100g', 0),
                'calcium': nutriments.get('calcium_100g', 0),
                'iron': nutriments.get('iron_100g', 0),
                'vitamin_c': nutriments.get('vitamin-c_100g', 0)
            }

            logger.debug(f"Retrieved nutrition data for {ingredient_name}")
            return nutrition_data

    except Exception as e:
        logger.warning(f"Failed to get nutrition data for {ingredient_name}: {e}")

    return None


def calculate_health_score_from_nutrition(nutrition_data: Dict[str, Union[int, float]]) -> int:
    """
    Calculate health score based on nutrition data.

    Args:
        nutrition_data (Dict[str, Union[int, float]]): Nutrition information

    Returns:
        int: Health score from 1-10 (higher is healthier)

    Note:
        Algorithm considers calories, fats, sugars, fiber, protein,
        salt content, and food processing level (NOVA group)
    """
    if not nutrition_data:
        return 5

    score = 10  # Start with perfect score

    # Penalty for high calories
    if nutrition_data['calories'] > 300:
        score -= 1
    elif nutrition_data['calories'] > 500:
        score -= 2

    # Penalty for high saturated fat
    if nutrition_data['saturated_fat'] > 5:
        score -= 1
    elif nutrition_data['saturated_fat'] > 10:
        score -= 2

    # Penalty for high sugar
    if nutrition_data['sugar'] > 10:
        score -= 1
    elif nutrition_data['sugar'] > 20:
        score -= 2

    # Penalty for high salt
    if nutrition_data['salt'] > 1:
        score -= 1
    elif nutrition_data['salt'] > 2:
        score -= 2

    # Bonus for high fiber
    if nutrition_data['fiber'] > 3:
        score += 1

    # Bonus for high protein
    if nutrition_data['protein'] > 10:
        score += 1

    # NOVA group penalty (higher = more processed)
    nova_penalty = {1: 0, 2: -1, 3: -2, 4: -3}
    score += nova_penalty.get(nutrition_data['nova_group'], -1)

    final_score = max(1, min(10, score))
    logger.debug(f"Calculated health score: {final_score} from nutrition data")
    return final_score


def get_health_score(ingredient_name: str) -> int:
    """
    Get health score for an ingredient using multiple sources.

    Args:
        ingredient_name (str): Name of ingredient

    Returns:
        int: Health score from 1-10 (higher is healthier)

    Note:
        Tries local database first, then fuzzy matching, then API lookup,
        finally falls back to default score
    """
    ingredient_lower = ingredient_name.lower()

    # Direct lookup in local database
    for key, score in HEALTH_SCORES.items():
        if key in ingredient_lower:
            logger.debug(f"Direct match for {ingredient_name}: {score}")
            return score

    # Fuzzy matching
    match = process.extractOne(
        ingredient_lower, 
        HEALTH_SCORES.keys(), 
        scorer=fuzz.WRatio, 
        score_cutoff=70
    )
    if match:
        score = HEALTH_SCORES[match[0]]
        logger.debug(f"Fuzzy match for {ingredient_name}: {score} (matched: {match[0]})")
        return score

    # API lookup
    nutrition_data = get_nutrition_data(ingredient_name)
    if nutrition_data:
        api_score = calculate_health_score_from_nutrition(nutrition_data)
        logger.info(f"API score for {ingredient_name}: {api_score}")
        return api_score

    # Default score
    default_score = CONFIG.get("health_scoring", {}).get("default_unknown_score", 5)
    logger.debug(f"Default score for {ingredient_name}: {default_score}")
    return default_score


def parse_quantity(line: str) -> Tuple[Optional[float], Optional[str], str]:
    """
    Parse quantity, unit, and ingredient name from ingredient line.

    Args:
        line (str): Raw ingredient line from recipe

    Returns:
        Tuple[Optional[float], Optional[str], str]: (amount, unit, ingredient_name)

    Example:
        >>> parse_quantity("200 gram tomaten, in blokjes")
        (200.0, 'gram', 'tomaten')
    """
    patterns = [
        r"(\d+(?:[.,]\d+)?(?:\s*[-/]\s*\d+(?:[.,]\d+)?)?)\s*(gram|g|ml|milliliter|liter|l|eetlepels?|el|theelepels?|tl|kopjes?|stuks?|st|teen|teentjes?|blik|blikken|pak|pakken|zakje|zakjes)\s+(.*)",
        r"(\d+(?:[.,]\d+)?(?:\s*[-/]\s*\d+(?:[.,]\d+)?)?)\s+(.*?)\s*\(([^)]+)\)",
        r"(\d+(?:[.,]\d+)?)\s+(.*)",
        r"(een\s+(?:half|halve|kwart|hele)?)\s+(.*)",
        r"(½|¼|¾|⅓|⅔|⅛)\s+(.*)",
    ]

    line_lower = line.lower().strip()

    for pattern in patterns:
        m = re.match(pattern, line_lower)
        if m:
            amount_str = m.group(1)

            # Handle special cases
            if 'een half' in amount_str or 'halve' in amount_str:
                amount = 0.5
                unit = 'stuks'
                name = m.group(2) if len(m.groups()) >= 2 else ''
            elif '½' in amount_str:
                amount = 0.5
                unit = 'stuks'
                name = m.group(2) if len(m.groups()) >= 2 else ''
            else:
                try:
                    amount_clean = amount_str.replace(',', '.')
                    if '-' in amount_clean or '/' in amount_clean:
                        nums = re.findall(r'\d+(?:\.\d+)?', amount_clean)
                        if len(nums) >= 2:
                            amount = (float(nums[0]) + float(nums[1])) / 2
                        else:
                            amount = float(nums[0]) if nums else 1
                    else:
                        amount = float(amount_clean)
                except:
                    amount = 1

                if len(m.groups()) >= 3:
                    unit = m.group(2)
                    name = m.group(3).strip()
                elif len(m.groups()) >= 2:
                    if pattern == patterns[1]:
                        name = m.group(2).strip()
                        unit = m.group(3) if len(m.groups()) >= 3 else 'stuks'
                    else:
                        unit = 'stuks'
                        name = m.group(2).strip()
                else:
                    unit = 'stuks'
                    name = line_lower.strip()

            # Normalize units
            unit_mapping = {
                'g': 'gram', 'ml': 'milliliter', 'l': 'liter',
                'el': 'eetlepel', 'eetlepels': 'eetlepel',
                'tl': 'theelepel', 'theelepels': 'theelepel',
                'st': 'stuks', 'stuks': 'stuks', 'stuk': 'stuks',
                'teen': 'teentje', 'teentjes': 'teentje'
            }

            unit = unit_mapping.get(unit, unit)

            logger.debug(f"Parsed quantity: {amount} {unit} {name}")
            return amount, unit, name

    # No pattern matched
    return None, None, line.lower().strip()


def find_substitution(ingredient_name: str) -> Optional[str]:
    """
    Find healthier substitution for ingredient.

    Args:
        ingredient_name (str): Name of ingredient to substitute

    Returns:
        Optional[str]: Suggested substitution or None if none found

    Note:
        Uses fuzzy matching against substitutions database
    """
    match = process.extractOne(
        ingredient_name.lower(), 
        SUBSTITUTIONS.keys(), 
        scorer=fuzz.WRatio, 
        score_cutoff=85
    )

    if match:
        substitution = SUBSTITUTIONS[match[0]]
        logger.debug(f"Found substitution for {ingredient_name}: {substitution}")
        return substitution

    return None


def get_ingredient_health_facts(ingredient_name: str) -> str:
    """
    Get health facts and benefits for an ingredient.

    Args:
        ingredient_name (str): Name of ingredient

    Returns:
        str: Health fact or benefit description

    Note:
        Provides educational information about ingredient health benefits
    """
    health_facts = {
        'tomaat': "Tomaten zijn rijk aan lycopeen, een krachtige antioxidant die cellen beschermt tegen schade en het risico op hartziekten en kanker kan verlagen.",
        'ui': "Uien bevatten quercetine, een flavonoïde die ontstekingen in het lichaam vermindert en het immuunsysteem versterkt.",
        'knoflook': "Knoflook bevat allicine dat helpt bij het verlagen van bloeddruk en cholesterol, en heeft antibacteriële eigenschappen die infecties bestrijden.",
        'spinazie': "Spinazie is rijk aan ijzer (voor zuurstoftransport), foliumzuur (voor celgroei) en vitamine K (voor sterke botten en bloedstolling).",
        'wortel': "Wortelen bevatten bètacaroteen dat in het lichaam wordt omgezet in vitamine A, essentieel voor goed zicht en een sterk immuunsysteem.",
        'paprika': "Paprika's bevatten meer vitamine C dan sinaasappels - belangrijk voor weerstand, collageen productie en ijzeropname.",
        'courgette': "Courgettes zijn laag in calorieën en rijk aan kalium dat de bloeddruk reguleert en spieren en zenuwen ondersteunt.",
        'broccoli': "Broccoli bevat sulforafaan dat de lever helpt bij het ontgiften en mogelijk beschermt tegen kanker door DNA-schade te voorkomen.",
        'avocado': "Avocado's bevatten gezonde enkelvoudig onverzadigde vetten die 'slecht' cholesterol verlagen en hart- en bloedvaten beschermen.",
        'noten': "Noten zijn rijk aan omega-3 vetzuren die ontstekingen verminderen, het hart beschermen en de hersenfunctie ondersteunen.",
        'vis': "Vette vis bevat omega-3 vetzuren (EPA en DHA) die cruciaal zijn voor hersenontwikkeling, geheugen en het verminderen van ontstekingen.",
        'yoghurt': "Yoghurt bevat probiotica (goede bacteriën) die de darmgezondheid bevorderen, de weerstand versterken en voedingsstoffen beter opnemen.",
        'peterselie': "Peterselie is rijk aan vitamine K (voor botgezondheid), vitamine C (voor weerstand) en foliumzuur (voor celgroei en hersensfunctie).",
        'asperges': "Asperges bevatten foliumzuur dat essentieel is voor DNA-synthese en rode bloedcelvorming, plus vezels voor een gezonde spijsvertering.",
        'nectarine': "Nectarines bevatten vitamine C voor weerstand, vezels voor spijsvertering en antioxidanten die cellen beschermen tegen veroudering.",
        'olijfolie': "Extra vierge olijfolie bevat gezonde enkelvoudig onverzadigde vetten en antioxidanten die het hart beschermen en ontstekingen verminderen."
    }

    ingredient_lower = ingredient_name.lower()
    for key, fact in health_facts.items():
        if key in ingredient_lower:
            return fact

    # Enhanced category-based fallbacks with explanations
    if any(veg in ingredient_lower for veg in ['sla', 'andijvie', 'rucola']):
        return "Groene bladgroenten zijn rijk aan foliumzuur (voor celgroei en DNA-productie) en ijzer (voor zuurstoftransport in het bloed), essentieel voor energie en vitaliteit."
    elif any(fruit in ingredient_lower for fruit in ['appel', 'peer', 'aardbei', 'banaan']):
        return "Fruit bevat natuurlijke suikers voor energie, vezels die cholesterol verlagen en de darmgezondheid bevorderen, plus antioxidanten die cellen beschermen."
    elif 'vlees' in ingredient_lower:
        return "Vlees levert hoogwaardige eiwitten met alle essentiële aminozuren voor spieropbouw en herstel, plus vitamine B12 voor zenuwfunctie."
    elif any(herb in ingredient_lower for herb in ['basilicum', 'tijm', 'oregano', 'rozemarijn']):
        return "Verse kruiden bevatten meer antioxidanten dan veel groenten en hebben ontstekingsremmende eigenschappen die het immuunsysteem versterken."

    return None


def calculate_total_nutrition(all_ingredients: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate total nutrition values for the entire recipe.

    Args:
        all_ingredients (List[Dict[str, Any]]): List of ingredient data with nutrition

    Returns:
        Dict[str, float]: Total nutrition values per recipe

    Note:
        Estimates portion sizes based on quantities when available,
        uses conservative defaults otherwise
    """
    total = {
        'calories': 0, 'protein': 0, 'carbohydrates': 0, 'fiber': 0,
        'sugar': 0, 'fat': 0, 'saturated_fat': 0, 'sodium': 0,
        'potassium': 0, 'calcium': 0, 'iron': 0, 'vitamin_c': 0
    }

    for ingredient in all_ingredients:
        nutrition = ingredient.get('nutrition')
        if nutrition:
            # Estimate portion factor
            portion_factor = 1.0
            if ingredient.get('amount'):
                if ingredient.get('unit') in ['gram', 'g']:
                    portion_factor = ingredient['amount'] / 100
                elif ingredient.get('unit') in ['eetlepel', 'el']:
                    portion_factor = ingredient['amount'] * 15 / 100
                elif ingredient.get('unit') in ['theelepel', 'tl']:
                    portion_factor = ingredient['amount'] * 5 / 100
                else:
                    portion_factor = 0.5
            else:
                portion_factor = 0.3

            for key in total.keys():
                if nutrition.get(key):
                    total[key] += nutrition[key] * portion_factor

    # Round for readability
    for key in total.keys():
        total[key] = round(total[key], 1)

    logger.debug(f"Calculated total nutrition: {total}")
    return total


def calculate_health_goals_scores(total_nutrition: Dict[str, float]) -> Dict[str, int]:
    """
    Calculate health scores for specific health goals.

    Args:
        total_nutrition (Dict[str, float]): Total nutrition values

    Returns:
        Dict[str, int]: Health scores for different goals (1-10)

    Note:
        Evaluates recipe suitability for weight loss, muscle building,
        energy boost, blood pressure control, and general health
    """
    if not total_nutrition:
        return {}

    scores = {}

    # Weight loss (low calories, high fiber, low sugar)
    weight_loss_score = 10
    if total_nutrition['calories'] > 400:
        weight_loss_score -= 3
    elif total_nutrition['calories'] > 600:
        weight_loss_score -= 5

    if total_nutrition['sugar'] > 15:
        weight_loss_score -= 2
    elif total_nutrition['sugar'] > 25:
        weight_loss_score -= 4

    if total_nutrition['fiber'] > 8:
        weight_loss_score += 1

    scores['weight_loss'] = max(1, min(10, weight_loss_score))

    # Muscle building (high protein, moderate calories)
    muscle_score = 5
    if total_nutrition['protein'] > 20:
        muscle_score += 3
    elif total_nutrition['protein'] > 35:
        muscle_score += 5

    if 300 < total_nutrition['calories'] < 600:
        muscle_score += 2

    scores['muscle_building'] = max(1, min(10, muscle_score))

    # Energy boost (complex carbs, low sugar)
    energy_score = 6
    if total_nutrition['carbohydrates'] > 40 and total_nutrition['sugar'] < 20:
        energy_score += 2

    if total_nutrition['iron'] > 5:
        energy_score += 1

    if total_nutrition['fiber'] > 5:
        energy_score += 1

    scores['energy_boost'] = max(1, min(10, energy_score))

    # Blood pressure (low sodium, high potassium)
    blood_pressure_score = 8
    if total_nutrition['sodium'] > 500:
        blood_pressure_score -= 3
    elif total_nutrition['sodium'] > 800:
        blood_pressure_score -= 5

    if total_nutrition['potassium'] > 500:
        blood_pressure_score += 1

    if total_nutrition['fiber'] > 8:
        blood_pressure_score += 1

    scores['blood_pressure'] = max(1, min(10, blood_pressure_score))

    # General health (balanced)
    general_health_score = 6
    if total_nutrition['fiber'] > 6:
        general_health_score += 1
    if total_nutrition['protein'] > 15:
        general_health_score += 1
    if total_nutrition['sugar'] < 15:
        general_health_score += 1
    if total_nutrition['sodium'] < 400:
        general_health_score += 1

    scores['general_health'] = max(1, min(10, general_health_score))

    logger.debug(f"Health goals scores: {scores}")
    return scores


def calculate_health_explanation(ingredients_with_scores: List[Dict[str, Any]]) -> List[str]:
    """
    Generate explanations for health scores and recommendations.

    Args:
        ingredients_with_scores (List[Dict[str, Any]]): Ingredients with health scores

    Returns:
        List[str]: List of explanation strings with emojis

    Note:
        Provides user-friendly explanations of why a recipe scored
        the way it did and what could be improved
    """
    explanations = []
    high_scoring = [ing for ing in ingredients_with_scores if ing['health_score'] >= 7]
    medium_scoring = [ing for ing in ingredients_with_scores if 4 <= ing['health_score'] < 7]
    low_scoring = [ing for ing in ingredients_with_scores if ing['health_score'] < 4]

    if high_scoring:
        names = ', '.join([ing['name'] for ing in high_scoring])
        explanations.append(f"✅ Gezonde ingrediënten (score 7-10): {names}")

    if medium_scoring:
        names = ', '.join([ing['name'] for ing in medium_scoring])
        explanations.append(f"⚠️ Neutrale ingrediënten (score 4-6): {names}")

    if low_scoring:
        names = ', '.join([ing['name'] for ing in low_scoring])
        explanations.append(f"❌ Minder gezonde ingrediënten (score 1-3): {names}")

    # Additional insights
    total_ingredients = len(ingredients_with_scores)
    processed_count = sum(1 for ing in ingredients_with_scores if ing['health_score'] <= 4)
    natural_count = sum(1 for ing in ingredients_with_scores if ing['health_score'] >= 7)

    if processed_count > total_ingredients * 0.5:
        explanations.append("🔍 Dit recept bevat veel bewerkte ingrediënten. Overweeg verse alternatieven.")

    if natural_count > total_ingredients * 0.6:
        explanations.append("🌱 Excellent! Dit recept is rijk aan natuurlijke, onbewerkte ingrediënten.")

    return explanations


def analyse(url: str) -> Dict[str, Any]:
    """
    Main analysis function for recipe health assessment.

    Args:
        url (str): URL of recipe webpage to analyze

    Returns:
        Dict[str, Any]: Complete analysis results including ingredients,
                       health scores, nutrition data, and recommendations

    Raises:
        Exception: When analysis fails due to scraping issues or invalid data

    Note:
        Primary entry point for recipe analysis. Orchestrates scraping,
        processing, scoring, and data compilation
    """
    try:
        logger.info(f"Starting analysis for {url}")

        # Extract ingredients from webpage
        ingredients_list, recipe_title = smart_ingredient_scraping(url)

        if not ingredients_list or len(ingredients_list) < 3:
            raise Exception("Geen voldoende ingrediënten gevonden")

        # Process each ingredient
        all_ingredients = []
        swaps = []
        seen_ingredients = set()  # Track to prevent duplicates

        for line in ingredients_list:
            if not line or len(line.strip()) < 2:
                continue

            amount, unit, name = parse_quantity(line)

            if len(name.strip()) < 2:
                continue

            # Normalize name for duplicate checking
            normalized_name = name.lower().strip()
            
            # Skip if we've already seen this ingredient
            if normalized_name in seen_ingredients:
                logger.debug(f"Skipping duplicate ingredient: {name}")
                continue
            
            seen_ingredients.add(normalized_name)

            # Get health data
            health_score = get_health_score(name)
            nutrition_data = get_nutrition_data(name)
            substitution = find_substitution(name)
            health_fact = get_ingredient_health_facts(name)

            ingredient_data = {
                "original_line": line,
                "name": name.title(),
                "amount": amount,
                "unit": unit,
                "health_score": health_score,
                "nutrition": nutrition_data,
                "substitution": substitution,
                "has_healthier_alternative": bool(substitution),
                "health_fact": health_fact
            }

            all_ingredients.append(ingredient_data)

            # Track substitutions
            if substitution:
                swaps.append({
                    "ongezond_ingredient": name.title(),
                    "vervang_door": substitution,
                    "health_score": health_score
                })

        if not all_ingredients:
            raise Exception("Geen bruikbare ingrediënten gevonden na processing")

        # Sort ingredients by health score and substitution availability
        all_ingredients.sort(
            key=lambda x: (-x['health_score'], -int(x['has_healthier_alternative']))
        )

        # Calculate overall metrics
        total_health_score = sum(ing['health_score'] for ing in all_ingredients) / len(all_ingredients)
        health_explanation = calculate_health_explanation(all_ingredients)
        total_nutrition = calculate_total_nutrition(all_ingredients)
        health_goals_scores = calculate_health_goals_scores(total_nutrition)

        result = {
            "all_ingredients": all_ingredients,
            "swaps": swaps,
            "health_score": round(total_health_score, 1),
            "health_explanation": health_explanation,
            "recipe_title": recipe_title,
            "total_nutrition": total_nutrition,
            "health_goals_scores": health_goals_scores
        }

        logger.info(f"Analysis complete: {len(all_ingredients)} ingredients, score: {total_health_score:.1f}")
        return result

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise


if __name__ == "__main__":
    """
    Command line interface for testing recipe analysis.

    Usage:
        python analyse.py <recipe_url>
    """
    import sys
    import pprint

    if len(sys.argv) != 2:
        print("Usage: python analyse.py <recipe_url>")
        sys.exit(1)

    try:
        result = analyse(sys.argv[1])
        pprint.pprint(result)
    except Exception as e:
        print(f"Analysis failed: {e}")
        sys.exit(1)
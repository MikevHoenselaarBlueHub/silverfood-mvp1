import json, re, time, os, random
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config file
with open("config.json", encoding="utf-8") as f:
    CONFIG = json.load(f)

# Laad vervanglijst
with open("substitutions.json", encoding="utf-8") as f:
    SUBS = json.load(f)

# Website patterns cache
WEBSITE_PATTERNS_FILE = "website_patterns.json"

try:
    with open(WEBSITE_PATTERNS_FILE, encoding="utf-8") as f:
        WEBSITE_PATTERNS = json.load(f)
except FileNotFoundError:
    WEBSITE_PATTERNS = {}

# Health scores database
HEALTH_SCORES = {
    'ui': 7, 'uien': 7, 'tomaat': 8, 'tomaten': 8, 'paprika': 8,
    'courgette': 8, 'wortel': 9, 'aardappel': 6, 'rijst': 5,
    'pasta': 4, 'knoflook': 8, 'peterselie': 9, 'basilicum': 9,
    'olie': 3, 'boter': 2, 'kaas': 4, 'vlees': 5, 'kip': 6,
    'vis': 8, 'melk': 5, 'room': 3, 'ei': 6, 'eieren': 6,
    'bloem': 3, 'suiker': 1, 'azijn': 6, 'couscous': 5,
    'feta': 4, 'ricotta': 5, 'burrata': 4, 'asperges': 9,
    'nectarine': 8, 'doperwten': 8
}

def calculate_health_score_from_nutrition(nutrition_data):
    """Calculate health score from nutrition data"""
    score = 5  # Default
    
    # Adjust based on nutrition facts
    if 'fat_100g' in nutrition_data:
        fat = nutrition_data['fat_100g']
        if fat > 20:
            score -= 2
        elif fat < 5:
            score += 1
            
    if 'sugars_100g' in nutrition_data:
        sugar = nutrition_data['sugars_100g']
        if sugar > 15:
            score -= 2
        elif sugar < 5:
            score += 1
            
    if 'fiber_100g' in nutrition_data:
        fiber = nutrition_data['fiber_100g']
        if fiber > 5:
            score += 2
            
    if 'salt_100g' in nutrition_data:
        salt = nutrition_data['salt_100g']
        if salt > 1.5:
            score -= 1
            
    nova_penalty = {4: -2, 3: -1, 2: 0, 1: 1}
    score += nova_penalty.get(nutrition_data.get('nova_group'), 0)

    return max(1, min(10, score))

def save_website_patterns():
    """Sla website patterns op naar bestand"""
    try:
        with open(WEBSITE_PATTERNS_FILE, 'w', encoding="utf-8") as f:
            json.dump(WEBSITE_PATTERNS, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save website patterns: {e}")



def get_domain(url: str) -> str:
    """Extract domain from URL"""
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc.replace('www.', '')
        return domain
    except:
        return ""

def get_random_user_agent():
    """Get random user agent to avoid detection"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
    ]
    return random.choice(user_agents)

def setup_selenium_driver():
    """Setup Selenium Chrome driver with options optimized for Replit"""
    try:
        chrome_options = Options()

        # Replit specific Chrome setup
        chrome_options.add_argument('--headless=new')  # Use new headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-features=TranslateUI')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        chrome_options.add_argument('--force-device-scale-factor=1')
        chrome_options.add_argument('--single-process')  # Better for containers
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument(f'--user-agent={get_random_user_agent()}')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Set Chrome binary location for Replit/Nix
        import shutil
        chrome_binary = shutil.which('chromium') or shutil.which('chrome') or shutil.which('google-chrome')
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info(f"Chrome binary found at: {chrome_binary}")
        else:
            logger.warning("Chrome binary not found in PATH")

        # Try to find ChromeDriver
        chromedriver_path = shutil.which('chromedriver')

        driver = None
        try:
            if chromedriver_path:
                from selenium.webdriver.chrome.service import Service
                service = Service(chromedriver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info(f"ChromeDriver found at: {chromedriver_path}")
            else:
                # Fallback: try without explicit service
                driver = webdriver.Chrome(options=chrome_options)
                logger.info("Using default ChromeDriver")

            # Anti-detection measures
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": get_random_user_agent()
            })

            return driver

        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            return None

    except Exception as e:
        logger.error(f"Failed to setup Selenium driver: {e}")
        return None

def selenium_scrape_ingredients(url: str):
    """Scrape ingredients using Selenium for dynamic content"""
    driver = None
    try:
        driver = setup_selenium_driver()
        if not driver:
            return [], ""

        logger.info(f"Using Selenium for {url}")

        # Set page load timeout


def save_website_patterns():
    """Save learned patterns to file"""
    try:
        with open(WEBSITE_PATTERNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(WEBSITE_PATTERNS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save patterns: {e}")

def get_driver():
    """Create a Chrome WebDriver instance"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument(f'--user-agent={get_random_user_agent()}')
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logger.error(f"Failed to create driver: {e}")
        return None

def analyse(url):
    """Main analysis function"""
    try:
        # Parse domain
        domain = urlparse(url).netloc.replace('www.', '')
        
        # Try to get page with requests first
        headers = {'User-Agent': get_random_user_agent()}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract ingredients using various methods
        ingredients = extract_ingredients_from_soup(soup, domain)
        
        if not ingredients:
            # Try with Selenium if requests failed
            driver = get_driver()
            if driver:
                try:
                    driver.get(url)
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    ingredients = extract_ingredients_from_soup(soup, domain)
                finally:
                    driver.quit()
        
        if not ingredients:
            raise Exception("Geen ingrediënten gevonden op deze pagina")
            
        # Calculate health scores
        ingredient_data = []
        for ingredient in ingredients:
            health_score = get_health_score(ingredient)
            ingredient_data.append({
                'name': ingredient,
                'health_score': health_score
            })
        
        return {
            'ingredients': ingredient_data,
            'total_ingredients': len(ingredient_data),
            'average_health_score': sum(i['health_score'] for i in ingredient_data) / len(ingredient_data) if ingredient_data else 0
        }
        
    except Exception as e:
        logger.error(f"Analysis failed for {url}: {e}")
        raise

def extract_ingredients_from_soup(soup, domain):
    """Extract ingredients from BeautifulSoup object"""
    ingredients = []
    
    # Try known patterns first
    if domain in WEBSITE_PATTERNS:
        pattern = WEBSITE_PATTERNS[domain]
        for selector in pattern.get('ingredient_selectors', []):
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if is_likely_ingredient(text):
                    ingredients.append(text)
    
    # If no known patterns or no results, try generic selectors
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
                    ingredients.append(text)
            if ingredients:
                # Save successful pattern
                if domain not in WEBSITE_PATTERNS:
                    WEBSITE_PATTERNS[domain] = {'ingredient_selectors': [selector], 'auto_detected': True, 'success_count': 1}
                    save_website_patterns()
                break
    
    return ingredients[:20]  # Limit to 20 ingredients

        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)

        driver.get(url)

        # Wait for page to load with better error handling
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            logger.warning("Page load timeout, trying to continue anyway")

        # Progressive wait for dynamic content
        for wait_time in [2, 3, 5]:
            time.sleep(wait_time)
            if driver.page_source and len(driver.page_source) > 1000:
                break

        # Get page source and title with error handling
        try:
            html = driver.page_source
            title = driver.title or "Recept"
        except Exception as e:
            logger.warning(f"Error getting page content: {e}")
            html = ""
            title = "Recept"

        soup = BeautifulSoup(html, 'html.parser')

        domain = get_domain(url)
        ingredients = []

        # Domain-specific selectors
        domain_selectors = {
            'ah.nl': [
                '.recipe-ingredients-ingredient-list_name__YX7Rl',
                '[data-testhook="ingredients"] td:last-child p',
                '[data-testhook="ingredients"] td',
                '.recipe-ingredients li'
            ],
            'jumbo.com': [
                '.ingredient-line',
                '.ingredients-list li',
                '.recipe-ingredient',
                '.jum-ingredient'
            ],
            'leukerecepten.nl': [
                '.recipe-ingredients li',
                '.ingredients li',
                '.ingredient-list li',
                '.recipe-content li'
            ]
        }

        # Generic selectors
        generic_selectors = [
            '[class*="ingredient"]',
            '[class*="recipe"] li',
            'ul li',
            'ol li',
            'table td',
            'table tr td:last-child',
            '.ingredient',
            '.ingredients li',
            '[data-ingredient]',
            '[itemtype*="ingredient"]',
            '[class*="item"] span',
            '.recipe-list li',
            '.step li'
        ]

        selectors_to_try = domain_selectors.get(domain, []) + generic_selectors

        for selector in selectors_to_try:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(strip=True)
                    if text and is_likely_ingredient(text):
                        clean_text = clean_ingredient_text(text)
                        if clean_text and clean_text not in ingredients:
                            ingredients.append(clean_text)

                if len(ingredients) >= 5:
                    logger.info(f"Selenium success with selector: {selector} - Found {len(ingredients)} ingredients")
                    break
            except Exception:
                continue

        return ingredients, title

    except Exception as e:
        logger.error(f"Selenium scraping failed: {e}")
        return [], ""
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as cleanup_error:
                logger.warning(f"Error during driver cleanup: {cleanup_error}")
                try:
                    # Force kill if normal quit fails
                    driver.close()
                except:
                    pass

def clean_ingredient_text(text):
    """Maak ingrediënt tekst schoon"""
    if not text:
        return None

    # Fix encoding issues - handle different encodings
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8', errors='ignore')
        except:
            try:
                text = text.decode('latin-1', errors='ignore')
            except:
                return None

    # Remove non-printable characters but keep basic punctuation
    text = ''.join(char for char in text if char.isprintable() or char.isspace())

    # Remove garbled text patterns - stricter check
    if any(ord(char) > 1000 for char in text):
        return None

    # Check for control characters or weird encoding artifacts
    if any(ord(char) < 32 and char not in '\t\n\r' for char in text):
        return None

    # Check for gibberish (too many non-alphabetic chars)
    if len(text) > 0:
        alpha_ratio = sum(c.isalpha() or c.isspace() or c in ',-().' for c in text) / len(text)
        if alpha_ratio < 0.5:
            return None

    # Filter out obvious garbage text patterns
    garbage_patterns = [
        r'[]+',  # Common encoding artifacts
        r'[\x00-\x1f\x7f-\x9f]+',  # Control characters
        r'^[^a-zA-Z]*$',  # No letters at all
        r'[^\w\s\-,().]+',  # Too many special chars
    ]

    for pattern in garbage_patterns:
        if re.search(pattern, text):
            return None

    # Verwijder leading nummers en hoeveelheden
    text = re.sub(r'^\d+\s*[.,]?\s*', '', text)
    text = re.sub(r'^\d+\s*(gram|g|ml|eetlepel|el|theelepel|tl|stuks?|teen|liter|l|kopje|blik)\s*', '', text)
    text = re.sub(r'^[\W\d\s]*', '', text)

    # Verwijder trailing hoeveelheden
    text = re.sub(r'\s*\(\d+.*?\)$', '', text)

    text = text.strip()

    # Minimale lengte check
    if len(text) < 3:
        return None

    return text

def is_likely_ingredient(text):
    """Check of een tekst waarschijnlijk een ingrediënt is"""
    if not text or len(text) < 3 or len(text) > 100:
        return False

    text_lower = text.lower()

    # Skip common non-ingredients
    skip_words = [
        'recept', 'stap', 'bereiding', 'instructie', 'minuten', 'uur',
        'serveren', 'bakken', 'koken', 'snijden', 'mixen', 'roeren',
        'toevoegen', 'verhitten', 'laten', 'zout', 'peper', 'smaak',
        'bereidingstijd', 'porties', 'moeilijkheid', 'voorbereiding',
        'ingrediënten', 'benodigdheden', 'tips', 'variaties', 'reviews'
    ]

    if any(skip in text_lower for skip in skip_words):
        return False

    # Bevat hoeveelheid indicatoren
    quantity_indicators = [
        'gram', 'g ', 'ml', 'liter', 'l ', 'eetlepel', 'el', 'theelepel', 'tl',
        'stuks', 'stuk', 'teen', 'teentje', 'kopje', 'blik', 'pak', 'zakje'
    ]

    has_quantity = any(indicator in text_lower for indicator in quantity_indicators)

    # Bevat vaak voorkomende ingrediënt woorden
    common_ingredients = [
        'ui', 'uien', 'tomaat', 'tomaten', 'paprika', 'courgette', 'wortel',
        'aardappel', 'rijst', 'pasta', 'knoflook', 'peterselie', 'basilicum',
        'olie', 'boter', 'zout', 'peper', 'kaas', 'vlees', 'kip', 'vis',
        'melk', 'room', 'ei', 'eieren', 'bloem', 'suiker', 'azijn', 'couscous',
        'feta', 'ricotta', 'burrata', 'asperges', 'nectarine', 'doperwten'
    ]

    has_common_ingredient = any(ingredient in text_lower for ingredient in common_ingredients)

    # Niet teveel cijfers
    digit_ratio = sum(c.isdigit() for c in text) / len(text)

    # Geen HTML/URL content
    has_html = '<' in text or 'http' in text

    return (has_quantity or has_common_ingredient) and digit_ratio < 0.3 and not has_html

def smart_ingredient_scraping(url: str):
    """Slimme ingrediënten scraping met Selenium fallback"""

    # First try requests/BeautifulSoup (faster)
    session = requests.Session()

    # Rotate through different headers to avoid detection
    headers_options = [
        {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        },
        {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Referer': 'https://www.google.com/',
            'Cache-Control': 'no-cache'
        }
    ]

    domain = get_domain(url)
    ingredients = []
    title = "Recept"

    # Try multiple approaches with requests first
    for attempt, headers in enumerate(headers_options):
        try:
            logger.info(f"Requests attempt {attempt + 1} for {url}")

            session.headers.update(headers)
            time.sleep(random.uniform(1, 3))  # Random delay

            response = session.get(url, timeout=30, allow_redirects=True)

            # Check for blocked/forbidden responses
            if response.status_code == 403:
                logger.warning(f"403 Forbidden - website blocking access")
                continue
            elif response.status_code == 429:
                logger.warning(f"429 Rate limited - waiting longer")
                time.sleep(10)
                continue

            response.raise_for_status()

            # Additional check for empty or invalid content
            if len(response.content) < 100:
                logger.warning(f"Response too short: {len(response.content)} bytes")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find title
            for title_selector in ['h1', 'title', '.recipe-title', '[class*="title"]', '[class*="recipe"]']:
                title_elem = soup.select_one(title_selector)
                if title_elem and title_elem.get_text(strip=True):
                    title = title_elem.get_text(strip=True)
                    break

            # Domain-specific selectors
            domain_selectors = {
                'ah.nl': [
                    '.recipe-ingredients-ingredient-list_name__YX7Rl',
                    '[data-testhook="ingredients"] td:last-child p',
                    '[data-testhook="ingredients"] td',
                    '.recipe-ingredients li'
                ],
                'jumbo.com': [
                    '.ingredient-line',
                    '.ingredients-list li',
                    '.recipe-ingredient',
                    '.jum-ingredient'
                ],
                'leukerecepten.nl': [
                    '.recipe-ingredients li',
                    '.ingredients li',
                    '.ingredient-list li',
                    '.recipe-content li'
                ]
            }

            # Generic selectors for all sites
            generic_selectors = [
                '[class*="ingredient"]',
                '[class*="recipe"] li',
                'ul li',
                'ol li',
                'table td',
                'table tr td:last-child',
                '.ingredient',
                '.ingredients li',
                '[data-ingredient]',
                '[itemtype*="ingredient"]',
                '[class*="item"] span',
                '.recipe-list li',
                '.step li'
            ]

            # Use domain-specific selectors first
            selectors_to_try = domain_selectors.get(domain, []) + generic_selectors

            for selector in selectors_to_try:
                try:
                    elements = soup.select(selector)

                    for elem in elements:
                        text = elem.get_text(strip=True)
                        if text and is_likely_ingredient(text):
                            clean_text = clean_ingredient_text(text)
                            if clean_text and clean_text not in ingredients:
                                ingredients.append(clean_text)

                    if len(ingredients) >= 5:
                        logger.info(f"Requests success with selector: {selector} - Found {len(ingredients)} ingredients")
                        break

                except Exception:
                    continue

            # If we found enough ingredients, break
            if len(ingredients) >= 3:
                logger.info(f"Requests successful scraping: {len(ingredients)} ingredients found")
                break

            # Fallback: analyze all text content for ingredient patterns
            if len(ingredients) < 3:
                logger.info("Trying requests fallback text analysis")
                all_text = soup.get_text()
                lines = all_text.split('\n')

                for line in lines:
                    line = line.strip()
                    if line and is_likely_ingredient(line):
                        clean_text = clean_ingredient_text(line)
                        if clean_text and clean_text not in ingredients:
                            ingredients.append(clean_text)

                if len(ingredients) >= 3:
                    break

        except requests.RequestException as e:
            logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
            time.sleep(5)  # Wait before retry
            continue
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            continue

    # If requests failed, try Selenium with retry logic
    if len(ingredients) < 3:
        logger.info("Requests failed, trying Selenium...")
        max_selenium_retries = 2

        for retry in range(max_selenium_retries):
            try:
                selenium_ingredients, selenium_title = selenium_scrape_ingredients(url)
                if selenium_ingredients and len(selenium_ingredients) >= 3:
                    ingredients = selenium_ingredients
                    if selenium_title:
                        title = selenium_title
                    logger.info(f"Selenium successful: {len(ingredients)} ingredients found")
                    break
                else:
                    logger.warning(f"Selenium attempt {retry + 1} failed to find sufficient ingredients")
                    if retry < max_selenium_retries - 1:
                        time.sleep(2)  # Wait before retry
            except Exception as e:
                logger.error(f"Selenium attempt {retry + 1} failed: {e}")
                if retry < max_selenium_retries - 1:
                    time.sleep(3)  # Wait before retry

    # Final fallback: try to extract from meta data or structured data
    if len(ingredients) < 3:
        logger.info("Trying final fallback: structured data extraction")
        try:
            # Last attempt with most basic text analysis
            fallback_ingredients = extract_ingredients_from_text(url)
            if fallback_ingredients and len(fallback_ingredients) >= 3:
                ingredients = fallback_ingredients
                logger.info(f"Fallback successful: {len(ingredients)} ingredients found")
            else:
                # If still nothing, provide helpful error with specific site info
                domain = get_domain(url)
                if domain in ['ah.nl', 'jumbo.com']:
                    raise Exception(f"Deze website ({domain}) blokkeert automatische toegang. Probeer de ingrediënten handmatig te kopiëren.")
                else:
                    raise Exception(f"Kon geen ingrediënten detecteren op {domain}. Dit kan zijn omdat de website een onbekende structuur gebruikt of toegang blokkeert.")
        except Exception as fallback_error:
            logger.error(f"All extraction methods failed: {fallback_error}")
            raise Exception(f"Kon geen ingrediënten vinden op {url}. Website gebruikt mogelijk anti-bot bescherming of onbekende structuur.")

    return ingredients, title

def extract_ingredients_from_text(url):
    """Last resort: basic text pattern matching for ingredients"""
    try:
        import requests
        response = requests.get(url, timeout=10, headers={'User-Agent': get_random_user_agent()})
        text = response.text.lower()

        # Look for common ingredient patterns in text
        ingredient_patterns = [
            r'(\d+\s*(?:gram|g|ml|eetlepel|el|theelepel|tl|kopje|blik|pak|zakje)\s+)([a-zA-Zàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ\s]{3,30})',
            r'(\d+\s*)([a-zA-Zàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ\s]{3,30})\s*(?:gram|g|ml|eetlepel|el|theelepel|tl|kopje|blik|pak|zakje)',
        ]

        found_ingredients = []
        for pattern in ingredient_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                ingredient = match[1].strip() if len(match) > 1 else match[0].strip()
                if ingredient and len(ingredient) > 2 and is_likely_ingredient(ingredient):
                    clean_ingredient = clean_ingredient_text(ingredient)
                    if clean_ingredient and clean_ingredient not in found_ingredients:
                        found_ingredients.append(clean_ingredient)

        return found_ingredients[:20]  # Limit to 20 ingredients
    except:
        return []

def get_nutrition_data(ingredient_name):
    """Haal voedingsdata op van OpenFoodFacts API"""
    try:
        # Search for product
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

            return {
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
    except Exception as e:
        logger.warning(f"Failed to get nutrition data for {ingredient_name}: {e}")

    return None

def get_ingredient_health_facts(ingredient_name):
    """Haal gezondheidsweetjes op voor een ingrediënt"""
    health_facts = {
        'tomaat': "Tomaten zijn rijk aan lycopeen, een krachtige antioxidant die het risico op hartziekten kan verlagen.",
        'ui': "Uien bevatten quercetine, een flavonoïde die ontstekingsremmende eigenschappen heeft.",
        'knoflook': "Knoflook kan helpen bij het verlagen van de bloeddruk en heeft antibacteriële eigenschappen.",
        'spinazie': "Spinazie is rijk aan ijzer, foliumzuur en vitamine K, belangrijk voor botgezondheid.",
        'wortel': "Wortelen bevatten bètacaroteen, dat wordt omgezet in vitamine A voor goede oogfunctie.",
        'paprika': "Paprika's zijn een uitstekende bron van vitamine C, zelfs meer dan citrusvruchten.",
        'courgette': "Courgettes zijn laag in calorieën en rijk aan kalium, goed voor een gezonde bloeddruk.",
        'broccoli': "Broccoli bevat sulforafaan, een stof die mogelijk beschermt tegen bepaalde vormen van kanker.",
        'avocado': "Avocado's bevatten gezonde enkelvoudig onverzadigde vetten die goed zijn voor het hart.",
        'noten': "Noten zijn rijk aan omega-3 vetzuren en kunnen helpen bij het verlagen van cholesterol.",
        'vis': "Vette vis bevat omega-3 vetzuren die belangrijk zijn voor de hersenfunctie.",
        'yoghurt': "Yoghurt bevat probiotica die bijdragen aan een gezonde darmflora.",
        'haver': "Haver bevat bètaglucaan, een vezel die helpt bij het verlagen van cholesterol.",
        'bonen': "Bonen zijn rijk aan plantaardige eiwitten en vezels, goed voor spijsvertering.",
        'quinoa': "Quinoa is een complete eiwitbron en bevat alle essentiële aminozuren."
    }
    
    ingredient_lower = ingredient_name.lower()
    for key, fact in health_facts.items():
        if key in ingredient_lower:
            return fact
    
    # Fallback algemene weetjes
    if 'groente' in ingredient_lower or any(veg in ingredient_lower for veg in ['sla', 'andijvie', 'rucola']):
        return "Groene bladgroenten zijn rijk aan foliumzuur en ijzer, essentieel voor energiemetabolisme."
    elif 'fruit' in ingredient_lower:
        return "Fruit bevat natuurlijke suikers, vezels en antioxidanten die bijdragen aan uw dagelijkse vitaminebehoefte."
    elif 'vlees' in ingredient_lower:
        return "Vlees is een goede bron van hoogwaardige eiwitten en vitamine B12."
    
    return "Dit ingrediënt draagt bij aan een gevarieerd en uitgebalanceerd voedingspatroon."

def calculate_health_score_from_nutrition(nutrition_data):
    """Bereken gezondheidsscore op basis van voedingswaarden"""
    if not nutrition_data:
        return 5

    score = 10  # Start with perfect score

    # Penalty for high calories (more than 300 kcal/100g)
    if nutrition_data['calories'] > 300:
        score -= 1
    elif nutrition_data['calories'] > 500:
        score -= 2

    # Penalty for high saturated fat (more than 5g/100g)
    if nutrition_data['saturated_fat'] > 5:
        score -= 1
    elif nutrition_data['saturated_fat'] > 10:
        score -= 2

    # Penalty for high sugar (more than 10g/100g)
    if nutrition_data['sugar'] > 10:
        score -= 1
    elif nutrition_data['sugar'] > 20:
        score -= 2

    # Penalty for high salt (more than 1g/100g)
    if nutrition_data['salt'] > 1:
        score -= 1
    elif nutrition_data['salt'] > 2:
        score -= 2

    # Bonus for high fiber (more than 3g/100g)
    if nutrition_data['fiber'] > 3:
        score += 1

    # Bonus for high protein (more than 10g/100g)
    if nutrition_data['protein'] > 10:
        score += 1

    # NOVA group penalty (higher = more processed)
    nova_penalty = {1: 0, 2: -1, 3: -2, 4: -3}
    score += nova_penalty.get(nutrition_data['nova_group'], -1)

    return max(1, min(10, score))

def get_health_score(ingredient_name):
    """Geef gezondheidsscore voor een ingrediënt"""
    ingredient_lower = ingredient_name.lower()

    # First try local HEALTH_SCORES for fast lookup
    for key, score in HEALTH_SCORES.items():
        if key in ingredient_lower:
            return score

    match = process.extractOne(ingredient_lower, HEALTH_SCORES.keys(), 
                             scorer=fuzz.WRatio, score_cutoff=70)
    if match:
        return HEALTH_SCORES[match[0]]

    # If not found locally, try OpenFoodFacts API
    nutrition_data = get_nutrition_data(ingredient_name)
    if nutrition_data:
        api_score = calculate_health_score_from_nutrition(nutrition_data)
        logger.info(f"Using API nutrition score for {ingredient_name}: {api_score}")
        return api_score
    
    # Default score if nothing found
    return CONFIG.get("health_scoring", {}).get("default_unknown_score", 5)

def calculate_health_goals_scores(total_nutrition):
    """Bereken scores voor verschillende gezondheidsdoelen"""
    if not total_nutrition:
        return {}
    
    scores = {}
    
    # Gewicht verliezen (focus op lage calorieën, hoge vezels, lage suikers)
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
    
    # Spiergroei/herstel (focus op hoge eiwitten, matige calorieën)
    muscle_score = 5
    if total_nutrition['protein'] > 20:
        muscle_score += 3
    elif total_nutrition['protein'] > 35:
        muscle_score += 5
    
    if total_nutrition['calories'] > 300 and total_nutrition['calories'] < 600:
        muscle_score += 2
    
    scores['muscle_building'] = max(1, min(10, muscle_score))
    
    # Meer energie (focus op complexe koolhydraten, B-vitamines)
    energy_score = 6
    if total_nutrition['carbohydrates'] > 40 and total_nutrition['sugar'] < 20:
        energy_score += 2
    
    if total_nutrition['iron'] > 5:
        energy_score += 1
    
    if total_nutrition['fiber'] > 5:
        energy_score += 1
    
    scores['energy_boost'] = max(1, min(10, energy_score))
    
    # Bloeddruk verlagen (focus op laag natrium, hoog kalium)
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
    
    # Algemene gezondheid (uitgebalanceerd)
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
    
    return scores

def calculate_total_nutrition(all_ingredients):
    """Bereken totale voedingswaarden van het recept"""
    total = {
        'calories': 0,
        'protein': 0,
        'carbohydrates': 0,
        'fiber': 0,
        'sugar': 0,
        'fat': 0,
        'saturated_fat': 0,
        'sodium': 0,
        'potassium': 0,
        'calcium': 0,
        'iron': 0,
        'vitamin_c': 0
    }
    
    ingredient_count = 0
    
    for ingredient in all_ingredients:
        nutrition = ingredient.get('nutrition')
        if nutrition:
            # Schat portiegrootte op basis van hoeveelheid (als beschikbaar)
            portion_factor = 1.0
            if ingredient.get('amount'):
                # Basis schatting: 100g per ingredient tenzij anders aangegeven
                if ingredient.get('unit') == 'gram' or ingredient.get('unit') == 'g':
                    portion_factor = ingredient['amount'] / 100
                elif ingredient.get('unit') in ['eetlepel', 'el']:
                    portion_factor = ingredient['amount'] * 15 / 100  # 15ml per eetlepel
                elif ingredient.get('unit') in ['theelepel', 'tl']:
                    portion_factor = ingredient['amount'] * 5 / 100   # 5ml per theelepel
                else:
                    portion_factor = 0.5  # Standaard kleinere portie voor stuks/andere eenheden
            else:
                portion_factor = 0.3  # Conservatieve schatting zonder hoeveelheid
            
            for key in total.keys():
                if nutrition.get(key):
                    total[key] += nutrition[key] * portion_factor
            
            ingredient_count += 1
    
    # Rond af tot hele getallen voor betere leesbaarheid
    for key in total.keys():
        total[key] = round(total[key], 1)
    
    return total

def calculate_health_explanation(ingredients_with_scores):
    """Bereken uitleg voor gezondheidsscore"""
    explanations = []
    high_scoring = [ing for ing in ingredients_with_scores if ing['health_score'] >= 7]
    medium_scoring = [ing for ing in ingredients_with_scores if 4 <= ing['health_score'] < 7]
    low_scoring = [ing for ing in ingredients_with_scores if ing['health_score'] < 4]

    if high_scoring:
        explanations.append(f"✅ Gezonde ingrediënten (score 7-10): {', '.join([ing['name'] for ing in high_scoring])}")

    if medium_scoring:
        explanations.append(f"⚠️ Neutrale ingrediënten (score 4-6): {', '.join([ing['name'] for ing in medium_scoring])}")

    if low_scoring:
        explanations.append(f"❌ Minder gezonde ingrediënten (score 1-3): {', '.join([ing['name'] for ing in low_scoring])}")

    # Add nutrition insights
    total_ingredients = len(ingredients_with_scores)
    processed_count = sum(1 for ing in ingredients_with_scores if ing['health_score'] <= 4)
    natural_count = sum(1 for ing in ingredients_with_scores if ing['health_score'] >= 7)

    if processed_count > total_ingredients * 0.5:
        explanations.append("🔍 Dit recept bevat veel bewerkte ingrediënten. Overweeg verse alternatieven.")

    if natural_count > total_ingredients * 0.6:
        explanations.append("🌱 Excellent! Dit recept is rijk aan natuurlijke, onbewerkte ingrediënten.")

    return explanations

def parse_qty(line: str):
    """Parse hoeveelheid uit ingrediënt regel - verbeterde versie"""
    # Uitgebreidere pattern matching voor verschillende formaten
    patterns = [
        r"(\d+(?:[.,]\d+)?(?:\s*[-/]\s*\d+(?:[.,]\d+)?)?)\s*(gram|g|ml|milliliter|liter|l|eetlepels?|el|theelepels?|tl|kopjes?|stuks?|st|teen|teentjes?|blik|blikken|pak|pakken|zakje|zakjes|snufje|snufjes|takje|takjes)\s+(.*)",
        r"(\d+(?:[.,]\d+)?(?:\s*[-/]\s*\d+(?:[.,]\d+)?)?)\s+(.*?)\s*\(([^)]+)\)",  # met eenheid tussen haakjes
        r"(\d+(?:[.,]\d+)?)\s+(.*)",  # alleen getal en ingrediënt
        r"(een\s+(?:half|halve|kwart|hele)?)\s+(.*)",  # 'een half', 'een hele' etc
        r"(½|¼|¾|⅓|⅔|⅛)\s+(.*)",  # breuken
    ]
    
    original_line = line
    line_lower = line.lower().strip()
    
    for pattern in patterns:
        m = re.match(pattern, line_lower)
        if m:
            amount_str = m.group(1)
            
            # Converteer speciale gevallen
            if 'een half' in amount_str or 'halve' in amount_str:
                amount = 0.5
                unit = 'stuks'
                name = m.group(2) if len(m.groups()) >= 2 else ''
            elif 'een kwart' in amount_str:
                amount = 0.25
                unit = 'stuks'
                name = m.group(2) if len(m.groups()) >= 2 else ''
            elif '½' in amount_str:
                amount = 0.5
                unit = 'stuks'
                name = m.group(2) if len(m.groups()) >= 2 else ''
            elif '¼' in amount_str:
                amount = 0.25
                unit = 'stuks'
                name = m.group(2) if len(m.groups()) >= 2 else ''
            elif '¾' in amount_str:
                amount = 0.75
                unit = 'stuks'
                name = m.group(2) if len(m.groups()) >= 2 else ''
            else:
                try:
                    # Vervang komma's door punten voor decimalen
                    amount_clean = amount_str.replace(',', '.')
                    # Handel ranges af (bijv. "2-3")
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
                
                # Bepaal unit en name op basis van pattern
                if len(m.groups()) >= 3:  # Pattern met unit
                    unit = m.group(2)
                    name = m.group(3).strip()
                elif len(m.groups()) >= 2:
                    if pattern == patterns[1]:  # Pattern met haakjes
                        name = m.group(2).strip()
                        unit = m.group(3) if len(m.groups()) >= 3 else 'stuks'
                    else:
                        unit = 'stuks'
                        name = m.group(2).strip()
                else:
                    unit = 'stuks'
                    name = line_lower.strip()
            
            # Normaliseer unit namen
            unit_mapping = {
                'g': 'gram', 'ml': 'milliliter', 'l': 'liter',
                'el': 'eetlepel', 'eetlepels': 'eetlepel',
                'tl': 'theelepel', 'theelepels': 'theelepel',
                'st': 'stuks', 'stuks': 'stuks', 'stuk': 'stuks',
                'teen': 'teentje', 'teentjes': 'teentje',
                'kopjes': 'kopje', 'blikken': 'blik', 'pakken': 'pak',
                'zakjes': 'zakje', 'snufjes': 'snufje', 'takjes': 'takje'
            }
            
            unit = unit_mapping.get(unit, unit)
            
            return amount, unit, name
    
    # Als geen pattern matcht, return original
    return None, None, line.lower().strip()

def find_substitution(name: str):
    """Zoek vervanging voor ingrediënt"""
    key = process.extractOne(name, SUBS.keys(), scorer=fuzz.WRatio, score_cutoff=85)
    return SUBS[key[0]] if key else None

def analyse(url: str):
    """Hoofdanalyse functie"""
    try:
        logger.info(f"Starting analysis for {url}")

        # Scrape ingredients
        ingredients_list, recipe_title = smart_ingredient_scraping(url)

        if not ingredients_list or len(ingredients_list) < 3:
            raise Exception("Geen voldoende ingrediënten gevonden")

        # Process ingredients
        all_ingredients = []
        swaps = []

        for line in ingredients_list:
            if not line or len(line.strip()) < 2:
                continue

            amount, unit, name = parse_qty(line)

            if len(name.strip()) < 2:
                continue

            health_score = get_health_score(name)
            nutrition_data = get_nutrition_data(name)
            alt = find_substitution(name)

            ingredient_data = {
                "original_line": line,
                "name": name.title(),
                "amount": amount,
                "unit": unit,
                "health_score": health_score,
                "nutrition": nutrition_data,
                "substitution": alt,
                "has_healthier_alternative": bool(alt),
                "health_fact": get_ingredient_health_facts(name)
            }

            all_ingredients.append(ingredient_data)

            if alt:
                swaps.append({
                    "ongezond_ingredient": name.title(), 
                    "vervang_door": alt,
                    "health_score": health_score
                })

        if not all_ingredients:
            raise Exception("Geen bruikbare ingrediënten gevonden na processing")

        all_ingredients.sort(key=lambda x: (-x['health_score'], -int(x['has_healthier_alternative'])))

        total_health_score = sum(ing['health_score'] for ing in all_ingredients) / len(all_ingredients)
        health_explanation = calculate_health_explanation(all_ingredients)
        
        # Bereken totale voedingswaarden en gezondheidsdoelen scores
        total_nutrition = calculate_total_nutrition(all_ingredients)
        health_goals_scores = calculate_health_goals_scores(total_nutrition)

        logger.info(f"Analysis complete: {len(all_ingredients)} ingredients, score: {total_health_score:.1f}")

        return {
            "all_ingredients": all_ingredients,
            "swaps": swaps,
            "health_score": round(total_health_score, 1),
            "health_explanation": health_explanation,
            "recipe_title": recipe_title,
            "total_nutrition": total_nutrition,
            "health_goals_scores": health_goals_scores
        }

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise

if __name__ == "__main__":
    import sys, pprint
    pprint.pp(analyse(sys.argv[1]))
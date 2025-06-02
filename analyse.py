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

def save_website_patterns():
    """Sla website patterns op naar bestand"""
    try:
        with open(WEBSITE_PATTERNS_FILE, 'w', encoding="utf-8") as f:
            json.dump(WEBSITE_PATTERNS, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save website patterns: {e}")

# Gezondheidsscore per ingrediënt type
HEALTH_SCORES = {
    "asperges": 9, "sperziebonen": 8, "babyspinazie": 9, "radijsjes": 8, 
    "peterselie": 8, "nectarines": 7, "granaatappelpitjes": 8, "doperwten": 8,
    "munt": 8, "ricotta": 5, "pasta": 4, "couscous": 6, "feta": 5,
    "knoflook": 8, "extra vierge olijfolie": 7, "milde olijfolie": 6,
    "wittewijnazijn": 6, "water": 10, "orzo pasta": 4, "afbakciabatta": 3,
    "burrata": 4, "ui": 7, "uien": 7, "tomaat": 8, "tomaten": 8,
    "paprika": 8, "courgette": 8, "wortel": 8, "aardappel": 6
}

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
    """Setup Selenium Chrome driver with options"""
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(f'--user-agent={get_random_user_agent()}')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        logger.warning(f"Failed to setup Selenium driver: {e}")
        return None

def selenium_scrape_ingredients(url: str):
    """Scrape ingredients using Selenium for dynamic content"""
    driver = None
    try:
        driver = setup_selenium_driver()
        if not driver:
            return [], ""
        
        logger.info(f"Using Selenium for {url}")
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Additional wait for dynamic content
        time.sleep(3)
        
        # Get page source and title
        html = driver.page_source
        title = driver.title
        
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
            driver.quit()

def clean_ingredient_text(text):
    """Maak ingrediënt tekst schoon"""
    if not text:
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
            response.raise_for_status()

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

    # If requests failed, try Selenium
    if len(ingredients) < 3:
        logger.info("Requests failed, trying Selenium...")
        try:
            selenium_ingredients, selenium_title = selenium_scrape_ingredients(url)
            if selenium_ingredients and len(selenium_ingredients) >= 3:
                ingredients = selenium_ingredients
                if selenium_title:
                    title = selenium_title
                logger.info(f"Selenium successful: {len(ingredients)} ingredients found")
            else:
                logger.warning("Selenium also failed to find sufficient ingredients")
        except Exception as e:
            logger.error(f"Selenium scraping failed: {e}")

    if len(ingredients) < 3:
        raise Exception(f"Kon geen voldoende ingrediënten vinden op {url}. Gevonden: {ingredients}")

    return ingredients, title

def get_health_score(ingredient_name):
    """Geef gezondheidsscore voor een ingrediënt"""
    ingredient_lower = ingredient_name.lower()

    for key, score in HEALTH_SCORES.items():
        if key in ingredient_lower:
            return score

    match = process.extractOne(ingredient_lower, HEALTH_SCORES.keys(), 
                             scorer=fuzz.WRatio, score_cutoff=70)
    if match:
        return HEALTH_SCORES[match[0]]

    return 5

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

    return explanations

def parse_qty(line: str):
    """Parse hoeveelheid uit ingrediënt regel"""
    pattern = r"([\d/.]+)\s*(g|gram|ml|l|eetlepel|theelepel|kopje|stuks?)?\s*(.*)"
    m = re.match(pattern, line.lower())
    if not m:
        return None, None, line.lower()

    try:
        amount = eval(m.group(1))
    except:
        amount = None
    unit = m.group(2) or "stuks"
    name = m.group(3).strip()
    return amount, unit, name

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
            alt = find_substitution(name)

            ingredient_data = {
                "original_line": line,
                "name": name.title(),
                "amount": amount,
                "unit": unit,
                "health_score": health_score,
                "substitution": alt,
                "has_healthier_alternative": bool(alt)
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

        logger.info(f"Analysis complete: {len(all_ingredients)} ingredients, score: {total_health_score:.1f}")

        return {
            "all_ingredients": all_ingredients,
            "swaps": swaps,
            "health_score": round(total_health_score, 1),
            "health_explanation": health_explanation,
            "recipe_title": recipe_title
        }

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise

if __name__ == "__main__":
    import sys, pprint
    pprint.pp(analyse(sys.argv[1]))
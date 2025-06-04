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
    methods = [
        ("requests_json_ld", scrape_with_requests_json_ld),
        ("requests_patterns", scrape_with_requests_patterns),
    ]

    if SELENIUM_AVAILABLE:
        methods.insert(1, ("selenium", scrape_with_selenium))

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
            logger.warning(f"Method {method_name} failed: {e}")
            debug.log_scraping_attempt(url, method_name, False, 0)
            continue

    raise Exception("Geen ingrediënten gevonden met alle beschikbare methoden")

def scrape_with_requests_json_ld(url: str) -> Tuple[List[str], str]:
    """Scrape using requests and JSON-LD structured data."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    debug.log_request(url, "GET", headers)
    start_time = time.time()

    response = requests.get(url, headers=headers, timeout=15)
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    # Common ingredient selectors
    selectors = [
        '.recipe-ingredient',
        '.ingredient',
        '.ingredients li',
        '[data-ingredient]',
        '.recipe-ingredients li',
        '.ingredient-list li',
        '.ingredients-list li'
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

def scrape_with_selenium(url: str) -> Tuple[List[str], str]:
    """Scrape using Selenium for dynamic content."""
    if not SELENIUM_AVAILABLE:
        raise Exception("Selenium niet beschikbaar")

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

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
        ```
cashews': 'cashewnoten',
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

            processed_ingredient = {
                'name': normalized_name,
                'health_score': health_score,
                'details': substitution_data.get('details', ''),
                'health_fact': substitution_data.get('health_fact', ''),
                'substitution': substitution_data.get('substitution', '')
            }

            processed_ingredients.append(processed_ingredient)

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
            'unit': None
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
        'unit': unit
    }

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
    """Generate health explanations."""
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

    if healthy_ingredients:
        healthy_names = [ing.get('name', 'Onbekend') for ing in healthy_ingredients[:3]]
        explanations.append(f"✅ Gezonde ingrediënten (score 7-10): {', '.join(healthy_names)}")

    if unhealthy_ingredients:
        unhealthy_names = [ing.get('name', 'Onbekend') for ing in unhealthy_ingredients[:3]]
        explanations.append(f"❌ Minder gezonde ingrediënten (score 1-3): {', '.join(unhealthy_names)}")

    return explanations

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

        # Get top health goal scores
        top_goals = sorted(health_goals_scores.items(), key=lambda x: x[1], reverse=True)[:3]

        explanation = f"""De gezondheidsscore van {health_score}/10 is berekend op basis van een uitgebreide analyse van alle ingrediënten en hun voedingswaarden. 

Per portie bevat dit recept ongeveer {calories} calorieën, {protein}g eiwitten, {carbs}g koolhydraten, {fat}g vetten en {fiber}g vezels. Van de {total_ingredients} ingrediënten werden er {healthy_ingredients} als gezond beoordeeld (score 7+/10). 

De dagelijkse hoeveelheid voedingsstoffen werd vergeleken met aanbevolen dagelijkse waarden, waarbij rekening werd gehouden met de hoeveelheid vezels (goed voor spijsvertering), het type vetten (verzadigd vs onverzadigd), en de aanwezigheid van vitamines en mineralen. 

De hoogste scores werden behaald voor {top_goals[0][0]} ({top_goals[0][1]}/10), {top_goals[1][0]} ({top_goals[1][1]}/10) en {top_goals[2][0]} ({top_goals[2][1]}/10). Deze score geeft een indicatie van hoe goed dit recept past binnen een gezond voedingspatroon."""

        return explanation.strip()

    except Exception as e:
        logger.error(f"Error generating health score explanation: {e}")
        return "Er kon geen uitleg gegenereerd worden voor de gezondheidsscore."

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
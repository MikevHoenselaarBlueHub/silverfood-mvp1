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
    """Extract ingredients from direct text input."""
    logger.info("Extracting ingredients from text")

    # Split text into lines and filter for potential ingredients
    lines = text.split('\n')
    ingredients = []

    # Patterns that suggest ingredient lines
    ingredient_patterns = [
        r'^\d+(?:\.\d+)?\s*(gram|g|kg|ml|l|el|tl|stuks?|blik|pak)',  # Amount + unit (with decimals)
        r'^\d+(?:\.\d+)?\s*[^\d\s]',  # Number followed by text (with decimals)
        r'^-\s*\d*\s*[^\d]',  # Dash lists
        r'^\*\s*\d*\s*[^\d]',  # Bullet lists
        r'^\d+\.\s*\d*\s*[^\d]',  # Numbered lists
        r'^\d+(?:\.\d+)?\s+\w+',  # Simple pattern: number + space + word
    ]

    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue

        # Check if line matches ingredient patterns
        is_ingredient = any(re.match(pattern, line, re.IGNORECASE) for pattern in ingredient_patterns)

        # Also include lines that contain common ingredient words
        ingredient_words = ['gram', 'g', 'kg', 'ml', 'l', 'liter', 'eetlepel', 'el', 'theelepel', 'tl', 'stuks', 'blik', 'pak', 'snufje', 'snufjes', 'takje', 'takjes']
        contains_ingredient_word = any(word in line.lower() for word in ingredient_words)

        if is_ingredient or contains_ingredient_word:
            ingredients.append(line)

    # If no pattern matches found, try to extract any meaningful lines
    if len(ingredients) < 3:
        for line in lines:
            line = line.strip()
            if len(line) > 5 and not line.startswith(('http', 'www')):
                ingredients.append(line)

    logger.info(f"Extracted {len(ingredients)} ingredients from text")
    return ingredients

def analyze_ingredient(ingredient_text: str) -> Dict[str, Any]:
    """Analyze a single ingredient for health scoring."""
    # Basic ingredient analysis
    clean_ingredient = re.sub(r'\d+\s*(gram|g|kg|ml|l|el|tl|stuks?|blik|pak)', '', ingredient_text).strip()
    clean_ingredient = re.sub(r'^[-*•]\s*', '', clean_ingredient).strip()

    # Simple health scoring based on keywords
    healthy_keywords = ['groente', 'fruit', 'volkoren', 'noten', 'vis', 'olijfolie', 'avocado']
    unhealthy_keywords = ['suiker', 'boter', 'room', 'spek', 'worst', 'gebak']

    health_score = 5  # Default neutral score

    ingredient_lower = clean_ingredient.lower()

    for keyword in healthy_keywords:
        if keyword in ingredient_lower:
            health_score = min(10, health_score + 2)
            break

    for keyword in unhealthy_keywords:
        if keyword in ingredient_lower:
            health_score = max(1, health_score - 2)
            break

    return {
        'name': clean_ingredient,
        'original_text': ingredient_text,
        'health_score': health_score,
        'category': 'unknown'
    }

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

    avg_score = sum(ing['health_score'] for ing in ingredients) / len(ingredients) if ingredients else 5

    if avg_score >= 7:
        explanations.append("🌱 Dit recept bevat voornamelijk gezonde ingrediënten!")
    elif avg_score >= 5:
        explanations.append("⚖️ Dit recept heeft een gemiddelde gezondheidscore.")
    else:
        explanations.append("⚠️ Dit recept bevat veel minder gezonde ingrediënten.")

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
                    'reason': 'Gezondere vetten'
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
    health_explanation = generate_health_explanation(all_ingredients, health_goals_scores)
    swaps = generate_healthier_swaps(all_ingredients)

    # Calculate overall health score
    health_score = sum(ing['health_score'] for ing in all_ingredients) / len(all_ingredients) if all_ingredients else 5

    result = {
        "success": True,
        "recipe_title": recipe_title,
        "source": "url" if url_or_text.startswith(('http://', 'https://')) else "text",
        "all_ingredients": all_ingredients,
        "total_nutrition": total_nutrition,
        "health_goals_scores": health_goals_scores,
        "health_explanation": health_explanation,
        "swaps": swaps,
        "ingredient_count": len(all_ingredients),
        "health_score": round(health_score, 1)
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
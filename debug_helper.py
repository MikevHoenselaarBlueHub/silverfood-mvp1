import logging
import json
import time
from typing import Dict, Any, List
import requests
from urllib.parse import urlparse
import os
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_ah_scraping(url: str):
    """Debug AH website scraping step by step"""
    logger.info(f"=== DEBUG AH SCRAPING START for {url} ===")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        session = requests.Session()
        session.headers.update(headers)
        
        logger.info("Step 1: Making request...")
        response = session.get(url, timeout=20, allow_redirects=True)
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        logger.info(f"Final URL after redirects: {response.url}")
        
        if response.status_code != 200:
            logger.error(f"Bad status code: {response.status_code}")
            return None
            
        logger.info("Step 2: Parsing HTML...")
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Save full HTML for debugging
        with open("debug/ah_debug.html", "w", encoding="utf-8") as f:
            f.write(str(soup.prettify()))
        logger.info("HTML saved to debug/ah_debug.html")
        
        logger.info("Step 3: Looking for JSON-LD...")
        json_scripts = soup.find_all('script', type='application/ld+json')
        logger.info(f"Found {len(json_scripts)} JSON-LD scripts")
        
        for i, script in enumerate(json_scripts):
            try:
                data = json.loads(script.string)
                logger.info(f"JSON-LD {i}: {json.dumps(data, indent=2)[:500]}...")
                with open(f"debug/ah_json_ld_{i}.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except:
                logger.warning(f"Could not parse JSON-LD {i}")
        
        logger.info("Step 4: Looking for ingredient selectors...")
        selectors_to_try = [
            '[data-testid="ingredient"]',
            '.ingredient',
            '.recipe-ingredient', 
            '.ingredients li',
            '[data-ingredient]',
            '.ingredient-item',
            '.recipe-ingredients-list li',
            'ul[data-testid="ingredients"] li',
            '.ingredients-section li',
            # More AH specific selectors
            '.recipe-ingredients .ingredient',
            '[data-qa="ingredient"]',
            '.ah-ingredient',
            '.allerhande-ingredient',
            '.ingredient-list-item'
        ]
        
        for selector in selectors_to_try:
            elements = soup.select(selector)
            logger.info(f"Selector '{selector}': {len(elements)} elements")
            if elements:
                for j, elem in enumerate(elements[:5]):  # Show first 5
                    logger.info(f"  Element {j}: {elem.get_text().strip()[:100]}")
        
        logger.info("Step 5: Looking for all text that might be ingredients...")
        # Look for patterns that might be ingredients
        all_text = soup.get_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        
        potential_ingredients = []
        for line in lines:
            # Look for lines that might be ingredients (contain measurements, food words)
            if any(word in line.lower() for word in ['gram', 'kg', 'ml', 'liter', 'el', 'tl', 'snuf', 'stuk']):
                potential_ingredients.append(line)
        
        logger.info(f"Found {len(potential_ingredients)} potential ingredient lines:")
        for ing in potential_ingredients[:10]:  # Show first 10
            logger.info(f"  Potential: {ing}")
            
        with open("debug/ah_potential_ingredients.txt", "w", encoding="utf-8") as f:
            f.write('\n'.join(potential_ingredients))
        
        return potential_ingredients
        
    except Exception as e:
        logger.error(f"Debug failed: {e}")
        return None

def log_request(url: str, method: str = "GET"):
    """Log API request"""
    logger.info(f"API Request: {method} {url}")

def log_scraping_attempt(url: str, method: str, success: bool, ingredient_count: int = 0):
    """Log scraping attempt results"""
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"Scraping {status}: {method} on {url} - {ingredient_count} ingredients")

def log_selenium_action(action: str, details: str):
    """Log Selenium actions"""
    logger.info(f"Selenium {action}: {details}")

def save_debug_html(html_content: str, url: str, method: str):
    """Save HTML content for debugging"""
    try:
        os.makedirs("debug", exist_ok=True)
        filename = f"debug/{method}_{int(time.time())}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Debug HTML saved: {filename}")
    except Exception as e:
        logger.error(f"Could not save debug HTML: {e}")

class DebugHelper:
    """
    Helper class for debugging recipe scraping and analysis.
    """

    def __init__(self, enable_debug: bool = True):
        """
        Initialize debug helper.

        Args:
            enable_debug (bool): Whether to enable detailed debugging
        """
        self.enable_debug = enable_debug
        self.logger = logging.getLogger(__name__)

        # Create debug directory if it doesn't exist
        if enable_debug:
            os.makedirs('debug', exist_ok=True)

    def log_request(self, url: str, method: str = "GET", headers: Dict[str, str] = None):
        """
        Log HTTP request details.

        Args:
            url (str): The URL being requested
            method (str): HTTP method (GET, POST, etc.)
            headers (Dict[str, str]): Request headers
        """
        self.logger.debug(f"REQUEST: {method} {url}")
        if headers and self.enable_debug:
            self.logger.debug(f"Headers: {json.dumps(headers, indent=2)}")

    def log_response(self, response, timing: float = None):
        """
        Log HTTP response details.

        Args:
            response: HTTP response object
            timing (float): Response time in seconds
        """
        if hasattr(response, 'status_code'):
            timing_str = f" ({timing:.2f}s)" if timing else " (N/A)"
            self.logger.debug(f"RESPONSE: {response.status_code}{timing_str}")
            self.logger.debug(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            if self.enable_debug:
                self.logger.debug(f"Response size: {len(response.content)} bytes")

    def log_selenium_action(self, action: str, details: str = ""):
        """
        Log Selenium actions for debugging browser automation.

        Args:
            action (str): The action being performed
            details (str): Additional details about the action
        """
        self.logger.debug(f"SELENIUM: {action} - {details}")

    def log_scraping_attempt(self, url: str, method: str, success: bool, ingredients_found: int = 0):
        """
        Log scraping attempts with results.

        Args:
            url (str): URL being scraped
            method (str): Scraping method used
            success (bool): Whether scraping was successful
            ingredients_found (int): Number of ingredients found
        """
        status = "SUCCESS" if success else "FAILED"
        domain = urlparse(url).netloc
        self.logger.info(f"SCRAPING {status}: {method} on {domain} - {ingredients_found} ingredients")

    def save_debug_html(self, html: str, url: str, method: str):
        """
        Save HTML content for debugging purposes.

        Args:
            html (str): HTML content to save
            url (str): Source URL
            method (str): Scraping method used
        """
        if not self.enable_debug:
            return

        try:
            domain = urlparse(url).netloc.replace('www.', '')
            timestamp = int(time.time())
            filename = f"debug_html_{domain}_{method}_{timestamp}.html"

            os.makedirs('debug', exist_ok=True)
            with open(f"debug/{filename}", 'w', encoding='utf-8') as f:
                f.write(html)

            self.logger.debug(f"Debug HTML saved: {filename}")
        except Exception as e:
            self.logger.warning(f"Failed to save debug HTML: {e}")

    def test_url_accessibility(self, url: str) -> Dict[str, Any]:
        """
        Test if URL is accessible and return detailed information.

        Args:
            url (str): URL to test

        Returns:
            Dict[str, Any]: Accessibility test results
        """
        result = {
            "url": url,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "accessible": False,
            "status_code": None,
            "content_type": None,
            "response_time": None,
            "error": None
        }

        try:
            import requests
            start_time = time.time()

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response_time = time.time() - start_time

            result.update({
                "accessible": True,
                "status_code": response.status_code,
                "content_type": response.headers.get('content-type', 'unknown'),
                "response_time": round(response_time, 2),
                "content_length": len(response.content)
            })

        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"URL accessibility test failed for {url}: {e}")

        return result

    def analyze_page_structure(self, html: str, url: str) -> Dict[str, Any]:
        """
        Analyze page structure for debugging ingredient detection.

        Args:
            html (str): HTML content to analyze
            url (str): Source URL

        Returns:
            Dict[str, Any]: Page structure analysis
        """
        soup = BeautifulSoup(html, 'html.parser')

        analysis = {
            "url": url,
            "title": soup.title.string if soup.title else "No title",
            "total_elements": len(soup.find_all()),
            "lists": len(soup.find_all(['ul', 'ol'])),
            "tables": len(soup.find_all('table')),
            "potential_ingredient_containers": [],
            "class_patterns": set(),
            "id_patterns": set()
        }

        # Find potential ingredient containers
        ingredient_keywords = ['ingredient', 'recipe', 'list', 'item']
        for element in soup.find_all():
            if element.get('class'):
                classes = ' '.join(element.get('class'))
                analysis["class_patterns"].add(classes)
                if any(keyword in classes.lower() for keyword in ingredient_keywords):
                    analysis["potential_ingredient_containers"].append({
                        "tag": element.name,
                        "class": classes,
                        "text_preview": element.get_text()[:100]
                    })

            if element.get('id'):
                analysis["id_patterns"].add(element.get('id'))

        analysis["class_patterns"] = list(analysis["class_patterns"])[:20]  # Limit output
        analysis["id_patterns"] = list(analysis["id_patterns"])[:20]

        self.logger.debug(f"Page Analysis: {json.dumps(analysis, indent=2, ensure_ascii=False)}")
        return analysis

    def create_debug_report(self, url: str, analysis_result: Dict) -> str:
        """
        Create comprehensive debug report for analysis results.

        Args:
            url (str): Analyzed URL
            analysis_result (Dict): Analysis results

        Returns:
            str: Formatted debug report
        """
        report = f"""
# Debug Report for {url}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Analysis Results
- Success: {analysis_result.get('success', False)}
- Ingredients Found: {len(analysis_result.get('all_ingredients', []))}
- Health Score: {analysis_result.get('health_score', 'N/A')}

## Ingredients Detected
"""
        for i, ingredient in enumerate(analysis_result.get('all_ingredients', [])[:10]):
            report += f"{i+1}. {ingredient.get('name', 'Unknown')} (Score: {ingredient.get('health_score', 'N/A')})\n"

        return report

def init_debug_folder():
    """Initialize debug folder if it doesn't exist."""
    os.makedirs('debug', exist_ok=True)

# Global debug instance
debug = DebugHelper(enable_debug=True)

# Auto-initialize debug folder
init_debug_folder()
import json
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DebugHelper:
    def __init__(self):
        self.debug_enabled = True
        
    def log_scraping_attempt(self, url: str, method: str, success: bool, ingredient_count: int):
        """Log scraping attempt"""
        if self.debug_enabled:
            logger.info(f"Scraping attempt: {method} on {url} - Success: {success}, Ingredients: {ingredient_count}")
    
    def log_request(self, url: str, method: str, headers: Dict[str, str]):
        """Log HTTP request"""
        if self.debug_enabled:
            logger.debug(f"HTTP {method} request to {url}")
    
    def log_response(self, response, duration: float):
        """Log HTTP response"""
        if self.debug_enabled:
            logger.debug(f"HTTP response {response.status_code} in {duration:.2f}s")
    
    def save_debug_html(self, html_content: str, url: str, method: str):
        """Save debug HTML for analysis"""
        if self.debug_enabled:
            try:
                import os
                from urllib.parse import urlparse
                
                # Create debug directory if it doesn't exist
                os.makedirs("debug", exist_ok=True)
                
                # Create filename
                domain = urlparse(url).netloc.replace("www.", "")
                timestamp = int(time.time())
                filename = f"debug/debug_html_{domain}_{method}_{timestamp}.html"
                
                # Save HTML content
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                    
                logger.debug(f"Saved debug HTML to {filename}")
            except Exception as e:
                logger.error(f"Failed to save debug HTML: {e}")
    
    def log_selenium_action(self, action: str, details: str):
        """Log Selenium action"""
        if self.debug_enabled:
            logger.debug(f"Selenium {action}: {details}")

# Create global debug instance
debug = DebugHelper()

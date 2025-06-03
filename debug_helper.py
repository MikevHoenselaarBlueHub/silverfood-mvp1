
import logging
import json
import time
from typing import Dict, Any, List
import requests
from urllib.parse import urlparse
import os

class DebugHelper:
    """Enhanced debugging helper for development and troubleshooting"""
    
    def __init__(self, enable_debug=True):
        self.enable_debug = enable_debug
        self.debug_data = {}
        self.setup_logging()
    
    def setup_logging(self):
        """Setup enhanced logging"""
        log_format = '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        logging.basicConfig(
            level=logging.DEBUG if self.enable_debug else logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('debug.log', encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log_request(self, url: str, method: str = "GET", headers: Dict = None):
        """Log HTTP requests with detailed info"""
        self.logger.debug(f"REQUEST: {method} {url}")
        if headers and self.enable_debug:
            self.logger.debug(f"Headers: {json.dumps(headers, indent=2)}")
    
    def log_response(self, response, timing: float = None):
        """Log HTTP response details"""
        if hasattr(response, 'status_code'):
            self.logger.debug(f"RESPONSE: {response.status_code} ({timing:.2f}s)" if timing else f"RESPONSE: {response.status_code} (N/A)")
            self.logger.debug(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            if self.enable_debug:
                self.logger.debug(f"Response size: {len(response.content)} bytes")
    
    def log_selenium_action(self, action: str, details: str = ""):
        """Log Selenium actions"""
        self.logger.debug(f"SELENIUM: {action} - {details}")
    
    def log_scraping_attempt(self, url: str, method: str, success: bool, ingredients_found: int = 0):
        """Log scraping attempts with results"""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"SCRAPING {status}: {method} on {urlparse(url).netloc} - {ingredients_found} ingredients")
    
    def save_debug_html(self, html: str, url: str, method: str):
        """Save HTML for debugging purposes"""
        if not self.enable_debug:
            return
            
        try:
            domain = urlparse(url).netloc.replace('www.', '')
            timestamp = int(time.time())
            filename = f"debug_html_{domain}_{method}_{timestamp}.html"
            
            with open(f"debug/{filename}", 'w', encoding='utf-8') as f:
                f.write(html)
            
            self.logger.debug(f"Debug HTML saved: {filename}")
        except Exception as e:
            self.logger.warning(f"Failed to save debug HTML: {e}")
    
    def test_url_accessibility(self, url: str) -> Dict[str, Any]:
        """Test if URL is accessible and return detailed info"""
        result = {
            "url": url,
            "accessible": False,
            "status_code": None,
            "content_type": None,
            "content_length": 0,
            "response_time": None,
            "error": None
        }
        
        import logging
import json
import time
import requests
from typing import Dict, Any, List
from bs4 import BeautifulSoup

class DebugHelper:
    """Helper class for debugging scraping issues"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def test_url_accessibility(self, url: str) -> Dict[str, Any]:
        """Test if URL is accessible and analyze response"""
        result = {
            "url": url,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "accessible": False,
            "error": None
        }
        
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            result["response_time"] = time.time() - start_time
            result["status_code"] = response.status_code
            result["content_type"] = response.headers.get('content-type', '')
            result["content_length"] = len(response.content)
            result["accessible"] = response.status_code == 200
            
        except Exception as e:
            result["error"] = str(e)
        
        self.logger.debug(f"URL Test: {json.dumps(result, indent=2)}")
        return result
    
    def analyze_page_structure(self, html: str, url: str) -> Dict[str, Any]:
        """Analyze page structure for debugging"""
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
        """Create comprehensive debug report"""
        report = f"""
# Debug Report for {url}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Analysis Results
Ingredients found: {len(analysis_result.get('all_ingredients', []))}
Health score: {analysis_result.get('health_score', 'N/A')}

## Scraped Ingredients
"""
        for i, ingredient in enumerate(analysis_result.get('all_ingredients', [])[:10]):
            report += f"{i+1}. {ingredient.get('name', 'Unknown')} (score: {ingredient.get('health_score', 'N/A')})\n"
        
        return report

# Global debug instance
debug = DebugHelper()

## Analysis Result
- Success: {analysis_result.get('success', False)}
- Ingredients Found: {len(analysis_result.get('all_ingredients', []))}
- Health Score: {analysis_result.get('health_score', 'N/A')}

## Ingredients Detected
"""
        for i, ingredient in enumerate(analysis_result.get('all_ingredients', [])[:10]):
            report += f"{i+1}. {ingredient.get('name', 'Unknown')} (Score: {ingredient.get('health_score', 'N/A')})\n"
        
        return report

# Global debug instance
debug = DebugHelper(enable_debug=True)

def init_debug_folder():
    """Initialize debug folder"""
    os.makedirs('debug', exist_ok=True)

# Auto-initialize
init_debug_folder()

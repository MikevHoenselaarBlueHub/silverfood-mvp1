import logging
import json
import time
from typing import Dict, Any, List
import requests
from urllib.parse import urlparse
import os
from bs4 import BeautifulSoup

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

import requests
import json
import time
import sys
from typing import Dict, Any, List

class SilverfoodTester:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.passed_tests = 0
        self.failed_tests = 0
        self.results = []

    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"   {message}")
        
        self.results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })
        
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1

    def test_api_health(self) -> bool:
        """Test if API is responsive"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            passed = response.status_code == 200
            self.log_test("API Health Check", passed, f"Status: {response.status_code}")
            return passed
        except Exception as e:
            self.log_test("API Health Check", False, str(e))
            return False

    def test_static_files(self) -> bool:
        """Test if static files are accessible"""
        static_files = [
            "/static/script.js",
            "/static/style.css", 
            "/static/config.json",
            "/static/lang.json",
            "/static/hide_icon.svg",
            "/static/show_icon.svg"
        ]
        
        all_passed = True
        for file_path in static_files:
            try:
                response = requests.get(f"{self.base_url}{file_path}", timeout=5)
                passed = response.status_code == 200
                if not passed:
                    all_passed = False
                self.log_test(f"Static File: {file_path}", passed, f"Status: {response.status_code}")
            except Exception as e:
                all_passed = False
                self.log_test(f"Static File: {file_path}", False, str(e))
        
        return all_passed

    def test_url_analysis(self) -> bool:
        """Test URL-based recipe analysis"""
        test_url = "https://www.ah.nl/allerhande/recept/R-R1201256/orzosalade-met-asperges-nectarines-en-burrata"
        
        try:
            response = requests.get(
                f"{self.base_url}/analyse",
                params={"url": test_url},
                timeout=30
            )
            
            passed = response.status_code == 200
            
            if passed:
                data = response.json()
                # Check required fields
                required_fields = ["success", "total_nutrition", "all_ingredients", "health_goals_scores"]
                for field in required_fields:
                    if field not in data:
                        passed = False
                        self.log_test("URL Analysis", False, f"Missing field: {field}")
                        return False
                
                # Check if we got meaningful data
                if not data.get("all_ingredients") or len(data["all_ingredients"]) < 3:
                    passed = False
                    self.log_test("URL Analysis", False, "Too few ingredients found")
                    return False
            
            self.log_test("URL Analysis", passed, f"Status: {response.status_code}")
            return passed
            
        except Exception as e:
            self.log_test("URL Analysis", False, str(e))
            return False

    def test_text_analysis(self) -> bool:
        """Test text-based recipe analysis"""
        test_text = """
        2 uien
        300g gehakt
        1 blik tomaten
        200ml room
        zout en peper
        """
        
        try:
            response = requests.post(
                f"{self.base_url}/analyse-text",
                json={"text": test_text},
                timeout=15
            )
            
            passed = response.status_code == 200
            
            if passed:
                data = response.json()
                # Check required fields
                required_fields = ["success", "total_nutrition", "all_ingredients"]
                for field in required_fields:
                    if field not in data:
                        passed = False
                        self.log_test("Text Analysis", False, f"Missing field: {field}")
                        return False
                
                # Check if we got ingredients
                if not data.get("all_ingredients") or len(data["all_ingredients"]) < 2:
                    passed = False
                    self.log_test("Text Analysis", False, "Too few ingredients found")
                    return False
            
            self.log_test("Text Analysis", passed, f"Status: {response.status_code}")
            return passed
            
        except Exception as e:
            self.log_test("Text Analysis", False, str(e))
            return False

    def test_chrome_extension_endpoints(self) -> bool:
        """Test Chrome extension specific endpoints"""
        test_url = "https://www.ah.nl/allerhande/recept/R-R1201256/orzosalade-met-asperges-nectarines-en-burrata"
        
        endpoints = [
            "/extension/analyze",
            "/extension/quick-check", 
            "/extension/suggestions"
        ]
        
        all_passed = True
        for endpoint in endpoints:
            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    params={"url": test_url},
                    timeout=20
                )
                
                passed = response.status_code == 200
                if not passed:
                    all_passed = False
                
                self.log_test(f"Extension Endpoint: {endpoint}", passed, f"Status: {response.status_code}")
                
            except Exception as e:
                all_passed = False
                self.log_test(f"Extension Endpoint: {endpoint}", False, str(e))
        
        return all_passed

    def test_error_handling(self) -> bool:
        """Test error handling for invalid inputs"""
        test_cases = [
            ("Invalid URL", {"url": "not-a-url"}),
            ("Empty text", {"text": ""}),
            ("Missing params", {})
        ]
        
        all_passed = True
        
        # Test invalid URL
        try:
            response = requests.get(f"{self.base_url}/analyse", params={"url": "not-a-url"}, timeout=10)
            passed = response.status_code in [400, 422, 500]  # Should return error status
            if not passed:
                all_passed = False
            self.log_test("Error Handling: Invalid URL", passed, f"Status: {response.status_code}")
        except Exception as e:
            all_passed = False
            self.log_test("Error Handling: Invalid URL", False, str(e))
        
        # Test empty text
        try:
            response = requests.post(f"{self.base_url}/analyse-text", json={"text": ""}, timeout=10)
            passed = response.status_code in [400, 422]  # Should return error status
            if not passed:
                all_passed = False
            self.log_test("Error Handling: Empty Text", passed, f"Status: {response.status_code}")
        except Exception as e:
            all_passed = False
            self.log_test("Error Handling: Empty Text", False, str(e))
        
        return all_passed

    def test_performance(self) -> bool:
        """Test basic performance metrics"""
        test_text = "2 uien, 300g gehakt, 1 blik tomaten"
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/analyse-text",
                json={"text": test_text},
                timeout=30
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            passed = response.status_code == 200 and response_time < 15  # Should complete within 15 seconds
            
            self.log_test("Performance Test", passed, f"Response time: {response_time:.2f}s")
            return passed
            
        except Exception as e:
            self.log_test("Performance Test", False, str(e))
            return False

    def run_all_tests(self):
        """Run all tests and print summary"""
        print("🧪 Starting Silverfood Functionality Tests...\n")
        
        # Run tests in order of importance
        tests = [
            self.test_api_health,
            self.test_static_files,
            self.test_text_analysis,
            self.test_url_analysis,
            self.test_chrome_extension_endpoints,
            self.test_error_handling,
            self.test_performance
        ]
        
        for test in tests:
            test()
            print()  # Add spacing between tests
        
        # Print summary
        total_tests = self.passed_tests + self.failed_tests
        print("=" * 50)
        print(f"📊 Test Results Summary:")
        print(f"   Total Tests: {total_tests}")
        print(f"   ✅ Passed: {self.passed_tests}")
        print(f"   ❌ Failed: {self.failed_tests}")
        print(f"   Success Rate: {(self.passed_tests/total_tests*100):.1f}%")
        
        if self.failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if not result["passed"]:
                    print(f"   - {result['test']}: {result['message']}")
        
        return self.failed_tests == 0

if __name__ == "__main__":
    # Allow custom base URL as command line argument
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    tester = SilverfoodTester(base_url)
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
from typing import Dict, Any
from analyse import analyse
from debug_helper import debug

logger = logging.getLogger(__name__)

def setup_chrome_extension_api(app: FastAPI):
    """Setup Chrome extension specific API endpoints"""
    
    @app.get("/chrome/analyze")
    async def chrome_analyze(url: str):
        """Chrome extension analysis endpoint"""
        try:
            result = analyse(url)
            
            # Return simplified data for chrome extension
            return {
                "success": True,
                "data": {
                    "health_score": result.get("health_score", 0),
                    "total_ingredients": len(result.get("all_ingredients", [])),
                    "recipe_title": result.get("recipe_title", "Recept"),
                    "top_ingredients": [
                        {
                            "name": ing["name"],
                            "health_score": ing["health_score"]
                        }
                        for ing in result.get("all_ingredients", [])[:5]
                    ]
                }
            }
        except Exception as e:
            logger.error(f"Chrome extension analysis failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @app.get("/chrome/health-check")
    async def chrome_health_check():
        """Health check for chrome extension"""
        return {
            "status": "healthy",
            "version": "3.1.0",
            "chrome_extension_ready": True
        }

class ChromeExtensionAPI:
    """API endpoints specifically for Chrome extension"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.setup_routes()
    
    def setup_routes(self):
        """Setup Chrome extension specific routes"""
        
        @self.app.get("/extension/analyze")
        async def extension_analyze(url: str, tab_id: int = None):
            """Analyze recipe for Chrome extension"""
            try:
                debug.log_request(url, "GET")
                
                # Quick validation
                if not url or len(url) < 10:
                    raise HTTPException(400, "Invalid URL")
                
                result = analyse(url)
                
                # Format for extension
                extension_result = {
                    "success": True,
                    "recipe_title": result.get("recipe_title", "Recipe"),
                    "health_score": result.get("health_score", 5),
                    "total_ingredients": len(result.get("all_ingredients", [])),
                    "healthy_count": len([i for i in result.get("all_ingredients", []) if i.get("health_score", 0) >= 7]),
                    "suggestions": result.get("swaps", [])[:5],  # Limit to 5 suggestions
                    "quick_summary": self.create_quick_summary(result)
                }
                
                debug.logger.info(f"Extension analysis success for {url}")
                return extension_result
                
            except Exception as e:
                debug.logger.error(f"Extension analysis failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "fallback_message": "Could not analyze this recipe. Try a different recipe page."
                }
        
        @self.app.get("/extension/quick-check")
        async def quick_health_check(url: str):
            """Quick health check for extension badge"""
            try:
                # Simplified analysis for badge
                result = analyse(url)
                health_score = result.get("health_score", 5)
                
                return {
                    "health_score": health_score,
                    "health_level": self.get_health_level(health_score),
                    "badge_color": self.get_badge_color(health_score),
                    "ingredient_count": len(result.get("all_ingredients", []))
                }
                
            except Exception as e:
                return {
                    "health_score": 0,
                    "health_level": "unknown",
                    "badge_color": "gray",
                    "error": str(e)
                }
        
        @self.app.get("/extension/suggestions")
        async def get_suggestions(url: str):
            """Get improvement suggestions for extension popup"""
            try:
                result = analyse(url)
                suggestions = []
                
                for swap in result.get("swaps", [])[:3]:
                    suggestions.append({
                        "original": swap.get("ongezond_ingredient", ""),
                        "replacement": swap.get("vervang_door", ""),
                        "improvement": "Healthier alternative"
                    })
                
                return {
                    "suggestions": suggestions,
                    "total_possible_improvements": len(result.get("swaps", [])),
                    "current_score": result.get("health_score", 5)
                }
                
            except Exception as e:
                return {"suggestions": [], "error": str(e)}
    
    def create_quick_summary(self, result: Dict[str, Any]) -> str:
        """Create quick summary for extension"""
        health_score = result.get("health_score", 5)
        ingredient_count = len(result.get("all_ingredients", []))
        swap_count = len(result.get("swaps", []))
        
        if health_score >= 8:
            return f"Great recipe! {ingredient_count} ingredients analyzed."
        elif health_score >= 6:
            return f"Good recipe with {swap_count} possible improvements."
        else:
            return f"Recipe could be healthier. {swap_count} suggestions available."
    
    def get_health_level(self, score: float) -> str:
        """Get health level description"""
        if score >= 8: return "excellent"
        elif score >= 6: return "good"
        elif score >= 4: return "fair"
        else: return "poor"
    
    def get_badge_color(self, score: float) -> str:
        """Get badge color for extension"""
        if score >= 8: return "green"
        elif score >= 6: return "yellow"
        elif score >= 4: return "orange"
        else: return "red"

def setup_chrome_extension_api(app: FastAPI):
    """Setup Chrome extension API"""
    chrome_api = ChromeExtensionAPI(app)
    return chrome_api

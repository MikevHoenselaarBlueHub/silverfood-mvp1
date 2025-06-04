
#!/usr/bin/env python3
"""
Central URL configuration manager for Silverfood
Handles deployment URLs and API endpoint configuration
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

class URLConfig:
    """Manages API URLs and deployment configuration"""
    
    def __init__(self):
        self.config = self._load_config()
        self._deployment_url = None
        self._api_url = None
    
    def _load_config(self):
        """Load configuration from config.json"""
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
            return self._get_default_config()
    
    def _get_default_config(self):
        """Default configuration if config.json fails to load"""
        return {
            "deployment": {
                "replit_app_name": "silverfood-analyzer",
                "replit_username": "your-username", 
                "use_deployment_url": True,
                "manual_override_url": None
            }
        }
    
    def get_deployment_url(self):
        """Get the deployment URL based on configuration"""
        if self._deployment_url:
            return self._deployment_url
            
        deployment_config = self.config.get("deployment", {})
        
        # Check for manual override first
        manual_url = deployment_config.get("manual_override_url")
        if manual_url:
            self._deployment_url = manual_url
            logger.info(f"Using manual override URL: {manual_url}")
            return self._deployment_url
        
        # Check if we should use deployment URL
        if deployment_config.get("use_deployment_url", True):
            app_name = deployment_config.get("replit_app_name", "silverfood-analyzer")
            username = deployment_config.get("replit_username", "your-username")
            
            # Try different Replit URL patterns
            possible_urls = [
                f"https://{app_name}.{username}.repl.co",
                f"https://{app_name}-{username}.replit.app", 
                f"https://{username}.replit.app/{app_name}"
            ]
            
            # Use the first pattern as default
            self._deployment_url = possible_urls[0]
            logger.info(f"Using Replit deployment URL: {self._deployment_url}")
            return self._deployment_url
        
        # Fallback to localhost for development
        self._deployment_url = "http://localhost:5000"
        logger.info("Using localhost for development")
        return self._deployment_url
    
    def get_api_url(self):
        """Get API URL for internal use"""
        if self._api_url:
            return self._api_url
            
        # For API endpoints, always use the deployment URL
        self._api_url = self.get_deployment_url()
        return self._api_url
    
    def is_development(self):
        """Check if we're in development mode"""
        return "localhost" in self.get_deployment_url()
    
    def update_deployment_config(self, app_name=None, username=None, manual_url=None):
        """Update deployment configuration"""
        if app_name:
            self.config["deployment"]["replit_app_name"] = app_name
        if username:
            self.config["deployment"]["replit_username"] = username
        if manual_url is not None:
            self.config["deployment"]["manual_override_url"] = manual_url
        
        # Reset cached URLs
        self._deployment_url = None
        self._api_url = None
        
        # Save updated config
        try:
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Deployment configuration updated")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

# Global instance
url_config = URLConfig()

def get_api_url():
    """Get the current API URL"""
    return url_config.get_api_url()

def get_deployment_url():
    """Get the current deployment URL"""
    return url_config.get_deployment_url()

def is_development():
    """Check if in development mode"""
    return url_config.is_development()


#!/usr/bin/env python3
"""
Configure deployment settings for Silverfood
Easy way to update Replit app name and username
"""

import json
import sys
from url_config import url_config

def update_deployment_config():
    """Interactive script to update deployment configuration"""
    
    print("🔧 Silverfood Deployment Configuration")
    print("=" * 50)
    
    current_config = url_config.config.get("deployment", {})
    
    print(f"Current configuration:")
    print(f"  App Name: {current_config.get('replit_app_name', 'Not set')}")
    print(f"  Username: {current_config.get('replit_username', 'Not set')}")
    print(f"  Manual URL: {current_config.get('manual_override_url', 'None')}")
    print(f"  Current URL: {url_config.get_deployment_url()}")
    
    print("\n📝 Enter new values (press Enter to keep current):")
    
    # Get new app name
    new_app_name = input(f"Replit App Name [{current_config.get('replit_app_name', '')}]: ").strip()
    if not new_app_name:
        new_app_name = current_config.get('replit_app_name')
    
    # Get new username
    new_username = input(f"Replit Username [{current_config.get('replit_username', '')}]: ").strip()
    if not new_username:
        new_username = current_config.get('replit_username')
    
    # Get manual URL (optional)
    print("\n🔗 Manual URL Override (optional, leave empty for auto-detection):")
    manual_url = input("Manual URL: ").strip()
    if not manual_url:
        manual_url = None
    
    # Update configuration
    try:
        url_config.update_deployment_config(
            app_name=new_app_name,
            username=new_username, 
            manual_url=manual_url
        )
        
        print(f"\n✅ Configuration updated!")
        print(f"📡 New deployment URL: {url_config.get_deployment_url()}")
        print(f"🔗 API URL: {url_config.get_api_url()}")
        
        # Update extension files
        update_extension_files(new_app_name, new_username, manual_url)
        
        print(f"\n🎉 All configuration files updated!")
        print(f"💡 You can now rebuild the Chrome extension with: python build_extension.py")
        
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        sys.exit(1)

def update_extension_files(app_name, username, manual_url):
    """Update extension files with new configuration"""
    
    if manual_url:
        primary_url = manual_url
    else:
        primary_url = f"https://{app_name}.{username}.repl.co"
    
    # Update popup.js
    try:
        with open('popup.js', 'r') as f:
            popup_content = f.read()
        
        # Replace the default URL in the array
        popup_content = popup_content.replace(
            'https://silverfood-analyzer.your-username.repl.co',
            primary_url
        )
        
        with open('popup.js', 'w') as f:
            f.write(popup_content)
        
        print(f"✅ Updated popup.js with URL: {primary_url}")
        
    except Exception as e:
        print(f"⚠️ Could not update popup.js: {e}")
    
    # Update background.js
    try:
        with open('background.js', 'r') as f:
            bg_content = f.read()
        
        # Replace the default URL in the array
        bg_content = bg_content.replace(
            'https://silverfood-analyzer.your-username.repl.co',
            primary_url
        )
        
        with open('background.js', 'w') as f:
            f.write(bg_content)
        
        print(f"✅ Updated background.js with URL: {primary_url}")
        
    except Exception as e:
        print(f"⚠️ Could not update background.js: {e}")

if __name__ == "__main__":
    update_deployment_config()

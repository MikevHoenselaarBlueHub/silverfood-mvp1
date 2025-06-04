
#!/usr/bin/env python3
"""
Build Chrome extension ZIP for easy installation
"""

import zipfile
import os
import json

def build_extension():
    """Build Chrome extension ZIP file"""
    
    # Extension files to include
    extension_files = [
        'manifest.json',
        'popup.html', 
        'popup.js',
        'background.js',
        'content.js',
        'static/icon-16.png',
        'static/icon-32.png', 
        'static/icon-48.png',
        'static/icon-128.png',
        'static/style.css'
    ]
    
    # Create ZIP file
    with zipfile.ZipFile('silverfood-extension.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in extension_files:
            if os.path.exists(file_path):
                # Add file to ZIP with proper path structure
                if file_path.startswith('static/'):
                    arcname = file_path
                else:
                    arcname = file_path
                zipf.write(file_path, arcname)
                print(f"✅ Added: {file_path}")
            else:
                print(f"⚠️  Missing: {file_path}")
    
    print(f"\n🎉 Extension ZIP created: silverfood-extension.zip")
    print("📁 Download this file and extract to load in Chrome")

if __name__ == "__main__":
    build_extension()

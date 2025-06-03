
# Silverfood Chrome Extension Setup

## Chrome Extension Bestanden

De volgende bestanden zijn toegevoegd voor Chrome extension functionaliteit:

- `manifest.json` - Extension manifest
- `popup.html` - Extension popup interface  
- `popup.js` - Popup JavaScript logic
- `background.js` - Background service worker
- `content.js` - Content script voor in-page functionaliteit
- `chrome_extension_api.py` - API endpoints voor extension

## Installation Chrome Extension

### 1. Developer Mode inschakelen
1. Open Chrome
2. Ga naar `chrome://extensions/`
3. Schakel "Developer mode" in (rechtsboven)

### 2. Extension laden
1. Klik "Load unpacked"
2. Selecteer de project folder (waar manifest.json staat)
3. Extension wordt geladen

### 3. API URL configureren
In `popup.js` en `background.js`, update de `apiUrl`:
```javascript
this.apiUrl = 'https://your-replit-app.replit.app';
```

## Features Chrome Extension

### Popup Interface
- Automatische recept detectie
- Health score weergave met kleurcodering
- Ingredient suggesties
- Link naar volledige analyse

### Badge Functionaliteit  
- Shows health score in extension badge
- Kleurcodering: groen (8+), geel (6-7), oranje (4-5), rood (<4)
- Alleen zichtbaar op recept pagina's

### Content Script
- Floating "Analyze Recipe" button op recept pagina's
- Quick analysis zonder popup te openen
- Automatische detectie van recept pagina's

## API Endpoints voor Extension

### `/extension/analyze`
Volledige analyse voor popup:
```javascript
GET /extension/analyze?url=<recipe_url>
```

### `/extension/quick-check`  
Snelle check voor badge:
```javascript
GET /extension/quick-check?url=<recipe_url>
```

### `/extension/suggestions`
Alleen suggesties:
```javascript
GET /extension/suggestions?url=<recipe_url>
```

## Development Tips

### Testing
1. Reload extension na code wijzigingen
2. Check console voor errors: `chrome://extensions/` → "Inspect views"
3. Test op verschillende recept websites

### Debug Mode
Enable debug logging in `debug_helper.py`:
```python
debug = DebugHelper(enable_debug=True)
```

### Icons
Plaats extension icons in `/icons/` folder:
- icon16.png (16x16)
- icon32.png (32x32) 
- icon48.png (48x48)
- icon128.png (128x128)

## Deployment

### Replit App
1. Deploy je Replit app naar productie
2. Update API URLs in extension files
3. Test extension met productie API

### Chrome Web Store
1. Zip alle extension bestanden
2. Upload naar Chrome Developer Dashboard
3. Volg Chrome Web Store review proces

## Ondersteunte Websites

Extension detecteert automatisch recept pagina's van:
- AH Allerhande
- Jumbo Recepten  
- Leuke Recepten
- 24Kitchen
- En andere sites met recept indicatoren

## Troubleshooting

### Extension laadt niet
- Check manifest.json syntax
- Zorg dat alle bestanden aanwezig zijn

### API connectie fails
- Verificeer API URL in popup.js/background.js
- Check CORS instellingen in API
- Test API endpoint direct in browser

### Badge toont niet
- Check tab permissions in manifest
- Verify background script werkt
- Test op bekende recept websites

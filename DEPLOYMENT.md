
# Silverfood API - Deployment Guide

## Quick Start (Na GitHub Import)

1. **Run de app:**
   ```bash
   python startup.py
   ```
   Dit installeert automatisch alle dependencies en start de server.

2. **Health Check:**
   ```bash
   python health_check.py
   ```
   Controleert of alles correct geconfigureerd is.

## Automatische Setup

De app is geconfigureerd voor plug-and-play deployment:

- **startup.py** - Installeert dependencies en start server automatisch
- **health_check.py** - Diagnosticeert problemen
- **.replit** - Correct geconfigureerd voor Replit
- **requirements.txt** - Alle benodigde packages

## Workflow Configuratie

- **Run Button**: Start `python startup.py`
- **Port**: 5000 (automatisch doorgestuurd naar 80/443)
- **Auto-reload**: Enabled voor development

## Troubleshooting

### App start niet?
```bash
python health_check.py
```

### Dependencies missing?
```bash
python -m pip install -r requirements.txt
```

### Selenium issues?
De app werkt ook zonder Selenium - fallback naar requests-only scraping.

## Features

✅ **Adaptieve Receptanalyse** - Werkt met alle receptsites  
✅ **Chrome Extension** - Browser integratie  
✅ **AI Health Analysis** - OpenAI powered ingredient analysis  
✅ **Debug Logging** - Uitgebreide debugging  
✅ **Rate Limiting** - API bescherming  
✅ **Auto-deployment** - Plug-and-play setup  

## API Endpoints

- `GET /` - Web interface
- `GET /analyse?url=<url>` - Recept analyse van URL
- `POST /analyse-text` - Recept analyse van tekst
- `GET /health` - System health check
- `GET /chrome/analyze?url=<url>` - Chrome extension API

## Chrome Extension

Zie `README_CHROME_EXTENSION.md` voor installatie-instructies.

## Production Deployment

App is ready voor Replit deployment:
1. Klik op Deploy knop in Replit
2. App start automatisch met correcte configuratie
3. HTTPS wordt automatisch geconfigureerd

**Versie:** 3.4.0  
**Status:** Production Ready ✅

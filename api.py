from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import time
import logging
import json
import os
import requests
from analyse import analyse
from urllib.parse import urlparse
from chrome_extension_api import setup_chrome_extension_api
from debug_helper import debug

# Laad configuratie
try:
    with open("config.json", encoding="utf-8") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    CONFIG = {
        "api": {"rate_limit_requests": 8, "rate_limit_window_seconds": 60, "enable_debug_logging": True},
        "ui": {"max_url_length": 500}
    }

# Logging configuratie
log_level = logging.DEBUG if CONFIG.get("api", {}).get("enable_debug_logging", True) else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Silverfood-API", 
    description="Adaptieve receptenanalyse API voor alle receptsites",
    version="3.4.0"
)

# Beveiligingsmiddleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Setup Chrome extension API
setup_chrome_extension_api(app)

# Rate limiting
request_history = {}

def rate_limit_check(client_ip: str, max_requests: int = 10, window_seconds: int = 60):
    """Simpele rate limiting"""
    current_time = time.time()

    cutoff_time = current_time - window_seconds
    request_history[client_ip] = [
        req_time for req_time in request_history.get(client_ip, [])
        if req_time > cutoff_time
    ]

    if len(request_history.get(client_ip, [])) >= max_requests:
        return False

    if client_ip not in request_history:
        request_history[client_ip] = []
    request_history[client_ip].append(current_time)

    return True

def validate_url_format(url: str) -> bool:
    """Basis URL validatie"""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and parsed.netloc
    except:
        return False

# Statische bestanden serveren
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log alle requests voor monitoring"""
    start_time = time.time()
    client_ip = request.client.host

    logger.info(f"Request: {request.method} {request.url} from {client_ip}")

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} in {process_time:.2f}s")

    return response

@app.get("/")
async def root():
    """Serve hoofdpagina"""
    return FileResponse("static/index.html")

@app.get("/analyse")
async def analyse_endpoint(request: Request, url: str):
    """Analyseer recept van URL met adaptieve detectie"""
    client_ip = request.client.host

    # Rate limiting from config
    max_req = CONFIG.get("api", {}).get("rate_limit_requests", 8)
    window_sec = CONFIG.get("api", {}).get("rate_limit_window_seconds", 60)
    if not rate_limit_check(client_ip, max_requests=max_req, window_seconds=window_sec):
        logger.warning(f"Rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=429, 
            detail="Te veel verzoeken. Probeer het over een minuut opnieuw."
        )

    # Input validatie
    if not url or not url.strip():
        raise HTTPException(
            status_code=400, 
            detail="Geen URL opgegeven. Voer een geldige recept URL in."
        )

    url = url.strip()

    # Basis URL format validatie
    if not validate_url_format(url):
        raise HTTPException(
            status_code=400, 
            detail="Ongeldige URL format. De URL moet beginnen met http:// of https:// en een domein bevatten."
        )

    # Maximale URL lengte from config
    max_length = CONFIG.get("ui", {}).get("max_url_length", 500)
    if len(url) > max_length:
        raise HTTPException(
            status_code=400,
            detail="URL te lang. Maximaal 500 karakters toegestaan."
        )

    # Basis veiligheidscheck - vermijd lokale/private URLs
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc.replace('www.', '')

        # Blokkeer lokale/private IPs en gevaarlijke protocollen
        blocked_patterns = [
            'localhost', '127.0.0.1', '0.0.0.0', '192.168.', '10.', '172.',
            'file://', 'ftp://', 'javascript:', 'data:'
        ]

        if any(pattern in url.lower() for pattern in blocked_patterns):
            raise HTTPException(
                status_code=400,
                detail="Deze URL wordt niet ondersteund om veiligheidsredenen."
            )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.warning(f"URL validation issue for {url}: {e}")

    try:
        logger.info(f"Analysing recipe from {url} for {client_ip}")
        result = analyse(url)
        logger.info(f"Analysis successful for {client_ip}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        logger.error(f"Analysis failed for {client_ip}: {error_message}")

        # Gebruikersvriendelijke foutmeldingen
        if "geen ingrediënten" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="Geen ingrediënten gevonden op deze pagina. Dit lijkt geen recept-pagina te zijn, of de website gebruikt een onbekende structuur. Probeer een andere recept-URL."
            )
        elif "not valid json" in error_message.lower() or "unexpected token" in error_message.lower():
            raise HTTPException(
                status_code=403,
                detail="Deze website blokkeert automatische toegang en stuurt HTML in plaats van data terug. Probeer een andere recept-URL of kopieer de ingrediënten handmatig."
            )
        elif "403" in error_message or "forbidden" in error_message.lower():
            raise HTTPException(
                status_code=403,
                detail="Deze website blokkeert automatische toegang. Probeer een andere recept-URL."
            )
        elif "404" in error_message or "not found" in error_message.lower():
            raise HTTPException(
                status_code=404,
                detail="Pagina niet gevonden. Controleer of de URL correct is."
            )
        elif "timeout" in error_message.lower() or "time" in error_message.lower():
            raise HTTPException(
                status_code=408,
                detail="Het ophalen van het recept duurt te lang. Controleer de URL en probeer opnieuw."
            )
        elif "ssl" in error_message.lower() or "certificate" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="SSL certificaat probleem met deze website. Probeer een andere recept-URL."
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail="Er is een onverwachte fout opgetreden bij het analyseren van deze pagina. Probeer het later opnieuw of gebruik een andere recept-URL."
            )

@app.post("/analyse-text")
async def analyse_text_endpoint(request: Request):
    """Analyseer recept van tekst met adaptieve detectie"""
    client_ip = request.client.host

    # Get text from request body
    try:
        body = await request.json()
        text = body.get('text', '')
    except Exception as e:
        logger.error(f"Failed to parse request body: {e}")
        raise HTTPException(
            status_code=400,
            detail="Ongeldige request format."
        )

    # Rate limiting from config
    max_req = CONFIG.get("api", {}).get("rate_limit_requests", 8)
    window_sec = CONFIG.get("api", {}).get("rate_limit_window_seconds", 60)
    if not rate_limit_check(client_ip, max_requests=max_req, window_seconds=window_sec):
        logger.warning(f"Rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Te veel verzoeken. Probeer het over een minuut opnieuw."
        )

    # Input validatie
    if not text or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Geen tekst opgegeven. Voer geldige recept tekst in."
        )

    text = text.strip()

    try:
        logger.info(f"Analysing recipe from text for {client_ip}")
        result = analyse(text)
        logger.info(f"Analysis successful for {client_ip}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        logger.error(f"Text analysis failed for {client_ip}: {error_message}")
        logger.error(f"Text content: {text[:100]}...")  # Log first 100 chars for debugging

        # Gebruikersvriendelijke foutmeldingen
        if "geen ingrediënten" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="Geen ingrediënten gevonden in deze tekst. Dit lijkt geen recept te zijn, of de website gebruikt een onbekende structuur. Probeer een andere recept-URL."
            )
        elif "not valid json" in error_message.lower() or "unexpected token" in error_message.lower():
            raise HTTPException(
                status_code=403,
                detail="Deze website blokkeert automatische toegang en stuurt HTML in plaats van data terug. Probeer een andere recept-URL of kopieer de ingrediënten handmatig."
            )
        elif "403" in error_message or "forbidden" in error_message.lower():
            raise HTTPException(
                status_code=403,
                detail="Deze website blokkeert automatische toegang. Probeer een andere recept-URL."
            )
        elif "404" in error_message or "not found" in error_message.lower():
            raise HTTPException(
                status_code=404,
                detail="Pagina niet gevonden. Controleer of de URL correct is."
            )
        elif "timeout" in error_message.lower() or "time" in error_message.lower():
            raise HTTPException(
                status_code=408,
                detail="Het ophalen van het recept duurt te lang. Controleer de URL en probeer opnieuw."
            )
        elif "ssl" in error_message.lower() or "certificate" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="SSL certificaat probleem met deze website. Probeer een andere recept-URL."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Er is een onverwachte fout opgetreden bij het analyseren van deze pagina. Probeer het later opnieuw of gebruik een andere recept-URL."
            )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Check Selenium availability
    selenium_available = False
    try:
        import shutil
        chrome_binary = shutil.which('chromium') or shutil.which('chrome')
        chromedriver_binary = shutil.which('chromedriver')
        selenium_available = bool(chrome_binary and chromedriver_binary)
    except:
        pass

    import shutil
    return {
        "status": "healthy", 
        "message": "Silverfood API is actief",
        "version": "3.4.0",
        "features": ["adaptive_detection", "pattern_learning", "universal_recipe_support", "ai_ingredient_validation"],
        "selenium_available": selenium_available,
        "components": {
            "chrome": bool(shutil.which('chromium') or shutil.which('chrome')),
            "chromedriver": bool(shutil.which('chromedriver'))
        }
    }

@app.get("/supported-sites")
async def supported_sites():
    """Informatie over site ondersteuning"""
    return {
        "message": "Deze API ondersteunt nu automatisch detectie van receptsites",
        "features": [
            "Automatische patroon detectie voor onbekende sites",
            "Lerende algoritmes die sites onthouden",
            "Ondersteuning voor alle recept websites"
        ],
        "examples": [
            {
                "name": "AH Allerhande",
                "url": "https://www.ah.nl/allerhande/recept/R-R1201256/orzosalade-met-asperges-nectarines-en-burrata"
            },
            {
                "name": "Jumbo Recepten", 
                "url": "https://www.jumbo.com/recepten/pasta-met-doperwten-ricotta-en-munt-999966"
            },
            {
                "name": "Leuke Recepten",
                "url": "https://www.leukerecepten.nl/recepten/couscous-salade-met-feta/"
            },
            {
                "name": "24Kitchen",
                "url": "https://www.24kitchen.nl/recepten/"
            }
        ],
        "how_it_works": [
            "1. Upload een recept-URL van elke website",
            "2. De AI detecteert automatisch de ingrediëntenstructuur", 
            "3. Patronen worden opgeslagen voor snellere toekomstige analyse",
            "4. Elke nieuwe site wordt geleerd en toegevoegd"
        ]
    }

@app.get("/learned-patterns")
async def learned_patterns():
    """Toon geleerde website patronen"""
    try:
        import json
        with open("website_patterns.json", encoding="utf-8") as f:
            patterns = json.load(f)

        summary = {}
        for domain, pattern_data in patterns.items():
            summary[domain] = {
                "success_count": pattern_data.get("success_count", 0),
                "auto_detected": pattern_data.get("auto_detected", False),
                "selectors_count": len(pattern_data.get("ingredient_selectors", []))
            }

        return {
            "learned_sites": summary,
            "total_sites": len(patterns),
            "message": "Deze sites zijn geleerd en kunnen snel geanalyseerd worden"
        }
    except:
        return {"learned_sites": {}, "total_sites": 0}

@app.get("/explain-unhealthy")
async def explain_unhealthy_ingredients(ingredients: str):
    """Generate AI explanation for unhealthy ingredients"""
    return await get_ai_explanation(ingredients, "unhealthy")

@app.get("/explain-healthy")
async def explain_healthy_ingredients(ingredients: str):
    """Generate AI explanation for healthy ingredients"""
    return await get_ai_explanation(ingredients, "healthy")

async def get_ai_explanation(ingredients: str, explanation_type: str):
    """Generate AI explanation for ingredients"""
    try:
        # OpenAI API key from environment variables
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.info("OpenAI API key not configured - using fallback explanations")
            fallback_msg = "Deze ingrediënten zijn rijk aan vitaminen en mineralen." if explanation_type == "healthy" else "Een voedingsexpert zou u adviseren om deze ingrediënten in balans te houden met veel groenten en fruit."
            return {"explanation": fallback_msg}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        if explanation_type == "healthy":
            prompt = f"""
            Je bent een voedingsexpert. Leg in 1-2 zinnen uit waarom deze gezonde ingrediënten zo goed zijn:

            Ingrediënten: {ingredients}

            Geef een korte, positieve uitleg in het Nederlands (max 100 woorden) over waarom deze ingrediënten gezond zijn.
            Focus op de belangrijkste voedingsstoffen en gezondheidsvoordelen.
            """
        else:
            prompt = f"""
            Je bent een voedingsexpert. Leg uit waarom deze ingrediënten minder gezond zijn en geef praktische tips:

            Ingrediënten: {ingredients}

            Geef een korte, begrijpelijke uitleg in het Nederlands (max 200 woorden) over:
            1. Waarom deze ingrediënten minder gezond zijn
            2. Wat je in plaats daarvan zou kunnen gebruiken
            3. Hoe je deze ingrediënten in balans kunt houden

            Wees positief en niet te streng - geef praktische tips.
            """

        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "Je bent een vriendelijke voedingsexpert die mensen helpt gezonder te eten."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 200 if explanation_type == "healthy" else 300,
            "temperature": 0.7
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15
        )

        if response.status_code == 200:
            result = response.json()
            explanation = result['choices'][0]['message']['content'].strip()
            return {"explanation": explanation}
        else:
            logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
            fallback_msg = "Deze ingrediënten zijn rijk aan vitaminen en mineralen." if explanation_type == "healthy" else "Een voedingsexpert zou u adviseren om deze ingrediënten in balans te houden met veel groenten en fruit."
            return {"explanation": fallback_msg}

    except Exception as e:
        logger.error(f"AI explanation error: {e}")
        fallback_msg = "Deze ingrediënten zijn rijk aan vitaminen en mineralen." if explanation_type == "healthy" else "Een voedingsexpert zou u adviseren om deze ingrediënten in balans te houden met veel groenten en fruit."
        return {"explanation": fallback_msg}

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    logger.warning(f"404 error for {request.url} from {request.client.host}")
    return FileResponse("static/index.html")

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"500 error for {request.url} from {request.client.host}: {exc}")
    raise HTTPException(
        status_code=500,
        detail="Er is een interne serverfout opgetreden. Probeer het later opnieuw."
    )
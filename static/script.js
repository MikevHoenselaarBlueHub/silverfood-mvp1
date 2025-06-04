// DOM elementen - gebruik lazy loading om null errors te voorkomen
function getElement(id) {
    return document.getElementById(id);
}

function getElements(selector) {
    return document.querySelectorAll(selector);
}

// Lazy getters voor DOM elementen
function getRecipeUrlInput() { return getElement("recipeUrl"); }
function getAnalyzeBtn() { return getElement("analyzeBtn"); }
function getBtnText() { return document.querySelector(".btn-text"); }
function getLoader() { return document.querySelector(".loader"); }
function getResultsDiv() { return getElement("results"); }
function getErrorDiv() { return getElement("error"); }
function getErrorMessage() { return getElement("errorMessage"); }

// Health tips functionaliteit
let healthTips = [];
let currentTipIndex = 0;
let tipInterval = null;
let config = {
    health_tips: {
        interval_seconds: 4,
        show_tips: true,
        fade_duration_ms: 500,
    },
    ui: {
        default_url: "",
        examples: [],
    },
};

// Voorbeelden van ondersteunde URLs (fallback)
let exampleUrls = [
    "https://www.ah.nl/allerhande/recept/R-R1201256/orzosalade-met-asperges-nectarines-en-burrata",
    "https://www.jumbo.com/recepten/pasta-met-doperwten-ricotta-en-munt-999966",
    "https://www.leukerecepten.nl/recepten/couscous-salade-met-feta/",
    "https://www.24kitchen.nl/recepten/pasta-pesto-met-zongedroogde-tomaten",
];

// Tab switching functionality
document.addEventListener('DOMContentLoaded', function() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');

            // Remove active class from all buttons and panes
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));

            // Add active class to clicked button and target pane
            this.classList.add('active');
            document.getElementById(targetTab).classList.add('active');
        });
    });

    // Add textarea element reference
    window.recipeTextArea = document.getElementById('recipeText');
    if (window.recipeTextArea) {
        window.recipeTextArea.addEventListener("keypress", (e) => {
            if (e.key === "Enter" && e.ctrlKey) {
                analyzeRecipe();
            }
        });
    }

    // Setup main event listeners
    const analyzeBtn = getAnalyzeBtn();
    const recipeUrlInput = getRecipeUrlInput();

    if (analyzeBtn) {
        analyzeBtn.addEventListener("click", analyzeRecipe);
    }

    if (recipeUrlInput) {
        recipeUrlInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                analyzeRecipe();
            }
        });

        // Input validatie met real-time feedback
        recipeUrlInput.addEventListener("input", (e) => {
            const url = e.target.value.trim();
            if (url) {
                validateUrl(url);
            }
        });
    }
});

function validateUrl(url) {
    const recipeUrlInput = getRecipeUrlInput();
    if (!recipeUrlInput) return;

    // Basis URL validatie - alle recept sites worden nu ondersteund!
    const isValidUrl = url.startsWith("http://") || url.startsWith("https://");

    if (url && !isValidUrl) {
        recipeUrlInput.style.borderColor = "#dc3545";
        recipeUrlInput.title = "URL moet beginnen met http:// of https://";
    } else if (url) {
        recipeUrlInput.style.borderColor = "#28a745";
        recipeUrlInput.title = "Elke receptenwebsite wordt ondersteund dankzij AI-detectie!";
    } else {
        recipeUrlInput.style.borderColor = "";
        recipeUrlInput.title = "";
    }
}

let currentProgress = 0;

function updateLoadingProgress(message, step) {
    const progressContainer = document.querySelector('.loading-progress');
    if (progressContainer) {
        progressContainer.innerHTML = `
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${(step / 4) * 100}%"></div>
            </div>
            <div class="progress-message">${message}</div>
        `;
    }
}

async function analyzeRecipe() {
    try {
        // Determine which tab is active
        const activeTab = document.querySelector('.tab-pane.active');
        const isUrlTab = activeTab && activeTab.id === 'url-tab';

        let inputData = '';
        let analysisType = '';

        const recipeUrlInput = getRecipeUrlInput();
        const analyzeBtn = getAnalyzeBtn();
        const btnText = getBtnText();
        const loader = getLoader();

        if (isUrlTab) {
            if (!recipeUrlInput) {
                showError("URL input niet gevonden", "Element fout");
                return;
            }

            inputData = recipeUrlInput.value.trim();
            analysisType = 'url';

            if (!inputData) {
                showError("Voer eerst een recept URL in", "Geen URL ingevuld");
                recipeUrlInput.focus();
                return;
            }

            // Basis URL validatie
            if (!inputData.startsWith("http://") && !inputData.startsWith("https://")) {
                showError(
                    "De URL moet beginnen met http:// of https://",
                    "Ongeldige URL"
                );
                recipeUrlInput.focus();
                return;
            }
        } else {
            const textArea = window.recipeTextArea || getElement('recipeText');
            if (!textArea) {
                showError("Tekst input niet gevonden", "Element fout");
                return;
            }

            inputData = textArea.value.trim();
            analysisType = 'text';

            if (!inputData) {
                showError("Voer eerst recept tekst in", "Geen tekst ingevuld");
                textArea.focus();
                return;
            }

            if (inputData.length < 20) {
                showError(
                    "De recept tekst is te kort. Voer meer ingrediënten of recept informatie in.",
                    "Tekst te kort"
                );
                textArea.focus();
                return;
            }
        }

        // UI updates voor loading state
        if (analyzeBtn) {
            analyzeBtn.disabled = true;
        }
        if (btnText) {
            btnText.textContent = "Recept wordt geanalyseerd...";
        }
        if (loader) {
            loader.style.display = "block";
        }
        hideError();
        hideResults();

        // Toon vriendelijke loading bericht
        showLoadingMessage();

        // Add progress steps
        updateLoadingProgress("Pagina ophalen...", 1);
        setTimeout(() => updateLoadingProgress("Ingrediënten detecteren...", 2), 2000);
        setTimeout(() => updateLoadingProgress("Voedingswaarden analyseren...", 3), 4000);

        let response;

        if (analysisType === 'url') {
            response = await fetch(`/analyse?url=${encodeURIComponent(inputData)}`);
        } else {
            response = await fetch('/analyse-text', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: inputData })
            });
        }

        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch (parseError) {
                console.error("Failed to parse error response:", parseError);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            throw new Error(
                errorData.detail ||
                    `HTTP ${response.status}: ${response.statusText}`,
            );
        }

        let data;
        try {
            data = await response.json();
        } catch (parseError) {
            console.error("Failed to parse response:", parseError);
            throw new Error("Ongeldige response van server. Probeer opnieuw.");
        }

        // Veilige controle van data structuur
        if (!data || typeof data !== 'object') {
            throw new Error("Ongeldige response structuur van server.");
        }

        // Zorg voor veilige fallbacks voor alle verwachte properties
        const safeData = {
            ...data,
            health_explanation: Array.isArray(data.health_explanation) ? data.health_explanation : [],
            all_ingredients: Array.isArray(data.all_ingredients) ? data.all_ingredients : [],
            swaps: Array.isArray(data.swaps) ? data.swaps : [],
            total_nutrition: data.total_nutrition || {},
            health_goals_scores: data.health_goals_scores || {}
        };

        displayResults(safeData);
    } catch (error) {
        console.error("Analysis Error:", error);

        // Check if error has message property
        const errorMessage = error?.message || error?.detail || String(error);
        console.log("Error message:", errorMessage);

        // Specifieke foutafhandeling met meer detail
        let userMessage = "Er is een onverwachte fout opgetreden. Probeer het later opnieuw.";
        let errorTitle = "Fout bij analyseren";

        if (
            errorMessage.includes("Failed to fetch") ||
            errorMessage.includes("NetworkError")
        ) {
            userMessage = "Geen internetverbinding. Controleer uw verbinding en probeer opnieuw.";
            errorTitle = "Verbindingsfout";
        } else if (errorMessage.includes("niet ondersteund")) {
            userMessage = "Deze website wordt niet ondersteund. Probeer een recept van AH Allerhande of Jumbo.";
            errorTitle = "Website niet ondersteund";
        } else if (errorMessage.includes("429")) {
            userMessage = "Te veel verzoeken. Wacht een minuut en probeer opnieuw.";
            errorTitle = "Te druk";
        } else if (
            errorMessage.includes("geen ingrediënten") ||
            errorMessage.includes("Geen ingrediënten")
        ) {
            userMessage = "Geen ingrediënten gevonden. Dit kan komen door:\\n• Website blokkeert automatische toegang\\n• Pagina laadt te langzaam\\n• URL is geen receptpagina\\n\\nProbeer een andere recept-URL.";
            errorTitle = "Geen ingrediënten gevonden";
        } else if (errorMessage.includes("tijdelijk niet beschikbaar")) {
            userMessage = "De analyseservice is tijdelijk niet beschikbaar. Dit kan komen door serveronderhoud. Probeer het over een paar minuten opnieuw.";
            errorTitle = "Service tijdelijk niet beschikbaar";
        } else if (
            errorMessage.includes("geblokkeerd") ||
            errorMessage.includes("403")
        ) {
            userMessage = "Deze website blokkeert automatische toegang. Probeer een andere recept-URL van een ondersteunde website.";
            errorTitle = "Website blokkeert toegang";
        } else if (errorMessage) {
            userMessage = errorMessage;
        }

        showError(userMessage, errorTitle);

        // Log voor debugging
        console.log("Failed input:", inputData);
        console.log("Error details:", error);
    } finally {
        // Reset UI
        const analyzeBtn = getAnalyzeBtn();
        const btnText = getBtnText();
        const loader = getLoader();

        if (analyzeBtn) {
            analyzeBtn.disabled = false;
        }
        if (btnText) {
            btnText.textContent = "Analyseer Recept";
        }
        if (loader) {
            loader.style.display = "none";
        }
        hideLoadingMessage();
    }
}

function showLoadingMessage() {
    const messages = [
        "🔍 Pagina wordt geanalyseerd...",
        "📊 Ingrediënten worden geëxtraheerd...",
        "🧠 AI analyseert de voedingswaarden...",
        "⚡ Gezondheidsscores worden berekend...",
        "🍽️ Receptanalyse bijna klaar..."
    ];
    const loadingDiv = document.createElement("div");
    loadingDiv.id = "loadingMessage";
    loadingDiv.style.cssText = `
        background: rgba(245, 128, 41, 0.1);
        border: 2px solid rgb(245, 128, 41);
        border-radius: 15px;
        padding: 25px;
        margin: 20px 0;
        text-align: center;
        font-size: 1.2rem;
        color: #d67e16;
    `;
    loadingDiv.innerHTML = "⏳ Even geduld, we analyseren uw recept...";

    // Voeg gezondheidstip toe
    const healthTipDiv = document.createElement("div");
    healthTipDiv.id = "healthTip";
    healthTipDiv.style.cssText = `
        background: rgba(40, 167, 69, 0.1);
        border: 2px solid #28a745;
        border-radius: 15px;
        padding: 20px;
        margin: 15px 0;
        text-align: center;
        font-size: 1.1rem;
        color: #28a745;
        min-height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: opacity ${config.health_tips.fade_duration_ms || 500}ms ease-in-out;
        font-weight: 500;
    `;

    loadingDiv.appendChild(healthTipDiv);

    // Add progress bar
    const progressDiv = document.createElement('div');
    progressDiv.className = 'loading-progress';
    progressDiv.innerHTML = `
        <div class="progress-bar">
            <div class="progress-fill" style="width: 0%"></div>
        </div>
        <div class="progress-message">Pagina ophalen...</div>
    `;
    progressDiv.style.marginTop = '15px';
    loadingDiv.appendChild(progressDiv);

    // Voeg toe na input sectie
    const inputSection = document.querySelector(".input-section");
    if (inputSection) {
        inputSection.insertAdjacentElement("afterend", loadingDiv);
    }

    // Start gezondheidstips
    startHealthTips();
}

function hideLoadingMessage() {
    stopHealthTips();
    const loadingDiv = document.getElementById("loadingMessage");
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

function displayResults(data) {
    const resultsDiv = document.getElementById('results');
    if (!resultsDiv) return;

    if (!data.success) {
        showError(data.message || 'Analyse mislukt');
        return;
    }

    // Update the title
    const titleElement = document.getElementById('recipeTitle');
    if (titleElement) {
        titleElement.textContent = data.recipe_title || 'Recept Analyse';
    }

    // Update nutrition summary
    const nutritionGrid = document.getElementById('nutritionGrid');
    if (nutritionGrid && data.total_nutrition) {
        let nutritionHtml = '';
        if (data.total_nutrition.calories) {
            nutritionHtml += `<div class="nutrition-item"><span class="nutrition-label">Calorieën</span><span class="nutrition-value">${data.total_nutrition.calories}</span></div>`;
        }
        if (data.total_nutrition.protein) {
            nutritionHtml += `<div class="nutrition-item"><span class="nutrition-label">Eiwitten</span><span class="nutrition-value">${data.total_nutrition.protein}g</span></div>`;
        }
        if (data.total_nutrition.carbs) {
            nutritionHtml += `<div class="nutrition-item"><span class="nutrition-label">Koolhydraten</span><span class="nutrition-value">${data.total_nutrition.carbs}g</span></div>`;
        }
        if (data.total_nutrition.fat) {
            nutritionHtml += `<div class="nutrition-item"><span class="nutrition-label">Vetten</span><span class="nutrition-value">${data.total_nutrition.fat}g</span></div>`;
        }
        if (data.total_nutrition.fiber) {
            nutritionHtml += `<div class="nutrition-item"><span class="nutrition-label">Vezels</span><span class="nutrition-value">${data.total_nutrition.fiber}g</span></div>`;
        }
        nutritionGrid.innerHTML = nutritionHtml;
    }

    // Update health goals
    const healthGoals = document.getElementById('healthGoals');
    if (healthGoals && data.health_goals_scores) {
        let goalsHtml = '';
        for (const [goal, score] of Object.entries(data.health_goals_scores)) {
            const percentage = Math.min(100, (score / 10) * 100);
            const color = score >= 7 ? '#4CAF50' : score >= 5 ? '#FF9800' : '#F44336';
            
            goalsHtml += `
                <div class="goal-item">
                    <div class="goal-header">
                        <span class="goal-title">${goal}</span>
                        <span class="goal-score">${score}/10</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${percentage}%; background-color: ${color};"></div>
                    </div>
                </div>
            `;
        }
        healthGoals.innerHTML = goalsHtml;
    }

    // Update health explanation
    const healthExplanation = document.getElementById('healthExplanation');
    if (healthExplanation) {
        let explanationHtml = '';
        if (data.health_explanation && data.health_explanation.length > 0) {
            data.health_explanation.forEach(explanation => {
                explanationHtml += `<div class="explanation-item">${explanation}</div>`;
            });
        } else {
            explanationHtml = '<div class="explanation-item">Geen uitleg beschikbaar.</div>';
        }
        healthExplanation.innerHTML = explanationHtml;
    }

    // Update ingredients
    const allIngredients = document.getElementById('allIngredients');
    if (allIngredients) {
        let ingredientsHtml = '';
        if (data.all_ingredients && data.all_ingredients.length > 0) {
            data.all_ingredients.forEach(ingredient => {
                const healthScore = ingredient.health_score || 5;
                const healthClass = healthScore >= 7 ? 'healthy' : healthScore >= 5 ? 'neutral' : 'unhealthy';
                const healthIcon = healthScore >= 7 ? '✅' : healthScore >= 5 ? '⚠️' : '❌';

                ingredientsHtml += `
                    <div class="ingredient-item ${healthClass}">
                        <div class="ingredient-info">
                            <div class="ingredient-name">${ingredient.name}</div>
                            ${ingredient.details ? `<div class="ingredient-details">${ingredient.details}</div>` : ''}
                            ${ingredient.health_fact ? `<div class="health-fact">${ingredient.health_fact}</div>` : ''}
                            ${ingredient.substitution ? `<div class="substitution">💡 Alternatief: ${ingredient.substitution}</div>` : ''}
                        </div>
                        <div class="health-badge">${healthIcon} ${healthScore}/10</div>
                    </div>
                `;
            });
        } else {
            ingredientsHtml = '<p>Geen ingrediënten gevonden.</p>';
        }
        allIngredients.innerHTML = ingredientsHtml;
    }

    // Update swaps
    const swapsSection = document.getElementById('swapsSection');
    const swapsList = document.getElementById('swapsList');
    if (swapsSection && swapsList) {
        if (data.swaps && data.swaps.length > 0) {
            let swapsHtml = '';
            data.swaps.forEach(swap => {
                swapsHtml += `
                    <div class="swap-item">
                        <div class="swap-from">❌ ${swap.original}</div>
                        <div class="swap-arrow">⬇️</div>
                        <div class="swap-to">✅ ${swap.suggestion}</div>
                        <div style="margin-top: 10px; font-style: italic; color: #666;">${swap.reason}</div>
                    </div>
                `;
            });
            swapsList.innerHTML = swapsHtml;
            swapsSection.style.display = 'block';
        } else {
            swapsSection.style.display = 'none';
        }
    }

    // Show results
    resultsDiv.style.display = 'block';
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

// Add print function
function printResults() {
    window.print();
}

function showError(message, title = "Er is een fout opgetreden") {
    hideLoadingMessage();

    // Update error titel als deze bestaat
    const errorTitle = document.querySelector("#error h3");
    if (errorTitle) {
        errorTitle.textContent = title;
    }

    const errorMessage = document.getElementById("errorMessage");
    const errorDiv = document.getElementById("error");
    const resultsDiv = document.getElementById("results");

    if (errorMessage) {
        errorMessage.textContent = message;
    }
    if (errorDiv) {
        errorDiv.style.display = "block";
        errorDiv.scrollIntoView({ behavior: "smooth" });
        errorDiv.focus();
    }

    // Als er geen error div is, toon in results
    if (!errorDiv && resultsDiv) {
        resultsDiv.innerHTML = `
            <div class="error-message">
                <h3>❌ ${title}</h3>
                <p>${message}</p>
                <p><small>Probeer een andere recept-URL of controleer of de URL correct is.</small></p>
            </div>
        `;
    }

    // Toon fout voor screen readers
    announceToScreenReader(`Fout: ${title}. ${message}`);
}

function hideError() {
    const errorDiv = document.getElementById("error");
    if (errorDiv) {
        errorDiv.style.display = "none";
    }
}

function hideResults() {
    const resultsDiv = document.getElementById("results");
    if (resultsDiv) {
        resultsDiv.style.display = "none";
    }
}

// Toegankelijkheidsfunctie voor screen readers
function announceToScreenReader(message) {
    const announcement = document.createElement("div");
    announcement.setAttribute("aria-live", "polite");
    announcement.setAttribute("aria-atomic", "true");
    announcement.style.position = "absolute";
    announcement.style.left = "-10000px";
    announcement.style.width = "1px";
    announcement.style.height = "1px";
    announcement.style.overflow = "hidden";
    announcement.textContent = message;

    document.body.appendChild(announcement);

    setTimeout(() => {
        document.body.removeChild(announcement);
    }, 1000);
}

// Laad configuratie en gezondheidstips
async function loadConfiguration() {
    try {
        const configResponse = await fetch("/static/config.json");
        if (configResponse.ok) {
            const loadedConfig = await configResponse.json();
            config = { ...config, ...loadedConfig };

            // Update URL examples uit config
            if (config.examples && config.examples.length > 0) {
                exampleUrls = config.examples;
            }

            // Stel default URL in uit config
            const recipeUrlInput = getRecipeUrlInput();
            if (recipeUrlInput) {
                const defaultUrl = config.ui.default_url || exampleUrls[0];
                recipeUrlInput.value = defaultUrl;
            }
        }
    } catch (error) {
        console.log("Configuratie laden mislukt, gebruik standaardwaarden");
        // Vul default URL in als fallback
        const recipeUrlInput = getRecipeUrlInput();
        if (recipeUrlInput) {
            recipeUrlInput.value = exampleUrls[0];
        }
    }
}

async function loadHealthTips() {
    try {
        const tipsResponse = await fetch("/static/health_tips.json");
        if (tipsResponse.ok) {
            const tipsData = await tipsResponse.json();
            healthTips = tipsData.tips;
        }
    } catch (error) {
        console.log("Gezondheidstips laden mislukt");
        healthTips = [
            "Drink voldoende water voor uw gezondheid.",
            "Eet dagelijks groenten en fruit.",
            "Bewegen is goed voor uw lichaam en geest.",
        ];
    }
}

function showHealthTip() {
    if (!config.health_tips.show_tips || healthTips.length === 0) return;

    const tipContainer = document.getElementById("healthTip");
    if (!tipContainer) return;

    // Fade out
    tipContainer.style.opacity = "0";

    setTimeout(() => {
        // Update tekst
        tipContainer.textContent = healthTips[currentTipIndex];
        currentTipIndex = (currentTipIndex + 1) % healthTips.length;

        // Fade in
        tipContainer.style.opacity = "1";
    }, config.health_tips.fade_duration_ms || 500);
}

function startHealthTips() {
    if (!config.health_tips.show_tips || healthTips.length === 0) return;

    // Stop bestaande interval
    if (tipInterval) {
        clearInterval(tipInterval);
    }

    // Toon eerste tip direct
    showHealthTip();

    // Start interval
    tipInterval = setInterval(
        showHealthTip,
        config.health_tips.interval_seconds * 1000,
    );
}

function stopHealthTips() {
    if (tipInterval) {
        clearInterval(tipInterval);
        tipInterval = null;
    }

    const tipContainer = document.getElementById("healthTip");
    if (tipContainer) {
        tipContainer.style.display = "none";
    }
}

// Global error handlers
window.addEventListener('error', function(e) {
    console.error('Global JavaScript error:', e.error);
    if (e.error) {
        showError("Er is een JavaScript fout opgetreden. Herlaad de pagina en probeer opnieuw.", "JavaScript Fout");
    }
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    e.preventDefault();
    showError("Er is een fout opgetreden bij het verwerken van een verzoek. Probeer opnieuw.", "Verzoek Fout");
});

// Keyboard shortcuts voor senioren
document.addEventListener("keydown", (e) => {
    // Alt + A voor analyseren
    if (e.altKey && e.key.toLowerCase() === "a") {
        e.preventDefault();
        analyzeRecipe();
    }

    // Escape om error te sluiten
    if (e.key === "Escape") {
        hideError();
    }
});

// Initialize the page
window.addEventListener("load", async () => {
    try {
        console.log("Sneltoetsen: Alt+A = Analyseren, Escape = Fout sluiten");
        await loadConfiguration();
        await loadHealthTips();
    } catch (error) {
        console.error("Error loading configuration:", error);
    }
});
// DOM elementen
const recipeUrlInput = document.getElementById("recipeUrl");
const analyzeBtn = document.getElementById("analyzeBtn");
const btnText = document.querySelector(".btn-text");
const loader = document.querySelector(".loader");
const resultsDiv = document.getElementById("results");
const errorDiv = document.getElementById("error");
const errorMessage = document.getElementById("errorMessage");

// Health tips functionaliteit
let healthTips = [];
let currentTipIndex = 0;
let tipInterval = null;
let config = {
    health_tips: {
        interval_seconds: 4, // Dit moet overeenkomen met de waarde in config.json
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

// Wordt ingesteld na config laden
recipeUrlInput.placeholder = "Voer een recept-URL in van elke website...";

// Event listeners
analyzeBtn.addEventListener("click", analyzeRecipe);
recipeUrlInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        analyzeRecipe();
    }
});

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
});

// Input validatie met real-time feedback
recipeUrlInput.addEventListener("input", (e) => {
    const url = e.target.value.trim();
    if (url) {
        validateUrl(url);
    }
});

function validateUrl(url) {
    // Basis URL validatie - alle recept sites worden nu ondersteund!
    const isValidUrl = url.startsWith("http://") || url.startsWith("https://");

    if (url && !isValidUrl) {
        recipeUrlInput.style.borderColor = "#dc3545";
        recipeUrlInput.title = "URL moet beginnen met http:// of https://";
    } else if (url) {
        recipeUrlInput.style.borderColor = "#28a745";
        recipeUrlInput.title =
            "Elke receptenwebsite wordt ondersteund dankzij AI-detectie!";
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
        const isUrlTab = activeTab.id === 'url-tab';

        let inputData = '';
        let analysisType = '';

        if (isUrlTab) {
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
            inputData = window.recipeTextArea.value.trim();
            analysisType = 'text';

            if (!inputData) {
                showError("Voer eerst recept tekst in", "Geen tekst ingevuld");
                window.recipeTextArea.focus();
                return;
            }

            if (inputData.length < 20) {
                showError(
                    "De recept tekst is te kort. Voer meer ingrediënten of recept informatie in.",
                    "Tekst te kort"
                );
                window.recipeTextArea.focus();
                return;
            }
        }

        // UI updates voor loading state - meer duidelijk voor senioren
        analyzeBtn.disabled = true;
        btnText.textContent = "Recept wordt geanalyseerd...";
        loader.style.display = "block";
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
        let userMessage =
            "Er is een onverwachte fout opgetreden. Probeer het later opnieuw.";
        let errorTitle = "Fout bij analyseren";

        if (
            errorMessage.includes("Failed to fetch") ||
            errorMessage.includes("NetworkError")
        ) {
            userMessage =
                "Geen internetverbinding. Controleer uw verbinding en probeer opnieuw.";
            errorTitle = "Verbindingsfout";
        } else if (errorMessage.includes("niet ondersteund")) {
            userMessage =
                "Deze website wordt niet ondersteund. Probeer een recept van AH Allerhande of Jumbo.";
            errorTitle = "Website niet ondersteund";
        } else if (errorMessage.includes("429")) {
            userMessage =
                "Te veel verzoeken. Wacht een minuut en probeer opnieuw.";
            errorTitle = "Te druk";
        } else if (
            errorMessage.includes("geen ingrediënten") ||
            errorMessage.includes("Geen ingrediënten")
        ) {
            userMessage =
                "Geen ingrediënten gevonden. Dit kan komen door:\\n• Website blokkeert automatische toegang\\n• Pagina laadt te langzaam\\n• URL is geen receptpagina\\n\\nProbeer een andere recept-URL.";
            errorTitle = "Geen ingrediënten gevonden";
        } else if (errorMessage.includes("tijdelijk niet beschikbaar")) {
            userMessage =
                "De analyseservice is tijdelijk niet beschikbaar. Dit kan komen door serveronderhoud. Probeer het over een paar minuten opnieuw.";
            errorTitle = "Service tijdelijk niet beschikbaar";
        } else if (
            errorMessage.includes("geblokkeerd") ||
            errorMessage.includes("403")
        ) {
            userMessage =
                "Deze website blokkeert automatische toegang. Probeer een andere recept-URL van een ondersteunde website.";
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
        analyzeBtn.disabled = false;
        btnText.textContent = "Analyseer Recept";
        loader.style.display = "none";
        hideLoadingMessage();
    }
}

async function analyzeText() {
    const analyzeBtn = document.getElementById('analyzeTextBtn');
    const textInput = document.getElementById('recipeText');
    const resultsDiv = document.getElementById('results');

    const text = textInput.value.trim();
    if (!text) {
        showError('Voer eerst de recept tekst in.');
        return;
    }

    try {
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = 'Analyseren...';
        resultsDiv.innerHTML = '<div class="loading">Recept wordt geanalyseerd...</div>';

        const response = await fetch('/analyse-text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: text })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Analyse mislukt');
        }

        const result = await response.json();
        displayResults(result);

    } catch (error) {
        console.error('Error:', error);
        showError('Er is een fout opgetreden bij het analyseren van de tekst.');
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = 'Analyseer Tekst';
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
    inputSection.insertAdjacentElement("afterend", loadingDiv);

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

function showSuccessMessage() {
    const successDiv = document.createElement("div");
    successDiv.id = "successMessage";
    successDiv.style.cssText = `
        background: rgba(40, 167, 69, 0.1);
        border: 2px solid #28a745;
        border-radius: 15px;
        padding: 25px;
        margin: 20px 0;
        text-align: center;
        font-size: 1.2rem;
        color: #28a745;
    `;
    successDiv.innerHTML = "✅ Recept succesvol geanalyseerd!";

    const inputSection = document.querySelector(".input-section");
    inputSection.insertAdjacentElement("afterend", successDiv);

    // Verwijder na 2 seconden
    setTimeout(() => {
        successDiv.remove();
    }, 2000);
}

function displayResults(data) {
    const resultsDiv = document.getElementById('results');

    if (!data.success) {
        showError(data.message || 'Analyse mislukt');
        return;
    }

    let html = `
        <div class="results-container">
            <h2>🍽️ ${data.recipe_title}</h2>
            <div class="health-score">
                <h3>Gezondheidscore: ${data.health_score || 'N/A'}/10</h3>
            </div>

            <h3>📋 Ingrediënten (${data.ingredient_count})</h3>
            <div class="ingredients-grid">
    `;

    if (data.all_ingredients && data.all_ingredients.length > 0) {
        data.all_ingredients.forEach(ingredient => {
            const healthScore = ingredient.health_score || 5;
            const healthColor = healthScore >= 7 ? '#4CAF50' : healthScore >= 5 ? '#FF9800' : '#F44336';
            const healthIcon = healthScore >= 7 ? '✅' : healthScore >= 5 ? '⚠️' : '❌';

            html += `
                <div class="ingredient-card" style="border-left: 4px solid ${healthColor}">
                    <div class="ingredient-header">
                        <span class="ingredient-name">${ingredient.name}</span>
                        <span class="health-badge">${healthIcon} ${healthScore}/10</span>
                    </div>
                </div>
            `;
        });
    }

    html += `
            </div>

            <h3>💡 Gezondheidsuitleg</h3>
            <div class="health-explanation">
    `;

    if (data.health_explanation && data.health_explanation.length > 0) {
        data.health_explanation.forEach(explanation => {
            html += `<p>${explanation}</p>`;
        });
    } else {
        html += '<p>Geen uitleg beschikbaar.</p>';
    }

    html += `
            </div>

            <h3>🔄 Gezondere alternatieven</h3>
            <div class="swaps-container">
    `;

    if (data.swaps && data.swaps.length > 0) {
        data.swaps.forEach(swap => {
            html += `
                <div class="swap-card">
                    <strong>Vervang:</strong> ${swap.original}<br>
                    <strong>Door:</strong> ${swap.suggestion}<br>
                    <small><em>${swap.reason}</em></small>
                </div>
            `;
        });
    } else {
        html += '<p>Dit recept bevat al grotendeels gezonde ingrediënten! 🎉</p>';
    }

    html += `
            </div>
        </div>
    `;

    resultsDiv.innerHTML = html;
}

function displayNutritionSummary(nutrition) {
    const container = document.getElementById("nutritionGrid");
    container.innerHTML = "";

    const nutritionLabels = {
        calories: "**Energie** (kcal)",
        protein: "**Eiwitten** (g)",
        carbohydrates: "**Koolhydraten** (g)",
        fiber: "**Vezels** (g)",
        sugar: "**Suikers** (g)",
        fat: "**Vetten** (g)",
        saturated_fat: "**Verzadigde vetten** (g)",
        sodium: "**Natrium** (mg)",
        potassium: "**Kalium** (mg)",
        calcium: "**Calcium** (mg)",
        iron: "**IJzer** (mg)",
        vitamin_c: "**Vitamine C** (mg)",
    };

    Object.entries(nutritionLabels).forEach(([key, label]) => {
        if (nutrition[key] && nutrition[key] > 0) {
            const item = document.createElement("div");
            item.className = "nutrition-item";

            const labelSpan = document.createElement("span");
            labelSpan.className = "nutrition-label";
            labelSpan.innerHTML = label;

            const valueSpan = document.createElement("span");
            valueSpan.className = "nutrition-value";
            valueSpan.textContent = nutrition[key];

            item.appendChild(labelSpan);
            item.appendChild(valueSpan);
            container.appendChild(item);
        }
    });
}

function displayHealthGoals(healthGoals) {
    const container = document.getElementById("healthGoals");
    container.innerHTML = "";

    const goalLabels = {
        general_health: "Algemene gezondheid",
        weight_loss: "Gewicht verliezen",
        muscle_building: "Herstel/Spieren",
        energy_boost: "Meer energie",
        blood_pressure: "Bloeddruk verlagen",
        heart_health: "Hart gezondheid",
        diabetes_control: "Diabetes controle",
        bone_health: "Botgezondheid",
        immune_system: "Immuunsysteem",
        brain_health: "Hersengezondheid"
    };

    // Load saved order from localStorage
    let goalOrder =
        JSON.parse(localStorage.getItem("healthGoalsOrder")) ||
        Object.keys(goalLabels);

    // Make sure all goals are included
    Object.keys(goalLabels).forEach((key) => {
        if (!goalOrder.includes(key)) {
            goalOrder.push(key);
        }
    });

    // Create sortable container
    container.style.position = "relative";

    goalOrder.forEach((key, index) => {
        if (healthGoals[key]) {
            const goalItem = document.createElement("div");
            goalItem.className = "goal-item";
            goalItem.draggable = true;
            goalItem.dataset.goalKey = key;
            goalItem.style.cursor = "move";

            const goalHeader = document.createElement("div");
            goalHeader.className = "goal-header";

            const dragHandle = document.createElement("span");
            dragHandle.className = "drag-handle";
            dragHandle.innerHTML = "⋮⋮";
            dragHandle.style.cssText =
                "margin-right: 10px; color: #666; cursor: move; user-select: none;";

            const goalTitle = document.createElement("span");
            goalTitle.className = "goal-title";
            goalTitle.textContent = goalLabels[key];

            const goalScore = document.createElement("span");
            goalScore.className = "goal-score";
            goalScore.textContent = `${healthGoals[key]}/10`;

            goalHeader.appendChild(dragHandle);
            goalHeader.appendChild(goalTitle);
            goalHeader.appendChild(goalScore);

            const progressBar = document.createElement("div");
            progressBar.className = "progress-bar";

            const progressFill = document.createElement("div");
            progressFill.className = "progress-fill";
            progressFill.style.width = `${(healthGoals[key] / 10) * 100}%`;

            // Kleur op basis van score
            if (healthGoals[key] >= 7) {
                progressFill.style.background = "#28a745";
            } else if (healthGoals[key] >= 5) {
                progressFill.style.background = "#ffc107";
            } else {
                progressFill.style.background = "#dc3545";
            }

            progressBar.appendChild(progressFill);

            goalItem.appendChild(goalHeader);
            goalItem.appendChild(progressBar);

            // Add drag event listeners
            goalItem.addEventListener("dragstart", handleDragStart);
            goalItem.addEventListener("dragover", handleDragOver);
            goalItem.addEventListener("drop", handleDrop);
            goalItem.addEventListener("dragend", handleDragEnd);

            container.appendChild(goalItem);
        }
    });
}

let draggedElement = null;

function handleDragStart(e) {
    draggedElement = this;
    this.style.opacity = "0.5";
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/html", this.outerHTML);
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";

    // Visual feedback
    const afterElement = getDragAfterElement(e.currentTarget.parentNode, e.clientY);
    if (afterElement == null) {
        e.currentTarget.parentNode.appendChild(draggedElement);
    } else {
        e.currentTarget.parentNode.insertBefore(draggedElement, afterElement);
    }
    return false;
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();

    if (draggedElement && draggedElement !== this) {
        // Save new order after drop
        saveGoalsOrder();
    }
    return false;
}

function handleDragEnd(e) {
    this.style.opacity = "1";
    this.classList.remove('dragging');
    draggedElement = null;

    // Clean up any temporary visual changes
    const container = document.getElementById("healthGoals");
    Array.from(container.children).forEach(child => {
        child.style.transform = "";
    });
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.goal-item:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;

        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function saveGoalsOrder() {
    const container = document.getElementById("healthGoals");
    const goalItems = Array.from(container.children);
    const newOrder = goalItems.map((item) => item.dataset.goalKey);

    localStorage.setItem("healthGoalsOrder", JSON.stringify(newOrder));
    console.log("Goals order saved:", newOrder);
}

function printResults() {
    // Maak een printbare versie
    const printWindow = window.open("", "_blank");
    const resultsContent = document.getElementById("results").innerHTML;

    const printHTML = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Recept Analyse - ${document.getElementById("recipeTitle").textContent}</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 20px; }
                .print-btn { display: none; }
                .nutrition-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin: 20px 0; }
                .nutrition-item { display: flex; justify-content: space-between; padding: 8px; background: #f8f9fa; border-radius: 5px; }
                .nutrition-label { font-weight: bold; }
                .goal-item { margin: 15px 0; }
                .goal-header { display: flex; justify-content: space-between; margin-bottom: 5px; font-weight: bold; }
                .progress-bar { height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; }
                .progress-fill { height: 100%; border-radius: 10px; }
                .ingredient-item { padding: 10px; margin: 10px 0; border-left: 4px solid #ccc; background: #f8f9fa; }
                .ingredient-name { font-weight: bold; font-size: 1.1em; }
                .ingredient-details { color: #666; margin: 5px 0; }
                .ingredient-nutrition { font-size: 0.9em; color: #555; margin: 5px 0; }
                .health-fact { font-style: italic; color: #28a745; margin: 5px 0; }
                h1, h2, h3 { color: #333; }
                @media print { body { margin: 0; } }
            </style>
        </head>
        <body>
            ${resultsContent}
        </body>
        </html>
    `;

    printWindow.document.write(printHTML);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
}

function animateScore(targetScore) {
    const scoreElement = document.getElementById("healthScore");
    let currentScore = 0;
    const increment = targetScore / 20; // 20 stappen voor animatie

    const timer = setInterval(() => {
        currentScore += increment;
        if (currentScore >= targetScore) {
            currentScore = targetScore;
            clearInterval(timer);
        }
        scoreElement.textContent = Math.round(currentScore * 10) / 10;
    }, 50);
}

function displayHealthExplanation(explanations) {
    const container = document.getElementById("healthExplanation");
    container.innerHTML = "";

    // Veilige controle of explanations bestaat en een array is
    if (!explanations || !Array.isArray(explanations) || explanations.length === 0) {
        container.innerHTML =
            '<p style="font-style: italic; color: #666;">Geen gedetailleerde uitleg beschikbaar.</p>';
        return;
    }

    explanations.forEach((explanation) => {
        // Veilige controle of explanation een string is
        if (!explanation || typeof explanation !== 'string') {
            return; // Skip deze explanation
        }

        const item = document.createElement("div");
        item.className = "explanation-item";
        item.textContent = explanation;
        container.appendChild(item);

        // Add AI explanation for unhealthy ingredients (only if API key available)
        if (explanation.includes("❌ Minder gezonde ingrediënten")) {
            const unhealthyIngredients = explanation.replace(
                "❌ Minder gezonde ingrediënten (score 1-3): ",
                "",
            );

            // Check if OpenAI is available first
            fetch('/health')
                .then(response => response.json())
                .then(data => {
                    if (!data.openai_available) {
                        console.log("OpenAI API niet beschikbaar - AI knoppen uitgeschakeld");
                        return;
                    }

                    const aiButton = document.createElement("button");
                    aiButton.textContent =
                        "🤖 Krijg AI uitleg waarom dit minder gezond is";
                    aiButton.className = "ai-explanation-btn";
            aiButton.style.cssText = `
                margin-top: 10px;
                padding: 8px 16px;
                background: linear-gradient(45deg, #ff6b6b, #ee5a24);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 0.9rem;
                transition: all 0.3s ease;
            `;

            aiButton.addEventListener("click", () =>
                loadAIExplanation(unhealthyIngredients, aiButton, "unhealthy"),
            );
            aiButton.addEventListener("mouseover", () => {
                aiButton.style.transform = "scale(1.05)";
                aiButton.style.boxShadow =
                    "0 4px 15px rgba(255, 107, 107, 0.4)";
            });
            aiButton.addEventListener("mouseout", () => {
                aiButton.style.transform = "scale(1)";
                aiButton.style.boxShadow = "none";
            });

            item.appendChild(aiButton);
        }

        // Add AI explanation for healthy ingredients
        if (explanation.includes("✅ Gezonde ingrediënten")) {
            const healthyIngredients = explanation.replace(
                "✅ Gezonde ingrediënten (score 7-10): ",
                "",
            );

            const aiButton = document.createElement("button");
            aiButton.textContent =
                "🌱 Ontdek waarom deze ingrediënten zo gezond zijn";
            aiButton.className = "ai-explanation-btn healthy-btn";
            aiButton.style.cssText = `
                margin-top: 10px;
                padding: 8px 16px;
                background: linear-gradient(45deg, #28a745, #20c997);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 0.9rem;
                transition: all 0.3s ease;
            `;

            aiButton.addEventListener("click", () =>
                loadAIExplanation(healthyIngredients, aiButton, "healthy"),
            );
            aiButton.addEventListener("mouseover", () => {
                aiButton.style.transform = "scale(1.05)";
                aiButton.style.boxShadow = "0 4px 15px rgba(40, 167, 69, 0.4)";
            });
            aiButton.addEventListener("mouseout", () => {
                aiButton.style.transform = "scale(1)";
                aiButton.style.boxShadow = "none";
            });

            item.appendChild(aiButton);
        }
    });
}

async function loadIngredientSubstitutions(ingredientName, container) {
    try {
        const response = await fetch(`/ingredient-substitutions?name=${encodeURIComponent(ingredientName)}`);
        const data = await response.json();

        if (data.substitutions && data.substitutions.length > 0) {
            const substitutionText = data.substitutions.join(', ');
            container.innerHTML = `🔄 Gezondere alternatieven: <strong>${substitutionText}</strong>`;
            container.style.cssText = `
                margin: 8px 0;
                padding: 10px;
                background: rgba(32, 201, 151, 0.1);
                border-left: 3px solid #20c997;
                border-radius: 5px;
                font-size: 0.9rem;
                line-height: 1.4;
                color: #444;
            `;
        } else {
            container.style.display = 'none';
        }
    } catch (error) {
        console.error('Failed to load substitutions:', error);
        container.style.display = 'none';
    }
}

async function loadIngredientDescription(ingredientName, healthScore, container) {
    try {
        const isHealthy = healthScore >= 6;
        const response = await fetch(`/ingredient-description?name=${encodeURIComponent(ingredientName)}&healthy=${isHealthy}`);
        const data = await response.json();

        if (data.description) {
            container.innerHTML = `💭 ${data.description}`;
            container.style.cssText = `
                margin: 8px 0;
                padding: 10px;
                background: ${isHealthy ? 'rgba(40, 167, 69, 0.1)' : 'rgba(255, 107, 107, 0.1)'};
                border-left: 3px solid ${isHealthy ? '#28a745' : '#ff6b6b'};
                border-radius: 5px;
                font-size: 0.9rem;
                line-height: 1.4;
                color: #444;
            `;
        } else {
            container.style.display = 'none';
        }
    } catch (error) {
        console.error('Failed to load ingredient description:', error);
        container.style.display = 'none';
    }
}

async function loadAIExplanation(ingredients, button, type = "unhealthy") {
    const originalText = button.textContent;
    button.textContent = "⏳ AI denkt na...";
    button.disabled = true;

    try {
        const endpoint =
            type === "healthy" ? "explain-healthy" : "explain-unhealthy";
        const response = await fetch(
            `/${endpoint}?ingredients=${encodeURIComponent(ingredients)}`,
        );
        const data = await response.json();

        // Create explanation div
        const explanationDiv = document.createElement("div");
        explanationDiv.className = "ai-explanation";

        if (type === "healthy") {
            explanationDiv.style.cssText = `
                margin-top: 15px;
                padding: 15px;
                background: linear-gradient(135deg, #f0fff4 0%, #e6ffed 100%);
                border-left: 4px solid #28a745;
                border-radius: 8px;
                line-height: 1.6;
                font-size: 0.95rem;
                color: #2d3748;
                box-shadow: 0 2px 10px rgba(40, 167, 69, 0.1);
            `;
        } else {
            explanationDiv.style.cssText = `
                margin-top: 15px;
                padding: 15px;
                background: linear-gradient(135deg, #fff5f5 0%, #ffe5e5 100%);
                border-left: 4px solid #ff6b6b;
                border-radius: 8px;
                line-height: 1.6;
                font-size: 0.95rem;
                color: #2d3748;
                box-shadow: 0 2px 10px rgba(255, 107, 107, 0.1);
            `;
        }

        const title = document.createElement("div");
        const icon = type === "healthy" ? "🌱" : "🤖";
        title.innerHTML = `<strong>${icon} AI Voedingsexpert:</strong>`;
        title.style.marginBottom = "10px";

        const content = document.createElement("div");
        content.textContent = data.explanation;

        explanationDiv.appendChild(title);
        explanationDiv.appendChild(content);

        // Replace button with explanation
        button.parentNode.replaceChild(explanationDiv, button);
    } catch (error) {
        console.error("AI explanation failed:", error);
        button.textContent = "❌ AI uitleg mislukt";
        button.style.background = "#dc3545";

        const originalBackground =
            type === "healthy"
                ? "linear-gradient(45deg, #28a745, #20c997)"
                : "linear-gradient(45deg, #ff6b6b, #ee5a24)";

        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;
            button.style.background = originalBackground;
        }, 3000);
    }
}

function displayAllIngredients(ingredients) {
    const container = document.getElementById("allIngredients");
    container.innerHTML = "";

    if (!ingredients || ingredients.length === 0) {
        container.innerHTML =
            '<p style="font-style: italic; color: #666;">Geen ingrediënten gevonden.</p>';
        return;
    }

    ingredients.forEach((ingredient, index) => {
        // Safe ingredient object with fallbacks
        const safeIngredient = {
            name: ingredient?.name || 'Onbekend ingrediënt',
            health_score: ingredient?.health_score || 5,
            original_text: ingredient?.original_text || '',
            quantity: ingredient?.quantity || null,
            unit: ingredient?.unit || null,
            nutrition: ingredient?.nutrition || null,
            health_fact: ingredient?.health_fact || null,
            substitution: ingredient?.substitution || null
        };

        const item = document.createElement("div");
        item.className = "ingredient-item";

        // Categoriseer op basis van health score
        if (safeIngredient.health_score >= 7) {
            item.classList.add("healthy");
        } else if (safeIngredient.health_score >= 4) {
            item.classList.add("neutral");
        } else {
            item.classList.add("unhealthy");
        }

        const info = document.createElement("div");
        info.className = "ingredient-info";

        const name = document.createElement("div");
        name.className = "ingredient-name";
        name.textContent = safeIngredient.name;

        // Verbeterde details met hoeveelheid info
        const details = document.createElement("div");
        details.className = "ingredient-details";

        let detailText = "";
        if (safeIngredient.quantity && safeIngredient.unit) {
            detailText = `**${safeIngredient.quantity} ${safeIngredient.unit}** - ${safeIngredient.name}`;
        } else {
            detailText = safeIngredient.original_text || safeIngredient.name;
        }

        // Safe replace with null check
        if (detailText && typeof detailText === 'string') {
            details.innerHTML = detailText.replace(
                /\*\*(.*?)\*\*/g,
                "<strong>$1</strong>",
            );
        } else {
            details.textContent = safeIngredient.name;
        }

        info.appendChild(name);
        info.appendChild(details);

        // Voedingswaarden per ingrediënt
        if (ingredient.nutrition) {
            const nutrition = ingredient.nutrition;
            const nutritionDiv = document.createElement("div");
            nutritionDiv.className = "ingredient-nutrition";

            const nutritionItems = [];
            if (nutrition.calories > 0)
                nutritionItems.push(`Energie: ${nutrition.calories} kcal/100g`);
            if (nutrition.protein > 0)
                nutritionItems.push(`Eiwitten: ${nutrition.protein}g`);
            if (nutrition.fiber > 0)
                nutritionItems.push(`Vezels: ${nutrition.fiber}g`);
            if (nutrition.sugar > 0)
                nutritionItems.push(`Suikers: ${nutrition.sugar}g`);

            if (nutritionItems.length > 0) {
                nutritionDiv.innerHTML = `📊 ${nutritionItems.join(" • ")}`;
                info.appendChild(nutritionDiv);
            }
        }

        // AI-gegenereerde ingredient uitleg
        if (safeIngredient.name && safeIngredient.name !== 'Onbekend ingrediënt') {
            const descriptionDiv = document.createElement("div");
            descriptionDiv.className = "ingredient-description";
            descriptionDiv.innerHTML = "⏳ AI genereert uitleg...";
            info.appendChild(descriptionDiv);

            // Load AI description
            loadIngredientDescription(safeIngredient.name, safeIngredient.health_score, descriptionDiv);
        }

        // Gezondheidsweetje (alleen als het een echte tip is, niet de generieke tekst)
        if (
            ingredient.health_fact &&
            ingredient.health_fact !==
                "Dit ingrediënt draagt bij aan een gevarieerd en uitgebalanceerd voedingspatroon."
        ) {
            const healthFact = document.createElement("div");
            healthFact.className = "health-fact";
            healthFact.innerHTML = `💡 ${ingredient.health_fact}`;
            info.appendChild(healthFact);
        }

        // AI-gegenereerde vervangingen voor ongezonde ingrediënten
        if (safeIngredient.health_score < 6 && safeIngredient.name !== 'Onbekend ingrediënt') {
            const substitutionDiv = document.createElement("div");
            substitutionDiv.className = "ingredient-substitution";
            substitutionDiv.innerHTML = "⏳ AI zoekt gezondere alternatieven...";
            info.appendChild(substitutionDiv);

            loadIngredientSubstitutions(safeIngredient.name, substitutionDiv);
        }

        // Toon substitutie als beschikbaar (bestaand systeem)
        if (ingredient.substitution) {
            const substitution = document.createElement("div");
            substitution.className = "substitution";
            substitution.textContent = `🔄 Vervang door: ${ingredient.substitution}`;
            info.appendChild(substitution);
        }

        const badge = document.createElement("div");
        badge.className = "health-badge";
        badge.textContent = `${ingredient.health_score}/10`;

        // Kleur badge op basis van score
        if (ingredient.health_score >= 7) {
            badge.style.color = "#28a745";
            badge.style.borderColor = "#28a745";
        } else if (ingredient.health_score >= 4) {
            badge.style.color = "#ffc107";
            badge.style.borderColor = "#ffc107";
        } else {
            badge.style.color = "#dc3545";
            badge.style.borderColor = "#dc3545";
        }

        item.appendChild(info);
        item.appendChild(badge);
        container.appendChild(item);
    });
}

function displaySwaps(swaps) {
    const container = document.getElementById("swapsList");
    container.innerHTML = "";

    swaps.forEach((swap) => {
        const item = document.createElement("div");
        item.className = "swap-item";

        const fromDiv = document.createElement("div");
        fromDiv.className = "swap-from";
        fromDiv.innerHTML = `❌ ${swap.ongezond_ingredient} <span style="font-size: 0.9rem; color: #666;">(score: ${swap.health_score || "onbekend"}/10)</span>`;

        const arrowDiv = document.createElement("div");
        arrowDiv.className = "swap-arrow";
        arrowDiv.textContent = "⬇️ Vervang door:";

        const toDiv = document.createElement("div");
        toDiv.className = "swap-to";
        toDiv.innerHTML = `✅ <strong>${swap.vervang_door}</strong>`;

        item.appendChild(fromDiv);
        item.appendChild(arrowDiv);
        item.appendChild(toDiv);
        container.appendChild(item);
    });
}

function showError(message, title = "Er is een fout opgetreden") {
    hideLoadingMessage();

    // Update error titel als deze bestaat
    const errorTitle = document.querySelector("#error h3");
    if (errorTitle) {
        errorTitle.textContent = title;
    }

    errorMessage.textContent = message;
    errorDiv.style.display = "block";
    errorDiv.scrollIntoView({ behavior: "smooth" });

    // Focus op error voor screen readers
    errorDiv.focus();

    // Toon fout voor screen readers
    announceToScreenReader(`Fout: ${title}. ${message}`);
}

function hideError() {
    errorDiv.style.display = "none";
}

function hideResults() {
    resultsDiv.style.display = "none";
}

function showError(message) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = `
        <div class="error-message">
            <h3>❌ Fout</h3>
            <p>${message}</p>
            <p><small>Probeer een andere recept-URL of controleer of de URL correct is.</small></p>
        </div>
    `;
}

function showTab(tabName) {
    // Hide all tabs
    document.getElementById('url-tab').style.display = 'none';
    document.getElementById('text-tab').style.display = 'none';

    // Show selected tab
    document.getElementById(tabName).style.display = 'block';

    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[onclick="showTab('${tabName}')"]`).classList.add('active');

    // Clear results when switching tabs
    document.getElementById('results').innerHTML = '';
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

// Utility function voor debugging
window.testAnalysis = function () {
    const testUrl = exampleUrls[Math.floor(Math.random() * exampleUrls.length)];
    recipeUrlInput.value = testUrl;
    analyzeRecipe();
};

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
document.addEventListener('DOMContentLoaded', function() {
    // Show URL tab by default
    showTab('url-tab');

    // Add enter key support for URL input
    document.getElementById('recipeUrl').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            analyzeRecipe();
        }
    });

    // Add enter key support for text input (Ctrl+Enter)
    document.getElementById('recipeText').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && e.ctrlKey) {
            analyzeText();
        }
    });
});

// Laad configuratie en gezondheidstips
async function loadConfiguration() {
    try {
        const configResponse = await fetch("/static/config.json");
        if (configResponse.ok) {
            const loadedConfig = await configResponse.json();
            config = { ...config, ...loadedConfig }; // Merge met defaults

            // Update URL examples uit config
            if (config.examples && config.examples.length > 0) {
                exampleUrls = config.examples;
            }

            // Stel default URL in uit config
            const defaultUrl = config.ui.default_url || exampleUrls[0];
            recipeUrlInput.value = defaultUrl;
        }
    } catch (error) {
        console.log("Configuratie laden mislukt, gebruik standaardwaarden");
        // Vul default URL in als fallback
        recipeUrlInput.value = exampleUrls[0];
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
    }, config.tips_fade_duration_ms || 500);
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
    e.preventDefault(); // Prevent default browser behavior
    showError("Er is een fout opgetreden bij het verwerken van een verzoek. Probeer opnieuw.", "Verzoek Fout");
});

// Toon shortcuts info en laad data
window.addEventListener("load", async () => {
    try {
        console.log("Sneltoetsen: Alt+A = Analyseren, Escape = Fout sluiten");
        await loadConfiguration();
        await loadHealthTips();
    } catch (error) {
        console.error("Error loading configuration:", error);
        // Continue with defaults if configuration fails
    }
});

// Configuration loading is already handled above in the main load event listener

// Language support
let currentLanguage = 'nl';
let translations = {};

// Load language file
async function loadLanguage(lang = 'nl') {
    try {
        const response = await fetch('/static/lang.json');
        if (response.ok) {
            translations = await response.json();
            currentLanguage = lang;
            updateUILanguage();
        }
    } catch (error) {
        console.log('Language loading failed, using defaults');
    }
}

function t(key) {
    const keys = key.split('.');
    let value = translations[currentLanguage];

    for (const k of keys) {
        if (value && typeof value === 'object') {
            value = value[k];
        } else {
            break;
        }
    }

    return value || key;
}

function updateUILanguage() {
    // Update static text elements
    const elements = {
        'recipe-analysis-title': t('recipe_analysis'),
        'url-tab-btn': t('url_tab'),
        'text-tab-btn': t('text_tab'),
        'recipe-url-label': t('recipe_url'),
        'recipe-text-label': t('recipe_text'),
        'analyze-btn-text': t('analyze_recipe'),
        'nutrition-title': t('nutrition_per_portion'),
        'health-goals-title': t('health_goals'),
        'health-explanation-title': t('how_we_calculate'),
        'ingredients-title': t('all_ingredients'),
        'swaps-title': t('recommended_swaps')
    };

    Object.entries(elements).forEach(([id, text]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = text;
        }
    });
}

// Portions calculator
let currentPortions = parseInt(localStorage.getItem('savedPortions')) || 4;
let originalNutrition = {};

function savePortions() {
    localStorage.setItem('savedPortions', currentPortions.toString());
}

function loadSavedPortions() {
    const saved = localStorage.getItem('savedPortions');
    if (saved) {
        currentPortions = parseInt(saved);
        console.log('Loaded saved portions:', currentPortions);
    }
}

function createPortionsControl() {
    const savedPortions = localStorage.getItem('savedPortions') || '4';
    return `
        <div class="portions-control">
            <label class="portions-label" for="portions-slider">${t('portions')}:</label>
            <input type="range" 
                   id="portions-slider" 
                   class="portions-slider"
                   min="1" 
                   max="12" 
                   value="${savedPortions}"
                   aria-label="${t('portions')}"
                   title="Stel het aantal personen in"
                   oninput="updatePortions(this.value)">
            <span class="portions-display" id="portions-display">${savedPortions}</span>
        </div>
    `;
}

function updatePortions(newPortions) {
    currentPortions = parseInt(newPortions);
    document.getElementById('portions-display').textContent = currentPortions;
    
    // Save to localStorage
    savePortions();
    console.log('Portions updated and saved:', currentPortions);

    if (Object.keys(originalNutrition).length > 0) {
        updateNutritionDisplay();
    }
}

function updateNutritionDisplay() {
    const nutritionGrid = document.getElementById('nutritionGrid');
    if (!nutritionGrid || !originalNutrition) return;

    // Make sure we use the current portions setting
    const portionMultiplier = currentPortions / 4; // Assuming original is for 4 people
    console.log('Updating nutrition display with multiplier:', portionMultiplier, 'for portions:', currentPortions);

    let nutritionHtml = '';
    const nutritionKeys = {
        'calories': t('calories'),
        'protein': t('protein'),
        'carbs': t('carbs'),
        'fat': t('fat'),
        'fiber': t('fiber')
    };

    Object.entries(nutritionKeys).forEach(([key, label]) => {
        if (originalNutrition[key]) {
            const adjustedValue = Math.round(originalNutrition[key] * portionMultiplier);
            const unit = key === 'calories' ? '' : 'g';
            nutritionHtml += `<div class="nutrition-item"><span class="nutrition-label">${label}</span><span class="nutrition-value">${adjustedValue}${unit}</span></div>`;
        }
    });

    nutritionGrid.innerHTML = nutritionHtml;
}

// Goal hiding functionality
let hiddenGoals = JSON.parse(localStorage.getItem('hiddenHealthGoals')) || [];

function saveHiddenGoals() {
    localStorage.setItem('hiddenHealthGoals', JSON.stringify(hiddenGoals));
}

function toggleGoalVisibility(goalName) {
    const goalElement = document.querySelector(`[data-goal="${goalName}"]`);
    if (!goalElement) return;

    const index = hiddenGoals.indexOf(goalName);
    const isCurrentlyHidden = index > -1;

    if (isCurrentlyHidden) {
        // Show the goal with animation
        hiddenGoals.splice(index, 1);
        goalElement.style.transform = 'translateX(-100%)';
        goalElement.style.opacity = '0';
        goalElement.style.display = 'block';
        
        setTimeout(() => {
            goalElement.style.transition = 'all 0.3s ease-in-out';
            goalElement.style.transform = 'translateX(0)';
            goalElement.style.opacity = '1';
        }, 10);
    } else {
        // Hide the goal with animation
        hiddenGoals.push(goalName);
        goalElement.style.transition = 'all 0.3s ease-in-out';
        goalElement.style.transform = 'translateX(-100%)';
        goalElement.style.opacity = '0';
        
        setTimeout(() => {
            goalElement.style.display = 'none';
            goalElement.style.transform = '';
            goalElement.style.opacity = '';
            goalElement.style.transition = '';
        }, 300);
    }

    saveHiddenGoals();
    
    // Update the button icon immediately
    const hideButton = goalElement.querySelector('.hide-goal-btn');
    if (hideButton) {
        hideButton.innerHTML = isCurrentlyHidden ? 
            (hideIconSVG || '🚫👁️') : 
            (showIconSVG || '👁️');
        hideButton.title = isCurrentlyHidden ? t('hide_goal') : t('show_goal');
    }

    // Update hidden goals toggle after animation
    setTimeout(() => {
        updateHiddenGoalsToggle();
    }, isCurrentlyHidden ? 100 : 350);
}

async function loadSVGIcon(iconPath) {
    try {
        const response = await fetch(iconPath);
        if (response.ok) {
            return await response.text();
        }
    } catch (error) {
        console.log('Failed to load SVG icon:', iconPath);
    }
    return null;
}

let hideIconSVG = null;
let showIconSVG = null;

async function loadIcons() {
    hideIconSVG = await loadSVGIcon('/static/hide_icon.svg');
    showIconSVG = await loadSVGIcon('/static/show_icon.svg');
}

function updateGoalsDisplay() {
    const allGoals = document.querySelectorAll('.goal-item');
    
    allGoals.forEach(goal => {
        const goalDataAttribute = goal.getAttribute('data-goal');
        const titleElement = goal.querySelector('.goal-title');
        const goalName = goalDataAttribute || (titleElement ? titleElement.textContent.trim() : '');

        const isHidden = hiddenGoals.includes(goalName);
        
        // Only update display if it's not already in the correct state
        if (isHidden && goal.style.display !== 'none') {
            goal.style.display = 'none';
        } else if (!isHidden && goal.style.display === 'none') {
            goal.style.display = 'block';
        }

        // Update button icon
        const hideButton = goal.querySelector('.hide-goal-btn');
        if (hideButton) {
            hideButton.innerHTML = isHidden ? 
                (showIconSVG || '👁️') : 
                (hideIconSVG || '🚫👁️');
            hideButton.title = isHidden ? t('show_goal') : t('hide_goal');
        }
    });

    // Show/hide toggle button
    updateHiddenGoalsToggle();
}

function updateHiddenGoalsToggle() {
    const container = document.getElementById('healthGoals');
    if (!container) return;

    let toggleButton = document.getElementById('hidden-goals-toggle');
    let hiddenSection = document.getElementById('hidden-goals-section');

    if (hiddenGoals.length > 0) {
        if (!toggleButton) {
            toggleButton = document.createElement('div');
            toggleButton.id = 'hidden-goals-toggle';
            toggleButton.className = 'hidden-goals-toggle';
            toggleButton.onclick = toggleHiddenGoalsSection;
            container.appendChild(toggleButton);

            hiddenSection = document.createElement('div');
            hiddenSection.id = 'hidden-goals-section';
            hiddenSection.className = 'hidden-goals-section';
            hiddenSection.style.display = 'none';
            container.appendChild(hiddenSection);
        }

        const isExpanded = hiddenSection && hiddenSection.style.display !== 'none';
        toggleButton.innerHTML = `${isExpanded ? t('hide_hidden_goals') : t('show_hidden_goals')} <span style="margin-left: 8px;">${isExpanded ? '▲' : '▼'}</span>`;
        toggleButton.title = `${hiddenGoals.length} verborgen doelen ${isExpanded ? 'verbergen' : 'bekijken'}`;
        toggleButton.style.display = 'block';
        
        // Update hidden section content
        updateHiddenGoalsSection();
    } else {
        if (toggleButton) {
            toggleButton.style.display = 'none';
        }
        if (hiddenSection) {
            hiddenSection.style.display = 'none';
        }
    }
}

function toggleHiddenGoalsSection() {
    const section = document.getElementById('hidden-goals-section');
    const button = document.getElementById('hidden-goals-toggle');

    if (!section || !button) return;

    const isCurrentlyVisible = section.style.display !== 'none';

    if (isCurrentlyVisible) {
        section.style.display = 'none';
        button.innerHTML = `${t('show_hidden_goals')} <span style="margin-left: 8px;">▼</span>`;
    } else {
        section.style.display = 'block';
        button.innerHTML = `${t('hide_hidden_goals')} <span style="margin-left: 8px;">▲</span>`;
        updateHiddenGoalsSection();
    }
}

function updateHiddenGoalsSection() {
    const section = document.getElementById('hidden-goals-section');
    if (!section || hiddenGoals.length === 0) return;

    section.innerHTML = '';

    // Find all hidden goals and add them to the section
    hiddenGoals.forEach(goalName => {
        const originalGoal = document.querySelector(`[data-goal="${goalName}"]`);
        if (originalGoal && originalGoal.style.display === 'none') {
            const clone = originalGoal.cloneNode(true);
            clone.style.display = 'block';
            clone.style.opacity = '0.7';
            clone.style.background = '#f5f5f5';
            
            // Update the hide button to show "show" functionality
            const hideButton = clone.querySelector('.hide-goal-btn');
            if (hideButton) {
                hideButton.innerHTML = showIconSVG || '👁️';
                hideButton.title = t('show_goal');
                hideButton.onclick = () => toggleGoalVisibility(goalName);
            }
            
            section.appendChild(clone);
        }
    });
}

// Enhanced drag and drop with proper drop zones
function setupDragAndDrop() {
    const goalItems = document.querySelectorAll('.goal-item:not([style*="display: none"])');
    let draggedElement = null;
    let dropZones = [];

    function createDropZones() {
        // Remove existing drop zones
        document.querySelectorAll('.drop-zone').forEach(zone => zone.remove());
        dropZones = [];

        const container = document.querySelector('.goals-container');
        if (!container) return;

        goalItems.forEach((item, index) => {
            // Create drop zone before each item
            const dropZone = document.createElement('div');
            dropZone.className = 'drop-zone';
            dropZone.dataset.position = index;
            container.insertBefore(dropZone, item);
            dropZones.push(dropZone);

            // Add drop zone after last item
            if (index === goalItems.length - 1) {
                const lastDropZone = document.createElement('div');
                lastDropZone.className = 'drop-zone';
                lastDropZone.dataset.position = index + 1;
                container.insertBefore(lastDropZone, item.nextSibling);
                dropZones.push(lastDropZone);
            }
        });
    }

    function setupDropZoneEvents() {
        dropZones.forEach(zone => {
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                
                if (draggedElement) {
                    // Clear all active zones
                    document.querySelectorAll('.drop-zone-active').forEach(z => {
                        z.classList.remove('drop-zone-active');
                    });
                    // Set forbidden cursor on goal items
                    document.querySelectorAll('.goal-item').forEach(item => {
                        if (item !== draggedElement) {
                            item.style.cursor = 'not-allowed';
                        }
                    });
                    
                    zone.classList.add('drop-zone-active');
                }
            });

            zone.addEventListener('dragleave', (e) => {
                // Only remove if we're actually leaving the zone
                if (!zone.contains(e.relatedTarget)) {
                    zone.classList.remove('drop-zone-active');
                }
            });

            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                if (draggedElement) {
                    const position = parseInt(zone.dataset.position);
                    const container = zone.parentNode;
                    
                    // Get all current goal items (excluding the dragged one)
                    const currentItems = Array.from(container.querySelectorAll('.goal-item')).filter(item => item !== draggedElement);
                    
                    // Insert at the correct position
                    if (position === 0) {
                        container.insertBefore(draggedElement, container.firstChild);
                    } else if (position >= currentItems.length) {
                        container.appendChild(draggedElement);
                    } else {
                        container.insertBefore(draggedElement, currentItems[position]);
                    }
                    
                    // Clean up
                    cleanupDragState();
                    // Recreate drop zones with new positions
                    createDropZones();
                    setupDropZoneEvents();
                }
            });
        });
    }

    function cleanupDragState() {
        document.querySelectorAll('.drop-zone-active').forEach(z => {
            z.classList.remove('drop-zone-active');
        });
        document.querySelectorAll('.goal-item').forEach(item => {
            item.style.cursor = '';
            item.classList.remove('dragging');
        });
        document.querySelectorAll('.drop-zone').forEach(zone => zone.remove());
        draggedElement = null;
    }

    // Initialize drop zones
    createDropZones();
    setupDropZoneEvents();

    goalItems.forEach(item => {
        const dragHandle = item.querySelector('.drag-handle');
        
        if (dragHandle) {
            dragHandle.addEventListener('dragstart', (e) => {
                draggedElement = item;
                item.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
                
                // Show drop zones
                document.querySelectorAll('.drop-zone').forEach(zone => {
                    zone.style.display = 'block';
                });
            });

            dragHandle.addEventListener('dragend', () => {
                cleanupDragState();
                // Hide drop zones
                document.querySelectorAll('.drop-zone').forEach(zone => {
                    zone.style.display = 'none';
                });
            });
        }

        // Prevent dropping on goal items themselves
        item.addEventListener('dragover', (e) => {
            if (draggedElement && draggedElement !== item) {
                e.dataTransfer.dropEffect = 'none';
                item.style.cursor = 'not-allowed';
            }
        });

        item.addEventListener('dragleave', () => {
            item.style.cursor = '';
        });
    });
}

// Ingredient sorting functionality
let ingredientSortOrder = localStorage.getItem('ingredientSortOrder') || 'alphabet';

function saveIngredientSortOrder() {
    localStorage.setItem('ingredientSortOrder', ingredientSortOrder);
}

function sortIngredients(ingredients, sortOrder) {
    if (sortOrder === 'alphabet') {
        return ingredients.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortOrder === 'health') {
        return ingredients.sort((a, b) => (b.health_score || 5) - (a.health_score || 5));
    }
    return ingredients;
}

function createSortingControl() {
    return `
        <div class="ingredient-sort-control">
            <label for="sort-select">${t('sort_by')}:</label>
            <select id="sort-select" onchange="changeSortOrder(this.value)">
                <option value="alphabet" ${ingredientSortOrder === 'alphabet' ? 'selected' : ''}>${t('alphabet')}</option>
                <option value="health" ${ingredientSortOrder === 'health' ? 'selected' : ''}>${t('health_score')}</option>
            </select>
        </div>
    `;
}

function changeSortOrder(newOrder) {
    ingredientSortOrder = newOrder;
    saveIngredientSortOrder();
    
    // Re-render ingredients with new sort order
    const allIngredients = document.getElementById('allIngredients');
    if (allIngredients && window.currentIngredients) {
        displayIngredientsList(window.currentIngredients);
    }
}

function displayIngredientsList(ingredients) {
    const allIngredients = document.getElementById('allIngredients');
    if (!allIngredients) return;

    let ingredientsHtml = '';
    if (ingredients && ingredients.length > 0) {
        // Sort ingredients based on current sort order
        const sortedIngredients = sortIngredients([...ingredients], ingredientSortOrder);
        
        sortedIngredients.forEach(ingredient => {
            const healthScore = ingredient.health_score || 5;
            const healthClass = healthScore >= 7 ? 'healthy' : healthScore >= 5 ? 'neutral' : 'unhealthy';
            const healthIcon = healthScore >= 7 ? '✅' : healthScore >= 5 ? '⚠️' : '❌';
            const capitalizedName = capitalizeName(ingredient.name);

            ingredientsHtml += `
                <div class="ingredient-item ${healthClass}">
                    <div class="ingredient-info">
                        <div class="ingredient-name">${capitalizedName}</div>
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

function capitalizeName(name) {
    if (!name) return '';
    return name.charAt(0).toUpperCase() + name.slice(1);
}

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
            btnText.textContent = t('analyze_recipe');
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
                console.error("Could not parse error response as JSON:", parseError);
                throw new Error(`HTTP ${response.status}: Server gaf geen geldige JSON response`);
            }
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        let data;
        try {
            data = await response.json();
        } catch (parseError) {
            console.error("Could not parse response as JSON:", parseError);
            throw new Error("Server gaf geen geldige JSON response. Probeer het opnieuw.");
        }

        if (!data || typeof data !== 'object') {
            console.error("Invalid response structure:", data);
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
        let errorMessage = "";
        
        if (error && typeof error === 'object') {
            errorMessage = error.message || error.detail || "Onbekende fout";
        } else if (typeof error === 'string') {
            errorMessage = error;
        } else {
            errorMessage = "Onbekende fout";
        }
        let userMessage = "";
        let errorTitle = "Analyse fout";

        // Check if error is from fetch response
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            userMessage = "Geen internetverbinding. Controleer uw verbinding en probeer opnieuw.";
            errorTitle = "Verbindingsfout";
        } else if (errorMessage.includes("Ongeldige response structuur")) {
            userMessage = "De server gaf een onverwachte respons. Dit kan komen door een tijdelijke storing. Probeer het opnieuw.";
            errorTitle = "Server communicatie fout";
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
            userMessage = "Geen ingrediënten gevonden. Dit kan komen door:\n• Website blokkeert automatische toegang\n• Pagina laadt te langzaam\n• URL is geen receptpagina\n\nProbeer een andere recept-URL.";
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
        } else if (errorMessage && errorMessage !== "Onbekende fout") {
            userMessage = errorMessage;
        } else {
            userMessage = "Er is een onverwachte fout opgetreden. Probeer het later opnieuw.";
        }
        
        console.error("Analysis Error:", error);
        showError(userMessage, errorTitle);
    } finally {
        // Reset UI
        const analyzeBtn = getAnalyzeBtn();
        const btnText = getBtnText();
        const loader = getLoader();

        if (analyzeBtn) {
            analyzeBtn.disabled = false;
        }
        if (btnText) {
            btnText.textContent = t('analyze_recipe');
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
        titleElement.textContent = data.recipe_title || t('recipe_analysis');
    }

    // Store original nutrition for portions calculation
    originalNutrition = data.total_nutrition || {};

    // Update nutrition summary with portions control
    const nutritionGrid = document.getElementById('nutritionGrid');
    const nutritionTitle = document.querySelector('.nutrition-summary h3');
    if (nutritionTitle) {
        nutritionTitle.innerHTML = `${t('nutrition_per_portion')} ${createPortionsControl()}`;
        
        // Make sure the slider reflects the current saved value
        setTimeout(() => {
            const slider = document.getElementById('portions-slider');
            const display = document.getElementById('portions-display');
            if (slider && display) {
                slider.value = currentPortions;
                display.textContent = currentPortions;
            }
        }, 100);
    }

    updateNutritionDisplay();

    // Update health goals with hide/show functionality
    const healthGoals = document.getElementById('healthGoals');
    if (healthGoals && data.health_goals_scores) {
        let goalsHtml = '';
        for (const [goal, score] of Object.entries(data.health_goals_scores)) {
            const percentage = Math.min(100, (score / 10) * 100);
            const color = score >= 7 ? '#4CAF50' : score >= 5 ? '#FF9800' : '#F44336';
            const translatedGoal = t(`health_goals_list.${goal}`) || goal;
            const isHidden = hiddenGoals.includes(goal);

            const hideIcon = isHidden ? 
                (showIconSVG || '👁️') : 
                (hideIconSVG || '🚫👁️');

            goalsHtml += `
                <div class="goal-item" data-goal="${goal}">
                    <div class="goal-header">
                        <span class="goal-title">${translatedGoal}</span>
                        <div class="goal-actions">
                            <span class="goal-score">${score}/10</span>
                            <span class="drag-handle" title="Versleep om volgorde te wijzigen" draggable="true">⋮⋮</span>
                            <button class="hide-goal-btn" 
                                    onclick="toggleGoalVisibility('${goal}')"
                                    title="${isHidden ? t('show_goal') : t('hide_goal')}"
                                    aria-label="${isHidden ? t('show_goal') : t('hide_goal')}">
                                ${hideIcon}
                            </button>
                        </div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${percentage}%; background-color: ${color};"></div>
                    </div>
                </div>
            `;
        }
        healthGoals.innerHTML = goalsHtml;

        // Update goals display and add drag and drop
        updateGoalsDisplay();
        setupDragAndDrop();
    }

    // Update health explanation
    const healthExplanation = document.getElementById('healthExplanation');
    if (healthExplanation) {
        let explanationHtml = '';

        // Add health score explanation first
        if (data.health_score_explanation) {
            explanationHtml += `<div class="explanation-item"><strong>${t('how_we_calculate')}</strong><br>${data.health_score_explanation}</div>`;
        }

        // Add other health explanations
        if (data.health_explanation && data.health_explanation.length > 0) {
            data.health_explanation.forEach(explanation => {
                explanationHtml += `<div class="explanation-item">${explanation}</div>`;
            });
        }

        if (!explanationHtml) {
            explanationHtml = '<div class="explanation-item">Geen uitleg beschikbaar.</div>';
        }

        healthExplanation.innerHTML = explanationHtml;
    }

    // Update ingredients
    const allIngredients = document.getElementById('allIngredients');
    if (allIngredients) {
        // Store ingredients globally for sorting
        window.currentIngredients = data.all_ingredients || [];
        displayIngredientsList(window.currentIngredients);
    }

    // Update ingredients section title with sorting controls
    const ingredientsTitle = document.querySelector('.ingredients-section h3');
    if (ingredientsTitle && !document.getElementById('sort-select')) {
        ingredientsTitle.innerHTML = `${t('all_ingredients')} ${createSortingControl()}`;
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
        await loadLanguage();
        await loadConfiguration();
        await loadHealthTips();
        await loadIcons();
        
        // Load saved preferences
        ingredientSortOrder = localStorage.getItem('ingredientSortOrder') || 'alphabet';
        loadSavedPortions();
        
        console.log('Initialized with saved portions:', currentPortions);
    } catch (error) {
        console.error("Initialization error:", error);
        showError("Er is een fout opgetreden bij het laden van de applicatie.", "Initialisatiefout");
    }
});

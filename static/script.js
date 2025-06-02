// DOM elementen
const recipeUrlInput = document.getElementById('recipeUrl');
const analyzeBtn = document.getElementById('analyzeBtn');
const btnText = document.querySelector('.btn-text');
const loader = document.querySelector('.loader');
const resultsDiv = document.getElementById('results');
const errorDiv = document.getElementById('error');
const errorMessage = document.getElementById('errorMessage');

// Voorbeelden van ondersteunde URLs
const exampleUrls = [
    'https://www.ah.nl/allerhande/recept/R-R1201256/orzosalade-met-asperges-nectarines-en-burrata',
    'https://www.jumbo.com/recepten/pasta-met-doperwten-ricotta-en-munt-999966',
    'https://www.leukerecepten.nl/recepten/couscous-salade-met-feta/',
    'https://www.24kitchen.nl/recepten/pasta-pesto-met-zongedroogde-tomaten'
];

// Vul automatisch de URL in als voorbeeld
recipeUrlInput.value = exampleUrls[0];
recipeUrlInput.placeholder = 'Voer een recept URL in van elke website...';

// Event listeners
analyzeBtn.addEventListener('click', analyzeRecipe);
recipeUrlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        analyzeRecipe();
    }
});

// Input validatie met real-time feedback
recipeUrlInput.addEventListener('input', (e) => {
    const url = e.target.value.trim();
    if (url) {
        validateUrl(url);
    }
});

function validateUrl(url) {
    // Basis URL validatie - alle recept sites worden nu ondersteund!
    const isValidUrl = url.startsWith('http://') || url.startsWith('https://');
    
    if (url && !isValidUrl) {
        recipeUrlInput.style.borderColor = '#dc3545';
        recipeUrlInput.title = 'URL moet beginnen met http:// of https://';
    } else if (url) {
        recipeUrlInput.style.borderColor = '#28a745';
        recipeUrlInput.title = 'Elke recept website wordt ondersteund dankzij AI detectie!';
    } else {
        recipeUrlInput.style.borderColor = '';
        recipeUrlInput.title = '';
    }
}

async function analyzeRecipe() {
    const url = recipeUrlInput.value.trim();

    if (!url) {
        showError('Voer eerst een recept URL in', 'Geen URL ingevuld');
        recipeUrlInput.focus(); // Focus terug naar input
        return;
    }

    // Basis URL validatie
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        showError('De URL moet beginnen met http:// of https://', 'Ongeldige URL');
        recipeUrlInput.focus();
        return;
    }

    // UI updates voor loading state - meer duidelijk voor senioren
    analyzeBtn.disabled = true;
    btnText.textContent = 'Recept wordt geanalyseerd...';
    loader.style.display = 'block';
    hideError();
    hideResults();

    // Toon vriendelijke loading bericht
    showLoadingMessage();

    try {
        const response = await fetch(`/analyse?url=${encodeURIComponent(url)}`);

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        displayResults(data);

    } catch (error) {
        console.error('Analysis Error:', error);

        // Specifieke foutafhandeling met meer detail
        let userMessage = 'Er is een onverwachte fout opgetreden. Probeer het later opnieuw.';
        let errorTitle = 'Fout bij analyseren';

        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
            userMessage = 'Geen internetverbinding. Controleer je verbinding en probeer opnieuw.';
            errorTitle = 'Verbindingsfout';
        } else if (error.message.includes('niet ondersteund')) {
            userMessage = 'Deze website wordt niet ondersteund. Probeer een recept van AH Allerhande of Jumbo.';
            errorTitle = 'Website niet ondersteund';
        } else if (error.message.includes('429')) {
            userMessage = 'Te veel verzoeken. Wacht een minuut en probeer opnieuw.';
            errorTitle = 'Te druk';
        } else if (error.message.includes('geen ingrediënten') || error.message.includes('Geen ingrediënten')) {
            userMessage = 'Geen ingrediënten gevonden. Dit kan komen door:\n• Website blokkeert automatische toegang\n• Pagina laadt te langzaam\n• URL is geen recept-pagina\n\nProbeer een andere recept-URL.';
            errorTitle = 'Geen ingrediënten gevonden';
        } else if (error.message.includes('tijdelijk niet beschikbaar')) {
            userMessage = 'De analyse service is tijdelijk niet beschikbaar. Dit kan komen door server onderhoud. Probeer het over een paar minuten opnieuw.';
            errorTitle = 'Service tijdelijk niet beschikbaar';
        } else if (error.message.includes('geblokkeerd') || error.message.includes('403')) {
            userMessage = 'Deze website blokkeert automatische toegang. Probeer een andere recept-URL van een ondersteunde website.';
            errorTitle = 'Website blokkeert toegang';
        } else if (error.message) {
            userMessage = error.message;
        }

        showError(userMessage, errorTitle);

        // Log voor debugging
        console.log('Failed URL:', url);
        console.log('Error details:', error);
    } finally {
        // Reset UI
        analyzeBtn.disabled = false;
        btnText.textContent = 'Analyseer Recept';
        loader.style.display = 'none';
        hideLoadingMessage();
    }
}

function showLoadingMessage() {
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loadingMessage';
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
    loadingDiv.innerHTML = '⏳ Even geduld, we analyseren uw recept...';

    // Voeg toe na input sectie
    const inputSection = document.querySelector('.input-section');
    inputSection.insertAdjacentElement('afterend', loadingDiv);
}

function hideLoadingMessage() {
    const loadingDiv = document.getElementById('loadingMessage');
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

function showSuccessMessage() {
    const successDiv = document.createElement('div');
    successDiv.id = 'successMessage';
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
    successDiv.innerHTML = '✅ Recept succesvol geanalyseerd!';

    const inputSection = document.querySelector('.input-section');
    inputSection.insertAdjacentElement('afterend', successDiv);

    // Verwijder na 2 seconden
    setTimeout(() => {
        successDiv.remove();
    }, 2000);
}

function displayResults(data) {
    hideLoadingMessage();

    // Update recipe titel
    document.getElementById('recipeTitle').textContent = data.recipe_title || 'Recept Analyse';

    // Update health score met animatie
    const healthScore = data.health_score || 0;
    animateScore(healthScore);

    // Update score circle color based on score
    const scoreCircle = document.querySelector('.score-circle');
    if (healthScore >= 7) {
        scoreCircle.style.background = '#28a745';
    } else if (healthScore >= 5) {
        scoreCircle.style.background = '#ffc107';
    } else {
        scoreCircle.style.background = '#dc3545';
    }

    // Display health explanation
    displayHealthExplanation(data.health_explanation || []);

    // Display all ingredients
    displayAllIngredients(data.all_ingredients || []);

    // Display swaps if available
    if (data.swaps && data.swaps.length > 0) {
        displaySwaps(data.swaps);
        document.getElementById('swapsSection').style.display = 'block';
    } else {
        document.getElementById('swapsSection').style.display = 'none';
    }

    // Show results met smooth scroll
    resultsDiv.style.display = 'block';
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Toon succesmelding voor screen readers
    announceToScreenReader(`Recept analyse compleet. Gezondheidsscore: ${healthScore} van de 10.`);
}

function animateScore(targetScore) {
    const scoreElement = document.getElementById('healthScore');
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
    const container = document.getElementById('healthExplanation');
    container.innerHTML = '';

    if (explanations.length === 0) {
        container.innerHTML = '<p style="font-style: italic; color: #666;">Geen gedetailleerde uitleg beschikbaar.</p>';
        return;
    }

    explanations.forEach(explanation => {
        const item = document.createElement('div');
        item.className = 'explanation-item';
        item.textContent = explanation;
        container.appendChild(item);
    });
}

function displayAllIngredients(ingredients) {
    const container = document.getElementById('allIngredients');
    container.innerHTML = '';

    if (ingredients.length === 0) {
        container.innerHTML = '<p style="font-style: italic; color: #666;">Geen ingrediënten gevonden.</p>';
        return;
    }

    ingredients.forEach((ingredient, index) => {
        const item = document.createElement('div');
        item.className = 'ingredient-item';

        // Categoriseer op basis van health score
        if (ingredient.health_score >= 7) {
            item.classList.add('healthy');
        } else if (ingredient.health_score >= 4) {
            item.classList.add('neutral');
        } else {
            item.classList.add('unhealthy');
        }

        const info = document.createElement('div');
        info.className = 'ingredient-info';

        const name = document.createElement('div');
        name.className = 'ingredient-name';
        name.textContent = ingredient.name;

        const details = document.createElement('div');
        details.className = 'ingredient-details';

        let detailText = ingredient.original_line;
        if (ingredient.amount && ingredient.unit) {
            detailText = `${ingredient.amount} ${ingredient.unit} - ${ingredient.original_line}`;
        }
        details.textContent = detailText;

        info.appendChild(name);
        info.appendChild(details);

        // Toon substitutie als beschikbaar
        if (ingredient.substitution) {
            const substitution = document.createElement('div');
            substitution.className = 'substitution';
            substitution.textContent = `💡 Vervang door: ${ingredient.substitution}`;
            info.appendChild(substitution);
        }

        const badge = document.createElement('div');
        badge.className = 'health-badge';
        badge.textContent = `${ingredient.health_score}/10`;

        // Kleur badge op basis van score
        if (ingredient.health_score >= 7) {
            badge.style.color = '#28a745';
            badge.style.borderColor = '#28a745';
        } else if (ingredient.health_score >= 4) {
            badge.style.color = '#ffc107';
            badge.style.borderColor = '#ffc107';
        } else {
            badge.style.color = '#dc3545';
            badge.style.borderColor = '#dc3545';
        }

        item.appendChild(info);
        item.appendChild(badge);
        container.appendChild(item);
    });
}

function displaySwaps(swaps) {
    const container = document.getElementById('swapsList');
    container.innerHTML = '';

    swaps.forEach(swap => {
        const item = document.createElement('div');
        item.className = 'swap-item';

        const fromDiv = document.createElement('div');
        fromDiv.className = 'swap-from';
        fromDiv.innerHTML = `❌ ${swap.ongezond_ingredient} <span style="font-size: 0.9rem; color: #666;">(score: ${swap.health_score || 'onbekend'}/10)</span>`;

        const arrowDiv = document.createElement('div');
        arrowDiv.className = 'swap-arrow';
        arrowDiv.textContent = '⬇️ Vervang door:';

        const toDiv = document.createElement('div');
        toDiv.className = 'swap-to';
        toDiv.innerHTML = `✅ <strong>${swap.vervang_door}</strong>`;

        item.appendChild(fromDiv);
        item.appendChild(arrowDiv);
        item.appendChild(toDiv);
        container.appendChild(item);
    });
}

function showError(message, title = 'Er is een fout opgetreden') {
    hideLoadingMessage();

    // Update error titel als deze bestaat
    const errorTitle = document.querySelector('#error h3');
    if (errorTitle) {
        errorTitle.textContent = title;
    }

    errorMessage.textContent = message;
    errorDiv.style.display = 'block';
    errorDiv.scrollIntoView({ behavior: 'smooth' });

    // Focus op error voor screen readers
    errorDiv.focus();

    // Toon fout voor screen readers
    announceToScreenReader(`Fout: ${title}. ${message}`);
}

function hideError() {
    errorDiv.style.display = 'none';
}

function hideResults() {
    resultsDiv.style.display = 'none';
}

// Toegankelijkheidsfunctie voor screen readers
function announceToScreenReader(message) {
    const announcement = document.createElement('div');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.style.position = 'absolute';
    announcement.style.left = '-10000px';
    announcement.style.width = '1px';
    announcement.style.height = '1px';
    announcement.style.overflow = 'hidden';
    announcement.textContent = message;

    document.body.appendChild(announcement);

    setTimeout(() => {
        document.body.removeChild(announcement);
    }, 1000);
}

// Utility function voor debugging
window.testAnalysis = function() {
    const testUrl = exampleUrls[Math.floor(Math.random() * exampleUrls.length)];
    recipeUrlInput.value = testUrl;
    analyzeRecipe();
};

// Keyboard shortcuts voor senioren
document.addEventListener('keydown', (e) => {
    // Alt + A voor analyseren
    if (e.altKey && e.key.toLowerCase() === 'a') {
        e.preventDefault();
        analyzeRecipe();
    }

    // Escape om error te sluiten
    if (e.key === 'Escape') {
        hideError();
    }
});

// Toon shortcuts info
window.addEventListener('load', () => {
    console.log('Sneltoetsen: Alt+A = Analyseren, Escape = Fout sluiten');
});
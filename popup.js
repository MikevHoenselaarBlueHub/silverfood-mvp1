// Popup script for Silverfood Chrome Extension
class SilverfoodPopup {
    constructor() {
        // Use current page's origin or fallback to localhost for development
        this.apiUrl = window.location.origin.includes('replit') ? window.location.origin : 'http://localhost:5000';
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.setupEventListeners();
            this.checkCurrentPage();
        });
    }

    setupEventListeners() {
        document.getElementById('analyzeBtn').addEventListener('click', () => {
            this.analyzeCurrentPage();
        });

        document.getElementById('openWebApp').addEventListener('click', () => {
            chrome.tabs.create({url: this.apiUrl});
        });
    }

    async checkCurrentPage() {
        try {
            const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
            document.getElementById('currentUrl').textContent = tab.url;

            // Check if it's likely a recipe page
            const isRecipePage = this.isRecipePage(tab.url);
            if (isRecipePage) {
                document.getElementById('status').innerHTML = '✅ Recept pagina gedetecteerd';
                document.getElementById('analyzeBtn').disabled = false;
            } else {
                document.getElementById('status').innerHTML = '⚠️ Geen recept pagina gedetecteerd';
                document.getElementById('analyzeBtn').disabled = true;
            }
        } catch (error) {
            console.error('Error checking current page:', error);
        }
    }

    isRecipePage(url) {
        const recipeIndicators = [
            'recept', 'recipe', 'cooking', 'kook', 'gerecht',
            'ingredient', 'bereiding', 'allerhande', 'jumbo.com'
        ];

        return recipeIndicators.some(indicator => 
            url.toLowerCase().includes(indicator)
        );
    }

    async analyzeCurrentPage() {
        const analyzeBtn = document.getElementById('analyzeBtn');
        const resultsDiv = document.getElementById('results');

        try {
            analyzeBtn.disabled = true;
            analyzeBtn.textContent = 'Analyseren...';
            resultsDiv.innerHTML = '<div class="loading">Recept wordt geanalyseerd...</div>';

            const [tab] = await chrome.tabs.query({active: true, currentWindow: true});

            const response = await fetch(`${this.apiUrl}/chrome/analyze?url=${encodeURIComponent(tab.url)}`);
            const result = await response.json();

            if (result.success) {
                this.displayResults(result.data);
            } else {
                resultsDiv.innerHTML = `<div class="error">Fout: ${result.error}</div>`;
            }
        } catch (error) {
            resultsDiv.innerHTML = `<div class="error">Netwerkfout: ${error.message}</div>`;
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = 'Analyseer Recept';
        }
    }

    displayResults(data) {
        const resultsDiv = document.getElementById('results');

        const healthScoreColor = data.health_score >= 7 ? '#4CAF50' : 
                                data.health_score >= 5 ? '#FF9800' : '#F44336';

        resultsDiv.innerHTML = `
            <div class="result-card">
                <h3>${data.recipe_title}</h3>
                <div class="health-score" style="color: ${healthScoreColor}">
                    Gezondheidsscore: ${data.health_score}/10
                </div>
                <div class="ingredient-count">
                    ${data.total_ingredients} ingrediënten gevonden
                </div>

                <h4>Top Ingrediënten:</h4>
                <ul class="ingredient-list">
                    ${data.top_ingredients.map(ing => `
                        <li>
                            <span class="ingredient-name">${ing.name}</span>
                            <span class="ingredient-score" style="color: ${ing.health_score >= 7 ? '#4CAF50' : ing.health_score >= 5 ? '#FF9800' : '#F44336'}">
                                ${ing.health_score}/10
                            </span>
                        </li>
                    `).join('')}
                </ul>

                <button id="viewFullReport" class="btn-primary">
                    Bekijk volledige analyse
                </button>
            </div>
        `;

        document.getElementById('viewFullReport').addEventListener('click', () => {
            const [tab] = chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
                const url = `${this.apiUrl}?url=${encodeURIComponent(tabs[0].url)}`;
                chrome.tabs.create({url});
            });
        });
    }
}

// Initialize popup
new SilverfoodPopup();
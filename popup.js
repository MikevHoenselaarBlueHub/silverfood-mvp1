// Popup script for Silverfood Chrome Extension
class SilverfoodPopup {
    constructor() {
        this.translations = {};
        this.currentLanguage = 'nl';
        this.getApiUrlFromConfig();
        this.loadTranslations();
        this.init();
    }

    async loadTranslations() {
        try {
            const response = await fetch(chrome.runtime.getURL('static/lang_nl.json'));
            if (response.ok) {
                this.translations = await response.json();
                this.updateUI();
            }
        } catch (error) {
            console.log('Failed to load translations');
        }
    }

    updateUI() {
        // Update all elements with data-i18n attributes
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            const text = this.t(key);
            if (text !== key) {
                element.textContent = text;
            }
        });
    }

    t(key) {
        const keys = key.split('.');
        let value = this.translations;
        for (const k of keys) {
            if (value && typeof value === 'object') {
                value = value[k];
            } else {
                break;
            }
        }
        return value || key;
    }

    async getApiUrlFromConfig() {
        try {
            // Try to get config from the extension's local environment first
            const defaultUrls = [
                'https://727cfeaf-e405-4336-bdae-5b555824a2d0-00-ceo3089p1ojz.janeway.replit.dev',
                'http://localhost:5000'  // Development URL - works without Core
            ];
            
            // Test each URL to find the working one
            for (const url of defaultUrls) {
                try {
                    const response = await fetch(`${url}/health`, { 
                        method: 'GET',
                        timeout: 3000 
                    });
                    if (response.ok) {
                        this.apiUrl = url;
                        console.log(`✅ API URL configured: ${url}`);
                        return;
                    }
                } catch (e) {
                    console.log(`❌ URL not reachable: ${url}`);
                }
            }
            
            // If no URL works, use the first as default
            this.apiUrl = defaultUrls[0];
            console.log(`⚠️ Using default API URL: ${this.apiUrl}`);
            
        } catch (error) {
            console.error('Error getting API URL:', error);
            this.apiUrl = 'http://localhost:5000';
        }
    }

    init() {
        document.addEventListener('DOMContentLoaded', async () => {
            await this.getApiUrlFromConfig();
            await this.loadTranslations();
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
                document.getElementById('status').innerHTML = `✅ ${this.t('chrome_extension.recipe_detected')}`;
                document.getElementById('analyzeBtn').disabled = false;
            } else {
                document.getElementById('status').innerHTML = `⚠️ ${this.t('chrome_extension.no_recipe_detected')}`;
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
            analyzeBtn.textContent = this.t('chrome_extension.analyzing');
            resultsDiv.innerHTML = `<div class="loading">${this.t('chrome_extension.analyzing')}</div>`;

            const [tab] = await chrome.tabs.query({active: true, currentWindow: true});

            if (!tab.url || (!tab.url.startsWith('http://') && !tab.url.startsWith('https://'))) {
                throw new Error(this.t('chrome_extension.page_not_supported'));
            }

            // Call our API
            const response = await fetch(`${this.apiUrl}/chrome/analyze?url=${encodeURIComponent(tab.url)}`);

            if (!response.ok) {
                throw new Error('API call failed');
            }

            const result = await response.json();

            if (result.success) {
                this.displayResults(result.data);
            } else {
                throw new Error(result.error || 'Analysis failed');
            }

        } catch (error) {
            console.error('Analysis error:', error);
            resultsDiv.innerHTML = `
                <div class="error">
                    <p>❌ ${error.message}</p>
                    <p><small>${this.t('chrome_extension.check_recipe_page')}</small></p>
                </div>
            `;
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = this.t('chrome_extension.analyze_page');
        }
    }

    displayResults(data) {
        const resultsDiv = document.getElementById('results');

        resultsDiv.innerHTML = `
            <div class="results">
                <h3>${data.recipe_title}</h3>
                <div class="score">
                    Gezondheidscore: ${data.health_score}/10
                </div>
                <div class="ingredients">
                    ${data.total_ingredients} ingrediënten gevonden
                </div>
                <div class="top-ingredients">
                    ${data.top_ingredients.map(ing => 
                        `<div class="ingredient">${ing.name} (${ing.health_score}/10)</div>`
                    ).join('')}
                </div>
            </div>
        `;
    }
}

// Initialize when popup loads
document.addEventListener('DOMContentLoaded', () => {
    new SilverfoodPopup();
});

// Silverfood Chrome Extension Popup
class SilverfoodPopup {
    constructor() {
        this.apiUrl = 'http://localhost:5000'; // Will be updated for production
        this.debugMode = false;
        this.cleanup = new Set(); // Track resources for cleanup
        this.init();
    }

    init() {
        this.log('🚀 Silverfood popup initializing...');
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.onDOMReady());
        } else {
            this.onDOMReady();
        }
    }

    onDOMReady() {
        this.log('📄 DOM ready, setting up popup...');
        this.setupEventListeners();
        this.checkCurrentPage();
        this.loadUserPreferences();
        
        // Add cleanup listener for when popup closes
        window.addEventListener('beforeunload', () => this.performCleanup());
    }

    setupEventListeners() {
        this.log('🎯 Setting up event listeners...');
        
        // Main analyze button
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => this.analyzeCurrentPage());
            this.cleanup.add(() => analyzeBtn.removeEventListener('click', this.analyzeCurrentPage));
        }

        // Open web app buttons
        const openWebAppBtns = [
            document.getElementById('openWebApp'),
            document.getElementById('openWebApp2')
        ];
        
        openWebAppBtns.forEach(btn => {
            if (btn) {
                const handler = () => this.openWebApp();
                btn.addEventListener('click', handler);
                this.cleanup.add(() => btn.removeEventListener('click', handler));
            }
        });

        // Debug toggle
        const debugToggle = document.getElementById('debugToggle');
        if (debugToggle) {
            const handler = () => this.toggleDebugMode();
            debugToggle.addEventListener('click', handler);
            this.cleanup.add(() => debugToggle.removeEventListener('click', handler));
        }

        // Keyboard shortcuts
        const keyHandler = (e) => this.handleKeyboard(e);
        document.addEventListener('keydown', keyHandler);
        this.cleanup.add(() => document.removeEventListener('keydown', keyHandler));

        this.log('✅ Event listeners configured');
    }

    async checkCurrentPage() {
        this.log('🔍 Checking current page...');
        
        try {
            const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
            this.log(`📍 Current tab: ${tab.url}`);
            
            const urlDisplay = document.getElementById('currentUrl');
            if (urlDisplay) {
                urlDisplay.textContent = this.truncateUrl(tab.url);
            }

            const isRecipePage = this.isRecipePage(tab.url);
            this.log(`🍽️ Recipe page detected: ${isRecipePage}`);
            
            this.updatePageStatus(isRecipePage, tab.url);
            
        } catch (error) {
            this.logError('❌ Error checking current page:', error);
            this.updatePageStatus(false, null, 'Fout bij laden pagina');
        }
    }

    updatePageStatus(isRecipePage, url, customMessage = null) {
        const statusElement = document.getElementById('status');
        const statusIcon = document.getElementById('statusIcon');
        const analyzeBtn = document.getElementById('analyzeBtn');

        if (customMessage) {
            statusElement.textContent = customMessage;
            statusIcon.textContent = '⚠️';
            analyzeBtn.disabled = true;
            return;
        }

        if (isRecipePage) {
            statusElement.textContent = 'Recept pagina gedetecteerd';
            statusIcon.textContent = '✅';
            analyzeBtn.disabled = false;
            this.log('✅ Recipe page confirmed, analysis enabled');
        } else {
            statusElement.textContent = 'Geen recept pagina gedetecteerd';
            statusIcon.textContent = '⚠️';
            analyzeBtn.disabled = true;
            this.log('⚠️ Not a recipe page, analysis disabled');
        }
    }

    isRecipePage(url) {
        if (!url) return false;

        const recipeIndicators = [
            'recept', 'recipe', 'cooking', 'kook', 'gerecht',
            'ingredient', 'bereiding', 'allerhande', 'jumbo.com',
            'leukerecepten', '24kitchen', 'ah.nl', 'cookpad',
            'smulweb', 'food', 'keuken', 'eten'
        ];

        const urlLower = url.toLowerCase();
        const detected = recipeIndicators.some(indicator => urlLower.includes(indicator));
        
        this.log(`🔍 Recipe detection for ${url}: ${detected} (matched: ${recipeIndicators.filter(i => urlLower.includes(i)).join(', ')})`);
        
        return detected;
    }

    async analyzeCurrentPage() {
        this.log('🔬 Starting recipe analysis...');
        
        const analyzeBtn = document.getElementById('analyzeBtn');
        const resultsDiv = document.getElementById('results');

        try {
            // Update UI to loading state
            this.setLoadingState(true);
            resultsDiv.innerHTML = '<div class="loading">Recept wordt geanalyseerd...</div>';

            const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
            this.log(`📡 Analyzing URL: ${tab.url}`);

            if (!this.isValidUrl(tab.url)) {
                throw new Error('Deze pagina wordt niet ondersteund');
            }

            // Try multiple API endpoints for better reliability
            const result = await this.tryMultipleEndpoints(tab.url);

            if (result.success) {
                this.log('✅ Analysis successful:', result.data);
                this.displayResults(result.data);
                this.saveAnalysisToStorage(tab.url, result.data);
            } else {
                throw new Error(result.error || 'Analysis failed');
            }

        } catch (error) {
            this.logError('❌ Analysis failed:', error);
            this.displayError(error.message);
        } finally {
            this.setLoadingState(false);
        }
    }

    async tryMultipleEndpoints(url) {
        const endpoints = [
            '/extension/analyze',
            '/chrome/analyze',
            '/analyze'
        ];

        for (const endpoint of endpoints) {
            try {
                this.log(`🔗 Trying endpoint: ${endpoint}`);
                
                const response = await fetch(`${this.apiUrl}${endpoint}?url=${encodeURIComponent(url)}`, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    },
                    timeout: 15000
                });

                this.log(`📡 Response from ${endpoint}: ${response.status}`);

                if (response.ok) {
                    const result = await response.json();
                    this.log(`✅ Success with ${endpoint}:`, result);
                    return result;
                }
                
                this.log(`⚠️ ${endpoint} failed with status ${response.status}`);
                
            } catch (error) {
                this.logError(`❌ ${endpoint} error:`, error);
            }
        }

        throw new Error('Alle API endpoints faalden. Controleer de internetverbinding.');
    }

    displayResults(data) {
        const resultsDiv = document.getElementById('results');
        
        const healthScore = data.health_score || 0;
        const totalIngredients = data.total_ingredients || 0;
        const healthyCount = data.healthy_count || 0;
        const recipeTitle = data.recipe_title || 'Recept';
        const topIngredients = data.top_ingredients || [];

        this.log(`📊 Displaying results: Score ${healthScore}/10, ${totalIngredients} ingredients`);

        resultsDiv.innerHTML = `
            <div class="results">
                <div class="health-score">
                    <span class="score-number">${healthScore}</span>
                    <span class="score-label">/ 10 gezondheidscore</span>
                </div>
                
                <div class="ingredients-summary">
                    <div class="stat-card">
                        <div class="stat-number">${totalIngredients}</div>
                        <div class="stat-label">Ingrediënten</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${healthyCount}</div>
                        <div class="stat-label">Gezond</div>
                    </div>
                </div>

                ${topIngredients.length > 0 ? `
                    <div class="top-ingredients">
                        <h4 style="margin-bottom: 10px; font-size: 14px; color: #333;">Top ingrediënten:</h4>
                        ${topIngredients.map(ing => `
                            <div class="ingredient-item">
                                <span class="ingredient-name">${ing.name}</span>
                                <span class="ingredient-score">${ing.health_score}/10</span>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;

        this.log('✅ Results displayed successfully');
    }

    displayError(message) {
        const resultsDiv = document.getElementById('results');
        resultsDiv.innerHTML = `
            <div class="error">
                <p>❌ ${message}</p>
                <p><small>Controleer of dit een receptpagina is en probeer opnieuw.</small></p>
            </div>
        `;
        this.logError('💥 Error displayed to user:', message);
    }

    setLoadingState(loading) {
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = loading;
            analyzeBtn.textContent = loading ? '⏳ Analyseren...' : '🔍 Analyseer Recept';
        }
    }

    async openWebApp() {
        this.log('🌐 Opening full web application...');
        try {
            await chrome.tabs.create({url: this.apiUrl});
            window.close(); // Close popup after opening
        } catch (error) {
            this.logError('❌ Failed to open web app:', error);
        }
    }

    toggleDebugMode() {
        this.debugMode = !this.debugMode;
        const debugToggle = document.getElementById('debugToggle');
        
        if (debugToggle) {
            debugToggle.textContent = this.debugMode ? '🐛 Debug ON' : '🐛 Debug';
            debugToggle.style.background = this.debugMode ? 'rgba(255,0,0,0.3)' : 'rgba(255,255,255,0.2)';
        }

        this.log(`🐛 Debug mode ${this.debugMode ? 'ENABLED' : 'DISABLED'}`);
        
        // Save debug preference
        this.saveUserPreference('debugMode', this.debugMode);
    }

    handleKeyboard(e) {
        // Alt + A = Analyze
        if (e.altKey && e.key.toLowerCase() === 'a') {
            e.preventDefault();
            const analyzeBtn = document.getElementById('analyzeBtn');
            if (analyzeBtn && !analyzeBtn.disabled) {
                this.analyzeCurrentPage();
            }
        }
        
        // Escape = Close error
        if (e.key === 'Escape') {
            const error = document.querySelector('.error');
            if (error) {
                error.remove();
            }
        }
    }

    // Utility functions
    truncateUrl(url, maxLength = 50) {
        if (!url) return 'Geen URL';
        return url.length > maxLength ? url.substring(0, maxLength) + '...' : url;
    }

    isValidUrl(url) {
        return url && (url.startsWith('http://') || url.startsWith('https://'));
    }

    // Storage functions
    async saveAnalysisToStorage(url, data) {
        try {
            const storageKey = `silverfood_analysis_${btoa(url).substring(0, 20)}`;
            const analysisData = {
                url,
                data,
                timestamp: Date.now()
            };
            await chrome.storage.local.set({[storageKey]: analysisData});
            this.log('💾 Analysis saved to storage');
        } catch (error) {
            this.logError('❌ Failed to save analysis:', error);
        }
    }

    async loadUserPreferences() {
        try {
            const result = await chrome.storage.local.get(['debugMode']);
            if (result.debugMode !== undefined) {
                this.debugMode = result.debugMode;
                const debugToggle = document.getElementById('debugToggle');
                if (debugToggle && this.debugMode) {
                    debugToggle.textContent = '🐛 Debug ON';
                    debugToggle.style.background = 'rgba(255,0,0,0.3)';
                }
            }
            this.log('👤 User preferences loaded');
        } catch (error) {
            this.logError('❌ Failed to load preferences:', error);
        }
    }

    async saveUserPreference(key, value) {
        try {
            await chrome.storage.local.set({[key]: value});
            this.log(`💾 Preference saved: ${key} = ${value}`);
        } catch (error) {
            this.logError('❌ Failed to save preference:', error);
        }
    }

    // Cleanup functions
    performCleanup() {
        this.log('🧹 Performing cleanup...');
        this.cleanup.forEach(cleanupFn => {
            try {
                cleanupFn();
            } catch (error) {
                this.logError('❌ Cleanup error:', error);
            }
        });
        this.cleanup.clear();
        this.log('✅ Cleanup completed');
    }

    // Logging functions
    log(...args) {
        if (this.debugMode) {
            console.log('[Silverfood Debug]', ...args);
        }
    }

    logError(...args) {
        console.error('[Silverfood Error]', ...args);
    }
}

// Initialize popup when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🥗 Silverfood Chrome Extension v3.0');
    console.log('Sneltoetsen: Alt+A = Analyseren, Escape = Fout sluiten');
    new SilverfoodPopup();
});

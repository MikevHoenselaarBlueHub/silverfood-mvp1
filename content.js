
// Silverfood Chrome Extension Content Script
class SilverfoodContent {
    constructor() {
        this.debugMode = true;
        this.cleanup = new Set();
        this.isInitialized = false;
        this.floatingButton = null;
        this.init();
    }

    init() {
        this.log('🚀 Silverfood content script initializing...');
        
        // Wait for page to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.onPageReady());
        } else {
            this.onPageReady();
        }
    }

    onPageReady() {
        this.log('📄 Page ready, setting up content features...');
        
        try {
            this.setupMessageListener();
            this.checkForRecipePage();
            this.setupCleanup();
            this.isInitialized = true;
            this.log('✅ Content script initialized successfully');
        } catch (error) {
            this.logError('❌ Content script initialization failed:', error);
        }
    }

    setupMessageListener() {
        const messageHandler = (request, sender, sendResponse) => {
            this.log('📨 Content script received message:', request);
            
            try {
                switch (request.action) {
                    case 'extractRecipe':
                        this.handleExtractRecipe(sendResponse);
                        break;
                        
                    case 'analyzeVisible':
                        this.handleAnalyzeVisible(sendResponse);
                        break;
                        
                    case 'toggleFloatingButton':
                        this.handleToggleFloatingButton(request.show, sendResponse);
                        break;
                        
                    case 'ping':
                        sendResponse({success: true, initialized: this.isInitialized});
                        break;
                        
                    default:
                        this.log('❓ Unknown message action:', request.action);
                        sendResponse({success: false, error: 'Unknown action'});
                }
            } catch (error) {
                this.logError('❌ Error handling message:', error);
                sendResponse({success: false, error: error.message});
            }
            
            return true; // Keep message channel open
        };

        chrome.runtime.onMessage.addListener(messageHandler);
        this.cleanup.add(() => chrome.runtime.onMessage.removeListener(messageHandler));
        
        this.log('👂 Message listener configured');
    }

    checkForRecipePage() {
        const isRecipe = this.isRecipePage();
        this.log(`🍽️ Recipe page check: ${isRecipe}`);
        
        if (isRecipe) {
            this.enhanceRecipePage();
        }
    }

    isRecipePage() {
        const url = window.location.href.toLowerCase();
        const title = document.title.toLowerCase();
        
        const recipeIndicators = [
            'recept', 'recipe', 'cooking', 'kook', 'gerecht',
            'ingredient', 'bereiding', 'allerhande', 'jumbo.com',
            'leukerecepten', '24kitchen', 'ah.nl', 'cookpad',
            'smulweb', 'food', 'keuken', 'eten'
        ];

        return recipeIndicators.some(indicator => 
            url.includes(indicator) || title.includes(indicator)
        );
    }

    enhanceRecipePage() {
        this.log('🎨 Enhancing recipe page with Silverfood features...');
        
        try {
            this.createFloatingButton();
            this.addSilverfoodStyles();
            this.log('✅ Recipe page enhanced');
        } catch (error) {
            this.logError('❌ Failed to enhance recipe page:', error);
        }
    }

    createFloatingButton() {
        if (this.floatingButton) {
            this.log('🔄 Floating button already exists, skipping...');
            return;
        }

        const button = document.createElement('div');
        button.id = 'silverfood-floating-btn';
        button.innerHTML = `
            <div class="silverfood-btn-content">
                <span class="silverfood-icon">🥗</span>
                <span class="silverfood-text">Analyseer</span>
            </div>
        `;

        const clickHandler = () => this.handleFloatingButtonClick();
        button.addEventListener('click', clickHandler);
        this.cleanup.add(() => button.removeEventListener('click', clickHandler));

        document.body.appendChild(button);
        this.floatingButton = button;
        this.cleanup.add(() => {
            if (this.floatingButton && this.floatingButton.parentNode) {
                this.floatingButton.parentNode.removeChild(this.floatingButton);
            }
        });

        this.log('🔘 Floating analyze button created');
    }

    addSilverfoodStyles() {
        if (document.getElementById('silverfood-content-styles')) {
            return; // Styles already added
        }

        const style = document.createElement('style');
        style.id = 'silverfood-content-styles';
        style.textContent = `
            #silverfood-floating-btn {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 10000;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 50px;
                padding: 15px 20px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
                transition: all 0.3s ease;
                user-select: none;
                min-width: 120px;
            }

            #silverfood-floating-btn:hover {
                transform: translateY(-3px);
                box-shadow: 0 6px 25px rgba(102, 126, 234, 0.4);
                background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
            }

            #silverfood-floating-btn:active {
                transform: translateY(-1px);
            }

            .silverfood-btn-content {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }

            .silverfood-icon {
                font-size: 16px;
            }

            .silverfood-text {
                font-weight: 600;
            }

            #silverfood-floating-btn.analyzing {
                background: linear-gradient(135deg, #ffc107 0%, #ff9800 100%);
                pointer-events: none;
            }

            #silverfood-floating-btn.analyzing .silverfood-icon {
                animation: silverfood-spin 1s linear infinite;
            }

            @keyframes silverfood-spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            .silverfood-notification {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10001;
                background: white;
                border: 2px solid #667eea;
                border-radius: 10px;
                padding: 15px 20px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 14px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                max-width: 300px;
                word-wrap: break-word;
            }

            .silverfood-notification.success {
                border-color: #4CAF50;
                background: #f8fff8;
            }

            .silverfood-notification.error {
                border-color: #F44336;
                background: #fff8f8;
            }
        `;

        document.head.appendChild(style);
        this.cleanup.add(() => {
            if (style.parentNode) {
                style.parentNode.removeChild(style);
            }
        });

        this.log('🎨 Silverfood styles added to page');
    }

    async handleFloatingButtonClick() {
        this.log('🔘 Floating button clicked');
        
        try {
            this.setButtonState('analyzing');
            const recipeData = this.extractRecipeFromPage();
            
            // Send to background for analysis
            chrome.runtime.sendMessage({
                action: 'analyzeRecipe',
                data: recipeData
            }, (response) => {
                this.setButtonState('normal');
                if (response && response.success) {
                    this.showNotification('✅ Recept geanalyseerd! Check de extension popup voor details.', 'success');
                } else {
                    this.showNotification('❌ Analyse mislukt. Probeer opnieuw.', 'error');
                }
            });
            
        } catch (error) {
            this.logError('❌ Floating button action failed:', error);
            this.setButtonState('normal');
            this.showNotification('❌ Er ging iets mis. Probeer opnieuw.', 'error');
        }
    }

    setButtonState(state) {
        if (!this.floatingButton) return;

        this.floatingButton.classList.remove('analyzing');
        
        if (state === 'analyzing') {
            this.floatingButton.classList.add('analyzing');
            this.floatingButton.querySelector('.silverfood-text').textContent = 'Bezig...';
            this.floatingButton.querySelector('.silverfood-icon').textContent = '⏳';
        } else {
            this.floatingButton.querySelector('.silverfood-text').textContent = 'Analyseer';
            this.floatingButton.querySelector('.silverfood-icon').textContent = '🥗';
        }
    }

    showNotification(message, type = 'info') {
        // Remove existing notification
        const existing = document.querySelector('.silverfood-notification');
        if (existing) {
            existing.remove();
        }

        const notification = document.createElement('div');
        notification.className = `silverfood-notification ${type}`;
        notification.textContent = message;

        document.body.appendChild(notification);

        // Auto-remove after 4 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 4000);

        this.log(`📢 Notification shown: ${message} (${type})`);
    }

    handleExtractRecipe(sendResponse) {
        try {
            const recipeData = this.extractRecipeFromPage();
            this.log('📋 Recipe extracted:', recipeData);
            sendResponse({success: true, data: recipeData});
        } catch (error) {
            this.logError('❌ Recipe extraction failed:', error);
            sendResponse({success: false, error: error.message});
        }
    }

    extractRecipeFromPage() {
        this.log('📋 Extracting recipe data from page...');

        const recipeData = {
            title: this.extractTitle(),
            ingredients: this.extractIngredients(),
            url: window.location.href,
            domain: window.location.hostname,
            timestamp: Date.now()
        };

        this.log('📊 Extracted recipe data:', recipeData);
        return recipeData;
    }

    extractTitle() {
        const selectors = [
            'h1',
            '.recipe-title',
            '[data-testid="recipe-title"]',
            '.title',
            'h1.recipe-header-title'
        ];

        for (const selector of selectors) {
            const element = document.querySelector(selector);
            if (element && element.textContent.trim()) {
                return element.textContent.trim();
            }
        }

        return document.title || 'Recept';
    }

    extractIngredients() {
        const selectors = [
            '.recipe-ingredient',
            '.ingredient',
            '.ingredients li',
            '[data-testid="ingredient"]',
            '[data-ingredient]',
            '.ingredient-item',
            '.recipe-ingredients-list li',
            'ul[data-testid="ingredients"] li',
            '.ingredients-section li',
            '.ah-ingredient',
            '.allerhande-ingredient'
        ];

        let ingredients = [];

        for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            if (elements.length > 0) {
                ingredients = Array.from(elements)
                    .map(el => el.textContent.trim())
                    .filter(text => text.length > 0 && text.length < 200);
                
                if (ingredients.length > 0) {
                    this.log(`🥕 Found ${ingredients.length} ingredients using selector: ${selector}`);
                    break;
                }
            }
        }

        return ingredients;
    }

    handleAnalyzeVisible(sendResponse) {
        try {
            // Implementation for analyzing visible content
            sendResponse({success: true, message: 'Visible analysis not yet implemented'});
        } catch (error) {
            sendResponse({success: false, error: error.message});
        }
    }

    handleToggleFloatingButton(show, sendResponse) {
        try {
            if (show && !this.floatingButton) {
                this.createFloatingButton();
            } else if (!show && this.floatingButton) {
                this.floatingButton.style.display = 'none';
            } else if (show && this.floatingButton) {
                this.floatingButton.style.display = 'block';
            }
            sendResponse({success: true});
        } catch (error) {
            sendResponse({success: false, error: error.message});
        }
    }

    setupCleanup() {
        // Page unload cleanup
        const unloadHandler = () => this.performCleanup();
        window.addEventListener('beforeunload', unloadHandler);
        this.cleanup.add(() => window.removeEventListener('beforeunload', unloadHandler));

        // Navigation cleanup (for SPAs)
        const popstateHandler = () => {
            this.log('🔄 Page navigation detected, re-checking recipe status...');
            setTimeout(() => this.checkForRecipePage(), 1000);
        };
        window.addEventListener('popstate', popstateHandler);
        this.cleanup.add(() => window.removeEventListener('popstate', popstateHandler));
    }

    performCleanup() {
        this.log('🧹 Performing content script cleanup...');
        
        this.cleanup.forEach(cleanupFn => {
            try {
                cleanupFn();
            } catch (error) {
                this.logError('❌ Cleanup error:', error);
            }
        });
        
        this.cleanup.clear();
        this.log('✅ Content script cleanup completed');
    }

    log(...args) {
        if (this.debugMode) {
            console.log('[Silverfood Content]', ...args);
        }
    }

    logError(...args) {
        console.error('[Silverfood Content ERROR]', ...args);
    }
}

// Initialize content script
const silverfoodContent = new SilverfoodContent();

// Global error handler
window.addEventListener('error', (event) => {
    console.error('[Silverfood Content CRITICAL]', event.error);
});

console.log('🥗 Silverfood Content Script v3.0 loaded');

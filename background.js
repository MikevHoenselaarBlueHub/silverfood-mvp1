// Background script for Chrome extension
class BackgroundService {
    constructor() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Handle extension installation
        chrome.runtime.onInstalled.addListener((details) => {
            if (details.reason === 'install') {
                this.onExtensionInstalled();
            }
        });

        // Handle tab updates to show badge
        chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
            if (changeInfo.status === 'complete' && tab.url) {
                try {
                    // Check if it's a recipe page
                    const isRecipePage = tab.url.includes('recept') || 
                                       tab.url.includes('recipe') || 
                                       tab.url.includes('allerhande') ||
                                       tab.url.includes('jumbo.com');

                    if (isRecipePage) {
                        // Set badge to show it's a recipe page
                        chrome.action.setBadgeText({
                            tabId: tabId,
                            text: '🍽️'
                        });
                        chrome.action.setBadgeBackgroundColor({
                            tabId: tabId, 
                            color: '#4CAF50'
                        });
                    } else {
                        // Clear badge
                        chrome.action.setBadgeText({
                            tabId: tabId,
                            text: ''
                        });
                    }
                } catch (error) {
                    console.error('Background script error:', error);
                }
            }
        });

        // Handle tab activation
        chrome.tabs.onActivated.addListener((activeInfo) => {
            chrome.tabs.get(activeInfo.tabId, (tab) => {
                this.updateBadge(tab);
            });
        });
    }

    onExtensionInstalled() {
        // Set default badge
        chrome.action.setBadgeText({text: ''});
        chrome.action.setBadgeBackgroundColor({color: '#4CAF50'});

        // Open welcome page
        chrome.tabs.create({
            url: 'https://your-replit-app.replit.app'
        });
    }

    async updateBadge(tab) {
        try {
            if (!this.isRecipePage(tab.url)) {
                chrome.action.setBadgeText({text: '', tabId: tab.id});
                return;
            }

            // Quick health check for badge
            const isRecipe = await this.quickRecipeCheck(tab.url);
            if (isRecipe) {
                const response = await fetch(`${window.location.origin}/extension/quick-check?url=${encodeURIComponent(tab.url)}`);
                const data = await response.json();

                if (data.health_score > 0) {
                    const score = Math.round(data.health_score);
                    chrome.action.setBadgeText({
                        text: score.toString(),
                        tabId: tab.id
                    });
                    chrome.action.setBadgeBackgroundColor({
                        color: data.badge_color === 'green' ? '#4CAF50' :
                               data.badge_color === 'yellow' ? '#FFC107' :
                               data.badge_color === 'orange' ? '#FF9800' : '#F44336',
                        tabId: tab.id
                    });
                }
            } else {
                chrome.action.setBadgeText({text: '', tabId: tab.id});
            }
        } catch (error) {
            // Silently fail for badge updates
            chrome.action.setBadgeText({text: '', tabId: tab.id});
        }
    }

    isRecipePage(url) {
        if (!url) return false;

        const recipeIndicators = [
            'recept', 'recipe', 'allerhande', 'jumbo.com/recepten',
            'leukerecepten', '24kitchen', 'ah.nl'
        ];
        return recipeIndicators.some(indicator => 
            url.toLowerCase().includes(indicator)
        );
    }

    async quickRecipeCheck(url) {
        // Simple heuristic check for recipe pages
        return this.isRecipePage(url);
    }
}

// Initialize background service
new BackgroundService();
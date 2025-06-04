
// Silverfood Chrome Extension Background Service Worker
class SilverfoodBackground {
    constructor() {
        this.debugMode = true; // Enable debug by default for development
        this.apiUrl = 'http://localhost:5000'; // Will be updated for production
        this.activeRequests = new Map(); // Track active requests for cleanup
        this.init();
    }

    init() {
        this.log('🚀 Silverfood background service initializing...');
        this.setupEventListeners();
        this.setupCleanupHandlers();
        this.log('✅ Background service ready');
    }

    setupEventListeners() {
        this.log('🎯 Setting up background event listeners...');

        // Extension installation
        chrome.runtime.onInstalled.addListener((details) => {
            this.log('📦 Extension event:', details.reason);
            if (details.reason === 'install') {
                this.onExtensionInstalled();
            } else if (details.reason === 'update') {
                this.onExtensionUpdated(details.previousVersion);
            }
        });

        // Tab updates for badge functionality
        chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
            if (changeInfo.status === 'complete' && tab.url) {
                this.log(`🔄 Tab ${tabId} updated: ${tab.url}`);
                this.handleTabUpdate(tabId, tab);
            }
        });

        // Tab activation
        chrome.tabs.onActivated.addListener((activeInfo) => {
            this.log(`👆 Tab ${activeInfo.tabId} activated`);
            chrome.tabs.get(activeInfo.tabId, (tab) => {
                if (chrome.runtime.lastError) {
                    this.logError('❌ Error getting active tab:', chrome.runtime.lastError);
                    return;
                }
                this.updateBadgeForTab(tab);
            });
        });

        // Message handling from content scripts and popup
        chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
            this.log('📨 Message received:', request);
            this.handleMessage(request, sender, sendResponse);
            return true; // Keep message channel open for async responses
        });

        // Tab removal cleanup
        chrome.tabs.onRemoved.addListener((tabId) => {
            this.log(`🗑️ Tab ${tabId} removed, cleaning up...`);
            this.cleanupTabData(tabId);
        });
    }

    setupCleanupHandlers() {
        this.log('🧹 Setting up cleanup handlers...');
        
        // Cleanup on extension unload/restart
        chrome.runtime.onSuspend.addListener(() => {
            this.log('💤 Extension suspending, performing cleanup...');
            this.performGlobalCleanup();
        });
    }

    onExtensionInstalled() {
        this.log('🎉 Extension installed for the first time');
        
        // Set default badge
        chrome.action.setBadgeText({text: ''});
        chrome.action.setBadgeBackgroundColor({color: '#667eea'});

        // Open welcome page
        chrome.tabs.create({
            url: this.apiUrl
        });

        // Initialize storage
        chrome.storage.local.set({
            'silverfood_installed': Date.now(),
            'silverfood_version': '3.0',
            'debugMode': true
        });

        this.log('✅ Extension installation completed');
    }

    onExtensionUpdated(previousVersion) {
        this.log(`🔄 Extension updated from ${previousVersion} to 3.0`);
        
        // Update storage with new version
        chrome.storage.local.set({
            'silverfood_updated': Date.now(),
            'silverfood_version': '3.0',
            'silverfood_previous_version': previousVersion
        });
    }

    async handleTabUpdate(tabId, tab) {
        try {
            const isRecipePage = this.isRecipePage(tab.url);
            this.log(`🍽️ Tab ${tabId} recipe check: ${isRecipePage} for ${tab.url}`);

            if (isRecipePage) {
                await this.setRecipeBadge(tabId);
                this.log(`✅ Recipe badge set for tab ${tabId}`);
                
                // Optionally get quick health score
                if (this.debugMode) {
                    this.getQuickHealthScore(tab.url, tabId);
                }
            } else {
                await this.clearBadge(tabId);
                this.log(`🧹 Badge cleared for non-recipe tab ${tabId}`);
            }
        } catch (error) {
            this.logError(`❌ Error handling tab ${tabId} update:`, error);
            await this.clearBadge(tabId);
        }
    }

    async updateBadgeForTab(tab) {
        try {
            if (!this.isRecipePage(tab.url)) {
                await this.clearBadge(tab.id);
                return;
            }

            await this.setRecipeBadge(tab.id);
            this.log(`🔄 Badge updated for active tab ${tab.id}`);
            
        } catch (error) {
            this.logError(`❌ Error updating badge for tab ${tab.id}:`, error);
            await this.clearBadge(tab.id);
        }
    }

    async getQuickHealthScore(url, tabId) {
        const requestId = `${tabId}_${Date.now()}`;
        this.log(`⚡ Getting quick health score for tab ${tabId}, request ${requestId}`);
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            
            this.activeRequests.set(requestId, { controller, timeoutId });

            const response = await fetch(`${this.apiUrl}/extension/quick-check?url=${encodeURIComponent(url)}`, {
                signal: controller.signal,
                headers: {
                    'Accept': 'application/json'
                }
            });

            clearTimeout(timeoutId);
            this.activeRequests.delete(requestId);

            if (response.ok) {
                const data = await response.json();
                this.log(`📊 Quick health score for tab ${tabId}:`, data);
                
                if (data.health_score > 0) {
                    await this.setHealthScoreBadge(tabId, data.health_score, data.badge_color);
                }
            }
        } catch (error) {
            this.activeRequests.delete(requestId);
            if (error.name !== 'AbortError') {
                this.logError(`❌ Quick health check failed for tab ${tabId}:`, error);
            }
        }
    }

    async setRecipeBadge(tabId) {
        await chrome.action.setBadgeText({
            tabId: tabId,
            text: '🍽️'
        });
        await chrome.action.setBadgeBackgroundColor({
            tabId: tabId,
            color: '#667eea'
        });
    }

    async setHealthScoreBadge(tabId, score, badgeColor) {
        const roundedScore = Math.round(score);
        const colors = {
            'green': '#4CAF50',
            'yellow': '#FFC107',
            'orange': '#FF9800',
            'red': '#F44336'
        };

        await chrome.action.setBadgeText({
            tabId: tabId,
            text: roundedScore.toString()
        });
        await chrome.action.setBadgeBackgroundColor({
            tabId: tabId,
            color: colors[badgeColor] || '#667eea'
        });

        this.log(`🏷️ Health badge set for tab ${tabId}: ${roundedScore} (${badgeColor})`);
    }

    async clearBadge(tabId) {
        await chrome.action.setBadgeText({
            tabId: tabId,
            text: ''
        });
    }

    isRecipePage(url) {
        if (!url) return false;

        const recipeIndicators = [
            'recept', 'recipe', 'allerhande', 'jumbo.com',
            'leukerecepten', '24kitchen', 'ah.nl', 'cookpad',
            'smulweb', 'food', 'keuken', 'eten', 'cooking',
            'ingredient', 'bereiding', 'kook', 'gerecht'
        ];

        const urlLower = url.toLowerCase();
        const isRecipe = recipeIndicators.some(indicator => urlLower.includes(indicator));
        
        if (this.debugMode) {
            this.log(`🔍 Recipe page check for ${url}: ${isRecipe}`);
        }
        
        return isRecipe;
    }

    async handleMessage(request, sender, sendResponse) {
        try {
            this.log('📨 Processing message:', request.action);

            switch (request.action) {
                case 'getHealthScore':
                    await this.handleHealthScoreRequest(request, sendResponse);
                    break;
                
                case 'toggleDebug':
                    this.debugMode = !this.debugMode;
                    await chrome.storage.local.set({'debugMode': this.debugMode});
                    this.log(`🐛 Debug mode toggled: ${this.debugMode}`);
                    sendResponse({success: true, debugMode: this.debugMode});
                    break;
                
                case 'ping':
                    sendResponse({success: true, timestamp: Date.now()});
                    break;
                
                default:
                    this.log('❓ Unknown message action:', request.action);
                    sendResponse({success: false, error: 'Unknown action'});
            }
        } catch (error) {
            this.logError('❌ Error handling message:', error);
            sendResponse({success: false, error: error.message});
        }
    }

    async handleHealthScoreRequest(request, sendResponse) {
        try {
            const response = await fetch(`${this.apiUrl}/extension/quick-check?url=${encodeURIComponent(request.url)}`);
            const data = await response.json();
            sendResponse({success: true, data});
        } catch (error) {
            this.logError('❌ Health score request failed:', error);
            sendResponse({success: false, error: error.message});
        }
    }

    cleanupTabData(tabId) {
        // Cancel any active requests for this tab
        for (const [requestId, request] of this.activeRequests.entries()) {
            if (requestId.startsWith(`${tabId}_`)) {
                clearTimeout(request.timeoutId);
                request.controller.abort();
                this.activeRequests.delete(requestId);
                this.log(`🧹 Cleaned up request ${requestId} for closed tab`);
            }
        }
    }

    performGlobalCleanup() {
        this.log('🧹 Performing global cleanup...');
        
        // Cancel all active requests
        for (const [requestId, request] of this.activeRequests.entries()) {
            clearTimeout(request.timeoutId);
            request.controller.abort();
            this.log(`🧹 Cancelled request ${requestId}`);
        }
        this.activeRequests.clear();
        
        this.log('✅ Global cleanup completed');
    }

    log(...args) {
        if (this.debugMode) {
            console.log('[Silverfood Background]', new Date().toISOString(), ...args);
        }
    }

    logError(...args) {
        console.error('[Silverfood Background ERROR]', new Date().toISOString(), ...args);
    }
}

// Initialize background service
const silverfoodBackground = new SilverfoodBackground();

// Global error handler
self.addEventListener('error', (event) => {
    console.error('[Silverfood Background CRITICAL]', event.error);
});

self.addEventListener('unhandledrejection', (event) => {
    console.error('[Silverfood Background PROMISE REJECTION]', event.reason);
});

console.log('🥗 Silverfood Background Service Worker v3.0 loaded');

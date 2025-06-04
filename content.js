// Content script for Silverfood Chrome Extension
class SilverfoodContentScript {
    constructor() {
        // Dynamic API URL detection
        this.apiUrl = this.detectApiUrl();
        this.init();
    }

    detectApiUrl() {
        // Try to get from extension storage or use current origin
        if (window.location.origin.includes('replit')) {
            return window.location.origin;
        }
        return 'http://localhost:5000';  // Development fallback
    }

    init() {
        // Listen for messages from popup
        chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
            if (message.action === 'analyzeCurrentPage') {
                this.analyzeCurrentPage().then(sendResponse);
                return true; // Indicates async response
            }
        });

        // Auto-detect recipe pages
        this.detectRecipePage();
    }

    async analyzeCurrentPage() {
        try {
            const url = window.location.href;
            const response = await fetch(`${this.apiUrl}/chrome/analyze?url=${encodeURIComponent(url)}`);
            const result = await response.json();

            return result;
        } catch (error) {
            return {
                success: false,
                error: 'Failed to analyze page: ' + error.message
            };
        }
    }

    detectRecipePage() {
        // Simple recipe page detection
        const indicators = [
            'recipe', 'recept', 'ingredient', 'cooking',
            'bereiding', 'kook', 'gerecht'
        ];

        const pageText = document.body.textContent.toLowerCase();
        const hasRecipeIndicators = indicators.some(indicator => 
            pageText.includes(indicator)
        );

        if (hasRecipeIndicators) {
            this.showRecipeDetectedNotification();
        }
    }

    showRecipeDetectedNotification() {
        // Create subtle notification that recipe was detected
        const notification = document.createElement('div');
        notification.id = 'silverfood-notification';
        notification.innerHTML = `
            <div style="
                position: fixed;
                top: 20px;
                right: 20px;
                background: #4CAF50;
                color: white;
                padding: 10px 15px;
                border-radius: 5px;
                z-index: 10000;
                font-family: Arial, sans-serif;
                font-size: 14px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                cursor: pointer;
            ">
                🍽️ Recept gedetecteerd - Klik hier voor gezondheidsanalyse
            </div>
        `;

        document.body.appendChild(notification);

        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);

        // Click to open extension popup
        notification.addEventListener('click', () => {
            chrome.runtime.sendMessage({action: 'openPopup'});
        });
    }
}

// Initialize content script
new SilverfoodContentScript();
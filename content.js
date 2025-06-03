
// Content script for Chrome extension
class ContentScript {
    constructor() {
        this.init();
    }
    
    init() {
        // Only run on recipe pages
        if (this.isRecipePage()) {
            this.injectAnalyzeButton();
            this.setupMessageListener();
        }
    }
    
    isRecipePage() {
        const recipeIndicators = [
            'recept', 'recipe', 'ingredient'
        ];
        
        const pageText = document.body.textContent.toLowerCase();
        const url = window.location.href.toLowerCase();
        
        return recipeIndicators.some(indicator => 
            pageText.includes(indicator) || url.includes(indicator)
        );
    }
    
    injectAnalyzeButton() {
        // Create floating analyze button
        const button = document.createElement('div');
        button.id = 'silverfood-analyze-btn';
        button.innerHTML = `
            <div style="
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 12px 20px;
                border-radius: 25px;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 8px;
            " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                🍽️ Analyze Recipe
            </div>
        `;
        
        button.addEventListener('click', () => {
            this.quickAnalyze();
        });
        
        document.body.appendChild(button);
    }
    
    async quickAnalyze() {
        const button = document.getElementById('silverfood-analyze-btn');
        const originalContent = button.innerHTML;
        
        button.innerHTML = `
            <div style="
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                background: #4CAF50;
                color: white;
                padding: 12px 20px;
                border-radius: 25px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 500;
                display: flex;
                align-items: center;
                gap: 8px;
            ">
                ⏳ Analyzing...
            </div>
        `;
        
        try {
            const response = await fetch(`https://your-replit-app.replit.app/extension/quick-check?url=${encodeURIComponent(window.location.href)}`);
            const data = await response.json();
            
            this.showQuickResult(data);
        } catch (error) {
            this.showError('Analysis failed');
        }
        
        // Restore button after 3 seconds
        setTimeout(() => {
            button.innerHTML = originalContent;
        }, 3000);
    }
    
    showQuickResult(data) {
        const button = document.getElementById('silverfood-analyze-btn');
        const score = data.health_score || 0;
        const color = score >= 8 ? '#4CAF50' : score >= 6 ? '#FFC107' : score >= 4 ? '#FF9800' : '#F44336';
        
        button.innerHTML = `
            <div style="
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                background: ${color};
                color: white;
                padding: 12px 20px;
                border-radius: 25px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 500;
                display: flex;
                align-items: center;
                gap: 8px;
            ">
                🎯 Health Score: ${score}/10
            </div>
        `;
    }
    
    showError(message) {
        const button = document.getElementById('silverfood-analyze-btn');
        button.innerHTML = `
            <div style="
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                background: #F44336;
                color: white;
                padding: 12px 20px;
                border-radius: 25px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 500;
                display: flex;
                align-items: center;
                gap: 8px;
            ">
                ❌ ${message}
            </div>
        `;
    }
    
    setupMessageListener() {
        chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
            if (request.action === 'analyze') {
                this.quickAnalyze();
            }
        });
    }
}

// Initialize content script
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new ContentScript());
} else {
    new ContentScript();
}

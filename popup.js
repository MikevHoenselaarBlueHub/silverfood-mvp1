
// Chrome Extension Popup JavaScript
class RecipeAnalyzer {
    constructor() {
        this.apiUrl = 'https://your-replit-app.replit.app'; // Update with your Replit URL
        this.init();
    }
    
    async init() {
        try {
            const tab = await this.getCurrentTab();
            if (this.isRecipePage(tab.url)) {
                await this.analyzeRecipe(tab.url);
            } else {
                this.showNoRecipe();
            }
        } catch (error) {
            this.showError('Failed to analyze page');
        }
        
        this.setupEventListeners();
    }
    
    async getCurrentTab() {
        return new Promise((resolve) => {
            chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
                resolve(tabs[0]);
            });
        });
    }
    
    isRecipePage(url) {
        const recipeIndicators = [
            'recept', 'recipe', 'allerhande', 'jumbo.com/recepten',
            'leukerecepten', '24kitchen', 'ah.nl'
        ];
        return recipeIndicators.some(indicator => 
            url.toLowerCase().includes(indicator)
        );
    }
    
    async analyzeRecipe(url) {
        try {
            const response = await fetch(`${this.apiUrl}/extension/analyze?url=${encodeURIComponent(url)}`);
            const data = await response.json();
            
            if (data.success) {
                this.showResults(data);
            } else {
                this.showError(data.error || 'Analysis failed');
            }
        } catch (error) {
            this.showError('Network error occurred');
        }
    }
    
    showResults(data) {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('results').style.display = 'block';
        
        // Update health score
        const scoreValue = document.getElementById('score-value');
        const scoreCircle = document.getElementById('score-circle');
        const scoreText = document.getElementById('score-text');
        
        scoreValue.textContent = data.health_score;
        scoreText.textContent = `Health Score (${data.total_ingredients} ingredients)`;
        
        // Set score color
        scoreCircle.className = 'score-circle';
        if (data.health_score >= 8) scoreCircle.classList.add('score-excellent');
        else if (data.health_score >= 6) scoreCircle.classList.add('score-good');
        else if (data.health_score >= 4) scoreCircle.classList.add('score-fair');
        else scoreCircle.classList.add('score-poor');
        
        // Update summary
        document.getElementById('summary').innerHTML = `
            <div style="text-align: center; margin: 15px 0;">
                ${data.quick_summary}
            </div>
        `;
        
        // Update suggestions
        const suggestionsList = document.getElementById('suggestions-list');
        if (data.suggestions && data.suggestions.length > 0) {
            suggestionsList.innerHTML = data.suggestions.map(suggestion => `
                <div class="suggestion-item">
                    <strong>${suggestion.ongezond_ingredient}</strong> → ${suggestion.vervang_door}
                </div>
            `).join('');
        } else {
            suggestionsList.innerHTML = '<div class="suggestion-item">No improvements needed! 🎉</div>';
        }
    }
    
    showNoRecipe() {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('no-recipe').style.display = 'block';
    }
    
    showError(message) {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'block';
        document.getElementById('error-message').textContent = message;
    }
    
    setupEventListeners() {
        document.getElementById('manual-analyze')?.addEventListener('click', async () => {
            const tab = await this.getCurrentTab();
            document.getElementById('no-recipe').style.display = 'none';
            document.getElementById('loading').style.display = 'block';
            await this.analyzeRecipe(tab.url);
        });
        
        document.getElementById('retry')?.addEventListener('click', async () => {
            document.getElementById('error').style.display = 'none';
            document.getElementById('loading').style.display = 'block';
            const tab = await this.getCurrentTab();
            await this.analyzeRecipe(tab.url);
        });
        
        document.getElementById('view-full')?.addEventListener('click', async () => {
            const tab = await this.getCurrentTab();
            const fullUrl = `${this.apiUrl}?url=${encodeURIComponent(tab.url)}`;
            chrome.tabs.create({ url: fullUrl });
        });
    }
}

// Initialize when popup loads
document.addEventListener('DOMContentLoaded', () => {
    new RecipeAnalyzer();
});

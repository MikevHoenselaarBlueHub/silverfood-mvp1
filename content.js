// Content script for Silverfood Chrome Extension
console.log('Silverfood content script loaded');

// Configuration for Replit deployment
const API_URL = 'https://[YOUR-REPL-NAME].[YOUR-USERNAME].repl.co';

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'extractRecipe') {
        try {
            const recipeData = extractRecipeFromPage();
            sendResponse({success: true, data: recipeData});
        } catch (error) {
            sendResponse({success: false, error: error.message});
        }
    }
    return true; // Keep message channel open for async response
});

function extractRecipeFromPage() {
    try {
        // Try to extract recipe title
        let title = document.querySelector('h1')?.textContent || 
                    document.querySelector('.recipe-title')?.textContent || 
                    document.title;

        // Try to find ingredients
        let ingredients = [];

        // Common ingredient selectors
        const ingredientSelectors = [
            '.recipe-ingredient',
            '.ingredient',
            '.ingredients li',
            '[data-ingredient]',
            '.recipe-ingredients li'
        ];

        for (const selector of ingredientSelectors) {
            const elements = document.querySelectorAll(selector);
            if (elements.length > 0) {
                ingredients = Array.from(elements).map(el => el.textContent.trim());
                break;
            }
        }

        return {
            title: title,
            ingredients: ingredients,
            url: window.location.href
        };
    } catch (error) {
        console.error('Error extracting recipe:', error);
        throw error;
    }
}
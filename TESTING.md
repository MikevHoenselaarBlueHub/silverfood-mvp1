
# 🧪 Silverfood Testing Guide

Dit document beschrijft hoe je de functionaliteit van Silverfood kunt testen om ervoor te zorgen dat alles correct werkt na wijzigingen.

## Quick Start

```bash
# Run alle tests automatisch
python run_tests.py
```

## Test Types

### 1. API Functionality Tests (`test_functionality.py`)

Test alle backend API endpoints:
- ✅ API health check
- ✅ Static file serving
- ✅ URL-based recipe analysis  
- ✅ Text-based recipe analysis
- ✅ Chrome extension endpoints
- ✅ Error handling
- ✅ Performance metrics

**Gebruik:**
```bash
# Test tegen localhost
python test_functionality.py

# Test tegen custom URL
python test_functionality.py https://your-replit-url.com
```

### 2. UI Functionality Tests (`test_ui_functionality.html`)

Test frontend JavaScript functionaliteit:
- ✅ JavaScript loading
- ✅ DOM elements presence
- ✅ Local storage functionality
- ✅ Tab switching
- ✅ Form validation

**Gebruik:**
1. Start je server: `uvicorn api:app --host 0.0.0.0 --port 5000`
2. Open: `http://localhost:5000/static/test_ui_functionality.html`
3. Klik op test buttons om alle functionaliteit te testen

## Test Scenarios

### Voor Major Changes
Voor grote wijzigingen aan de codebase:

```bash
# 1. Run volledige test suite
python run_tests.py

# 2. Test specifieke functionaliteit
python test_functionality.py

# 3. Browser tests
# Open test_ui_functionality.html en run alle tests
```

### Voor UI Changes
Voor wijzigingen aan frontend/CSS:

1. Open `test_ui_functionality.html` in browser
2. Test alle UI componenten
3. Test op verschillende schermgroottes
4. Verificeer drag & drop functionaliteit

### Voor API Changes
Voor wijzigingen aan backend/API:

```bash
# Test alleen API functionaliteit
python test_functionality.py
```

### Voor Deployment
Voor deployment naar productie:

```bash
# Test tegen productie URL
python test_functionality.py https://your-replit-deployment.com
```

## Test Results

### Success Criteria
- ✅ Alle API tests slagen (100% pass rate)
- ✅ Alle UI elements laden correct
- ✅ Tab switching werkt
- ✅ Form validation werkt
- ✅ Local storage werkt
- ✅ Drag & drop functionaliteit werkt

### Common Issues

#### API Tests Fail
- **Check server status**: Is uvicorn server running?
- **Check dependencies**: `pip install -r requirements.txt`
- **Check ports**: Server should run on port 5000
- **Check URL**: Verify correct base URL

#### UI Tests Fail  
- **Check static files**: Verify `/static/script.js` loads
- **Check browser console**: Look for JavaScript errors
- **Check localStorage**: Verify browser allows localStorage
- **Check CORS**: Verify static files serve correctly

#### Performance Issues
- **Selenium timeout**: Check if browser can access test URLs
- **API timeout**: Check if external recipe websites are accessible
- **Network issues**: Verify internet connection

## Continuous Testing

### Before Commits
```bash
# Quick test before committing changes
python test_functionality.py && echo "✅ Ready to commit"
```

### Before Deployment
```bash
# Full test suite before deployment
python run_tests.py && echo "✅ Ready to deploy"
```

### After Deployment
```bash
# Test production deployment
python test_functionality.py https://your-production-url.com
```

## Adding New Tests

### For New API Endpoints
1. Add test method to `SilverfoodTester` class in `test_functionality.py`
2. Follow pattern: `def test_your_feature(self) -> bool:`
3. Add to `run_all_tests()` method

### For New UI Features  
1. Add test function to `test_ui_functionality.html`
2. Add button to trigger test
3. Follow pattern: `function testYourFeature()`

## Troubleshooting

### Tests Timeout
- Increase timeout values in test files
- Check network connectivity
- Verify external services (recipe websites) are accessible

### Browser Tests Don't Work
- Check if server serves static files: `http://localhost:5000/static/`
- Verify JavaScript console for errors
- Try different browser

### API Tests Fail Locally But Work in Browser
- Check if you're testing correct port (5000)
- Verify server is running: `ps aux | grep uvicorn`
- Check firewall/antivirus blocking localhost connections

## Test Maintenance

### Weekly
- Run full test suite to catch regressions
- Update test URLs if recipe websites change
- Check if external dependencies still work

### Before Major Releases
- Run tests on multiple browsers
- Test on mobile devices  
- Verify accessibility features
- Performance testing with larger datasets

### After External Changes
- Test when recipe websites update their HTML structure
- Verify if new Chrome/Firefox versions affect extension
- Check if third-party APIs change

## Automation Ideas

Consider adding these automated tests:
- **Screenshot comparison**: Visual regression testing
- **Load testing**: Test with many concurrent users
- **Mobile testing**: Automated mobile browser testing
- **Accessibility testing**: Screen reader compatibility
- **Security testing**: Input sanitization verification

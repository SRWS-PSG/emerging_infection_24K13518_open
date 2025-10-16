# Heroku Deployment Steps

## Current Readiness
✅ All deployment files are ready:
- `Procfile` - Heroku startup config
- `setup.sh` - Streamlit setup
- `runtime.txt` - Python 3.11.0
- `requirements.txt` - Dependencies
- `static/pdf/` - PDF files (6)

## How to Deploy

### 1. Log in to Heroku
```bash
heroku login
```
Log in with your Heroku account in the browser window.

### 2. Create the Heroku app
```bash
# Change the app name as needed
heroku create emerging-infection-eval-app
```

### 3. Set environment variables
```bash
# Change to your app name
APP_NAME="emerging-infection-eval-app"

# Base settings
heroku config:set PAPERS_SPREADSHEET_ID="1fCr8o3bo31wUL33srXQj6ntUUpyBTJYQfCxAQLVt13w" --app $APP_NAME
heroku config:set RESULTS_SPREADSHEET_ID="1FDN1lVkWyokINlgStbfXUbF7WoZoaFO5EiRcnZ82mhM" --app $APP_NAME
heroku config:set PDF_BASE_URL="/app/static/pdf/" --app $APP_NAME
heroku config:set USER_GOOGLE_ACCOUNT="youkiti@gmail.com" --app $APP_NAME

# OpenAI API Key (from your .env)
heroku config:set OPENAI_API_KEY="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" --app $APP_NAME

# Google Service Account credentials must be set manually
echo "⚠️ Set Google Service Account credentials:"
echo "heroku config:set GOOGLE_SERVICE_ACCOUNT_INFO='...' --app $APP_NAME"
```

### 4. Deploy
```bash
# Commit changes
git add .
git commit -m "Deploy Streamlit app to Heroku"

# Push to Heroku
git push heroku main
```

### 5. Tail logs
```bash
heroku logs --tail --app $APP_NAME
```

### 6. Open app URL
```bash
heroku open --app $APP_NAME
```

## Google Service Account setup

### Get credentials from config/client_secret.json:
1. Copy contents of `config/client_secret.json`
2. Minify JSON to one line and set as env var:
```bash
heroku config:set GOOGLE_SERVICE_ACCOUNT_INFO='{"type":"service_account","project_id":"..."}' --app $APP_NAME
```

## Troubleshooting

### Common errors
1. **Buildpack detection failed**
   - Ensure requirements.txt is placed correctly

2. **Google Sheets API Error**
   - Check GOOGLE_SERVICE_ACCOUNT_INFO is correctly set
   - Verify spreadsheet IDs

3. **Static files not found**
   - Ensure static/pdf/ is committed to Git

### Debug commands
```bash
# Show config vars
heroku config --app $APP_NAME

# Tail logs
heroku logs --tail --app $APP_NAME

# Dyno status
heroku ps --app $APP_NAME
```

## Success checklist
- [ ] App starts successfully
- [ ] Google Sheets integration works
- [ ] PDF files are served
- [ ] Evaluation form works

App URL after deployment: `https://your-app-name.herokuapp.com`

# Heroku Deployment Guide

## Prerequisites

- Heroku account (free tier is fine)
- Heroku CLI installed
- Git installed

## Install Heroku CLI

### Windows
```bash
# Download the installer from the official site
# https://devcenter.heroku.com/articles/heroku-cli
```

### macOS
```bash
brew tap heroku/brew && brew install heroku
```

### Linux/WSL
```bash
curl https://cli-assets.heroku.com/install.sh | sh
```

## Deployment Steps

### 1. Log in to Heroku
```bash
heroku login
```

### 2. Create a Heroku app
```bash
heroku create your-app-name
# Example: heroku create emerging-infection-review
```

### 3. Configure environment variables

Set in the Heroku dashboard or via CLI:

```bash
# Google Sheets
heroku config:set PAPERS_SPREADSHEET_ID="your_spreadsheet_id"
heroku config:set RESULTS_SPREADSHEET_ID="your_results_id"
heroku config:set PAPERS_WORKSHEET_NAME="Papers"
heroku config:set RESULTS_WORKSHEET_NAME="Results"

# Google OAuth credentials (from your client_secret.json)
heroku config:set GOOGLE_OAUTH_CLIENT_ID="your_client_id"
heroku config:set GOOGLE_OAUTH_CLIENT_SECRET="your_client_secret"
heroku config:set GOOGLE_OAUTH_REFRESH_TOKEN="your_refresh_token"

# Other settings
heroku config:set USER_GOOGLE_ACCOUNT="your_email@gmail.com"
heroku config:set PDF_BASE_URL="your_pdf_base_url"
heroku config:set OPENAI_API_KEY="your_openai_key"
heroku config:set DEBUG="False"
```

### 4. Updating auth_helper.py

If needed, adjust to read credentials from Heroku env vars:

```python
# In auth_helper.py, replace get_google_creds_from_streamlit_secrets()
import os

def get_google_creds_from_heroku_env():
    """Read Google OAuth creds from Heroku env vars"""
    client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
    refresh_token = os.getenv('GOOGLE_OAUTH_REFRESH_TOKEN')
    
    if not all([client_id, client_secret, refresh_token]):
        return None
    
    token_info = {
        "type": "authorized_user",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    }
    
    return Credentials.from_authorized_user_info(token_info, SCOPES)
```

### 5. Deploy

```bash
# Add and commit
git add .
git commit -m "Add Heroku deployment configuration"

# Push to Heroku
git push heroku main
```

### 6. Verify the app

```bash
# Open the app
heroku open

# View logs
heroku logs --tail
```

## Troubleshooting

### Buildpack detection

If it isn’t detected as a Python app:
```bash
heroku buildpacks:set heroku/python
```

### Memory limit errors

Free dynos have a 512MB memory cap. For large files, consider upgrading the plan.

### Port errors

Ensure Streamlit uses the correct port. The `setup.sh` uses the `$PORT` env var.

## Security notes

- Always store secrets in environment variables
- Do not commit client_secret.json or tokens
- Use Heroku config vars even for private repos

## Cost

- Free plan: ~550 hours/month (1000 hours with credit card on file)
- App sleeps after 30 minutes of inactivity
- Custom domains require paid plans

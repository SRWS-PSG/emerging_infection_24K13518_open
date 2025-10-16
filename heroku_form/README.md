# Heroku Form (Streamlit)

Code for the Streamlit form used in the study, plus Heroku deployment settings.

Structure
- `code/`: フォーム本体（`form_implementation.py` ほか）
- `deployment/`: `Procfile`, `runtime.txt`, デプロイ手順

Setup
1. Install dependencies: `pip install -r ../../requirements.txt`
2. Configure `.env` (at repo root):
   - `PAPERS_SPREADSHEET_ID`, `PAPERS_WORKSHEET_NAME`
   - `RESULTS_SPREADSHEET_ID`, `RESULTS_WORKSHEET_NAME`
   - `PDF_BASE_URL`
   - `OPENAI_API_KEY` (optional)
3. Place service account key at `config/credentials.json`

Run locally
- `streamlit run code/form_implementation.py`

Deploy to Heroku
- See `deployment/README_HEROKU.md` and `HEROKU_DEPLOY_STEPS.md`

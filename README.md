# Public Export

This folder can be used directly as a public-facing repository. It contains the following three components:

- python_pdf_extraction: Python implementation for PDF text extraction and structured summarization
- heroku_form: Streamlit form used in the study (with Heroku deployment files)
- results_analysis: Analysis scripts, anonymized data, and figures

Setup
- Install dependencies using `export/requirements.txt`
- Copy `export/.env.example` to `.env` and set required values
- Place the service account key at `config/credentials.json` (do not commit to Git)

Folder overview
- python_pdf_extraction: Extraction and summarization using OpenAI API and Google Sheets/Drive
- heroku_form: Streamlit form and Heroku settings
- results_analysis: Scripts and outputs used for analyzing study results

Funding
- This study is funded by KAKENHI-PROJECT-24K13518.
- The study was registered with the UMIN Clinical Trials Registry (UMIN000058346). 

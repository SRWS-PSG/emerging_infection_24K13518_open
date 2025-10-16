# Python PDF Extraction

Extract text from PDFs and generate structured summaries with the OpenAI API. Optionally integrates with Google Sheets/Drive.

Included files
- `extract_structured_data.py`: Convert structured data from local PDFs into CSV
- `generate_structured_summary.py`: Google Drive/Sheets integration + summary generation

Prerequisites
- Python 3.10+
- Install dependencies from `../requirements.txt`
- Place a `.env` at the repo root and set the variables below

Required environment variables
- `OPENAI_API_KEY`
- `PAPERS_SPREADSHEET_ID` (if using Sheets integration)
- `PAPERS_WORKSHEET_NAME` (default `Papers`)
- `RESULTS_SPREADSHEET_ID` (optional)
- `RESULTS_WORKSHEET_NAME` (default `Results`)
- `PDF_BASE_URL` (optional)

Auth files
- Service account key: `config/credentials.json` (do not commit to Git)

How to run
- Structured data extraction (local PDFs): `python extract_structured_data.py`
- Drive/Sheets integration: `python generate_structured_summary.py`

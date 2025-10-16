"""
Structured summary generator for a systematic review of emerging infectious diseases.
Downloads PDFs from Google Drive, extracts text, and generates a structured summary using the OpenAI API.
Also fetches paper info from Google Sheets and writes back the generated summary and a processed flag.
"""

import os
import io
import re
import json
import sys
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pdfminer.high_level import extract_text
import time  # For sleep between API calls

# Add parent dir to Python path so we can import config.py
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
import config

# Load env vars from .env
load_dotenv()

# OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY is not set. OpenAI API calls will not work.")
    client = None
else:
    client = OpenAI(api_key=OPENAI_API_KEY)

# Google Drive API scopes
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
# Google Sheets API scopes
SHEETS_SCOPES = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']

# Service account key path
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), '..', config.CREDENTIALS_PATH)

# Processed flag column header (was column O in the original sheet)
PROCESSED_FLAG_COLUMN_HEADER = "llm_summary_processed"

def initialize_sheets_client():
    """Initialize Google Sheets API client."""
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SHEETS_SCOPES)
        gs_client = gspread.authorize(credentials)
        return gs_client
    except Exception as e:
        print(f"Google Sheets API auth error: {e}")
        return None

def get_papers_worksheet():
    """Get the worksheet that stores paper metadata."""
    gs_client = initialize_sheets_client()
    if not gs_client:
        return None
    try:
        spreadsheet = gs_client.open_by_key(config.PAPERS_SPREADSHEET_ID)
        sheet = spreadsheet.worksheet(config.PAPERS_WORKSHEET_NAME)
        return sheet
    except Exception as e:
        print(f"Error getting papers worksheet: {e}")
        return None

def get_all_paper_ids_from_papers_sheet(worksheet):
    """Get all paper IDs from the papers sheet (excluding header)."""
    if not worksheet:
        return []
    try:
        headers = worksheet.row_values(1)
        if "paper_id" not in headers:
            print("'paper_id' column not found in papers sheet.")
            return []
        paper_id_col_index = headers.index("paper_id") + 1
        paper_ids = worksheet.col_values(paper_id_col_index)[1:]  # exclude header
        return [pid for pid in paper_ids if pid]  # drop empty ids
    except Exception as e:
        print(f"Error getting paper ID list: {e}")
        return []

def get_paper_data_from_spreadsheet(worksheet, paper_id):
    """Fetch a paper's data by ID from the spreadsheet."""
    if not worksheet:
        print("Papers worksheet not provided.")
        return None
    try:
        paper_data_cell = worksheet.find(paper_id)
        if not paper_data_cell:
            print(f"Paper ID '{paper_id}' not found in the spreadsheet.")
            return None
        row_values = worksheet.row_values(paper_data_cell.row)
        sheet_headers = worksheet.row_values(1)
        paper_dict = {header: row_values[i] if i < len(row_values) else "" for i, header in enumerate(sheet_headers)}
        
        if "pdf_link" in paper_dict and paper_dict["pdf_link"]:
            pass  # use provided pdf_link
        elif "pdf_filename" in paper_dict and paper_dict["pdf_filename"]:
            paper_dict["pdf_link"] = f"{config.PDF_BASE_URL}{paper_dict['pdf_filename']}"
        else:
            paper_dict["pdf_link"] = f"{config.PDF_BASE_URL}{paper_id}.pdf"  # default link format
        return paper_dict
    except Exception as e:
        print(f"Error fetching paper data (ID: {paper_id}): {e}")
        return None

def update_paper_summary_in_spreadsheet(worksheet, paper_id, summary_text):
    """Update the 'summary' column for a paper in the sheet."""
    if not worksheet:
        print("Papers worksheet not provided. Cannot update summary.")
        return False
    try:
        paper_data_cell = worksheet.find(paper_id)
        if not paper_data_cell:
            print(f"Paper ID '{paper_id}' (for summary update) not found.")
            return False
        headers = worksheet.row_values(1)
        if "summary" not in headers:  # ensure 'summary' column exists
            print("Column 'summary' not found in the sheet.")
            return False
        summary_col_index = headers.index("summary") + 1
        worksheet.update_cell(paper_data_cell.row, summary_col_index, summary_text)
        print(f"Updated summary for paper ID '{paper_id}'.")
        return True
    except Exception as e:
        print(f"Summary update error (ID: {paper_id}): {e}")
        return False

def update_paper_processed_flag(worksheet, paper_id, flag_value="DONE"):
    """Update the processed flag column (originally column O) for the paper."""
    if not worksheet:
        print("Papers worksheet not provided. Cannot update flag.")
        return False
    try:
        paper_data_cell = worksheet.find(paper_id)
        if not paper_data_cell:
            print(f"Paper ID '{paper_id}' (for flag update) not found.")
            return False
        
        headers = worksheet.row_values(1)
        if PROCESSED_FLAG_COLUMN_HEADER not in headers:
            print(f"Warning: Column '{PROCESSED_FLAG_COLUMN_HEADER}' not found. Will attempt to write to column O (index 15).")
            flag_col_index = 15  # Column O is index 15
        else:
            flag_col_index = headers.index(PROCESSED_FLAG_COLUMN_HEADER) + 1
        
        worksheet.update_cell(paper_data_cell.row, flag_col_index, flag_value)
        print(f"Updated processed flag for '{paper_id}' to '{flag_value}' (col: {flag_col_index}).")
        return True
    except Exception as e:
        print(f"Processed flag update error (ID: {paper_id}): {e}")
        return False

def extract_file_id_from_url(google_drive_url: str) -> str | None:
    match = re.search(r'/d/([^/]+)', google_drive_url)
    return match.group(1) if match else None

def get_google_drive_service():
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=DRIVE_SCOPES)
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Google Drive API client init error: {e}")
        return None

def download_pdf_from_google_drive(file_id_or_url: str) -> bytes | None:
    service = get_google_drive_service()
    if not service: return None
    file_id = extract_file_id_from_url(file_id_or_url) if file_id_or_url.startswith("http") else file_id_or_url
    if not file_id:
        print(f"Could not extract a valid file ID: {file_id_or_url}")
        return None
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Google Drive download progress: {int(status.progress() * 100)}%")
        fh.seek(0)
        return fh.read()
    except Exception as e:
        print(f"Google Drive PDF download error (ID: {file_id}): {e}")
        return None

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        return extract_text(io.BytesIO(pdf_bytes)).strip()
    except Exception as e:
        print(f"PDF text extraction error: {e}")
        return ""

def generate_structured_summary_from_text(title: str, abstract: str, pdf_full_text: str) -> dict | None:
    if client is None:
        print("OpenAI API client not initialized. Check your API key.")
        return None
    input_text = f"Title: {title}\nAbstract: {abstract}\n\nBody:\n{pdf_full_text}"
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": input_text}],
            tools=[{
                "type": "function",
                "function": {
                    "name": "research_paper_extraction",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Thema": {"type": "string", "description": "Summarize the paper’s topic in one brief English phrase; include country/region if relevant. If unavailable, answer 'Unknown'."},
                            "Category": {"type": "string", "enum": ["Case management", "Epidemiology", "Laboratory", "Public health", "ICT(infection control team)", "Vaccine", "Unknown"], "description": "Select one category from the options above. If unavailable, answer 'Unknown'."},
                            "Time": {"type": "object", "properties": {"ja": {"type": "string", "description": "Japanese description is optional."}, "en": {"type": "string", "description": "Describe the date, time, or study period mentioned in the paper (e.g., experimental date or study period). If unavailable, answer 'Unknown'."}}, "required": ["en"], "additionalProperties": False},
                            "Place": {"type": "object", "properties": {"ja": {"type": "string", "description": "Japanese description is optional."}, "en": {"type": "string", "description": "Describe the location or region mentioned in the paper. If unavailable, answer 'Unknown'."}}, "required": ["en"], "additionalProperties": False},
                            "Person": {"type": "object", "properties": {"ja": {"type": "string", "description": "Japanese description is optional."}, "en": {"type": "string", "description": "Describe key person(s) or stakeholders mentioned. If unavailable, answer 'Unknown'."}}, "required": ["en"], "additionalProperties": False},
                            "Summary of Article": {"type": "object", "properties": {"ja": {"type": "string", "description": "Japanese description is optional."}, "en": {"type": "string", "description": "Provide a bullet-point summary in plain English, avoiding jargon. If unavailable, answer 'Unknown'."}}, "required": ["en"], "additionalProperties": False}
                        },
                        "required": ["Thema", "Category", "Time", "Place", "Person", "Summary of Article"],
                        "additionalProperties": False
                    }, "strict": True
                }
            }]
        )
        if response.choices and response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "research_paper_extraction":
                return json.loads(tool_call.function.arguments)
        print("Expected tool_calls were not present in the OpenAI API response.")
        return None
    except Exception as e:
        print(f"OpenAI API call error: {e}")
        return None

def format_as_yaml(structured_data):
    """Convert structured data to YAML text (English fields)."""
    yaml_lines = []
    
    # Thema
    if structured_data.get("Thema"):
        yaml_lines.append(f"thema: {structured_data['Thema']}")
    
    # Category
    if structured_data.get("Category"):
        yaml_lines.append(f"category: {structured_data['Category']}")
    
    # Time (English)
    if structured_data.get("Time", {}).get("en"):
        yaml_lines.append(f"time: {structured_data['Time']['en']}")
    
    # Place (English)
    if structured_data.get("Place", {}).get("en"):
        yaml_lines.append(f"place: {structured_data['Place']['en']}")
    
    # Person (English)
    if structured_data.get("Person", {}).get("en"):
        yaml_lines.append(f"person: {structured_data['Person']['en']}")
    
    # Summary (English) - support multi-line
    if structured_data.get("Summary of Article", {}).get("en"):
        summary_en = structured_data["Summary of Article"]["en"]
        if "\n" in summary_en:
            indented_summary = "\n  " + summary_en.replace("\n", "\n  ")
            yaml_lines.append(f"summary: |{indented_summary}")
        else:
            yaml_lines.append(f"summary: {summary_en}")
    
    return "\n".join(yaml_lines)

def process_single_paper(worksheet, paper_id):
    """Process a single paper ID, generate summary, and update the sheet."""
    print(f"\n--- Start processing paper ID: {paper_id} ---")
    paper_data = get_paper_data_from_spreadsheet(worksheet, paper_id)
    if not paper_data: return False

    title = paper_data.get("title", "")
    abstract = paper_data.get("abstract", "")
    pdf_link = paper_data.get("pdf_link", "")

    if not all([title, abstract, pdf_link]):
        print(f"Missing required info (title, abstract, PDF link) for paper ID '{paper_id}'.")
        return False

    print(f"  Title: {title}\n  PDF: {pdf_link}")
    pdf_bytes = download_pdf_from_google_drive(pdf_link)
    if not pdf_bytes: return False

    pdf_text = extract_text_from_pdf_bytes(pdf_bytes)
    if not pdf_text: return False
    print(f"  Text extraction done (chars: {len(pdf_text)})")

    structured_summary = generate_structured_summary_from_text(title, abstract, pdf_text)
    if not structured_summary: return False

    # Format as YAML
    yaml_summary = format_as_yaml(structured_summary)
    if not yaml_summary:
        print("Could not convert structured summary to YAML (English fields).")
        return False
    
    print(f"  YAML summary generated:\n{yaml_summary}")

    if update_paper_summary_in_spreadsheet(worksheet, paper_id, yaml_summary):
        update_paper_processed_flag(worksheet, paper_id, f"DONE_{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"--- Completed: paper ID {paper_id} ---")
        return True
    return False

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate structured summaries for papers and write to the spreadsheet')
    parser.add_argument('--paper_id', type=str, help='Process a single paper ID')
    parser.add_argument('--all', action='store_true', help='Process all papers in the spreadsheet')
    parser.add_argument('--start_from', type=str, help='Start processing from the specified paper ID (when processing all)')
    parser.add_argument('--limit', type=int, help='Maximum number of papers to process (when processing all)')
    args = parser.parse_args()

    print("Starting structured summary generation")
    papers_sheet = get_papers_worksheet()
    if not papers_sheet:
        print("Could not get the papers worksheet. Exiting.")
        exit()

    if args.paper_id:
        process_single_paper(papers_sheet, args.paper_id)
    elif args.all:
        all_ids = get_all_paper_ids_from_papers_sheet(papers_sheet)
        if not all_ids:
            print("No paper IDs found in the spreadsheet to process.")
            exit()
        
        start_index = 0
        if args.start_from:
            try:
                start_index = all_ids.index(args.start_from)
            except ValueError:
                print(f"Start paper ID '{args.start_from}' not found in the list. Starting from the beginning.")
        
        ids_to_process = all_ids[start_index:]
        if args.limit:
            ids_to_process = ids_to_process[:args.limit]

        print(f"Processing {len(ids_to_process)} papers (start ID: {ids_to_process[0] if ids_to_process else 'N/A'}).")
        processed_count = 0
        for i, paper_id_to_process in enumerate(ids_to_process):
            print(f"\nProcessing: {i+1}/{len(ids_to_process)} (ID: {paper_id_to_process})")
            if process_single_paper(papers_sheet, paper_id_to_process):
                processed_count += 1
            # Consider API rate limits: sleep periodically
            if (i + 1) % 5 == 0:  # sleep every 5 items
                 print("Sleeping 60 seconds to reduce API load...")
                 time.sleep(60)
            elif (i + 1) % 1 == 0:  # brief sleep per item
                 time.sleep(5)
        print(f"\nAll done. Updated summaries for {processed_count} papers.")
    else:
        print("\nUsage:")
        print("  Single paper: python data/generate_structured_summary.py --paper_id <PAPER_ID>")
        print("  All papers:   python data/generate_structured_summary.py --all")
        print("  Start from:   python data/generate_structured_summary.py --all --start_from <PAPER_ID>")
        print("  Limit count:  python data/generate_structured_summary.py --all --limit <N>")
        print("\nRequired env var: OPENAI_API_KEY")

    print("Structured summary generation finished")

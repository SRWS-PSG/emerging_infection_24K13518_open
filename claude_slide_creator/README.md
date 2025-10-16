Claude Slide Creator (Apps Script)

Overview
- Generates Google Slides from analyzed paper data.
- Orchestrates a Drive folder of PDFs: tracks processing in a Google Sheet, analyzes each PDF with Claude, and creates a slide deck from a template.
- Designed to run entirely in Google Apps Script (GAS) with time-based triggers.

Components
- SlideCreator.gs: Main script containing:
  - processAllPDFsInFolder: Batch processing entrypoint
  - processPDFFromDrive: Claude API call (stub provided)
  - createSlide: Create a Google Slides deck from structured fields
  - Tracking helpers: updateFileStatus, getProcessedFileIds
  - Utilities: createSlideFromSpreadsheetJSON, createSlideFromJSON, processPendingEntriesFromSpreadsheet, setupTrigger, testSlideCreation

Script Properties
- TEMPLATE_SLIDE_ID: Slide template deck ID (optional; default embedded in script)
- SLIDE_OUTPUT_FOLDER_ID: Folder ID to store generated slides (optional; defaults to My Drive root)
- PDF_FOLDER_ID: Drive folder ID that contains the PDFs to process
- TRACKING_SPREADSHEET_ID: Spreadsheet ID used to track processing state
- ANTHROPIC_API_KEY: Claude API key (required for processPDFFromDrive)

Tracking Sheet Format
- Sheet name: PDF Status (auto-created if missing)
- Columns:
  1. PDF ID
  2. File Name
  3. File URL
  4. Status (PROCESSING | DONE | ERROR)
  5. JSON Info (stringified analysis result)
  6. Error Info
  7. Processed At (ISO datetime)
  8. Done Flag (DONE | ERROR)
  9. Slide URL

Claude API Integration
- The function processPDFFromDrive(fileId) includes a reference implementation using UrlFetchApp against Anthropic’s Messages API.
- Important constraints:
  - Apps Script cannot reliably extract text from arbitrary PDFs. If your PDFs have embedded text, blob.getDataAsString() may work. Otherwise, add an OCR/Text extraction step before calling Claude.
  - The stub sends the (truncated) extracted text to Claude with a structured prompt and expects JSON in the response. Adjust the prompt and parsing as needed.
  - For large documents, consider chunking or summarization passes, then merging results.

Deployment Steps
1. Create a new Apps Script project (Standalone or bound to a Google Sheet).
2. Copy SlideCreator.gs content into your script project.
3. Set Script Properties (File > Project properties > Script properties):
   - TEMPLATE_SLIDE_ID, SLIDE_OUTPUT_FOLDER_ID, PDF_FOLDER_ID, TRACKING_SPREADSHEET_ID, ANTHROPIC_API_KEY
4. Ensure the Slides, Drive, and Sheets services are authorized on first run.
5. Run setupTrigger if you want a daily schedule.

Usage
- Manual test: Run testSlideCreation to validate slide template and replacements.
- Batch run: Run processAllPDFsInFolder; processed files are tracked in the PDF Status sheet.
- Post-hoc slide generation: Use createSlideFromSpreadsheetJSON(rowId) when JSON already exists.

Template Placeholders
- The template deck should include these placeholders in text boxes:
  - {Title}
  - {Japanese_Title}
  - {Journal}
  - {Citation}
  - {Limitation}
  - {ClinicalImplication}
  - {ResearchImplication}
  - {PolicyImplication}
  - {Summary}

Notes and Tips
- Time limits: processAllPDFsInFolder stops after ~3 files per run by default to avoid Apps Script quotas; adjust as needed.
- Error handling: Failures are recorded in Error Info and Done Flag columns.
- Security: Never commit ANTHROPIC_API_KEY. Keep the Apps Script project private or set the key via Script Properties.


/**
 * SlideCreator.gs
 * Generate Google Slides from analyzed paper data using Apps Script.
 *
 * Features:
 * 1. Duplicate a template slide deck
 * 2. Replace placeholder text
 * 3. Save in a target folder and track processing state in a spreadsheet
 */

/**
 * Create a slide deck from analysis results.
 * @param {Object} paperInfo Parsed paper info object
 * @returns {string} URL of the created slide deck
 */
function createSlide(paperInfo) {
  try {
    console.log('Starting slide creation...');

    if (!paperInfo) {
      console.error('paperInfo is null or undefined');
      throw new Error('Paper info not provided');
    }

    console.log('paperInfo:', JSON.stringify(paperInfo, null, 2));

    // Use a template slide deck ID (override via Script Property TEMPLATE_SLIDE_ID if needed)
    const TEMPLATE_SLIDE_ID = PropertiesService.getScriptProperties().getProperty('TEMPLATE_SLIDE_ID')
      || '1Z4eV6RhyBrMHtRUxPpNRNPa2IG61cK3lAq84zm1muiA';

    // Output folder ID for generated slides (optional)
    const SLIDE_OUTPUT_FOLDER_ID = PropertiesService.getScriptProperties().getProperty('SLIDE_OUTPUT_FOLDER_ID');

    // New file name: yyyy-mm-dd_title
    const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
    const title = (paperInfo && paperInfo.Title) ? paperInfo.Title.substring(0, 50) : 'Untitled';
    const fileName = `${timestamp}_${title}`;
    console.log(`Slide file name: ${fileName}`);

    // Copy the template
    const templateFile = DriveApp.getFileById(TEMPLATE_SLIDE_ID);
    const targetFolder = SLIDE_OUTPUT_FOLDER_ID ? DriveApp.getFolderById(SLIDE_OUTPUT_FOLDER_ID) : DriveApp.getRootFolder();
    const newFile = templateFile.makeCopy(fileName, targetFolder);
    console.log(`Template copied: ${newFile.getName()}`);

    // Open the new presentation
    const presentation = SlidesApp.openById(newFile.getId());

    // Placeholder replacements (safe access)
    const replacements = {
      '{Title}': (paperInfo && paperInfo.Title) ? paperInfo.Title : 'N/A',
      '{Japanese_Title}': (paperInfo && paperInfo.Japanese_Title) ? paperInfo.Japanese_Title : 'N/A',
      '{Journal}': (paperInfo && paperInfo.Journal) ? paperInfo.Journal : 'N/A',
      '{Citation}': (paperInfo && paperInfo.Citation) ? paperInfo.Citation : 'N/A',
      '{Limitation}': (paperInfo && paperInfo.Limitation) ? paperInfo.Limitation : 'N/A',
      '{ClinicalImplication}': (paperInfo && paperInfo.ClinicalImplication) ? paperInfo.ClinicalImplication : 'N/A',
      '{ResearchImplication}': (paperInfo && paperInfo.ResearchImplication) ? paperInfo.ResearchImplication : 'N/A',
      '{PolicyImplication}': (paperInfo && paperInfo.PolicyImplication) ? paperInfo.PolicyImplication : 'N/A',
      '{Summary}': (paperInfo && paperInfo.Summary) ? paperInfo.Summary : 'N/A'
    };
    console.log('Replacements:', replacements);
    console.log('Starting placeholder replacement');

    const slides = presentation.getSlides();
    for (const slide of slides) {
      for (const placeholder in replacements) {
        try {
          slide.replaceAllText(placeholder, replacements[placeholder]);
        } catch (replaceError) {
          console.warn(`Error replacing placeholder ${placeholder}: ${replaceError}`);
          // Continue on replacement errors
        }
      }
    }

    presentation.saveAndClose();
    console.log(`Slide creation completed: ${newFile.getUrl()}`);
    return newFile.getUrl();
  } catch (error) {
    console.error(`Error while creating slide: ${error}`);
    throw error;
  }
}

/**
 * Process all PDFs in a Drive folder:
 * - Track status in a spreadsheet
 * - Analyze with Claude (via processPDFFromDrive)
 * - Create slide deck for each analyzed file
 */
function processAllPDFsInFolder() {
  try {
    console.log('Processing PDFs in folder...');

    const folderId = PropertiesService.getScriptProperties().getProperty('PDF_FOLDER_ID');
    const spreadsheetId = PropertiesService.getScriptProperties().getProperty('TRACKING_SPREADSHEET_ID');
    if (!folderId) throw new Error('PDF_FOLDER_ID not set');
    if (!spreadsheetId) throw new Error('TRACKING_SPREADSHEET_ID not set');

    const folder = DriveApp.getFolderById(folderId);
    const pdfFiles = folder.getFilesByType(MimeType.PDF);
    const processedIds = getProcessedFileIds();
    let processedCount = 0;
    let errorCount = 0;

    while (pdfFiles.hasNext()) {
      const file = pdfFiles.next();
      const fileId = file.getId();
      if (processedIds.has(fileId)) {
        console.log(`Already processed: ${file.getName()}`);
        continue;
      }
      try {
        console.log(`Start: ${file.getName()}`);
        updateFileStatus(fileId, file.getName(), file.getUrl(), 'PROCESSING');

        // Analyze PDF with Claude
        const paperInfo = processPDFFromDrive(fileId);
        if (!paperInfo) throw new Error('Claude analysis returned empty result');
        console.log('Analysis result:', paperInfo);

        let jsonInfoStr = '';
        try {
          jsonInfoStr = JSON.stringify(paperInfo);
        } catch (jsonError) {
          console.warn(`JSON stringify error: ${jsonError}`);
          jsonInfoStr = `{"error":"JSON stringify failed: ${jsonError}"}`;
        }

        const slideUrl = createSlide(paperInfo);
        updateFileStatus(
          fileId,
          file.getName(),
          file.getUrl(),
          'DONE',
          jsonInfoStr,
          '',
          slideUrl,
          'DONE'
        );
        console.log(`Completed: ${file.getName()}`);
        processedCount++;
        if (processedCount >= 3) { // time quota safety
          console.log('Reached per-run limit; continue next run.');
          break;
        }
      } catch (error) {
        console.error(`File error: ${error}`);
        updateFileStatus(fileId, file.getName(), file.getUrl(), 'ERROR', '', String(error), '', 'ERROR');
        errorCount++;
      }
    }

    console.log(`Done: processed=${processedCount}, errors=${errorCount}`);
  } catch (error) {
    console.error(`Batch error: ${error}`);
  }
}

/**
 * Read processed file IDs from the tracking sheet.
 * @returns {Set<string>} Processed file ID set
 */
function getProcessedFileIds() {
  try {
    const spreadsheetId = PropertiesService.getScriptProperties().getProperty('TRACKING_SPREADSHEET_ID');
    if (!spreadsheetId) {
      console.warn('TRACKING_SPREADSHEET_ID not set');
      return new Set();
    }
    const ss = SpreadsheetApp.openById(spreadsheetId);
    const sheet = ss.getSheetByName('PDF Status');
    if (!sheet) return new Set();

    const data = sheet.getDataRange().getValues();
    const processedIds = new Set();
    for (let i = 1; i < data.length; i++) {
      const status = data[i][3]; // status col
      if (status === 'DONE') processedIds.add(data[i][0]); // file ID col
    }
    console.log(`Loaded ${processedIds.size} processed IDs`);
    return processedIds;
  } catch (error) {
    console.error(`getProcessedFileIds error: ${error}`);
    return new Set();
  }
}

/**
 * Update a row (create if missing) in the tracking sheet.
 */
function updateFileStatus(fileId, fileName, fileUrl, status, jsonInfo = '', errorInfo = '', slideUrl = '', completionFlag = '') {
  try {
    const spreadsheetId = PropertiesService.getScriptProperties().getProperty('TRACKING_SPREADSHEET_ID');
    if (!spreadsheetId) {
      console.warn('TRACKING_SPREADSHEET_ID not set');
      return;
    }
    const ss = SpreadsheetApp.openById(spreadsheetId);
    let sheet = ss.getSheetByName('PDF Status');
    if (!sheet) {
      sheet = ss.insertSheet('PDF Status');
      sheet.appendRow(['PDF ID', 'File Name', 'File URL', 'Status', 'JSON Info', 'Error Info', 'Processed At', 'Done Flag', 'Slide URL']);
    }

    const data = sheet.getDataRange().getValues();
    let rowIndex = -1;
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === fileId) { rowIndex = i + 1; break; }
    }
    const timestamp = new Date().toISOString();
    if (rowIndex > 0) {
      sheet.getRange(rowIndex, 4).setValue(status);
      if (jsonInfo) sheet.getRange(rowIndex, 5).setValue(jsonInfo);
      if (errorInfo) sheet.getRange(rowIndex, 6).setValue(errorInfo);
      sheet.getRange(rowIndex, 7).setValue(timestamp);
      if (completionFlag) sheet.getRange(rowIndex, 8).setValue(completionFlag);
      if (slideUrl) sheet.getRange(rowIndex, 9).setValue(slideUrl);
    } else {
      sheet.appendRow([fileId, fileName, fileUrl, status, jsonInfo, errorInfo, timestamp, completionFlag, slideUrl]);
    }
    console.log(`Updated status for ${fileName} -> ${status}`);
  } catch (error) {
    console.error(`updateFileStatus error: ${error}`);
  }
}

/**
 * Set up a time-based trigger for processAllPDFsInFolder.
 */
function setupTrigger() {
  try {
    const triggers = ScriptApp.getProjectTriggers();
    for (const trigger of triggers) {
      if (trigger.getHandlerFunction() === 'processAllPDFsInFolder') {
        ScriptApp.deleteTrigger(trigger);
      }
    }
    ScriptApp.newTrigger('processAllPDFsInFolder').timeBased().atHour(9).everyDays(1).create();
    console.log('Scheduled processAllPDFsInFolder at 09:00 daily');
    return 'Scheduled at 09:00 daily';
  } catch (error) {
    console.error(`setupTrigger error: ${error}`);
    return `setupTrigger error: ${error}`;
  }
}

/**
 * Create a slide deck from a JSON stored in the tracking sheet.
 * @param {string} rowId Row key (usually PDF file ID)
 */
function createSlideFromSpreadsheetJSON(rowId) {
  try {
    if (!rowId) throw new Error('Valid rowId not provided');
    const spreadsheetId = PropertiesService.getScriptProperties().getProperty('TRACKING_SPREADSHEET_ID');
    if (!spreadsheetId) throw new Error('TRACKING_SPREADSHEET_ID not set');

    const ss = SpreadsheetApp.openById(spreadsheetId);
    const sheet = ss.getSheetByName('PDF Status');
    if (!sheet) throw new Error('Sheet "PDF Status" not found');

    const data = sheet.getDataRange().getValues();
    let rowIndex = -1;
    let jsonStr = '';
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === rowId) { // ID col
        rowIndex = i + 1;
        jsonStr = data[i][4]; // JSON Info col
        break;
      }
    }
    if (rowIndex === -1) throw new Error(`Row for ID '${rowId}' not found`);
    if (!jsonStr) throw new Error(`JSON Info for ID '${rowId}' is empty`);

    let paperInfo;
    try { paperInfo = JSON.parse(jsonStr); } catch (e) { throw new Error(`JSON parse error: ${e}`); }
    const slideUrl = createSlide(paperInfo);
    sheet.getRange(rowIndex, 8).setValue('DONE'); // Done Flag
    sheet.getRange(rowIndex, 9).setValue(slideUrl); // Slide URL
    sheet.getRange(rowIndex, 7).setValue(new Date().toISOString()); // Processed At
    console.log(`Slide created: ${slideUrl}`);
    return slideUrl;
  } catch (error) {
    console.error(`createSlideFromSpreadsheetJSON error: ${error}`);
    throw error;
  }
}

/**
 * Create a slide deck directly from a JSON string.
 */
function createSlideFromJSON(jsonString) {
  try {
    if (!jsonString) throw new Error('jsonString not provided');
    let paperInfo;
    try { paperInfo = JSON.parse(jsonString); } catch (e) { throw new Error(`JSON parse error: ${e}`); }
    return createSlide(paperInfo);
  } catch (error) {
    console.error(`createSlideFromJSON error: ${error}`);
    throw error;
  }
}

/**
 * Process pending entries in the tracking sheet:
 * entries with JSON Info present and empty Done Flag.
 */
function processPendingEntriesFromSpreadsheet() {
  try {
    console.log('Processing pending entries from sheet...');
    const spreadsheetId = PropertiesService.getScriptProperties().getProperty('TRACKING_SPREADSHEET_ID');
    if (!spreadsheetId) throw new Error('TRACKING_SPREADSHEET_ID not set');

    const ss = SpreadsheetApp.openById(spreadsheetId);
    const sheet = ss.getSheetByName('PDF Status');
    if (!sheet) throw new Error('Sheet "PDF Status" not found');

    const data = sheet.getDataRange().getValues();
    let processedCount = 0;
    let errorCount = 0;
    const processedEntries = [];

    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      const fileId = row[0];
      const fileName = row[1];
      const jsonStr = row[4];
      const doneFlag = row[7];
      if (jsonStr && !doneFlag) {
        try {
          if (!fileId) { console.warn(`Row ${i+1}: missing file ID; skipping`); continue; }
          const url = createSlideFromSpreadsheetJSON(fileId);
          processedEntries.push({ id: fileId, name: fileName, url });
          processedCount++;
          if (processedCount >= 3) { console.log('Reached per-run limit'); break; }
        } catch (error) {
          console.error(`Entry error (${fileId}): ${error}`);
          const rowIndex = i + 1;
          sheet.getRange(rowIndex, 6).setValue(String(error)); // Error Info
          sheet.getRange(rowIndex, 8).setValue('ERROR'); // Done Flag
          sheet.getRange(rowIndex, 7).setValue(new Date().toISOString()); // Processed At
          errorCount++;
        }
      }
    }

    const result = { processed: processedCount, errors: errorCount, entries: processedEntries };
    console.log(`Done: processed=${processedCount}, errors=${errorCount}`);
    return result;
  } catch (error) {
    console.error(`processPendingEntriesFromSpreadsheet error: ${error}`);
    throw error;
  }
}

/**
 * Test helper to create a slide with sample data.
 */
function testSlideCreation() {
  try {
    const testPaperInfo = {
      Title: 'Test Paper Title',
      Japanese_Title: 'Test Paper Title (Japanese optional)',
      Journal: 'Test Journal',
      Citation: 'Test Author et al. (2025) Test Journal, 1(1), 1-10',
      Limitation: 'This is a test limitation.',
      ClinicalImplication: 'This is a test clinical implication.',
      ResearchImplication: 'This is a test research implication.',
      PolicyImplication: 'This is a test policy implication.',
      Summary: 'This is a test summary.'
    };
    const slideUrl = createSlide(testPaperInfo);
    return `Created test slide: ${slideUrl}`;
  } catch (error) {
    return `Test error: ${error}`;
  }
}

/**
 * Stub: Analyze a PDF with Claude and return a structured JSON.
 * IMPORTANT: This is a reference implementation. You must provide your
 * Anthropic API key in Script Properties as ANTHROPIC_API_KEY and ensure
 * the PDF content is converted to text (or another supported input) before
 * sending to Claude.
 */
function processPDFFromDrive(fileId) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');
  if (!apiKey) {
    throw new Error('ANTHROPIC_API_KEY is not set in Script Properties');
  }

  // NOTE: Extracting text from PDFs is non-trivial in Apps Script.
  // If your PDFs contain embedded text, DriveApp.getFileById(fileId)
  // .getBlob().getDataAsString() may return readable text. Otherwise,
  // consider using an external OCR/Text extraction service first.
  const file = DriveApp.getFileById(fileId);
  const blob = file.getBlob();
  const maybeText = blob.getDataAsString();
  if (!maybeText || maybeText.trim() === '') {
    throw new Error('PDF text extraction failed or returned empty text');
  }

  const prompt = [
    'You are an expert assistant for extracting structured information from scientific PDFs.',
    'Extract the following fields as JSON with these keys:',
    'Title, Japanese_Title, Journal, Citation, Limitation, ClinicalImplication, ResearchImplication, PolicyImplication, Summary.',
    'Use concise, plain language. Japanese_Title should be Japanese if possible.',
  ].join('\n');

  const url = 'https://api.anthropic.com/v1/messages';
  const body = {
    model: 'claude-3-5-sonnet-20240620',
    max_tokens: 1500,
    messages: [
      {
        role: 'user',
        content: [
          { type: 'text', text: prompt },
          { type: 'text', text: maybeText.substring(0, 20000) }
        ]
      }
    ]
  };

  const params = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    muteHttpExceptions: true,
    payload: JSON.stringify(body)
  };

  const resp = UrlFetchApp.fetch(url, params);
  const code = resp.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error(`Claude API error: HTTP ${code} - ${resp.getContentText()}`);
  }
  const data = JSON.parse(resp.getContentText());
  // data.content[0].text is typical for simple text responses
  let text = '';
  try {
    text = (data && data.content && data.content.length && data.content[0].text) ? data.content[0].text : '';
  } catch (e) {}
  if (!text) {
    throw new Error('Claude response missing content');
  }
  // Attempt to parse JSON from model output; if not valid, wrap it
  try {
    return JSON.parse(text);
  } catch (e) {
    return { raw: text };
  }
}

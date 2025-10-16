"""
Script to extract structured data from PDF files.
Structures research paper information using the OpenAI o3 API.
"""

import os
import sys
import json
import csv
from typing import Dict, List
import logging
from datetime import datetime

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdfminer.high_level import extract_text
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file."""
    try:
        text = extract_text(pdf_path)
        logger.info(f"Text extraction succeeded: {pdf_path}")
        return text
    except Exception as e:
        logger.error(f"PDF text extraction error ({pdf_path}): {e}")
        return ""

def generate_structured_output(pdf_text: str, filename: str) -> Dict:
    """Generate structured data using the OpenAI o3 API."""
    logger.info(f"Starting structured data generation: {filename}")
    
    # Define system and user messages
    messages = [
        {
            "role": "system",
            "content": "You are an expert at extracting structured data from research papers. From the provided paper text, extract information following the specified schema."
        },
        {
            "role": "user",
            "content": f"Extract structured information from the following paper text:\n\n{pdf_text[:10000]}"  # Use the first 10,000 characters
        }
    ]
    
    # Request JSON using a schema
    try:
        response = client.chat.completions.create(
            model="o3",
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "research_paper_extraction",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "PDF file name"
                            },
                            "thema": {
                                "type": "string",
                                "description": "In one brief English phrase, summarize the paper’s theme based on the title and content. Include country or region if relevant. If unknown, write 'Unknown'."
                            },
                            "category": {
                                "type": "string",
                                "enum": [
                                    "Case management",
                                    "Epidemiology",
                                    "Laboratory",
                                    "Public health",
                                    "ICT(infection control team)",
                                    "Vaccine",
                                    "Unknown"
                                ],
                                "description": "Select the category that applies to the paper."
                            },
                            "time": {
                                "type": "string",
                                "description": "Describe the date/time or study period mentioned in the paper (e.g., experimental date, study period). If unknown, write 'Unknown'."
                            },
                            "place": {
                                "type": "string",
                                "description": "Describe the location or region mentioned in the paper. If unknown, write 'Unknown'."
                            },
                            "person": {
                                "type": "string",
                                "description": "Describe key people, subjects, or stakeholders mentioned in the paper. If unknown, write 'Unknown'."
                            },
                            "summary": {
                                "type": "string",
                                "description": "Provide a bullet-point summary of the paper using plain language that avoids jargon. Use hyphen bullets, 3–5 items. If unknown, write 'Unknown'."
                            }
                        },
                        "required": ["filename", "thema", "category", "time", "place", "person", "summary"],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            }
        )
        
        # Extract JSON from response
        result = json.loads(response.choices[0].message.content)
        result["filename"] = filename  # Ensure filename is set
        logger.info(f"Structured data generation succeeded: {filename}")
        return result
        
    except Exception as e:
        logger.error(f"OpenAI API error ({filename}): {e}")
        # Defaults on error
        return {
            "filename": filename,
            "thema": "Error",
            "category": "Unknown",
            "time": "Unknown",
            "place": "Unknown",
            "person": "Unknown",
            "summary": f"An error occurred: {str(e)}"
        }

def process_all_pdfs() -> List[Dict]:
    """Process all PDFs in this folder."""
    pdf_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
    
    logger.info(f"Number of PDF files to process: {len(pdf_files)}")
    
    results = []
    for pdf_file in sorted(pdf_files):
        pdf_path = os.path.join(pdf_dir, pdf_file)
        logger.info(f"Processing: {pdf_file}")
        
        # Extract text from PDF
        pdf_text = extract_text_from_pdf(pdf_path)
        
        if pdf_text:
            # Generate structured data
            structured_data = generate_structured_output(pdf_text, pdf_file)
            results.append(structured_data)
        else:
            logger.warning(f"Text extraction failed, skipping: {pdf_file}")
    
    return results

def save_to_csv(results: List[Dict], output_file: str = "structured_data.csv"):
    """Save results to a CSV file."""
    if not results:
        logger.warning("No data to save")
        return
    
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_file)
    
    # CSV header
    headers = ["filename", "thema", "category", "time", "place", "person", "summary"]
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results)
        
        logger.info(f"Saved CSV file: {output_path}")
    except Exception as e:
        logger.error(f"CSV save error: {e}")

def main():
    """Main routine."""
    logger.info("Starting PDF structured data extraction")
    
    # Check OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY is not set. Please check your .env file.")
        return
    
    # Process all PDFs
    results = process_all_pdfs()
    
    # Save to CSV
    if results:
        save_to_csv(results)
        logger.info(f"Done: structured {len(results)} PDFs")
    else:
        logger.warning("No processable PDFs found")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Analyze Google Sheets results data to check participant progress.
"""
import json
from auth_helper import get_sheets_client
import config

def analyze_participant_progress():
    """Analyze participant progress from Google Sheets results data."""
    try:
        # Initialize Google Sheets client
        client = get_sheets_client()
        if not client:
            print("Failed to initialize Google Sheets client")
            return None
        
        # Get results sheet
        results_spreadsheet = client.open_by_key(config.RESULTS_SPREADSHEET_ID)
        results_sheet = results_spreadsheet.worksheet(config.RESULTS_WORKSHEET_NAME)
        
        # Fetch all records
        all_records = results_sheet.get_all_records()
        print(f"Fetched record count: {len(all_records)}")
        
        # Aggregate progress per participant
        participant_progress = {}
        
        for record in all_records:
            participant_name = record.get('participant_name', '').strip()
            processed = str(record.get('processed', '')).strip().upper()
            paper_id = str(record.get('paper_id', '')).strip()
            has_summary = str(record.get('has_summary', '')).strip().upper()
            
            # Count only records where processed == TRUE
            if processed == 'TRUE' and participant_name and paper_id:
                if participant_name not in participant_progress:
                    participant_progress[participant_name] = {
                        'completed_evaluations': [],
                        'total_completed': 0
                    }
                
                # Record details of completed evaluation
                evaluation_detail = {
                    'paper_id': paper_id,
                    'has_summary': has_summary == 'TRUE',
                    'evaluation': record.get('evaluation', ''),
                    'timestamp': record.get('timestamp', '')
                }
                
                participant_progress[participant_name]['completed_evaluations'].append(evaluation_detail)
                participant_progress[participant_name]['total_completed'] += 1
        
        # Print results
        print("\n=== Participant Progress ===")
        for participant_name, progress in participant_progress.items():
            print(f"\n{participant_name}: {progress['total_completed']} completed")
            for i, eval_detail in enumerate(progress['completed_evaluations'], 1):
                summary_status = "LLM" if eval_detail['has_summary'] else "No LLM"
                print(f"  {i}. Paper {eval_detail['paper_id']} ({summary_status}) - {eval_detail['timestamp']}")
        
        # Reverse-lookup participant IDs
        name_to_id = {name: pid for pid, name in config.PARTICIPANT_NAMES.items()}
        
        # Build mapping for evaluation_records.json
        participant_slot_mapping = {}
        for participant_name, progress in participant_progress.items():
            participant_id = name_to_id.get(participant_name)
            if participant_id:
                completed_count = progress['total_completed']
                next_slot = completed_count + 1 if completed_count < 4 else 5  # 5 means all done
                participant_slot_mapping[participant_id] = {
                    'completed_slots': completed_count,
                    'next_slot': next_slot,
                    'completed_evaluations': progress['completed_evaluations']
                }
        
        print("\n=== Participant ID Mapping ===")
        for pid, mapping in participant_slot_mapping.items():
            participant_name = config.PARTICIPANT_NAMES.get(pid, pid)
            print(f"{pid} ({participant_name}): {mapping['completed_slots']} slots complete → next slot {mapping['next_slot']}")
        
        return participant_slot_mapping
        
    except Exception as e:
        print(f"Error analyzing progress: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main"""
    print("Analyzing Google Sheets results data...")
    progress_mapping = analyze_participant_progress()
    
    if progress_mapping:
        print("\nDone. Ready to reflect progress into evaluation_records.json.")
        
        # Save to JSON (for debugging)
        with open('progress_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(progress_mapping, f, indent=2, ensure_ascii=False)
        print("Saved analysis results to progress_analysis.json.")
    else:
        print("Failed to analyze progress.")

if __name__ == "__main__":
    main()

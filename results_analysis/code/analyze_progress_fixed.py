#!/usr/bin/env python3
"""
Analyze Google Sheets results data to check participant progress (revised version).
"""
import json
from auth_helper import get_sheets_client
import config

def analyze_participant_progress():
    """Analyze participant progress from Google Sheets results (revised)."""
    try:
        # Get Google Sheets client
        sheets_client = get_sheets_client()
        
        # Read data from Results sheet
        sheet = sheets_client.open_by_key(config.RESULTS_SPREADSHEET_ID)
        results_worksheet = sheet.worksheet('Results')
        all_records = results_worksheet.get_all_records()
        
        print(f"Fetched record count: {len(all_records)}")
        
        # Track participant progress
        participant_progress = {}
        
        for record in all_records:
            participant_name = record.get('participant_name', '').strip()
            paper_id = str(record.get('paper_id', '')).strip()
            action = record.get('action', '').strip()
            end_time = record.get('end_time', '').strip()
            has_summary = record.get('has_summary', '')
            
            # Consider as completed only if: valid participant, not INTERRUPTED, and has end_time
            if (participant_name and 
                participant_name in config.PARTICIPANT_NAMES.values() and 
                paper_id and 
                'INTERRUPTED' not in action and 
                end_time):
                
                if participant_name not in participant_progress:
                    participant_progress[participant_name] = {
                        'completed_evaluations': [],
                        'total_completed': 0
                    }
                
                # Normalize has_summary value
                has_summary_bool = has_summary in [True, 'True', 'TRUE', 'true']
                
                # Record details for completed evaluation
                evaluation_detail = {
                    'paper_id': paper_id,
                    'has_summary': has_summary_bool,
                    'action': action,
                    'timestamp': record.get('timestamp', ''),
                    'start_time': record.get('start_time', ''),
                    'end_time': end_time
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
        
        # Add participants who haven't started yet
        for pid, name in config.PARTICIPANT_NAMES.items():
            if pid not in participant_slot_mapping and pid != 'test':
                participant_slot_mapping[pid] = {
                    'completed_slots': 0,
                    'next_slot': 1,
                    'completed_evaluations': []
                }
        
        print("\n=== Participant ID Mapping ===")
        for pid, mapping in participant_slot_mapping.items():
            participant_name = config.PARTICIPANT_NAMES.get(pid, pid)
            if pid != 'test':  # exclude test user
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
        print("\n✅ Done. Ready to reflect progress into evaluation_records.json.")
        
        # Save to JSON (for debugging)
        with open('participant_progress_mapping.json', 'w', encoding='utf-8') as f:
            json.dump(progress_mapping, f, indent=2, ensure_ascii=False)
        print("Created debug file 'participant_progress_mapping.json'.")
        
        return progress_mapping
    else:
        print("❌ Failed to analyze progress.")
        return None

if __name__ == "__main__":
    main()

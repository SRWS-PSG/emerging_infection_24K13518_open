"""
新興感染症のシステマティック・レビュー研究のためのウェブフォーム実装例
クロスオーバーRCT用のランダム割り付け機能付きStreamlitアプリケーション
（進捗管理はGoogle Spreadsheetで行うバージョン）
"""

import streamlit as st
import pandas as pd
import time
import random
import os
from datetime import datetime
import json
import config
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

# 静的ファイル配信の設定
@st.cache_data
def get_pdf_path(filename):
    """PDFファイルのパスを取得"""
    static_path = os.path.join(os.path.dirname(__file__), 'static', 'pdf', filename)
    if os.path.exists(static_path):
        return f"/app/static/pdf/{filename}"
    return None

def serve_pdf_file(paper_id):
    """PDFファイルを直接提供する"""
    # 論文IDからファイル名をマッピング
    pdf_mapping = {
        "1": "2023_EID_Teco.pdf",
        "2": "2022_NEJM_Review.pdf", 
        "3": "2023_MMWR_Vaccine.pdf",
        "4": "2023_Lancet Microbe_respiratory.pdf",
        "5": "2022_Eurosuveilance_Pet.pdf",
        "6": "2022_CID_self swab.pdf"
    }
    
    filename = pdf_mapping.get(paper_id)
    if not filename:
        return None
        
    pdf_path = os.path.join(os.path.dirname(__file__), 'static', 'pdf', filename)
    if os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        return pdf_data, filename
    return None

# evaluation_records.jsonからデータを読み取り・書き込みするための関数

def load_evaluation_records():
    """evaluation_records.jsonからレコードを読み込む"""
    try:
        with open(config.EVAL_RECORDS_PATH, 'r', encoding='utf-8') as file:
            records = json.load(file)
        return records
    except (FileNotFoundError, json.JSONDecodeError) as e:
        st.error(f"評価レコードファイルの読み込みエラー: {e}")
        return []

def save_evaluation_records(records):
    """evaluation_records.jsonにレコードを保存"""
    try:
        with open(config.EVAL_RECORDS_PATH, 'w', encoding='utf-8') as file:
            json.dump(records, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"評価レコードファイルの保存エラー: {e}")
        return False

def initialize_sheets_client():
    """Google Sheets APIクライアントを初期化"""
    try:
        from auth_helper import get_sheets_client
        return get_sheets_client()
    except Exception as e:
        st.error(f"Google Sheets認証エラー: {e}")
        return None

def initialize_sheets_client_old():
    """Google Sheets APIクライアントを初期化（旧バージョン）"""
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    import config
    
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    credentials_path = os.path.join(os.path.dirname(__file__), config.CREDENTIALS_PATH)
    
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Google Sheets API認証エラー: {e}")
        return None

def get_papers_worksheet():
    """論文データが格納されているワークシートを取得"""
    client = initialize_sheets_client()
    if not client:
        return None
    try:
        spreadsheet = client.open_by_key(config.PAPERS_SPREADSHEET_ID)
        sheet = spreadsheet.worksheet(config.PAPERS_WORKSHEET_NAME)
        return sheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"論文データ用スプレッドシート (ID: {config.PAPERS_SPREADSHEET_ID}) が見つかりません。")
        return None
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"論文データ用ワークシート '{config.PAPERS_WORKSHEET_NAME}' が見つかりません。")
        return None
    except Exception as e:
        st.error(f"論文データ用ワークシートの取得中にエラー: {e}")
        return None

def get_results_worksheet():
    """結果と進捗を管理するワークシートを取得。なければ作成。"""
    client = initialize_sheets_client()
    if not client:
        return None
    try:
        spreadsheet = client.open_by_key(config.RESULTS_SPREADSHEET_ID)
        try:
            worksheet = spreadsheet.worksheet(config.RESULTS_WORKSHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            st.info(f"結果保存用ワークシート '{config.RESULTS_WORKSHEET_NAME}' が見つかりません。作成します。")
            worksheet = spreadsheet.add_worksheet(title=config.RESULTS_WORKSHEET_NAME, rows="1000", cols=len(config.RESULTS_HEADERS) + 5)
            worksheet.append_row(config.RESULTS_HEADERS)
            st.info(f"ワークシート '{config.RESULTS_WORKSHEET_NAME}' を作成し、ヘッダーを書き込みました。")
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"結果保存用スプレッドシート (ID: {config.RESULTS_SPREADSHEET_ID}) が見つかりません。setup_spreadsheets.py を実行して作成してください。")
        return None
    except Exception as e:
        st.error(f"結果保存用ワークシートの取得中にエラー: {e}")
        return None

def update_csv_info_from_sheets():
    """Google Sheetsから最新の論文メタデータを取得してevaluation_records.jsonの_csv_infoフィールドを更新"""
    try:
        # Google Sheetsから論文データを取得
        papers_sheet = get_papers_worksheet()
        if not papers_sheet:
            print("⚠️ 論文データシートの取得に失敗しました。既存のJSONデータを使用します。")
            return False
        
        # ヘッダー行を取得
        headers = papers_sheet.row_values(1)
        if "paper_id" not in headers:
            print("⚠️ 論文データシートに 'paper_id' 列が見つかりません。")
            return False
        
        # 全データを取得
        all_records = papers_sheet.get_all_records()
        
        # paper_idをキーとした辞書を作成
        paper_metadata = {}
        for record in all_records:
            paper_id = str(record.get('paper_id', '')).strip()
            if paper_id:
                # CSV情報として保存したいフィールドを抽出
                csv_info = {
                    'thema': record.get('thema', ''),
                    'category': record.get('category', ''),
                    'place': record.get('place', ''),
                    'time': record.get('time', ''),
                    'person': record.get('person', ''),
                    'summary': record.get('summary', '')
                }
                paper_metadata[paper_id] = csv_info
        
        # evaluation_records.jsonを更新
        records = load_evaluation_records()
        if not records:
            print("⚠️ evaluation_records.jsonが見つかりません。")
            return False
        
        updated_count = 0
        for record in records:
            paper_id = record.get('paper_id', '')
            if paper_id in paper_metadata:
                # _csv_infoフィールドを更新
                record['_csv_info'] = paper_metadata[paper_id]
                updated_count += 1
        
        # 更新したレコードを保存
        if save_evaluation_records(records):
            print(f"✅ {updated_count}件のレコードの_csv_info情報を更新しました。")
            return True
        else:
            print("❌ evaluation_records.jsonの保存に失敗しました。")
            return False
            
    except Exception as e:
        print(f"⚠️ _csv_info更新中にエラーが発生しました: {e}")
        return False

def get_all_paper_ids_from_papers_sheet():
    """論文データシートから全ての論文IDのリストを取得"""
    papers_sheet = get_papers_worksheet()
    if not papers_sheet:
        return []
    try:
        # paper_id列のインデックスを取得 (1始まり)
        headers = papers_sheet.row_values(1)
        if "paper_id" not in headers:
            st.error("論文データシートに 'paper_id' 列が見つかりません。")
            return []
        paper_id_col_index = headers.index("paper_id") + 1
        paper_ids = papers_sheet.col_values(paper_id_col_index)[1:] # ヘッダーを除外
        return [pid for pid in paper_ids if pid] # 空のIDを除外
    except Exception as e:
        st.error(f"論文IDリストの取得中にエラー: {e}")
        return []

def get_current_slot_for_participant(participant_id):
    """
    参加者IDから現在評価すべきslotレコードを取得する（slot-based構造対応）
    """
    try:
        records = load_evaluation_records()
        if not records:
            st.error("評価レコードが見つかりません。")
            return None
        
        # 指定参加者のレコードを取得
        participant_records = [r for r in records if r.get("participant_id") == participant_id]
        
        if not participant_records:
            st.error(f"参加者 {participant_id} のレコードが見つかりません。")
            return None
        
        # slot順でソートして未完了の最初のslotを取得
        participant_records.sort(key=lambda x: x.get("slot", 0))
        
        for record in participant_records:
            if record.get("status") == "assigned" and not record.get("processed"):
                # 開始時刻を設定
                record["start_timestamp"] = time.time()
                save_evaluation_records(records)
                
                st.info(f"Slot {record['slot']} を開始します: 論文{record['paper_id']} ({'LLMあり' if record['has_summary'] else 'LLMなし'})")
                return record
        
        # すべてのslotが完了している場合
        completed_slots = len([r for r in participant_records if r.get("status") == "completed"])
        st.success(f"参加者 {participant_id} のすべての評価が完了しています！ (完了: {completed_slots}/4 slots)")
        return None
        
    except Exception as e:
        st.error(f"現在slot取得中にエラー: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None

def get_participant_progress(participant_id):
    """参加者の進捗情報を取得"""
    try:
        records = load_evaluation_records()
        participant_records = [r for r in records if r.get("participant_id") == participant_id]
        
        if not participant_records:
            return {"completed_slots": 0, "current_slot": 1, "total_slots": 4}
        
        completed_slots = len([r for r in participant_records if r.get("status") == "completed"])
        current_slot = 1
        
        # 次の未完了slotを探す
        participant_records.sort(key=lambda x: x.get("slot", 0))
        for record in participant_records:
            if record.get("status") != "completed":
                current_slot = record.get("slot", 1)
                break
        else:
            current_slot = 5  # 全完了
            
        return {
            "completed_slots": completed_slots,
            "current_slot": current_slot,
            "total_slots": 4
        }
        
    except Exception as e:
        st.error(f"進捗取得エラー: {e}")
        return {"completed_slots": 0, "current_slot": 1, "total_slots": 4}


def get_unprocessed_record_from_sheet(participant_name):
    """
    JSONファイルから未処理の論文を割り当てる。
    Spreadsheetバージョンからの移行用のラッパー関数。
    """
    return get_unprocessed_record_from_json(participant_name)

def handle_interruption(participant_id, slot, paper_id):
    """
    評価中断処理（slot-based対応）
    中断された論文を除外し、代替論文を割り当て
    """
    try:
        records = load_evaluation_records()
        if not records:
            st.error("評価レコードが見つかりません。")
            return False
        
        # 対象レコードを検索
        target_record = None
        for record in records:
            if (record.get("participant_id") == participant_id and 
                record.get("slot") == slot and
                record.get("paper_id") == paper_id):
                target_record = record
                break
        
        if not target_record:
            st.error(f"中断対象のレコードが見つかりません: 参加者{participant_id} slot{slot} 論文{paper_id}")
            return False
        
        # 中断論文を除外リストに追加
        if paper_id not in target_record.get("excluded_papers", []):
            if "excluded_papers" not in target_record:
                target_record["excluded_papers"] = []
            target_record["excluded_papers"].append(paper_id)
        
        # 代替論文を選択
        replacement_paper = select_replacement_paper(target_record)
        
        if replacement_paper:
            # 代替論文を割り当て
            target_record["paper_id"] = replacement_paper
            target_record["status"] = "assigned"
            target_record["start_timestamp"] = None  # 再開時に設定
            
            # JSONファイルに保存
            save_evaluation_records(records)
            
            # Google Sheetsに中断記録を保存
            save_interruption_to_sheets(participant_id, slot, paper_id, replacement_paper)
            
            st.warning(f"論文{paper_id}を中断しました。代替論文{replacement_paper}を割り当てました。")
            return True
        else:
            st.error("利用可能な代替論文がありません。")
            return False
            
    except Exception as e:
        st.error(f"中断処理エラー: {e}")
        import traceback
        st.error(traceback.format_exc())
        return False

def select_replacement_paper(record):
    """代替論文を選択"""
    try:
        # 全論文リスト
        all_papers = ["1", "2", "3", "4", "5", "6"]
        
        # 除外論文
        excluded_papers = record.get("excluded_papers", [])
        
        # 利用可能な論文
        available_papers = [p for p in all_papers if p not in excluded_papers]
        
        if not available_papers:
            return None
        
        # LLM条件に合う論文を選択（シンプルにランダム選択）
        import random
        selected_paper = random.choice(available_papers)
        
        return selected_paper
        
    except Exception as e:
        st.error(f"代替論文選択エラー: {e}")
        return None

def save_interruption_to_sheets(participant_id, slot, interrupted_paper, replacement_paper):
    """中断記録をGoogle Sheetsに保存"""
    try:
        results_sheet = get_results_worksheet()
        if not results_sheet:
            return False
        
        # 中断記録を作成（participant_nameを含める）
        participant_name = participant_id
        interruption_row = [
            participant_name,  # participant_name
            "",  # has_summary (中断時は空欄)
            interrupted_paper,  # paper_id
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # start_time
            "",  # end_time (空)
            "",  # answer_time (空)
            "",  # evaluation (空)
            f"INTERRUPTED (replaced with {replacement_paper})",  # action
            "",  # summary (空)
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # timestamp
        ]
        
        results_sheet.append_row(interruption_row)
        return True
        
    except Exception as e:
        st.warning(f"中断記録のGoogle Sheets保存エラー: {e}")
        return False
            
        st.success("中断レコードをJSONファイルに保存しました。該当論文は再割り当て可能になりました。")
        
        # スプレッドシートにも中断記録を保存
        save_interruption_to_sheet(interruption_data)
        
        return True
        
    except Exception as e:
        st.error(f"中断レコードの保存中にエラー: {e}")
        import traceback
        st.error(traceback.format_exc())
        return False

def save_interruption_to_sheet(interruption_data):
    """中断記録をスプレッドシートに保存"""
    results_sheet = get_results_worksheet()
    if not results_sheet:
        st.warning("中断記録をスプレッドシートに保存できませんでした。")
        return False

    try:
        # 中断記録として保存（processedはFALSE、特別な中断フラグを設定）
        form_data_dict = interruption_data.get("form_data", {})
        row_to_save = []
        
        for header in config.RESULTS_HEADERS:
            if header == "participant_name": 
                row_to_save.append(f"{interruption_data.get('participant_name', '')} (中断)")
            elif header == "has_summary": 
                row_to_save.append(str(interruption_data.get("has_summary", False)))
            elif header == "paper_id": 
                row_to_save.append(interruption_data.get("paper_id", ""))
            elif header == "start_time": 
                row_to_save.append(str(interruption_data.get("start_time", "")))
            elif header == "end_time": 
                row_to_save.append(str(interruption_data.get("interruption_timestamp", "")))
            elif header == "answer_time": 
                row_to_save.append(str(interruption_data.get("answer_time", "")))
            elif header == "action": 
                row_to_save.append(form_data_dict.get("action", ""))
            elif header == "timestamp": 
                row_to_save.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            else: 
                row_to_save.append("")
        
        # 中断フラグを追加（HEADERSにない場合は最後に追加）
        row_to_save.append("INTERRUPTED")
        
        results_sheet.append_row(row_to_save)
        st.success("中断記録をスプレッドシートに保存しました。")
        return True
        
    except Exception as e:
        st.warning(f"中断記録のスプレッドシート保存エラー: {e}")
        return False

def handle_completion(participant_id, slot, evaluation_data):
    """
    評価完了処理（slot-based対応）
    評価結果を保存し、継続選択画面に遷移
    """
    try:
        records = load_evaluation_records()
        if not records:
            st.error("評価レコードが見つかりません。")
            return False
        
        # 対象レコードを検索
        target_record = None
        for record in records:
            if (record.get("participant_id") == participant_id and 
                record.get("slot") == slot and
                not record.get("processed")):
                target_record = record
                break
        
        if not target_record:
            st.error(f"完了対象のレコードが見つかりません: 参加者{participant_id} slot{slot}")
            return False
        
        # レコードを完了状態に更新
        submit_time = time.time()
        start_time = target_record.get("start_timestamp", submit_time)
        work_duration = int(submit_time - start_time) if start_time else 0
        
        target_record["status"] = "completed"
        target_record["processed"] = True
        target_record["submit_timestamp"] = submit_time
        target_record["work_duration"] = work_duration
        target_record["evaluation"] = evaluation_data.get("evaluation", "")
        target_record["action"] = evaluation_data.get("action", "")
        target_record["summary"] = evaluation_data.get("summary", "")  # summaryを追加
        
        # JSONファイルに保存
        if not save_evaluation_records(records):
            st.error("評価レコードの保存に失敗しました。")
            return False
            
        # Google Sheetsに結果保存
        save_completion_to_sheets(target_record)
        
        st.success(f"Slot {slot} の評価が完了しました！")
        
        # 継続選択を設定
        st.session_state.show_continuation_choice = True
        st.session_state.completed_slot = slot
        st.session_state.participant_id = participant_id
        
        return True
        
    except Exception as e:
        st.error(f"完了処理エラー: {e}")
        import traceback
        st.error(traceback.format_exc())
        return False

def save_completion_to_sheets(record):
    """完了した評価結果をGoogle Sheetsに保存"""
    try:
        results_sheet = get_results_worksheet()
        if not results_sheet:
            return False
        
        # 完了記録を作成
        start_time = record.get("start_timestamp")
        submit_time = record.get("submit_timestamp")
        
        # participant_nameを含めて保存（RESULTS_HEADERS順）
        # 公開版では参加者マッピングを使用せず、ID（または入力名）をそのまま保存
        participant_name = record.get("participant_name", record.get("participant_id", ""))
        completion_row = [
            participant_name,  # participant_nameフィールドに実名を保存
            str(record.get("has_summary", False)),
            record.get("paper_id", ""),
            datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S') if start_time else "",
            datetime.fromtimestamp(submit_time).strftime('%Y-%m-%d %H:%M:%S') if submit_time else "",
            str(record.get("work_duration", 0)),
            record.get("evaluation", ""),  # evaluationフィールドを追加
            record.get("action", ""),
            record.get("summary", ""),  # summaryフィールドを追加
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ]
        
        results_sheet.append_row(completion_row)
        return True
        
    except Exception as e:
        st.warning(f"完了記録のGoogle Sheets保存エラー: {e}")
        return False

def update_record_in_sheet(updated_record_data):
    """Resultsスプレッドシートにレコードを更新・追加（バックアップ用）"""
    results_sheet = get_results_worksheet()
    if not results_sheet:
        st.error("結果の保存に失敗しました: Resultsシートにアクセスできません。")
        return False

    try:
        # participant_name, paper_id, has_summary で該当行を検索
        # start_time もキーに加えることで、同じ参加者が同じ論文・条件を複数回行うケースに対応（通常はないが念のため）
        
        # まず全レコードを取得
        all_records = results_sheet.get_all_records()
        
        target_row_index = -1
        for idx, record in enumerate(all_records):
            # gspreadはbool値を文字列 "TRUE" / "FALSE" で返すことがあるので比較時に注意
            record_has_summary_str = str(record.get("has_summary", "")).strip().upper()
            updated_has_summary_str = str(updated_record_data.get("has_summary", "")).strip().upper()

            if str(record.get("participant_name", "")) == str(updated_record_data.get("participant_name", "")) and \
               str(record.get("paper_id", "")) == str(updated_record_data.get("paper_id", "")) and \
               record_has_summary_str == updated_has_summary_str and \
               str(record.get("processed", "")).lower() != "true": # まだ処理されていないものを対象
                # 最もstart_timeが近いもの（あるいはstart_timeで一意に特定できるもの）を選ぶ
                # ここでは簡単化のため、最初に見つかった未処理のものを更新対象とする
                # 厳密には、割り当て時のstart_timestampと一致するものを探すべき
                target_row_index = idx + 2 # gspreadの行インデックスは1始まり、ヘッダー行があるので+2
                break
        
        if target_row_index == -1:
            st.error(f"更新対象のレコードが見つかりません: {updated_record_data}")
            # 見つからない場合は新規行として追加する（フォールバック）
            st.warning("更新対象が見つからなかったため、新規行として結果を保存します。")
            row_to_save = [
                updated_record_data.get("participant_name", ""),
                str(updated_record_data.get("has_summary", False)),
                updated_record_data.get("paper_id", ""),
                str(updated_record_data.get("start_time", "")), # session_stateから
                str(updated_record_data.get("submit_timestamp", "")),
                str(updated_record_data.get("answer_time", "")),
                updated_record_data.get("evaluation", ""),
                updated_record_data.get("action", ""),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'), # timestamp 列
                "TRUE" # processed 列
            ]
            # RESULTS_HEADERSの順序に合わせて整形
            final_row_to_save = []
            form_data_dict = updated_record_data.get("form_data", {}) # submit時のデータ
            for header in config.RESULTS_HEADERS:
                if header == "participant_name": final_row_to_save.append(updated_record_data.get("participant_name", ""))
                elif header == "has_summary": final_row_to_save.append(str(updated_record_data.get("has_summary", False)))
                elif header == "paper_id": final_row_to_save.append(updated_record_data.get("paper_id", ""))
                elif header == "start_time": final_row_to_save.append(str(updated_record_data.get("start_time", "")))
                elif header == "end_time": final_row_to_save.append(str(updated_record_data.get("submit_timestamp", ""))) # end_timeはsubmit_timestamp
                elif header == "answer_time": final_row_to_save.append(str(updated_record_data.get("answer_time", "")))
                elif header == "evaluation": final_row_to_save.append(form_data_dict.get("evaluation", ""))
                elif header == "action": final_row_to_save.append(form_data_dict.get("action", ""))
                elif header == "summary": final_row_to_save.append(form_data_dict.get("summary", ""))
                elif header == "timestamp": final_row_to_save.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                elif header == "processed": final_row_to_save.append("TRUE")
                else: final_row_to_save.append(form_data_dict.get(header, "")) # その他のカスタムフィールド
            results_sheet.append_row(final_row_to_save)
            st.success("結果を新しい行としてResultsシートに保存しました。")
            return True

        # 更新するデータを準備
        # RESULTS_HEADERS に基づいて更新
        updates = []
        form_data_dict = updated_record_data.get("form_data", {})

        if "evaluation" in config.RESULTS_HEADERS:
            updates.append(gspread.Cell(target_row_index, config.RESULTS_HEADERS.index("evaluation") + 1, form_data_dict.get("evaluation", "")))
        if "action" in config.RESULTS_HEADERS:
            updates.append(gspread.Cell(target_row_index, config.RESULTS_HEADERS.index("action") + 1, form_data_dict.get("action", "")))
        if "end_time" in config.RESULTS_HEADERS: # submit_timestamp を end_time にマッピング
            updates.append(gspread.Cell(target_row_index, config.RESULTS_HEADERS.index("end_time") + 1, str(updated_record_data.get("submit_timestamp", ""))))
        if "answer_time" in config.RESULTS_HEADERS:
            updates.append(gspread.Cell(target_row_index, config.RESULTS_HEADERS.index("answer_time") + 1, str(updated_record_data.get("answer_time", ""))))
        if "processed" in config.RESULTS_HEADERS:
             updates.append(gspread.Cell(target_row_index, config.RESULTS_HEADERS.index("processed") + 1, "TRUE")) # 文字列 "TRUE"
        if "timestamp" in config.RESULTS_HEADERS: # 最終更新時刻
            updates.append(gspread.Cell(target_row_index, config.RESULTS_HEADERS.index("timestamp") + 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        if updates:
            results_sheet.update_cells(updates, value_input_option='USER_ENTERED')
        st.success("レコードをResultsシートで更新しました。")
        return True
    except Exception as e:
        st.error(f"レコードの更新中にエラー: {e}")
        import traceback
        st.error(traceback.format_exc())
        # フォールバックとしてローカルに保存する処理は削除（スプレッドシート一本化のため）
        return False


st.set_page_config(
    page_title="論文データ抽出システム評価",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def load_css():
    """カスタムCSSをロード"""
    st.markdown("""
    <style>
        /* 全体のフォントとスタイル */
        .stApp {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: var(--text-color);
        }
        
        /* ライトモードのデフォルト設定 */
        :root {
            --background-color: #ffffff;
            --text-color: #000000;
            --text-secondary: #333333;
            --border-color: #e1e8ed;
            --card-shadow: 0 4px 12px rgba(0,0,0,0.1);
            --highlight-color: #3498db;
            --success-bg: #d4edda;
            --success-color: #155724;
            --input-bg: #ffffff;
            --input-border: #ced4da;
        }
        
        /* Streamlitダークテーマ対応 */
        [data-theme="dark"] {
            --background-color: #0e1117;
            --text-color: #fafafa;
            --text-secondary: #e0e0e0;
            --border-color: #262730;
            --card-shadow: 0 4px 12px rgba(0,0,0,0.5);
            --highlight-color: #5cabff;
            --success-bg: #1e4835;
            --success-color: #a1e3b3;
            --input-bg: #262730;
            --input-border: #4a4a4a;
        }
        
        /* システムダークモード対応（フォールバック） */
        @media (prefers-color-scheme: dark) {
            :root {
                --background-color: #0e1117;
                --text-color: #fafafa;
                --text-secondary: #e0e0e0;
                --border-color: #262730;
                --card-shadow: 0 4px 12px rgba(0,0,0,0.5);
                --highlight-color: #5cabff;
                --success-bg: #1e4835;
                --success-color: #a1e3b3;
                --input-bg: #262730;
                --input-border: #4a4a4a;
            }
        }
        
        /* テキスト色をCSS変数で制御 */
        .stApp p, .stApp span, .stApp div, .stApp label {
            color: var(--text-color);
        }
        
        body, .stApp {
            color: var(--text-color);
            background-color: var(--background-color);
        }
        
        /* テキスト入力とテキストエリア */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            background-color: var(--input-bg) !important;
            color: var(--text-color) !important;
            border: 1px solid var(--input-border) !important;
        }
        
        /* ラジオボタンのラベル */
        .stRadio > div label {
            color: var(--text-color);
            font-weight: normal;
        }
        
        /* マークダウンコンテンツ */
        .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            color: var(--text-color);
        }
        
        /* ヘッダースタイル */
        h1 {
            color: var(--text-color); 
            font-weight: 600; 
            border-bottom: 2px solid var(--highlight-color); 
            padding-bottom: 10px; 
            margin-bottom: 30px;
        }
        
        h2 {
            color: var(--text-color);
            font-weight: 500;
            margin-top: 20px;
            margin-bottom: 15px;
            font-size: 1.5rem;
        }
        
        /* カードスタイル */
        .paper-info-card {
            background-color: var(--background-color);
            color: var(--text-color);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            box-shadow: var(--card-shadow);
            padding: 20px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
        }
        
        .paper-info-card:hover {
            box-shadow: 0 6px 16px rgba(0,0,0,0.15);
        }
        
        /* 論文タイトル */
        .paper-title {
            font-size: 1.4rem;
            font-weight: 600;
            color: var(--text-color);
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border-color);
        }
        
        /* 書誌情報 */
        .bibliographic-info {
            font-size: 0.9rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border-color);
        }
        
        /* 入力フォーム */
        .input-form {
            background-color: var(--background-color);
            border-radius: 10px;
            box-shadow: var(--card-shadow);
            padding: 20px;
            border: 1px solid var(--border-color);
        }
        
        /* 完了メッセージ */
        .completion-message {
            background-color: var(--success-bg);
            color: var(--success-color);
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            text-align: center;
            box-shadow: var(--card-shadow);
        }
        
        /* ボタンスタイル */
        .stButton > button {
            background-color: var(--highlight-color);
            color: white;
            border-radius: 5px;
            border: none;
            padding: 0.5rem 1rem;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            background-color: #2980b9;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        /* プログレスバー */
        .progress-container {
            width: 100%;
            background-color: var(--border-color);
            border-radius: 5px;
            margin: 10px 0;
            height: 8px;
        }
        
        .progress-bar {
            height: 8px;
            background-color: var(--highlight-color);
            border-radius: 5px;
            transition: width 0.5s ease;
        }
        
        /* サマリー表示スタイル */
        .summary-header {
            font-weight: 500;
            font-size: 1rem;
            margin-bottom: 5px;
            color: var(--text-color);
        }
        
        [data-testid="stTextArea"] textarea {
            font-size: 1.05rem !important;
            line-height: 1.5 !important;
            background-color: var(--background-color) !important;
            border-left: 3px solid var(--highlight-color) !important;
            padding: 10px !important;
        }
        
        /* サマリーフィールド用の特別スタイル */
        [data-key="summary_field"] textarea {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
            letter-spacing: 0.01rem !important;
        }
        
        /* PDFリンク強調表示 */
        .pdf-link {
            display: inline-block;
            padding: 5px 10px;
            background-color: var(--highlight-color);
            color: white;
            border-radius: 4px;
            text-decoration: none;
            margin-top: 10px;
            transition: all 0.3s ease;
        }
        
        .pdf-link:hover {
            background-color: #2980b9;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        
        /* タイムスタンプ表示 */
        .timestamp-display {
            font-size: 0.9rem;
            color: #888;
            margin-top: 5px;
            text-align: right;
        }
    </style>
    """, unsafe_allow_html=True)

def calculate_summary_height(summary_text, has_summary=False):
    """サマリーテキストから適切な表示高さを計算"""
    if not has_summary or not summary_text:
        # サマリーなし群は入力用に十分な高さを確保
        return 250  # 入力しやすいように少し大きめ
    
    # サマリーあり群は内容に応じて調整
    lines = summary_text.count('\n') + 1
    bullet_points = summary_text.count('・')
    estimated_lines = max(lines, bullet_points)
    
    # 1行あたり45ピクセルで計算
    height = estimated_lines * 45 + 50  # 余白を追加
    
    # 最小250、最大400に制限
    return min(max(height, 250), 400)

def get_paper_data_from_spreadsheet(paper_id):
    """
    Google Spreadsheetから論文データを取得する関数
    """
    progress_message = st.empty() # 進捗メッセージ表示用のプレースホルダー
    try:
        progress_message.info(f"論文情報を読み込んでいます (論文ID: {paper_id})...")
        
        papers_sheet = get_papers_worksheet()
        if not papers_sheet:
            progress_message.warning("論文データシートの取得に失敗しました。サンプルデータを使用します。")
            return _get_sample_paper_data()
        
        paper_data_cell = papers_sheet.find(paper_id) # gspread.Cell オブジェクト
        if not paper_data_cell:
            progress_message.warning(f"論文ID '{paper_id}' が論文データシートで見つかりませんでした。サンプルデータを使用します。")
            return _get_sample_paper_data()
                
        row_values = papers_sheet.row_values(paper_data_cell.row)
        sheet_headers = papers_sheet.row_values(1)  # ヘッダー行を取得
            
        paper_dict = {}
        for i, header in enumerate(sheet_headers):
            if i < len(row_values):
                paper_dict[header] = row_values[i]
            else:
                paper_dict[header] = ""
            
        # PDFリンクの処理: スプレッドシートの 'pdf_link' 列を最優先
        if "pdf_link" in paper_dict and paper_dict["pdf_link"]:
            paper_dict["pdf_link"] = paper_dict["pdf_link"]
        elif "pdf_filename" in paper_dict and paper_dict["pdf_filename"]:
            paper_dict["pdf_link"] = f"{config.PDF_BASE_URL}{paper_dict['pdf_filename']}"
        else:
            paper_dict["pdf_link"] = f"{config.PDF_BASE_URL}{paper_id}.pdf"
            
        progress_message.empty() # 読み込み完了したらメッセージを消す
        return paper_dict

    except Exception as e:
        progress_message.error(f"論文データの取得中にエラーが発生しました: {e}")
        # import traceback # 詳細エラーは通常ユーザーには不要
        # st.error(f"詳細エラー: {traceback.format_exc()}")
        return _get_sample_paper_data()

def _get_sample_paper_data():
    """サンプル論文データを返す"""
    return {
        "title": "COVID-19の新興変異株に対するワクチン効果の体系的レビュー",
        "abstract": "本研究では、COVID-19の新興変異株に対する各種ワクチンの有効性について体系的レビューを行った。mRNAワクチン、ウイルスベクターワクチン、組換えタンパクワクチンを含む主要なCOVID-19ワクチンについて、オミクロン株、デルタ株などの主要変異株に対する有効性データを分析。第1相から第3相試験、および実世界データから得られた結果を統合し、ワクチンの種類、接種回数、接種間隔による防御効果の違いを評価した。追加接種の効果と最適なタイミングについても検討し、今後の変異株出現に備えたワクチン戦略への示唆を提供する。",
        "pdf_link": f"{config.PDF_BASE_URL}covid19_variants.pdf",
        "authors": "鈴木一郎, 田中花子, 佐藤次郎, 山本三郎",
        "journal": "感染症学ジャーナル",
        "year": "2023",
        "doi": "10.1234/jsid.2023.001",
        "thema": "COVID-19ワクチンの変異株への効果",
        "category": "ワクチン効果研究",
        "time": "2021年1月〜2022年6月",
        "place": "グローバル（25カ国）",
        "person": "18歳以上の成人、特に高齢者と基礎疾患保有者",
        "summary": "- mRNAワクチンはオミクロン株に対して70%の有効性\n- 追加接種により効果が15-20%向上\n- 重症化予防効果は90%以上維持"
    }

def get_paper_info_from_spreadsheet(paper_id):
    """
    Google Spreadsheetから論文の基本情報のみを取得する関数 (get_paper_data_from_spreadsheet と同じで良い)
    """
    # 詳細データ取得関数をそのまま呼び出す（表示する側で取捨選択するため）
    return get_paper_data_from_spreadsheet(paper_id)


def _get_sample_paper_info():
    """サンプル論文基本情報を返す"""
    return {
        "title": "COVID-19の新興変異株に対するワクチン効果の体系的レビュー",
        "abstract": "本研究では、COVID-19の新興変異株に対する各種ワクチンの有効性について体系的レビューを行った。mRNAワクチン、ウイルスベクターワクチン、組換えタンパクワクチンを含む主要なCOVID-19ワクチンについて、オミクロン株、デルタ株などの主要変異株に対する有効性データを分析。第1相から第3相試験、および実世界データから得られた結果を統合し、ワクチンの種類、接種回数、接種間隔による防御効果の違いを評価した。追加接種の効果と最適なタイミングについても検討し、今後の変異株出現に備えたワクチン戦略への示唆を提供する。",
        "pdf_link": f"{config.PDF_BASE_URL}covid19_variants.pdf",
        "authors": "鈴木一郎, 田中花子, 佐藤次郎, 山本三郎",
        "journal": "感染症学ジャーナル",
        "year": "2023",
        "doi": "10.1234/jsid.2023.001"
    }

# save_results_to_spreadsheet は update_record_in_sheet に統合・置き換え

def main():
    load_css()
    
    # アプリケーション起動時の自動進捗復元
    if "progress_restored" not in st.session_state:
        st.session_state.progress_restored = False
    
    if not st.session_state.progress_restored:
        try:
            from progress_restore import check_if_restore_needed, restore_progress_from_sheets
            needs_restore, reason = check_if_restore_needed()
            
            if needs_restore:
                with st.spinner("進捗状況を復元中..."):
                    if restore_progress_from_sheets():
                        st.success("✅ 進捗状況を Google Sheets から復元しました")
                        time.sleep(1)  # ユーザーに確認時間を与える
                    else:
                        st.warning("⚠️ 進捗復元に失敗しました。管理者に連絡してください。")
            
            st.session_state.progress_restored = True
            
        except Exception as e:
            st.error(f"❌ 進捗復元処理でエラーが発生しました: {e}")
            st.session_state.progress_restored = True  # エラーでも次回は復元処理をスキップ
    
    # JSONファイルの_csv_info情報を更新（起動時に1回のみ）
    if "csv_info_updated" not in st.session_state:
        st.session_state.csv_info_updated = False
    
    if not st.session_state.csv_info_updated:
        try:
            with st.spinner("論文メタデータを更新中..."):
                if update_csv_info_from_sheets():
                    print("✅ 論文メタデータを Google Sheets から更新しました")
                else:
                    print("⚠️ 論文メタデータの更新をスキップしました（既存データを使用）")
            
            st.session_state.csv_info_updated = True
            
        except Exception as e:
            print(f"⚠️ 論文メタデータ更新中にエラーが発生しました: {e}")
            st.session_state.csv_info_updated = True  # エラーでも次回は更新処理をスキップ
    
    if "page" not in st.session_state:
        st.session_state.page = "consent"
    
    if st.session_state.page == "consent":
        st.title("論文データ抽出システム評価研究")
        
        st.markdown("""
        この研究は、新興感染症のシステマティック・レビューを効率的に実施するためのデータ抽出システムの有効性を評価するものです。
        参加者は論文からデータを抽出する作業を行い、その効率性と正確性を測定します。
        """)
        
        # 参加者入力（公開版では自由入力）
        entered_participant = st.text_input(
            "参加者ID（またはお名前）を入力してください:",
            value="",
            help="入力された文字列がそのまま参加者識別子として使用されます"
        )

        if entered_participant:
            # 進捗情報を表示
            progress = get_participant_progress(entered_participant)
            completed_slots = progress["completed_slots"]
            current_slot = progress["current_slot"]

            st.markdown(f"""
            ### 進捗状況 ({entered_participant})
            - **完了済み**: {completed_slots}/4 slots
            - **次回評価**: Slot {current_slot if current_slot <= 4 else "全完了"}
            """)

            if completed_slots >= 4:
                st.success("🎉 すべてのslot評価が完了しています！")
                st.info("別の参加者IDで開始するか、新しいセッションを開始してください。")
            else:
                if st.button("評価を開始する", type="primary"):
                    st.session_state.participant_id = entered_participant
                    st.session_state.participant_name = entered_participant
                    record_assignment = get_current_slot_for_participant(entered_participant)

                    if record_assignment is None:
                        return

                    st.session_state.eval_record = record_assignment
                    st.session_state.page = "form"
                    st.rerun()
    
    elif st.session_state.page == "form":
        st.title("論文データ抽出フォーム")

        eval_record = st.session_state.eval_record
        participant_id = eval_record["participant_id"]
        slot = eval_record["slot"]
        paper_id = eval_record["paper_id"]
        has_summary = eval_record["has_summary"]
        start_timestamp = eval_record["start_timestamp"]

        participant_name = eval_record.get("participant_name", participant_id)
        st.sidebar.write(f"参加者: {participant_name}")
        st.sidebar.write(f"Slot: {slot}/4")
        st.sidebar.write(f"論文ID: {paper_id}")
        st.sidebar.write(f"割り付け: {'LLMサマリーあり' if has_summary else 'LLMサマリーなし'}")
        st.sidebar.write(f"開始時間: {datetime.fromtimestamp(start_timestamp).strftime('%H:%M:%S')}")
        
        # 進捗表示
        progress = get_participant_progress(participant_id)
        st.sidebar.write(f"進捗: {progress['completed_slots']}/4 slots完了")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("## 論文情報")
            # サマリーあり/なしで取得データを分岐するが、実質同じ関数を呼ぶ
            paper_info = get_paper_data_from_spreadsheet(paper_id) # これが基本情報も含む

            st.markdown(f"""
            <div class="paper-info-card">
                <div class="paper-title">{paper_info.get('title', 'タイトル不明')}</div>
                <div class="bibliographic-info">
                    <p><strong>著者:</strong> {paper_info.get('authors', '著者不明')}</p>
                    <p><strong>ジャーナル:</strong> {paper_info.get('journal', 'ジャーナル不明')}, {paper_info.get('year', '年不明')}</p>
                    <p><strong>DOI:</strong> {paper_info.get('doi', 'DOI不明')}</p>
                </div>
                <p><strong>Abstract:</strong> {paper_info.get('abstract', '抄録なし')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # PDFダウンロードボタンを追加
            pdf_result = serve_pdf_file(str(paper_id))
            if pdf_result:
                pdf_data, filename = pdf_result
                st.download_button(
                    label="📄 PDFをダウンロード",
                    data=pdf_data,
                    file_name=filename,
                    mime="application/pdf",
                    key=f"download_pdf_{paper_info.get('paper_id', '')}"
                )

        with col2:
            st.markdown("## データ入力")

            summary_field_val = ""
            with st.form("data_extraction_form"):
                # 常にサマリーヘッダーを表示
                st.markdown("<div class='summary-header'>サマリー</div>", unsafe_allow_html=True)
                
                if has_summary:
                    # サマリーあり群の場合、o3生成サマリーを編集可能で表示
                    st.markdown("📝 **以下のAI生成サマリーを確認・修正してください（必須）**")
                    summary_field_val = st.text_area("", value=paper_info.get("summary", ""), height=calculate_summary_height(paper_info.get("summary", ""), has_summary=True), key="summary_field")
                else:
                    # サマリーなし群の場合、空のサマリーフィールドに入力必須
                    st.markdown("📝 **論文のサマリーを入力してください（必須）**")
                    summary_field_val = st.text_area("", value="", height=calculate_summary_height("", has_summary=False), placeholder="論文の内容をまとめてください...", key="summary_field")
                
                st.markdown("<style>.stTextArea[data-baseweb='textarea'] {margin-top: -40px;}</style>", unsafe_allow_html=True)
                
                # 評価者の考察フィールド（入力必須）
                st.markdown("📝 **評価者の考察（評価）を入力してください（必須）**")
                evaluation = st.text_area("", height=150, placeholder="論文内容に対するあなたの考察や評価を記述してください...", key="evaluation_field")
                
                # アクションフィールド（入力必須）
                st.markdown("📝 **アクション（今後の対応や理由など）を入力してください（必須）**")
                action = st.text_area("", height=150, placeholder="今後の対応や理由を具体的に記述してください...")

                # ボタンを並べて配置
                col1, col2 = st.columns([1, 1])
                with col1:
                    submitted = st.form_submit_button("評価完了", type="primary")
                with col2:
                    interrupted = st.form_submit_button("評価中断(途中で離席などして、時間評価不能)")

                if submitted:
                    # バリデーション
                    errors = []
                    
                    if not action or not action.strip():
                        errors.append("「アクション」を入力してください。")
                    
                    if not evaluation or not evaluation.strip():
                        errors.append("「評価者の考察（評価）」を入力してください。")
                    
                    if not summary_field_val or not summary_field_val.strip():
                        if has_summary:
                            errors.append("AI生成サマリーを確認・修正してください。")
                        else:
                            errors.append("論文のサマリーを入力してください。")
                    
                    if errors:
                        for error in errors:
                            st.error(error)
                    else:
                        # 評価データを準備
                        evaluation_data = {
                            "evaluation": evaluation.strip(),  # 評価フィールドを使用
                            "action": action.strip(),
                            "summary": summary_field_val.strip()
                        }
                        
                        # 完了処理を実行
                        success = handle_completion(participant_id, slot, evaluation_data)
                        if success:
                            st.session_state.page = "continuation"
                            st.rerun()
                        else:
                            st.error("評価完了処理に失敗しました。")
                
                elif interrupted:
                    # 中断処理を実行
                    success = handle_interruption(participant_id, slot, paper_id)
                    if success:
                        # 中断後も継続選択画面に遷移（完了処理と同じ）
                        st.session_state.page = "continuation"
                        st.rerun()
                    else:
                        st.error("中断処理に失敗しました。")
    
    elif st.session_state.page == "continuation":
        show_continuation_choice()
        
    elif st.session_state.page == "complete":
        st.title("データ入力完了")
        
        st.markdown("""
        <div class="completion-message">
            <h2>ありがとうございました！</h2>
            <p>データ入力が完了しました。</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("## 入力情報")
        
        result_data_display = st.session_state.get("result_data", {})
        answer_time_display = result_data_display.get("answer_time", 0)
        minutes = answer_time_display // 60
        seconds = answer_time_display % 60
        st.write(f"所要時間: {minutes}分 {seconds}秒")
        
        # アクション結果を表示
        form_data = result_data_display.get("form_data", {})
        action_value = form_data.get("action", "")
        
        st.write(f"**アクション**: {action_value}")
        
        if form_data.get("summary") and form_data.get("summary") != "サマリーなし条件":
            st.write("**サマリー**: あり")
        else:
            st.write("**サマリー**: なし")
        
        # 全体の進捗表示 (Resultsシートから計算)
        results_sheet = get_results_worksheet()
        total_papers_count = len(get_all_paper_ids_from_papers_sheet()) * 2 # 各論文にサマリーあり/なしの2条件
        
        processed_count = 0
        if results_sheet:
            all_res_records = results_sheet.get_all_records()
            processed_count = sum(1 for r in all_res_records if str(r.get("processed", "")).lower() == "true")
        
        progress_percentage = (processed_count / total_papers_count * 100) if total_papers_count > 0 else 0

        st.markdown(f"""
        <div>
            <p>全体の進捗（推定）: {processed_count} / {total_papers_count} ({progress_percentage:.1f}%)</p>
            <div class="progress-container">
                <div class="progress-bar" style="width: {progress_percentage}%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("別の論文で再開"):
            # session_stateをクリアして同意ページに戻る
            for key in list(st.session_state.keys()):
                if key not in ['participant_name_input']: # 参加者名は保持しても良いかも
                     del st.session_state[key]
            st.session_state.page = "consent"
            st.rerun()
    
    elif st.session_state.page == "interrupted":
        st.title("中断記録完了")
        
        st.markdown("""
        <div class="completion-message">
            <h2>中断を記録しました</h2>
            <p>この論文は再度割り当て可能になりました。</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("## 中断記録情報")
        
        interruption_data_display = st.session_state.get("interruption_data", {})
        answer_time_display = interruption_data_display.get("answer_time", 0)
        minutes = answer_time_display // 60
        seconds = answer_time_display % 60
        st.write(f"中断までの時間: {minutes}分 {seconds}秒")
        
        st.json(interruption_data_display.get("form_data", {}))
        
        if st.button("別の論文で再開"):
            # session_stateをクリアして同意ページに戻る
            for key in list(st.session_state.keys()):
                if key not in ['participant_name_input']: # 参加者名は保持
                     del st.session_state[key]
            st.session_state.page = "consent"
            st.rerun()
    
    elif st.session_state.page == "thank_you":
        show_thank_you_page()
    
    elif st.session_state.page == "all_complete":
        st.title("研究完了")
        st.success("🎉 すべての評価が完了しました！")
        st.markdown("ご協力ありがとうございました。")
        
        if st.button("新しいセッションを開始"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.session_state.page = "consent"
            st.rerun()

def show_continuation_choice():
    """継続選択画面を表示"""
    st.title("評価完了")
    
    participant_id = st.session_state.get("participant_id", "")
    participant_name = st.session_state.get("participant_name", participant_id)
    completed_slot = st.session_state.get("completed_slot", 0)
    
    st.success(f"Slot {completed_slot} の評価が完了しました！")
    
    # 進捗情報を取得
    progress = get_participant_progress(participant_id)
    completed_slots = progress["completed_slots"]
    next_slot = progress["current_slot"]
    
    st.markdown(f"""
    ### 進捗状況
    - **完了済み**: {completed_slots}/4 slots
    - **参加者**: {participant_name}
    """)
    
    if next_slot <= 4:
        st.markdown(f"**次回評価**: Slot {next_slot}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("次のslotを始める", type="primary"):
                # 次のslotを開始
                # 新しいeval_recordを取得
                record_assignment = get_current_slot_for_participant(participant_id)
                
                if record_assignment is None:
                    st.error("次のスロットが見つかりません。")
                    return
                
                # セッション状態をクリア（必要な情報以外）
                keys_to_keep = ["participant_id", "participant_name", "page"]
                for key in list(st.session_state.keys()):
                    if key not in keys_to_keep:
                        del st.session_state[key]
                
                # 新しいeval_recordを設定してからformページに遷移
                st.session_state.eval_record = record_assignment
                st.session_state.page = "form"
                st.rerun()
        
        with col2:
            if st.button("今日はここまで"):
                st.session_state.page = "thank_you"
                st.rerun()
    else:
        st.success("🎉 すべてのslot評価が完了しました！")
        st.balloons()
        
        if st.button("研究完了"):
            st.session_state.page = "all_complete"
            st.rerun()

def show_thank_you_page():
    """感謝ページを表示"""
    st.title("お疲れさまでした")
    
    participant_id = st.session_state.get("participant_id", "")
    participant_name = st.session_state.get("participant_name", participant_id)
    progress = get_participant_progress(participant_id)
    
    st.markdown(f"""
    ### 本日の評価
    
    参加者: **{participant_name}**  
    完了済み: **{progress["completed_slots"]}/4 slots**
    
    ご協力ありがとうございました！
    次回は Slot {progress["current_slot"]} から開始できます。
    """)
    
    if st.button("新しいセッションを開始"):
        # セッション状態をリセット
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.page = "consent"
        st.rerun()

if __name__ == "__main__":
    main()

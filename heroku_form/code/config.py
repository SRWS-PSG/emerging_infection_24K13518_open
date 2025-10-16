"""
設定情報を管理するモジュール
"""
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

EVAL_RECORDS_PATH = "evaluation_records.json"
# 注: 以下の設定は不要になりましたが、一部スクリプトとの互換性のために残しています
CREDENTIALS_PATH = "config/credentials.json"

# Streamlit Secretsを優先、なければ環境変数を使用
def get_config(key, default=""):
    """Streamlit Secretsまたは環境変数から設定値を取得"""
    # Heroku環境では環境変数を優先
    env_value = os.getenv(key)
    if env_value:
        return env_value
    # ローカル開発環境でのみStreamlit Secretsを確認
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return default

PAPERS_SPREADSHEET_ID = get_config("PAPERS_SPREADSHEET_ID", "YOUR_PAPERS_SPREADSHEET_ID_HERE")
PAPERS_WORKSHEET_NAME = get_config("PAPERS_WORKSHEET_NAME", "Papers")
RESULTS_SPREADSHEET_ID = get_config("RESULTS_SPREADSHEET_ID", "YOUR_RESULTS_SPREADSHEET_ID_HERE")
RESULTS_WORKSHEET_NAME = get_config("RESULTS_WORKSHEET_NAME", "Results")

PDF_BASE_URL = get_config("PDF_BASE_URL", "https://example.com/papers/")

RESULTS_HEADERS = [
    "participant_name", "has_summary", "paper_id", 
    "start_time", "end_time", "answer_time", 
    "action", "evaluation", "summary", "timestamp"
]

DEBUG = get_config("DEBUG", "False").lower() in ("true", "1", "t")

# 参加者IDと実名のマッピング

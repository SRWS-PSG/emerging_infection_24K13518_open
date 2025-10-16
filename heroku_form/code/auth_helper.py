"""
認証ヘルパーモジュール
OAuth2トークンまたはサービスアカウントキーを自動選択
"""

import os
import gspread
from google.oauth2.credentials import Credentials
from oauth2client.service_account import ServiceAccountCredentials
from google.auth.transport.requests import Request
import streamlit as st
import json
import logging
from datetime import datetime

# ログ設定
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/auth_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_sheets_client():
    """
    利用可能な認証方法を自動検出してGoogle Sheetsクライアントを返す
    優先順位: Heroku環境変数 > Streamlit Secrets > OAuth2トークン > サービスアカウントキー > ADC
    """
    logger.info("認証処理を開始")
    
    # 方法0: Heroku環境変数でサービスアカウント（Heroku用）
    if os.getenv('GOOGLE_SERVICE_ACCOUNT_INFO'):
        logger.debug("Heroku環境変数 GOOGLE_SERVICE_ACCOUNT_INFO が検出されました")
        try:
            import json
            service_account_info = json.loads(os.getenv('GOOGLE_SERVICE_ACCOUNT_INFO'))
            
            # これはOAuth2のクライアント情報なので、別の方法を試す
            if 'installed' in service_account_info:
                logger.debug("OAuth2クライアント情報が検出されました")
                # OAuth2用の情報は使用せず、次の方法に進む
                pass
            else:
                # サービスアカウント情報として処理
                credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                    service_account_info,
                    ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/drive']
                )
                client = gspread.authorize(credentials)
                print("✓ Heroku環境変数 (Service Account)で認証しました")
                return client
            
        except Exception as e:
            logger.error(f"Heroku環境変数認証エラー: {e}")
            print(f"Heroku環境変数認証エラー: {e}")
    
    # 方法0b: Heroku環境変数でOAuth2（Heroku用）
    if os.getenv('GOOGLE_OAUTH_CLIENT_ID') and os.getenv('GOOGLE_OAUTH_REFRESH_TOKEN'):
        logger.debug("Heroku OAuth2環境変数が検出されました")
        try:
            creds = Credentials(
                token=None,
                refresh_token=os.getenv('GOOGLE_OAUTH_REFRESH_TOKEN'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
            )
            
            # トークンをリフレッシュ
            if not creds.valid:
                logger.debug("Heroku OAuth2トークンをリフレッシュ中")
                creds.refresh(Request())
            
            client = gspread.authorize(creds)
            print("✓ Heroku環境変数 (OAuth2)で認証しました")
            return client
            
        except Exception as e:
            logger.error(f"Heroku OAuth2環境変数認証エラー: {e}")
            print(f"Heroku OAuth2環境変数認証エラー: {e}")
    
    # 方法1: Streamlit Secrets（Streamlit Community Cloud用）
    try:
        if hasattr(st, 'secrets') and st.secrets:
            logger.debug("Streamlit Secretsが利用可能")
            # OAuth2トークンがsecretsにある場合
            if 'google_oauth_token' in st.secrets:
                logger.debug("google_oauth_tokenが見つかりました")
                try:
                    token_data = dict(st.secrets['google_oauth_token'])
                    # Credentialsオブジェクトを作成
                    creds = Credentials(
                        token=token_data.get('access_token'),
                        refresh_token=token_data.get('refresh_token'),
                        token_uri='https://oauth2.googleapis.com/token',
                        client_id=token_data.get('client_id'),
                        client_secret=token_data.get('client_secret')
                    )
                    
                    # トークンが期限切れの場合はリフレッシュ
                    if not creds.valid:
                        if creds.expired and creds.refresh_token:
                            logger.debug("Streamlit Secretsトークンをリフレッシュ中")
                            creds.refresh(Request())
                    
                    client = gspread.authorize(creds)
                    print("✓ Streamlit Secrets (OAuth2)で認証しました")
                    return client
                    
                except Exception as e:
                    logger.error(f"Streamlit Secrets OAuth2認証エラー: {e}")
                    print(f"Streamlit Secrets OAuth2認証エラー: {e}")
            
            # サービスアカウントがsecretsにある場合
            if 'gcp_service_account' in st.secrets:
                try:
                    # secrets から JSON を作成
                    service_account_info = dict(st.secrets['gcp_service_account'])
                    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                        service_account_info,
                        ['https://spreadsheets.google.com/feeds',
                         'https://www.googleapis.com/auth/drive']
                    )
                    client = gspread.authorize(credentials)
                    print("✓ Streamlit Secrets (Service Account)で認証しました")
                    return client
                    
                except Exception as e:
                    logger.error(f"Streamlit Secrets Service Account認証エラー: {e}")
                    print(f"Streamlit Secrets Service Account認証エラー: {e}")
    except Exception as e:
        logger.error(f"Streamlit Secrets確認中にエラー: {e}")
        print(f"Streamlit Secrets確認中にエラー: {e}")
    
    # 方法1: OAuth2トークンファイルを確認
    token_file = 'config/token.json'
    if os.path.exists(token_file):
        logger.debug(f"OAuth2トークンファイルが存在: {token_file}")
        try:
            creds = Credentials.from_authorized_user_file(token_file)
            
            # トークンが期限切れの場合はリフレッシュ
            if creds.expired and creds.refresh_token:
                logger.info(f"トークンが期限切れです。リフレッシュします... (期限: {creds.expiry})")
                creds.refresh(Request())
                # リフレッシュしたトークンを保存
                with open(token_file, 'w') as f:
                    f.write(creds.to_json())
                logger.info(f"トークンをリフレッシュしました（新しい期限: {creds.expiry}）")
            
            client = gspread.authorize(creds)
            print("✓ OAuth2トークンで認証しました")
            return client
            
        except Exception as e:
            logger.error(f"OAuth2トークン認証エラー: {e}", exc_info=True)
            print(f"OAuth2トークン認証エラー: {e}")
    
    # 方法2: サービスアカウントキーを確認
    service_account_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'config/credentials.json')
    if os.path.exists(service_account_file):
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/drive']
            
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                service_account_file, scope)
            client = gspread.authorize(credentials)
            print("✓ サービスアカウントで認証しました")
            return client
            
        except Exception as e:
            print(f"サービスアカウント認証エラー: {e}")
    
    # 方法3: Application Default Credentials
    try:
        import google.auth
        credentials, project = google.auth.default(
            scopes=['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'])
        client = gspread.authorize(credentials)
        print("✓ Application Default Credentialsで認証しました")
        return client
        
    except Exception as e:
        print(f"ADC認証エラー: {e}")
    
    # すべての認証方法が失敗
    raise Exception("""
Google Sheets認証に失敗しました。以下のいずれかを実行してください:

1. OAuth2認証を実行:
   python setup_oauth.py

2. サービスアカウントキーを配置:
   config/credentials.json

3. Application Default Credentialsを設定:
   gcloud auth application-default login
""")
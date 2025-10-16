"""
改良版認証ヘルパーモジュール
環境別認証設定に基づいた自動認証選択
"""

import os
import gspread
import json
import logging
import streamlit as st
from datetime import datetime
from google.oauth2.credentials import Credentials
from oauth2client.service_account import ServiceAccountCredentials
from google.auth.transport.requests import Request
from google.auth import default

from config.auth_settings import auth_manager, AuthEnvironment

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

class AuthenticationManager:
    """認証管理クラス"""
    
    def __init__(self):
        self.environment = auth_manager.detect_environment()
        self.config = auth_manager.get_config(self.environment)
        logger.info(f"認証環境: {self.environment.value} ({self.config.description})")
    
    def get_sheets_client(self):
        """環境に応じた認証方法でGoogle Sheetsクライアントを取得"""
        logger.info(f"認証開始: {self.environment.value} 環境")
        
        # 環境設定の検証
        is_valid, errors = auth_manager.validate_environment(self.environment)
        if not is_valid:
            logger.warning(f"環境設定に問題があります: {errors}")
        
        # 環境別認証方法の実行
        auth_methods = {
            AuthEnvironment.LOCAL: self._auth_local,
            AuthEnvironment.HEROKU: self._auth_heroku,
            AuthEnvironment.PRODUCTION: self._auth_production,
            AuthEnvironment.TESTING: self._auth_testing
        }
        
        auth_method = auth_methods.get(self.environment, self._auth_fallback)
        return auth_method()
    
    def _auth_local(self):
        """ローカル環境認証"""
        logger.debug("ローカル環境認証を実行")
        
        # 1. OAuth2トークンファイル
        token_file = 'config/token.json'
        if os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(token_file)
                
                # トークンが期限切れの場合はリフレッシュ
                if creds.expired and creds.refresh_token:
                    logger.info(f"トークンをリフレッシュ中... (期限: {creds.expiry})")
                    creds.refresh(Request())
                    # リフレッシュしたトークンを保存
                    with open(token_file, 'w') as f:
                        f.write(creds.to_json())
                    logger.info(f"トークンをリフレッシュしました (新期限: {creds.expiry})")
                
                client = gspread.authorize(creds)
                logger.info("✓ OAuth2トークンファイル認証成功")
                print("✓ OAuth2トークンファイル認証成功")
                return client
                
            except Exception as e:
                logger.error(f"OAuth2トークンファイル認証エラー: {e}")
        
        # 2. サービスアカウントファイル
        return self._try_service_account_file()
    
    def _auth_heroku(self):
        """Heroku環境認証"""
        logger.debug("Heroku環境認証を実行")
        
        # 1. OAuth2環境変数
        if self._has_oauth_env_vars():
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
                logger.info("✓ Heroku OAuth2環境変数認証成功")
                print("✓ Heroku OAuth2環境変数認証成功")
                return client
                
            except Exception as e:
                logger.error(f"Heroku OAuth2環境変数認証エラー: {e}")
        
        # 2. サービスアカウント環境変数
        return self._try_service_account_env_var()
    
    def _auth_production(self):
        """本番環境認証"""
        logger.debug("本番環境認証を実行")
        
        # 1. サービスアカウントファイル
        client = self._try_service_account_file()
        if client:
            return client
        
        # 2. サービスアカウント環境変数
        client = self._try_service_account_env_var()
        if client:
            return client
        
        # 3. OAuth2環境変数（フォールバック）
        if self._has_oauth_env_vars():
            return self._auth_heroku()
        
        # 4. Application Default Credentials
        return self._try_application_default_credentials()
    
    def _auth_testing(self):
        """テスト環境認証（モック）"""
        logger.debug("テスト環境認証（モック）を実行")
        # テスト用のモック実装
        raise NotImplementedError("テスト環境認証は未実装")
    
    def _auth_fallback(self):
        """フォールバック認証（全方法を試行）"""
        logger.warning("フォールバック認証を実行")
        
        methods = [
            ("OAuth2トークンファイル", self._try_oauth_token_file),
            ("OAuth2環境変数", self._try_oauth_env_vars),
            ("サービスアカウントファイル", self._try_service_account_file),
            ("サービスアカウント環境変数", self._try_service_account_env_var),
            ("Application Default Credentials", self._try_application_default_credentials)
        ]
        
        for method_name, method_func in methods:
            try:
                logger.debug(f"フォールバック試行: {method_name}")
                client = method_func()
                if client:
                    logger.info(f"✓ フォールバック成功: {method_name}")
                    print(f"✓ フォールバック成功: {method_name}")
                    return client
            except Exception as e:
                logger.debug(f"フォールバック失敗 {method_name}: {e}")
        
        # 全ての方法が失敗
        raise Exception(self._get_auth_error_message())
    
    def _has_oauth_env_vars(self) -> bool:
        """OAuth2環境変数が設定されているかチェック"""
        required_vars = ['GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_REFRESH_TOKEN']
        return all(os.getenv(var) for var in required_vars)
    
    def _try_oauth_token_file(self):
        """OAuth2トークンファイル認証を試行"""
        token_file = 'config/token.json'
        if not os.path.exists(token_file):
            return None
        
        creds = Credentials.from_authorized_user_file(token_file)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_file, 'w') as f:
                f.write(creds.to_json())
        
        return gspread.authorize(creds)
    
    def _try_oauth_env_vars(self):
        """OAuth2環境変数認証を試行"""
        if not self._has_oauth_env_vars():
            return None
        
        creds = Credentials(
            token=None,
            refresh_token=os.getenv('GOOGLE_OAUTH_REFRESH_TOKEN'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
        )
        
        if not creds.valid:
            creds.refresh(Request())
        
        return gspread.authorize(creds)
    
    def _try_service_account_file(self):
        """サービスアカウントファイル認証を試行"""
        service_account_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'config/credentials.json')
        if not os.path.exists(service_account_file):
            return None
        
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            service_account_file, scope)
        
        client = gspread.authorize(credentials)
        logger.info("✓ サービスアカウントファイル認証成功")
        print("✓ サービスアカウントファイル認証成功")
        return client
    
    def _try_service_account_env_var(self):
        """サービスアカウント環境変数認証を試行"""
        service_account_info = os.getenv('GOOGLE_SERVICE_ACCOUNT_INFO')
        if not service_account_info:
            return None
        
        try:
            service_account_data = json.loads(service_account_info)
            
            # OAuth2クライアント情報かサービスアカウント情報かを判定
            if 'installed' in service_account_data:
                # OAuth2クライアント情報の場合はスキップ
                return None
            
            scope = ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/drive']
            
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                service_account_data, scope)
            
            client = gspread.authorize(credentials)
            logger.info("✓ サービスアカウント環境変数認証成功")
            print("✓ サービスアカウント環境変数認証成功")
            return client
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"サービスアカウント環境変数パースエラー: {e}")
            return None
    
    def _try_application_default_credentials(self):
        """Application Default Credentials認証を試行"""
        try:
            credentials, project = default(
                scopes=['https://spreadsheets.google.com/feeds',
                        'https://www.googleapis.com/auth/drive'])
            
            client = gspread.authorize(credentials)
            logger.info("✓ Application Default Credentials認証成功")
            print("✓ Application Default Credentials認証成功")
            return client
            
        except Exception as e:
            logger.error(f"Application Default Credentials認証エラー: {e}")
            return None
    
    def _get_auth_error_message(self) -> str:
        """認証失敗時のエラーメッセージを生成"""
        status = auth_manager.get_environment_status()
        
        error_message = f"""
Google Sheets認証に失敗しました。

現在の環境: {status['current_environment']} ({status['description']})
認証方法: {status['method']}

設定エラー:
"""
        for error in status['errors']:
            error_message += f"- {error}\n"
        
        error_message += f"""
環境別解決方法:

【ローカル環境】
1. OAuth2認証を実行:
   python3 scripts/setup_oauth.py
   
2. または手動認証:
   python3 manual_auth.py '認証コード'

【Heroku環境】
1. OAuth2環境変数を設定:
   heroku config:set GOOGLE_OAUTH_REFRESH_TOKEN="your_refresh_token"
   
2. または認証同期ツールを使用:
   python3 tools/sync_token_to_heroku.py

【本番環境】
1. サービスアカウントキーを配置:
   config/credentials.json
   
2. または環境変数を設定:
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"

詳細: https://github.com/your-repo/auth-troubleshooting
"""
        return error_message

# グローバルインスタンス
auth_instance = AuthenticationManager()

def get_sheets_client():
    """Google Sheetsクライアントを取得（後方互換性のため）"""
    return auth_instance.get_sheets_client()

def get_auth_status():
    """認証状態を取得"""
    return auth_manager.get_environment_status()
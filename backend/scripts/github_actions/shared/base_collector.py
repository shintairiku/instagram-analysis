"""
Base Collector Class for GitHub Actions
GitHub Actions用の共通基底クラス
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import os

from app.core.database import get_db_sync
from app.repositories.instagram_account_repository import InstagramAccountRepository

class BaseCollector:
    """GitHub Actions用コレクターの基底クラス"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.db = None
        self.setup_logging()
        
    def setup_logging(self):
        """ログ設定"""
        log_dir = Path(__file__).parent.parent.parent.parent / "logs" / "github_actions"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"{self.service_name}_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file, encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(self.service_name)
        
    async def _init_database(self):
        """データベース接続初期化"""
        if not self.db:
            self.db = get_db_sync()
            self.logger.info("Database connection initialized")
            
    async def _cleanup_database(self):
        """データベース接続クリーンアップ"""
        self.db = None
            
    async def _get_target_accounts(self, target_accounts: Optional[List[str]] = None):
        """対象アカウント取得"""
        account_repo = InstagramAccountRepository(self.db)
        
        if target_accounts:
            # 指定アカウントのみ
            accounts = []
            for account_id in target_accounts:
                account = await account_repo.get_by_instagram_user_id(account_id)
                if account:
                    accounts.append(account)
                else:
                    self.logger.warning(f"Account not found: {account_id}")
        else:
            # 全アクティブアカウント
            accounts = await account_repo.get_active_accounts()
            
        self.logger.info(f"Target accounts retrieved: {len(accounts)}")
        return accounts

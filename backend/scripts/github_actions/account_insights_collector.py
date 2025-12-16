#!/usr/bin/env python3
"""
Account Insights Collector for GitHub Actions
アカウントレベルインサイト（Daily Stats）の自動収集

実行例:
    python account_insights_collector.py --notify-slack
    python account_insights_collector.py --target-date 2025-07-01
    python account_insights_collector.py --target-accounts "123,456" --force-update
"""

import asyncio
import sys
import argparse
import logging
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
from dataclasses import dataclass, field

# プロジェクトルートをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_daily_stats_repository import InstagramDailyStatsRepository
from app.services.data_collection.instagram_api_client import InstagramAPIClient

from shared.base_collector import BaseCollector
from shared.notification_service import NotificationService
from shared.error_handler import ErrorHandler

@dataclass
class AccountInsightsResult:
    """アカウントインサイト収集結果"""
    execution_id: str
    target_date: date
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # 実行統計
    total_accounts: int = 0
    successful_accounts: int = 0
    failed_accounts: int = 0
    
    # データ統計
    stats_created: int = 0
    stats_updated: int = 0
    api_calls_made: int = 0
    
    # エラー情報
    errors: List[str] = field(default_factory=list)
    account_results: List[Dict] = field(default_factory=list)

class AccountInsightsCollector(BaseCollector):
    """アカウントインサイト収集クラス"""
    
    def __init__(self):
        super().__init__("account_insights")
        self.notification = NotificationService()
        self.error_handler = ErrorHandler()
        
    async def collect_daily_stats(
        self,
        target_date: date,
        target_accounts: Optional[List[str]] = None,
        force_update: bool = False
    ) -> AccountInsightsResult:
        """メイン処理: 日次統計データ収集"""
        
        execution_id = f"account_insights_{target_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}"
        result = AccountInsightsResult(
            execution_id=execution_id,
            target_date=target_date,
            started_at=datetime.now()
        )
        
        try:
            self.logger.info(f"🚀 Account insights collection started: {execution_id}")
            self.logger.info(f"📅 Target date: {target_date}")
            
            # データベース接続初期化
            await self._init_database()
            
            # 対象アカウント取得
            accounts = await self._get_target_accounts(target_accounts)
            result.total_accounts = len(accounts)
            
            self.logger.info(f"🎯 Target accounts: {result.total_accounts}")
            
            # アカウント別処理
            for account in accounts:
                account_result = await self._collect_account_stats(
                    account, target_date, force_update
                )
                
                result.account_results.append(account_result)
                
                if account_result['success']:
                    result.successful_accounts += 1
                    if account_result['created']:
                        result.stats_created += 1
                    else:
                        result.stats_updated += 1
                    result.api_calls_made += account_result['api_calls']
                else:
                    result.failed_accounts += 1
                    result.errors.append(
                        f"Account {account_result['username']}: {account_result['error']}"
                    )
                
                # アカウント間の待機（API制限対応）
                await asyncio.sleep(5)
            
            result.completed_at = datetime.now()
            
            # 実行結果ログ
            duration = (result.completed_at - result.started_at).total_seconds()
            success_rate = (result.successful_accounts / result.total_accounts * 100) if result.total_accounts > 0 else 0
            
            self.logger.info(f"✅ Collection completed in {duration:.1f}s")
            self.logger.info(f"📊 Success rate: {success_rate:.1f}% ({result.successful_accounts}/{result.total_accounts})")
            self.logger.info(f"📝 Stats created: {result.stats_created}, updated: {result.stats_updated}")
            self.logger.info(f"📞 API calls made: {result.api_calls_made}")
            
            return result
            
        except Exception as e:
            result.completed_at = datetime.now()
            error_msg = f"Critical error in account insights collection: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg, exc_info=True)
            return result
            
        finally:
            await self._cleanup_database()

    async def _collect_account_stats(
        self, 
        account, 
        target_date: date, 
        force_update: bool
    ) -> Dict[str, Any]:
        """単一アカウントの統計データ収集"""
        
        account_result = {
            'account_id': account.id,
            'instagram_user_id': account.instagram_user_id,
            'username': account.username,
            'success': False,
            'created': False,
            'api_calls': 0,
            'error': None
        }
        
        try:
            self.logger.info(f"🔄 Processing account: {account.username}")
            
            # 既存データチェック
            daily_stats_repo = InstagramDailyStatsRepository(self.db)
            existing_stats = await daily_stats_repo.get_by_specific_date(account.id, target_date)
            
            if existing_stats and not force_update:
                self.logger.info(f"⏭️ Skipping {account.username}: stats already exist for {target_date}")
                account_result['success'] = True
                account_result['created'] = False
                return account_result
            
            # API経由でデータ収集
            async with InstagramAPIClient() as api_client:
                # 1. 基本アカウントデータ取得
                basic_data = await api_client.get_basic_account_data(
                    account.instagram_user_id,
                    account.access_token_encrypted
                )
                account_result['api_calls'] += 1
                
                # 2. 当日投稿データ取得・集計
                daily_posts = await api_client.get_posts_for_date(
                    account.instagram_user_id,
                    account.access_token_encrypted,
                    target_date
                )
                account_result['api_calls'] += 1
                
                # 3. 統計データ計算
                stats_data = await self._calculate_daily_stats(
                    account.id,
                    target_date,
                    basic_data,
                    daily_posts
                )
                
                # 4. データベース保存
                if existing_stats:
                    # 更新
                    await daily_stats_repo.update(existing_stats.id, stats_data)
                    account_result['created'] = False
                    self.logger.info(f"✏️ Updated stats for {account.username}: {target_date}")
                else:
                    # 新規作成
                    await daily_stats_repo.create(stats_data)
                    account_result['created'] = True
                    self.logger.info(f"✨ Created stats for {account.username}: {target_date}")
                
                account_result['success'] = True
                
        except Exception as e:
            account_result['error'] = str(e)
            self.logger.error(f"❌ Failed to process account {account.username}: {e}")
        
        return account_result

    async def _calculate_daily_stats(
        self,
        account_id: str,
        target_date: date,
        basic_data: Dict,
        daily_posts: List[Dict]
    ) -> Dict[str, Any]:
        """日次統計データ計算"""
        
        # 投稿数・エンゲージメント計算
        posts_count = len(daily_posts)
        total_likes = sum(p.get('like_count', 0) for p in daily_posts)
        total_comments = sum(p.get('comments_count', 0) for p in daily_posts)
        
        # メディアタイプ分布
        media_types = {}
        for post in daily_posts:
            media_type = post.get('media_type', 'UNKNOWN')
            media_types[media_type] = media_types.get(media_type, 0) + 1
        
        return {
            'account_id': account_id,
            'stats_date': target_date,
            'followers_count': basic_data.get('followers_count', 0),
            'following_count': basic_data.get('follows_count', 0),
            'media_count': basic_data.get('media_count', 0),
            'posts_count': posts_count,
            'total_likes': total_likes,
            'total_comments': total_comments,
            'media_type_distribution': json.dumps(media_types),
            'data_sources': json.dumps(['github_actions_daily_collection'])
        }

# CLI エントリーポイント
async def main():
    parser = argparse.ArgumentParser(description='Account Insights Collector')
    parser.add_argument('--target-date', help='対象日付 (YYYY-MM-DD)')
    parser.add_argument('--target-accounts', help='対象アカウント (カンマ区切り)')
    parser.add_argument('--force-update', action='store_true', help='既存データの強制上書き')
    parser.add_argument('--notify-slack', action='store_true', help='Slack通知を送信')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='ログレベル')
    
    args = parser.parse_args()
    
    # 対象日付の設定
    if args.target_date:
        try:
            target_date = date.fromisoformat(args.target_date)
        except ValueError:
            print(f"❌ Invalid date format: {args.target_date}")
            return 1
    else:
        target_date = date.today()
    
    # 対象アカウントの設定
    target_accounts = None
    if args.target_accounts:
        target_accounts = [acc.strip() for acc in args.target_accounts.split(',') if acc.strip()]
    
    # ログレベル設定
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # 収集実行
    collector = AccountInsightsCollector()
    result = await collector.collect_daily_stats(
        target_date=target_date,
        target_accounts=target_accounts,
        force_update=args.force_update
    )
    
    # 結果表示
    print(f"\n{'='*60}")
    print("📊 ACCOUNT INSIGHTS COLLECTION RESULT")
    print(f"{'='*60}")
    print(f"📅 Target date: {target_date}")
    print(f"🎯 Accounts: {result.successful_accounts}/{result.total_accounts} succeeded")
    print(f"📝 Stats created: {result.stats_created}")
    print(f"✏️ Stats updated: {result.stats_updated}")
    print(f"📞 API calls: {result.api_calls_made}")
    
    if result.errors:
        print(f"❌ Errors ({len(result.errors)}):")
        for error in result.errors[:5]:  # 最初の5個のエラーのみ表示
            print(f"   {error}")
    
    duration = (result.completed_at - result.started_at).total_seconds()
    print(f"⏱️ Duration: {duration:.1f}s")
    print(f"{'='*60}")
    
    # Slack通知
    if args.notify_slack:
        await collector.notification.send_account_insights_result(result)
    
    # 失敗があった場合は exit code 1
    return 1 if result.failed_accounts > 0 else 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

#!/usr/bin/env python3
"""
New Posts Collector for GitHub Actions
24時間以内の新規投稿検出・収集

実行例:
    python new_posts_collector.py --notify-new-posts
    python new_posts_collector.py --target-accounts "123,456" --check-hours-back 6
    python new_posts_collector.py --force-reprocess
"""

import asyncio
import sys
import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
from dataclasses import dataclass, field

# プロジェクトルートをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_post_repository import InstagramPostRepository
from app.repositories.instagram_post_metrics_repository import InstagramPostMetricsRepository
from app.services.data_collection.instagram_api_client import InstagramAPIClient

from shared.base_collector import BaseCollector
from shared.notification_service import NotificationService
from shared.post_detector import PostDetector
from shared.post_processor import PostProcessor
from shared.execution_tracker import ExecutionTracker

@dataclass
class NewPostsResult:
    """新規投稿収集結果"""
    execution_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # 実行統計
    total_accounts: int = 0
    successful_accounts: int = 0
    failed_accounts: int = 0
    
    # 検出統計
    total_posts_checked: int = 0
    new_posts_found: int = 0
    new_posts_saved: int = 0
    insights_collected: int = 0
    
    # API使用統計
    api_calls_made: int = 0
    
    # エラー情報
    errors: List[str] = field(default_factory=list)
    account_results: List[Dict] = field(default_factory=list)
    new_posts_details: List[Dict] = field(default_factory=list)

class NewPostsCollector(BaseCollector):
    """新規投稿収集クラス"""
    
    def __init__(self):
        super().__init__("new_posts")
        self.notification = NotificationService()
        self.post_detector = PostDetector()
        self.post_processor = PostProcessor()
        self.execution_tracker = ExecutionTracker()
        
    async def detect_and_collect(
        self,
        target_accounts: Optional[List[str]] = None,
        check_hours_back: int = 8,
        force_reprocess: bool = False
    ) -> NewPostsResult:
        """メイン処理: 新規投稿検出・収集"""
        
        execution_id = f"new_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = NewPostsResult(
            execution_id=execution_id,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            self.logger.info(f"🚀 New posts detection started: {execution_id}")
            
            # 前回実行時刻の取得
            last_execution_time = self.execution_tracker.get_last_execution_time()
            
            # チェック開始時刻の決定
            if last_execution_time and not force_reprocess:
                check_from = last_execution_time
                self.logger.info(f"📅 Checking posts since last execution: {check_from}")
            else:
                check_from = datetime.now(timezone.utc) - timedelta(hours=check_hours_back)
                self.logger.info(f"📅 Checking posts from {check_hours_back} hours back: {check_from}")
            
            # データベース接続初期化
            await self._init_database()
            
            # 対象アカウント取得
            accounts = await self._get_target_accounts(target_accounts)
            result.total_accounts = len(accounts)
            
            self.logger.info(f"🎯 Target accounts: {result.total_accounts}")
            
            # アカウント別処理
            for account in accounts:
                account_result = await self._detect_account_new_posts(
                    account, check_from, force_reprocess
                )
                
                result.account_results.append(account_result)
                
                if account_result['success']:
                    result.successful_accounts += 1
                    result.total_posts_checked += account_result['posts_checked']
                    result.new_posts_found += account_result['new_posts_found']
                    result.new_posts_saved += account_result['new_posts_saved']
                    result.insights_collected += account_result['insights_collected']
                    result.api_calls_made += account_result['api_calls']
                    
                    # 新規投稿詳細を記録
                    for post_detail in account_result['new_posts_details']:
                        result.new_posts_details.append(post_detail)
                else:
                    result.failed_accounts += 1
                    result.errors.append(
                        f"Account {account_result['username']}: {account_result['error']}"
                    )
                
                # アカウント間の待機（API制限対応）
                await asyncio.sleep(3)
            
            result.completed_at = datetime.now(timezone.utc)
            
            # 実行時刻の更新
            self.execution_tracker.update_last_execution_time(result.started_at)
            
            # 実行結果ログ
            duration = (result.completed_at - result.started_at).total_seconds()
            success_rate = (result.successful_accounts / result.total_accounts * 100) if result.total_accounts > 0 else 0
            
            self.logger.info(f"✅ Detection completed in {duration:.1f}s")
            self.logger.info(f"📊 Success rate: {success_rate:.1f}% ({result.successful_accounts}/{result.total_accounts})")
            self.logger.info(f"🆕 New posts found: {result.new_posts_found}")
            self.logger.info(f"💾 New posts saved: {result.new_posts_saved}")
            self.logger.info(f"📈 Insights collected: {result.insights_collected}")
            self.logger.info(f"📞 API calls made: {result.api_calls_made}")
            
            return result
            
        except Exception as e:
            result.completed_at = datetime.now(timezone.utc)
            error_msg = f"Critical error in new posts detection: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg, exc_info=True)
            return result
            
        finally:
            await self._cleanup_database()

    async def _detect_account_new_posts(
        self, 
        account, 
        check_from: datetime,
        force_reprocess: bool
    ) -> Dict[str, Any]:
        """単一アカウントの新規投稿検出"""
        
        account_result = {
            'account_id': account.id,
            'instagram_user_id': account.instagram_user_id,
            'username': account.username,
            'success': False,
            'posts_checked': 0,
            'new_posts_found': 0,
            'new_posts_saved': 0,
            'insights_collected': 0,
            'api_calls': 0,
            'new_posts_details': [],
            'error': None
        }
        
        try:
            self.logger.info(f"🔍 Checking account: {account.username}")
            
            async with InstagramAPIClient() as api_client:
                # 最新投稿データ取得（最大50件）
                recent_posts = await self._fetch_recent_posts(api_client, account, limit=50)
                account_result['api_calls'] += 1
                account_result['posts_checked'] = len(recent_posts)
                
                # 新規投稿の検出
                new_posts = await self.post_detector.detect_new_posts(
                    recent_posts, 
                    check_from, 
                    account.id,
                    force_reprocess
                )
                account_result['new_posts_found'] = len(new_posts)
                
                if new_posts:
                    self.logger.info(f"🆕 Found {len(new_posts)} new posts for {account.username}")
                    
                    # 新規投稿の処理
                    for post_data in new_posts:
                        try:
                            # 投稿データ保存
                            saved_post = await self.post_processor.save_post_data(
                                account.id, post_data
                            )
                            
                            if saved_post:
                                account_result['new_posts_saved'] += 1
                                
                                # 投稿インサイト収集
                                insights = await api_client.get_post_insights(
                                    post_data['id'],
                                    account.access_token_encrypted,
                                    post_data.get('media_type', 'IMAGE')
                                )
                                account_result['api_calls'] += 1
                                
                                if insights:
                                    await self.post_processor.save_post_insights(
                                        saved_post.id, insights
                                    )
                                    account_result['insights_collected'] += 1
                                
                                # 新規投稿詳細を記録
                                post_detail = {
                                    'account_username': account.username,
                                    'post_id': post_data['id'],
                                    'media_type': post_data.get('media_type'),
                                    'timestamp': post_data.get('timestamp'),
                                    'permalink': post_data.get('permalink'),
                                    'caption_preview': (post_data.get('caption', '') or '')[:100] + '...' if post_data.get('caption') else None,
                                    'insights_collected': insights is not None
                                }
                                account_result['new_posts_details'].append(post_detail)
                                
                                self.logger.info(
                                    f"✅ Saved new post: {post_data['id']} "
                                    f"({post_data.get('media_type')}) "
                                    f"- insights: {'✓' if insights else '✗'}"
                                )
                                
                                # API制限対応（投稿間の待機）
                                await asyncio.sleep(2)
                                
                        except Exception as e:
                            self.logger.error(f"❌ Failed to process new post {post_data['id']}: {e}")
                            continue
                else:
                    self.logger.info(f"📭 No new posts found for {account.username}")
                
                account_result['success'] = True
                
        except Exception as e:
            account_result['error'] = str(e)
            self.logger.error(f"❌ Failed to check account {account.username}: {e}")
        
        return account_result

    async def _fetch_recent_posts(
        self, 
        api_client: InstagramAPIClient, 
        account, 
        limit: int = 50
    ) -> List[Dict]:
        """最新投稿データ取得"""
        
        url = api_client.config.get_user_media_url(account.instagram_user_id)
        
        params = {
            'fields': 'id,media_type,permalink,caption,timestamp,like_count,comments_count,media_url,thumbnail_url',
            'access_token': account.access_token_encrypted,
            'limit': min(limit, 100)  # API制限に合わせる
        }
        
        try:
            response = await api_client._make_request(url, params)
            posts = response.get('data', [])
            
            self.logger.debug(f"Retrieved {len(posts)} recent posts for {account.username}")
            return posts
            
        except Exception as e:
            self.logger.error(f"Failed to fetch recent posts for {account.username}: {e}")
            return []

# CLI エントリーポイント
async def main():
    parser = argparse.ArgumentParser(description='New Posts Collector')
    parser.add_argument('--target-accounts', help='対象アカウント (カンマ区切り)')
    parser.add_argument('--check-hours-back', type=int, default=8, help='遡及時間 (時間)')
    parser.add_argument('--force-reprocess', action='store_true', help='既存投稿の再処理を強制実行')
    parser.add_argument('--notify-new-posts', action='store_true', help='新規投稿をSlack通知')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='ログレベル')
    
    args = parser.parse_args()
    
    # 対象アカウントの設定
    target_accounts = None
    if args.target_accounts:
        target_accounts = [acc.strip() for acc in args.target_accounts.split(',') if acc.strip()]
    
    # ログレベル設定
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # 検出・収集実行
    collector = NewPostsCollector()
    result = await collector.detect_and_collect(
        target_accounts=target_accounts,
        check_hours_back=args.check_hours_back,
        force_reprocess=args.force_reprocess
    )
    
    # 結果表示
    print(f"\n{'='*60}")
    print("🆕 NEW POSTS DETECTION RESULT")
    print(f"{'='*60}")
    print(f"🎯 Accounts: {result.successful_accounts}/{result.total_accounts} succeeded")
    print(f"📊 Posts checked: {result.total_posts_checked}")
    print(f"🆕 New posts found: {result.new_posts_found}")
    print(f"💾 New posts saved: {result.new_posts_saved}")
    print(f"📈 Insights collected: {result.insights_collected}")
    print(f"📞 API calls: {result.api_calls_made}")
    
    # 新規投稿詳細表示
    if result.new_posts_details:
        print(f"\n📝 New Posts Details:")
        for post in result.new_posts_details[:10]:  # 最初の10件のみ表示
            print(f"   @{post['account_username']}: {post['media_type']} - {post['insights_collected'] and '📊' or '❌'}")
    
    if result.errors:
        print(f"\n❌ Errors ({len(result.errors)}):")
        for error in result.errors[:5]:
            print(f"   {error}")
    
    duration = (result.completed_at - result.started_at).total_seconds()
    print(f"\n⏱️ Duration: {duration:.1f}s")
    print(f"{'='*60}")
    
    # Slack通知（新規投稿があった場合のみ）
    if args.notify_new_posts and result.new_posts_found > 0:
        await collector.notification.send_new_posts_notification(result)
    
    # 失敗があった場合は exit code 1
    return 1 if result.failed_accounts > 0 else 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

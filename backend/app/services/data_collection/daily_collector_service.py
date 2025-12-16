"""
Daily Data Collection Service
毎日のデータ収集を統括するサービス
各リポジトリと Instagram API Client を連携
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ...core.database import get_db_sync
from ...repositories.instagram_account_repository import InstagramAccountRepository
from ...repositories.instagram_daily_stats_repository import InstagramDailyStatsRepository
from ...repositories.instagram_post_repository import InstagramPostRepository
from ...repositories.instagram_post_metrics_repository import InstagramPostMetricsRepository
from .instagram_api_client import InstagramAPIClient, InstagramAPIError
from .data_aggregator_service import DataAggregatorService

# ログ設定
logger = logging.getLogger(__name__)

@dataclass
class CollectionResult:
    """データ収集結果"""
    success: bool
    account_id: int
    instagram_user_id: str
    collected_at: datetime
    error_message: Optional[str] = None
    data_summary: Optional[Dict[str, Any]] = None

@dataclass
class DailyCollectionSummary:
    """日次収集サマリー"""
    target_date: date
    total_accounts: int
    successful_accounts: int
    failed_accounts: int
    collection_results: List[CollectionResult]
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None

class DailyCollectorService:
    """毎日のデータ収集サービス"""
    
    def __init__(self):
        """初期化"""
        self.db = None
        self.account_repo = None
        self.daily_stats_repo = None
        self.post_repo = None
        self.post_metrics_repo = None
        self.aggregator = DataAggregatorService()
    
    def _init_repositories(self):
        """リポジトリ初期化"""
        if not self.db:
            self.db = get_db_sync()
            self.account_repo = InstagramAccountRepository(self.db)
            self.daily_stats_repo = InstagramDailyStatsRepository(self.db)
            self.post_repo = InstagramPostRepository(self.db)
            self.post_metrics_repo = InstagramPostMetricsRepository(self.db)
            logger.info("Repositories initialized successfully")
    
    async def collect_daily_data(
        self,
        target_date: Optional[date] = None,
        account_filter: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> DailyCollectionSummary:
        """
        日次データ収集のメイン処理
        
        Args:
            target_date: 対象日付（未指定時は昨日）
            account_filter: 収集対象アカウントのフィルタ（instagram_user_idのリスト）
            dry_run: ドライラン実行フラグ
            
        Returns:
            DailyCollectionSummary: 収集結果サマリー
        """
        started_at = datetime.now()
        
        # デフォルト日付設定（昨日）
        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).date()
        
        logger.info(f"Starting daily data collection for {target_date}, dry_run={dry_run}")
        
        try:
            # リポジトリ初期化
            self._init_repositories()
            
            # 対象アカウント取得
            target_accounts = await self._get_target_accounts(account_filter)
            logger.info(f"Found {len(target_accounts)} target accounts")
            
            if dry_run:
                logger.info("DRY RUN MODE - No data will be saved to database")
            
            # 各アカウントのデータ収集
            collection_results = []
            successful_count = 0
            
            async with InstagramAPIClient() as api_client:
                for account in target_accounts:
                    try:
                        logger.info(f"Collecting data for account: {account.instagram_user_id}")
                        
                        result = await self._collect_account_data(
                            api_client=api_client,
                            account=account,
                            target_date=target_date,
                            dry_run=dry_run
                        )
                        
                        collection_results.append(result)
                        
                        if result.success:
                            successful_count += 1
                            logger.info(f"Successfully collected data for account: {account.instagram_user_id}")
                        else:
                            logger.error(f"Failed to collect data for account: {account.instagram_user_id} - {result.error_message}")
                            
                        # レート制限対応: アカウント間で少し待機
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        error_msg = f"Unexpected error collecting data for account {account.instagram_user_id}: {str(e)}"
                        logger.error(error_msg)
                        
                        collection_results.append(CollectionResult(
                            success=False,
                            account_id=account.id,
                            instagram_user_id=account.instagram_user_id,
                            collected_at=datetime.now(),
                            error_message=error_msg
                        ))
            
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()
            
            summary = DailyCollectionSummary(
                target_date=target_date,
                total_accounts=len(target_accounts),
                successful_accounts=successful_count,
                failed_accounts=len(target_accounts) - successful_count,
                collection_results=collection_results,
                started_at=started_at,
                completed_at=completed_at,
                total_duration_seconds=duration
            )
            
            logger.info(f"Daily collection completed - Success: {successful_count}/{len(target_accounts)}, Duration: {duration:.2f}s")
            return summary
            
        except Exception as e:
            logger.error(f"Critical error in daily data collection: {str(e)}")
            raise
        finally:
            # リソース解放
            self.db = None
            self.account_repo = None
            self.daily_stats_repo = None
            self.post_repo = None
            self.post_metrics_repo = None
    
    async def _get_target_accounts(self, account_filter: Optional[List[str]] = None) -> List:
        """
        収集対象アカウント取得
        
        Args:
            account_filter: instagram_user_idのフィルタリスト
            
        Returns:
            List: 対象アカウントリスト
        """
        try:
            # 全アクティブアカウント取得
            all_accounts = await self.account_repo.get_active_accounts()
            
            # フィルタ適用
            if account_filter:
                filtered_accounts = [
                    account for account in all_accounts 
                    if account.instagram_user_id in account_filter
                ]
                logger.info(f"Applied account filter - {len(filtered_accounts)}/{len(all_accounts)} accounts selected")
                return filtered_accounts
            
            return all_accounts
            
        except Exception as e:
            logger.error(f"Failed to get target accounts: {str(e)}")
            raise
    
    async def _collect_account_data(
        self,
        api_client: InstagramAPIClient,
        account,  # InstagramAccount model
        target_date: date,
        dry_run: bool = False
    ) -> CollectionResult:
        """
        単一アカウントのデータ収集
        
        Args:
            api_client: Instagram API クライアント
            account: アカウント情報
            target_date: 対象日付
            dry_run: ドライラン実行フラグ
            
        Returns:
            CollectionResult: 収集結果
        """
        collected_at = datetime.now()
        
        try:
            # TODO: 暗号化実装時にはここでトークンを復号化
            # access_token = decrypt_token(account.access_token_encrypted)
            access_token = account.access_token_encrypted  # 平文での取得
            
            # アクセストークン検証
            is_valid = await api_client.validate_access_token(
                account.instagram_user_id,
                access_token
            )
            
            if not is_valid:
                return CollectionResult(
                    success=False,
                    account_id=account.id,
                    instagram_user_id=account.instagram_user_id,
                    collected_at=collected_at,
                    error_message="Invalid access token"
                )
            
            # 基本アカウントデータ取得
            basic_data = await api_client.get_basic_account_data(
                account.instagram_user_id,
                access_token
            )
            
            # インサイトメトリクス取得
            insights_data = await api_client.get_insights_metrics(
                account.instagram_user_id,
                access_token,
                target_date
            )
            
            # 投稿データ取得
            posts_data = await api_client.get_posts_for_date(
                account.instagram_user_id,
                access_token,
                target_date
            )
            
            # データ集約処理
            if not dry_run:
                await self._save_collected_data(
                    account=account,
                    target_date=target_date,
                    basic_data=basic_data,
                    insights_data=insights_data,
                    posts_data=posts_data,
                    collected_at=collected_at
                )
            
            # 収集データサマリー作成
            data_summary = {
                "basic_data_fields": len(basic_data.keys()),
                "insights_metrics_count": len(insights_data.keys()),
                "posts_count": len(posts_data),
                "follower_count": basic_data.get("followers_count", 0),
                "reach": insights_data.get("reach", 0)
            }
            
            return CollectionResult(
                success=True,
                account_id=account.id,
                instagram_user_id=account.instagram_user_id,
                collected_at=collected_at,
                data_summary=data_summary
            )
            
        except InstagramAPIError as e:
            return CollectionResult(
                success=False,
                account_id=account.id,
                instagram_user_id=account.instagram_user_id,
                collected_at=collected_at,
                error_message=f"Instagram API error: {str(e)}"
            )
        except Exception as e:
            return CollectionResult(
                success=False,
                account_id=account.id,
                instagram_user_id=account.instagram_user_id,
                collected_at=collected_at,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    async def _save_collected_data(
        self,
        account,
        target_date: date,
        basic_data: Dict[str, Any],
        insights_data: Dict[str, Any],
        posts_data: List[Dict[str, Any]],
        collected_at: datetime
    ):
        """
        収集データの保存
        
        Args:
            account: アカウント情報
            target_date: 対象日付
            basic_data: 基本アカウントデータ
            insights_data: インサイトデータ
            posts_data: 投稿データ
            collected_at: 収集時刻
        """
        try:
            # 日次統計データ集約・保存
            daily_stats_data = self.aggregator.aggregate_daily_stats(
                account_id=account.id,
                target_date=target_date,
                basic_data=basic_data,
                insights_data=insights_data,
                posts_data=posts_data,
                collected_at=collected_at
            )
            
            await self.daily_stats_repo.save_daily_stats(daily_stats_data)
            logger.debug(f"Saved daily stats for account {account.instagram_user_id}")
            
            # 投稿データ保存
            if posts_data:
                for post_data in posts_data:
                    # 投稿基本情報保存
                    post_info = self.aggregator.extract_post_info(post_data, account.id)
                    saved_post = await self.post_repo.create_or_update(post_info)
                    
                    # 投稿メトリクス保存（利用可能な場合）
                    try:
                        post_metrics = await self._collect_post_metrics(
                            post_data,
                            account.access_token_encrypted,
                            target_date
                        )
                        if post_metrics:
                            post_metrics['post_id'] = saved_post.id
                            await self.post_metrics_repo.create_or_update_daily(post_metrics)
                    except Exception as e:
                        logger.warning(f"Failed to save post metrics for post {post_data.get('id')}: {str(e)}")
            
            # アカウント最終同期時刻更新
            await self.account_repo.update_last_sync(account.id, collected_at)
            
            logger.info(f"Successfully saved all data for account {account.instagram_user_id}")
            
        except Exception as e:
            logger.error(f"Failed to save collected data for account {account.instagram_user_id}: {str(e)}")
            raise
    
    async def _collect_post_metrics(
        self,
        post_data: Dict[str, Any],
        access_token: str,
        target_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        投稿メトリクス収集（オプション）
        
        Args:
            post_data: 投稿データ
            access_token: アクセストークン
            target_date: 対象日付
            
        Returns:
            Optional[Dict[str, Any]]: 投稿メトリクス（取得失敗時は None）
        """
        try:
            async with InstagramAPIClient() as api_client:
                return await api_client.get_post_insights(
                    post_data.get('id'),
                    access_token,
                    post_data.get('media_type', 'IMAGE')
                )
        except Exception as e:
            logger.warning(f"Failed to collect post metrics for {post_data.get('id')}: {str(e)}")
            return None

# サービスインスタンス作成関数
def create_daily_collector() -> DailyCollectorService:
    """Daily Collector Service インスタンス作成"""
    return DailyCollectorService()

# 使用例（開発・テスト用）
async def test_daily_collection():
    """デイリーコレクションのテスト"""
    collector = create_daily_collector()
    
    try:
        # 昨日のデータ収集をドライランで実行
        summary = await collector.collect_daily_data(dry_run=True)
        
        print(f"Collection Summary:")
        print(f"  Target Date: {summary.target_date}")
        print(f"  Total Accounts: {summary.total_accounts}")
        print(f"  Successful: {summary.successful_accounts}")
        print(f"  Failed: {summary.failed_accounts}")
        print(f"  Duration: {summary.total_duration_seconds:.2f}s")
        
        for result in summary.collection_results:
            status = "✓" if result.success else "✗"
            print(f"  {status} {result.instagram_user_id}")
            if result.error_message:
                print(f"    Error: {result.error_message}")
            if result.data_summary:
                print(f"    Data: {result.data_summary}")
                
    except Exception as e:
        print(f"Test failed: {str(e)}")

if __name__ == "__main__":
    # テスト実行
    asyncio.run(test_daily_collection())

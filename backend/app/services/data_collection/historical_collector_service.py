"""
Historical Data Collection Service
過去の投稿データとメトリクスを効率的に収集するサービス
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json

from ...core.database import get_db_sync
from ...repositories.instagram_account_repository import InstagramAccountRepository
from ...repositories.instagram_post_repository import InstagramPostRepository
from ...repositories.instagram_post_metrics_repository import InstagramPostMetricsRepository
from .instagram_api_client import InstagramAPIClient, InstagramAPIError
from .data_aggregator_service import DataAggregatorService

# ログ設定
logger = logging.getLogger(__name__)

@dataclass
class HistoricalCollectionResult:
    """過去データ収集結果"""
    account_id: str
    instagram_user_id: str
    collection_type: str  # 'posts', 'metrics', 'both'
    start_date: Optional[date]
    end_date: Optional[date]
    total_items: int
    processed_items: int
    success_items: int
    failed_items: int
    duration_seconds: float
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    checkpoint_data: Optional[Dict] = None

@dataclass
class PostCollectionStats:
    """投稿収集統計"""
    total_api_calls: int = 0
    new_posts: int = 0
    updated_posts: int = 0
    skipped_posts: int = 0
    failed_posts: int = 0
    metrics_collected: int = 0
    metrics_failed: int = 0

class HistoricalCollectorService:
    """過去データ収集サービス"""
    
    def __init__(self):
        """初期化"""
        self.db = None
        self.account_repo = None
        self.post_repo = None
        self.post_metrics_repo = None
        self.aggregator = DataAggregatorService()
    
    def _init_repositories(self):
        """リポジトリ初期化"""
        if not self.db:
            self.db = get_db_sync()
            self.account_repo = InstagramAccountRepository(self.db)
            self.post_repo = InstagramPostRepository(self.db)
            self.post_metrics_repo = InstagramPostMetricsRepository(self.db)
            logger.info("Historical collector repositories initialized")
    
    async def collect_historical_posts(
        self,
        account_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        max_posts: Optional[int] = None,
        include_metrics: bool = True,
        chunk_size: int = 100
    ) -> HistoricalCollectionResult:
        """
        過去投稿データの一括収集
        
        Args:
            account_id: アカウントID (instagram_user_id)
            start_date: 開始日付（未指定時は制限なし）
            end_date: 終了日付（未指定時は今日）
            max_posts: 最大投稿数
            include_metrics: メトリクス取得フラグ
            chunk_size: バッチサイズ
            
        Returns:
            HistoricalCollectionResult: 収集結果
        """
        started_at = datetime.now()
        collection_type = "both" if include_metrics else "posts"
        
        logger.info(f"Starting historical collection for account: {account_id}")
        logger.info(f"  Date range: {start_date} to {end_date}")
        logger.info(f"  Max posts: {max_posts}, Include metrics: {include_metrics}")
        
        try:
            # リポジトリ初期化
            self._init_repositories()
            
            # アカウント取得
            account = await self.account_repo.get_by_instagram_user_id(account_id)
            if not account:
                raise ValueError(f"Account not found: {account_id}")
            
            stats = PostCollectionStats()
            
            async with InstagramAPIClient() as api_client:
                # 全投稿データ取得
                logger.info("Fetching all posts from Instagram API...")
                all_posts = await self._fetch_all_posts(
                    api_client, 
                    account_id, 
                    account.access_token_encrypted
                )
                
                stats.total_api_calls += 1
                logger.info(f"Retrieved {len(all_posts)} posts from API")
                
                # 日付フィルタリング
                filtered_posts = self._filter_posts_by_date(
                    all_posts, 
                    start_date, 
                    end_date
                )
                
                # 最大数制限
                if max_posts and len(filtered_posts) > max_posts:
                    filtered_posts = filtered_posts[:max_posts]
                
                logger.info(f"Processing {len(filtered_posts)} posts after filtering")
                
                # バッチ処理
                total_posts = len(filtered_posts)
                for i in range(0, total_posts, chunk_size):
                    chunk = filtered_posts[i:i + chunk_size]
                    chunk_start = i + 1
                    chunk_end = min(i + chunk_size, total_posts)
                    
                    logger.info(f"Processing batch {chunk_start}-{chunk_end}/{total_posts}")
                    
                    # 投稿データ保存
                    for post_data in chunk:
                        try:
                            await self._save_post_data(post_data, account.id, stats)
                        except Exception as e:
                            logger.error(f"Failed to save post {post_data.get('id')}: {str(e)}")
                            stats.failed_posts += 1
                    
                    # メトリクス収集（オプション）
                    if include_metrics:
                        await self._collect_chunk_metrics(
                            api_client,
                            chunk,
                            account.access_token_encrypted,
                            stats
                        )
                    
                    # レート制限対応：チャンク間の待機
                    if i + chunk_size < total_posts:
                        logger.debug("Waiting between chunks to respect rate limits...")
                        await asyncio.sleep(2)  # 2秒待機
            
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()
            
            result = HistoricalCollectionResult(
                account_id=account_id,
                instagram_user_id=account_id,
                collection_type=collection_type,
                start_date=start_date,
                end_date=end_date,
                total_items=total_posts,
                processed_items=stats.new_posts + stats.updated_posts + stats.skipped_posts,
                success_items=stats.new_posts + stats.updated_posts,
                failed_items=stats.failed_posts,
                duration_seconds=duration,
                started_at=started_at,
                completed_at=completed_at
            )
            
            logger.info(f"Historical collection completed:")
            logger.info(f"  Processed: {result.processed_items}/{result.total_items}")
            logger.info(f"  New posts: {stats.new_posts}")
            logger.info(f"  Updated posts: {stats.updated_posts}")
            logger.info(f"  Metrics collected: {stats.metrics_collected}")
            logger.info(f"  Duration: {duration:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Critical error in historical collection: {str(e)}")
            
            return HistoricalCollectionResult(
                account_id=account_id,
                instagram_user_id=account_id,
                collection_type=collection_type,
                start_date=start_date,
                end_date=end_date,
                total_items=0,
                processed_items=0,
                success_items=0,
                failed_items=0,
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now(),
                error_message=str(e)
            )
        finally:
            # リソース解放
            self.db = None
            self.account_repo = None
            self.post_repo = None
            self.post_metrics_repo = None
    
    async def _fetch_all_posts(
        self,
        api_client: InstagramAPIClient,
        instagram_user_id: str,
        access_token: str
    ) -> List[Dict[str, Any]]:
        """
        Instagram APIから全投稿を取得
        
        Args:
            api_client: Instagram API クライアント
            instagram_user_id: Instagram User ID
            access_token: アクセストークン
            
        Returns:
            List[Dict[str, Any]]: 全投稿データ
        """
        url = api_client.config.get_user_media_url(instagram_user_id)
        all_posts = []
        next_url = None
        page_count = 0
        
        while True:
            page_count += 1
            logger.debug(f"Fetching posts page {page_count}")
            
            params = {
                'fields': api_client.config.get_media_fields(),
                'access_token': access_token,
                'limit': 100  # 最大値
            }
            
            try:
                if next_url:
                    # ページネーション
                    response = await api_client._make_request(next_url, {})
                else:
                    # 初回リクエスト
                    response = await api_client._make_request(url, params)
                
                posts = response.get('data', [])
                all_posts.extend(posts)
                
                logger.debug(f"Page {page_count}: {len(posts)} posts retrieved")
                
                # 次ページの確認
                paging = response.get('paging', {})
                next_url = paging.get('next')
                
                if not next_url:
                    logger.info(f"All posts retrieved - Total pages: {page_count}, Total posts: {len(all_posts)}")
                    break
                
                # レート制限対応
                await asyncio.sleep(1)
                
            except InstagramAPIError as e:
                logger.error(f"API error while fetching posts page {page_count}: {str(e)}")
                break
        
        return all_posts
    
    def _filter_posts_by_date(
        self,
        posts: List[Dict[str, Any]],
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> List[Dict[str, Any]]:
        """
        投稿を日付でフィルタリング
        
        Args:
            posts: 投稿データリスト
            start_date: 開始日付
            end_date: 終了日付
            
        Returns:
            List[Dict[str, Any]]: フィルタリング済み投稿データ
        """
        if not start_date and not end_date:
            return posts
        
        filtered_posts = []
        
        for post in posts:
            timestamp_str = post.get('timestamp', '')
            if not timestamp_str:
                continue
            
            try:
                post_datetime = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                post_date = post_datetime.date()
                
                # 日付範囲チェック
                if start_date and post_date < start_date:
                    continue
                if end_date and post_date > end_date:
                    continue
                
                filtered_posts.append(post)
                
            except ValueError as e:
                logger.warning(f"Invalid timestamp format: {timestamp_str}")
        
        logger.info(f"Date filtering: {len(posts)} -> {len(filtered_posts)} posts")
        return filtered_posts
    
    async def _save_post_data(
        self,
        post_data: Dict[str, Any],
        account_id: str,
        stats: PostCollectionStats
    ):
        """
        投稿データの保存
        
        Args:
            post_data: 投稿データ
            account_id: アカウントID
            stats: 統計情報
        """
        instagram_post_id = post_data.get('id')
        
        try:
            # 既存投稿チェック
            existing_post = await self.post_repo.get_by_instagram_post_id(instagram_post_id)
            
            # 投稿情報抽出
            post_info = self.aggregator.extract_post_info(post_data, account_id)
            
            if existing_post:
                # 既存投稿の更新
                updated_post = await self.post_repo.update(existing_post.id, post_info)
                stats.updated_posts += 1
                logger.debug(f"Updated post: {instagram_post_id}")
            else:
                # 新規投稿作成
                new_post = await self.post_repo.create(post_info)
                stats.new_posts += 1
                logger.debug(f"Created new post: {instagram_post_id}")
                
        except Exception as e:
            logger.error(f"Failed to save post {instagram_post_id}: {str(e)}")
            stats.failed_posts += 1
            raise
    
    async def _collect_chunk_metrics(
        self,
        api_client: InstagramAPIClient,
        chunk: List[Dict[str, Any]],
        access_token: str,
        stats: PostCollectionStats
    ):
        """
        チャンク内投稿のメトリクス収集
        
        Args:
            api_client: Instagram API クライアント
            chunk: 投稿データチャンク
            access_token: アクセストークン
            stats: 統計情報
        """
        logger.debug(f"Collecting metrics for {len(chunk)} posts")
        
        for post_data in chunk:
            post_id = post_data.get('id')
            media_type = post_data.get('media_type', 'IMAGE')
            
            try:
                # 投稿メトリクス取得
                metrics = await api_client.get_post_insights(
                    post_id,
                    access_token,
                    media_type
                )
                
                stats.total_api_calls += 1
                
                if metrics:
                    # データベース投稿取得
                    db_post = await self.post_repo.get_by_instagram_post_id(post_id)
                    if db_post:
                        # メトリクス保存
                        metrics_data = self.aggregator.extract_post_metrics(
                            post_id,
                            metrics,
                            datetime.now().date()
                        )
                        metrics_data['post_id'] = db_post.id
                        
                        await self.post_metrics_repo.create_or_update_daily(metrics_data)
                        stats.metrics_collected += 1
                        logger.debug(f"Saved metrics for post: {post_id}")
                
                # API呼び出し間隔
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Failed to collect metrics for post {post_id}: {str(e)}")
                stats.metrics_failed += 1
    
    async def collect_missing_metrics(
        self,
        account_id: str,
        days_back: int = 30
    ) -> HistoricalCollectionResult:
        """
        メトリクスが未取得の投稿のメトリクスを収集
        
        Args:
            account_id: アカウントID
            days_back: 遡及日数
            
        Returns:
            HistoricalCollectionResult: 収集結果
        """
        started_at = datetime.now()
        
        try:
            # リポジトリ初期化
            self._init_repositories()
            
            # アカウント取得
            account = await self.account_repo.get_by_instagram_user_id(account_id)
            if not account:
                raise ValueError(f"Account not found: {account_id}")
            
            # メトリクス未取得の投稿を検索
            cutoff_date = datetime.now() - timedelta(days=days_back)
            posts = await self.post_repo.get_posts_without_metrics(
                account.id, 
                cutoff_date.date()
            )
            
            logger.info(f"Found {len(posts)} posts without metrics")
            
            stats = PostCollectionStats()
            
            async with InstagramAPIClient() as api_client:
                for post in posts:
                    try:
                        # 投稿メトリクス取得
                        metrics = await api_client.get_post_insights(
                            post.instagram_post_id,
                            account.access_token_encrypted,
                            post.media_type
                        )
                        
                        stats.total_api_calls += 1
                        
                        if metrics:
                            # メトリクス保存
                            metrics_data = self.aggregator.extract_post_metrics(
                                post.instagram_post_id,
                                metrics,
                                post.posted_at.date()
                            )
                            metrics_data['post_id'] = post.id
                            
                            await self.post_metrics_repo.create_or_update_daily(metrics_data)
                            stats.metrics_collected += 1
                        
                        # レート制限対応
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Failed to collect metrics for post {post.instagram_post_id}: {str(e)}")
                        stats.metrics_failed += 1
            
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()
            
            result = HistoricalCollectionResult(
                account_id=account_id,
                instagram_user_id=account_id,
                collection_type="metrics",
                start_date=cutoff_date.date(),
                end_date=datetime.now().date(),
                total_items=len(posts),
                processed_items=stats.metrics_collected + stats.metrics_failed,
                success_items=stats.metrics_collected,
                failed_items=stats.metrics_failed,
                duration_seconds=duration,
                started_at=started_at,
                completed_at=completed_at
            )
            
            logger.info(f"Missing metrics collection completed:")
            logger.info(f"  Metrics collected: {stats.metrics_collected}")
            logger.info(f"  Failed: {stats.metrics_failed}")
            logger.info(f"  Duration: {duration:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in missing metrics collection: {str(e)}")
            
            return HistoricalCollectionResult(
                account_id=account_id,
                instagram_user_id=account_id,
                collection_type="metrics",
                start_date=None,
                end_date=None,
                total_items=0,
                processed_items=0,
                success_items=0,
                failed_items=0,
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now(),
                error_message=str(e)
            )
        finally:
            self.db = None
            self.account_repo = None
            self.post_repo = None
            self.post_metrics_repo = None

# サービスインスタンス作成関数
def create_historical_collector() -> HistoricalCollectorService:
    """Historical Collector Service インスタンス作成"""
    return HistoricalCollectorService()

# 使用例（開発・テスト用）
async def test_historical_collection():
    """過去データ収集のテスト"""
    collector = create_historical_collector()
    
    try:
        # 過去30日間の投稿データ収集
        result = await collector.collect_historical_posts(
            account_id="17841402015304577",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            max_posts=50,
            include_metrics=True
        )
        
        print(f"Historical Collection Result:")
        print(f"  Account: {result.instagram_user_id}")
        print(f"  Processed: {result.processed_items}/{result.total_items}")
        print(f"  Success: {result.success_items}")
        print(f"  Failed: {result.failed_items}")
        print(f"  Duration: {result.duration_seconds:.2f}s")
        
    except Exception as e:
        print(f"Test failed: {str(e)}")

if __name__ == "__main__":
    # テスト実行
    asyncio.run(test_historical_collection())

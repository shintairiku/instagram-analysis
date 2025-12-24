"""
Instagram Graph API Client
Instagram Graph API との通信を担当するクライアント
verification/about-daily-stats の知見を活用した実装
"""
import aiohttp
import asyncio
import json
from datetime import date, datetime, timezone
from typing import Dict, Any, List, Optional
import logging
from urllib.parse import urlencode

from ...core.instagram_config import instagram_config

# ログ設定
logger = logging.getLogger(__name__)

class InstagramAPIError(Exception):
    """Instagram API エラー"""
    def __init__(self, message: str, error_code: Optional[int] = None, error_data: Optional[Dict] = None):
        super().__init__(message)
        self.error_code = error_code
        self.error_data = error_data or {}

class InstagramAPIClient:
    """Instagram Graph API クライアント"""
    
    def __init__(self):
        self.config = instagram_config
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """非同期コンテキストマネージャー入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.REQUEST_TIMEOUT_SECONDS),
            headers=self.config.get_common_headers()
        )
        logger.debug("Instagram API client session created")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャー出口"""
        if self.session:
            await self.session.close()
            logger.debug("Instagram API client session closed")
    
    async def _make_request(
        self, 
        url: str, 
        params: Dict[str, Any],
        method: str = "GET"
    ) -> Dict[str, Any]:
        """
        API リクエストを実行
        
        Args:
            url: リクエストURL
            params: クエリパラメータ
            method: HTTPメソッド
            
        Returns:
            Dict[str, Any]: API レスポンス
            
        Raises:
            InstagramAPIError: API エラー時
        """
        if not self.session:
            raise InstagramAPIError("API client session not initialized")
        
        try:
            logger.debug(f"Making {method} request to {url} with params: {list(params.keys())}")
            
            if method.upper() == "GET":
                async with self.session.get(url, params=params) as response:
                    response_data = await response.json()
            else:
                async with self.session.request(method, url, params=params) as response:
                    response_data = await response.json()
            
            # エラーレスポンスのチェック
            if "error" in response_data:
                error_info = response_data["error"]
                error_code = error_info.get("code")
                error_message = error_info.get("message", "Unknown API error")
                
                logger.error(f"Instagram API error - Code: {error_code}, Message: {error_message}")
                raise InstagramAPIError(
                    f"Instagram API error: {error_message}",
                    error_code=error_code,
                    error_data=error_info
                )
            
            logger.debug(f"API request successful - Response keys: {list(response_data.keys())}")
            return response_data
            
        except aiohttp.ClientError as e:
            logger.error(f"Network error during API request: {str(e)}")
            raise InstagramAPIError(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise InstagramAPIError(f"Invalid JSON response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during API request: {str(e)}")
            raise InstagramAPIError(f"Unexpected error: {str(e)}")
    
    async def get_basic_account_data(
        self, 
        instagram_user_id: str, 
        access_token: str
    ) -> Dict[str, Any]:
        """
        基本アカウントデータ取得（最も安定）
        verification で確認済みの取得可能データのみ
        
        Args:
            instagram_user_id: Instagram User ID
            access_token: アクセストークン（平文）
            
        Returns:
            Dict[str, Any]: 基本アカウント情報
        """
        url = self.config.get_user_url(instagram_user_id)
        
        params = {
            'fields': self.config.get_basic_fields(),
            'access_token': access_token
        }
        
        try:
            logger.info(f"Fetching basic account data for user: {instagram_user_id}")
            data = await self._make_request(url, params)
            
            # データの検証
            required_fields = ['id', 'username']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                logger.warning(f"Missing required fields in basic account data: {missing_fields}")
            
            logger.info(f"Successfully fetched basic account data - Username: {data.get('username', 'unknown')}")
            return data
            
        except InstagramAPIError as e:
            logger.error(f"Failed to fetch basic account data for user {instagram_user_id}: {str(e)}")
            raise
    
    async def get_insights_metrics(
        self,
        instagram_user_id: str,
        access_token: str,
        target_date: date
    ) -> Dict[str, Any]:
        """
        Insights メトリクス取得（verification で利用可能と確認済みの2つのみ）
        
        Args:
            instagram_user_id: Instagram User ID
            access_token: アクセストークン（平文）
            target_date: 対象日付
            
        Returns:
            Dict[str, Any]: インサイトメトリクス
        """
        url = self.config.get_user_insights_url(instagram_user_id)
        
        # verification で利用可能と確認済みのメトリクスのみ使用
        available_metrics = self.config.get_available_insights_metrics()["account_metrics"]
        
        params = {
            'metric': ','.join(available_metrics),  # follower_count,reach
            'since': target_date.strftime('%Y-%m-%d'),
            'until': target_date.strftime('%Y-%m-%d'),
            'period': 'day',
            'access_token': access_token
        }
        
        try:
            logger.info(f"Fetching insights metrics for user: {instagram_user_id}, date: {target_date}")
            data = await self._make_request(url, params)
            
            # レスポンス解析
            metrics = {}
            for metric_data in data.get('data', []):
                metric_name = metric_data.get('name')
                values = metric_data.get('values', [])
                if values:
                    metrics[metric_name] = values[0].get('value', 0)
                    logger.debug(f"Parsed metric - {metric_name}: {metrics[metric_name]}")
                else:
                    logger.warning(f"No values found for metric: {metric_name}")
                    metrics[metric_name] = 0
            
            logger.info(f"Successfully fetched insights metrics - {len(metrics)} metrics retrieved")
            return metrics
            
        except InstagramAPIError as e:
            # Insights API はオプション扱いとし、エラーでも処理を継続
            logger.warning(f"Failed to fetch insights metrics for user {instagram_user_id} (continuing): {str(e)}")
            
            # デフォルト値を返す
            default_metrics = {metric: 0 for metric in available_metrics}
            logger.info(f"Returning default insights metrics: {default_metrics}")
            return default_metrics
    
    async def get_posts_for_date(
        self,
        instagram_user_id: str,
        access_token: str,
        target_date: date
    ) -> List[Dict[str, Any]]:
        """
        指定日の投稿データ取得
        
        Args:
            instagram_user_id: Instagram User ID
            access_token: アクセストークン（平文）
            target_date: 対象日付
            
        Returns:
            List[Dict[str, Any]]: 投稿データリスト
        """
        url = self.config.get_user_media_url(instagram_user_id)
        
        params = {
            'fields': self.config.get_media_fields(),
            'access_token': access_token,
            'limit': self.config.DEFAULT_POSTS_LIMIT
        }
        
        try:
            logger.info(f"Fetching posts for user: {instagram_user_id}, date: {target_date}")
            data = await self._make_request(url, params)
            
            # 指定日の投稿をフィルタリング
            target_date_str = target_date.strftime('%Y-%m-%d')
            daily_posts = []
            
            for post in data.get('data', []):
                timestamp = post.get('timestamp', '')
                if timestamp:
                    post_date = timestamp.split('T')[0]
                    if post_date == target_date_str:
                        daily_posts.append(post)
                        logger.debug(f"Found post for target date - ID: {post.get('id', 'unknown')}")
                else:
                    logger.warning(f"Post without timestamp found: {post.get('id', 'unknown')}")
            
            logger.info(f"Successfully filtered posts - {len(daily_posts)} posts found for {target_date}")
            return daily_posts
            
        except InstagramAPIError as e:
            logger.error(f"Failed to fetch posts for user {instagram_user_id}, date {target_date}: {str(e)}")
            # 投稿データ取得失敗時は空リストを返す
            return []

    async def get_posts_since(
        self,
        instagram_user_id: str,
        access_token: str,
        since_datetime: datetime,
        max_posts: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        指定日時以降の投稿データ取得（ページング対応・新しい順）。

        Args:
            instagram_user_id: Instagram User ID
            access_token: アクセストークン（平文）
            since_datetime: これ以降の投稿のみ返す（timezone-aware推奨）
            max_posts: 最大取得件数（安全のため上限）
        """
        if since_datetime.tzinfo is None:
            since_datetime = since_datetime.replace(tzinfo=timezone.utc)

        url = self.config.get_user_media_url(instagram_user_id)
        per_page = min(self.config.MAX_POSTS_LIMIT, max(1, max_posts))

        params = {
            "fields": self.config.get_media_fields(),
            "access_token": access_token,
            "limit": per_page,
        }

        collected: list[dict] = []
        next_url: Optional[str] = url
        next_params: Dict[str, Any] = params

        try:
            logger.info(
                f"Fetching recent posts for user: {instagram_user_id}, since={since_datetime.isoformat()}, max_posts={max_posts}"
            )

            while next_url and len(collected) < max_posts:
                data = await self._make_request(next_url, next_params)
                batch = data.get("data", []) or []

                stop = False
                for post in batch:
                    timestamp = post.get("timestamp")
                    if not timestamp:
                        continue
                    try:
                        post_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    except ValueError:
                        continue

                    if post_dt < since_datetime:
                        # 新しい順なので、ここ以降は全て古い
                        stop = True
                        break

                    collected.append(post)
                    if len(collected) >= max_posts:
                        break

                if stop or len(collected) >= max_posts:
                    break

                paging = data.get("paging", {}) or {}
                next_url = paging.get("next")
                next_params = {}  # next URL にはクエリが含まれるため

            logger.info(f"Successfully fetched recent posts - {len(collected)} posts collected")
            return collected

        except InstagramAPIError as e:
            logger.error(f"Failed to fetch recent posts for user {instagram_user_id}: {str(e)}")
            return []
    
    async def get_post_insights(
        self,
        post_id: str,
        access_token: str,
        media_type: str
    ) -> Dict[str, Any]:
        """
        投稿メトリクス取得
        
        Args:
            post_id: 投稿ID
            access_token: アクセストークン（平文）
            media_type: メディアタイプ（VIDEO/CAROUSEL_ALBUM/IMAGE）
            
        Returns:
            Dict[str, Any]: 投稿メトリクス
        """
        url = self.config.get_media_insights_url(post_id)
        
        # メディアタイプ別メトリクス
        available_metrics = self.config.get_available_insights_metrics()
        base_metrics = available_metrics["media_metrics_all"]
        
        metrics_to_request = base_metrics.copy()
        
        if media_type == 'VIDEO':
            metrics_to_request.extend(available_metrics["media_metrics_video"])
        elif media_type == 'CAROUSEL_ALBUM':
            metrics_to_request.extend(available_metrics["media_metrics_carousel"])
        
        params = {
            'metric': ','.join(metrics_to_request),
            'access_token': access_token
        }
        
        try:
            logger.info(f"Fetching post insights for post: {post_id}, media_type: {media_type}")
            data = await self._make_request(url, params)
            
            # レスポンス解析
            metrics = {}
            for metric_data in data.get('data', []):
                metric_name = metric_data.get('name')
                values = metric_data.get('values', [])
                if values:
                    metrics[metric_name] = values[0].get('value', 0)
                    logger.debug(f"Parsed post metric - {metric_name}: {metrics[metric_name]}")
                else:
                    logger.warning(f"No values found for post metric: {metric_name}")
                    metrics[metric_name] = 0
            
            logger.info(f"Successfully fetched post insights - {len(metrics)} metrics retrieved")
            return metrics
            
        except InstagramAPIError as e:
            logger.error(f"Failed to fetch post insights for post {post_id}: {str(e)}")
            # デフォルト値を返す
            default_metrics = {metric: 0 for metric in metrics_to_request}
            logger.info(f"Returning default post metrics: {list(default_metrics.keys())}")
            return default_metrics
    
    async def validate_access_token(
        self,
        instagram_user_id: str,
        access_token: str
    ) -> bool:
        """
        アクセストークンの有効性を検証
        
        Args:
            instagram_user_id: Instagram User ID
            access_token: アクセストークン（平文）
            
        Returns:
            bool: トークンが有効な場合 True
        """
        try:
            logger.info(f"Validating access token for user: {instagram_user_id}")
            
            # 基本アカウント情報取得でトークンをテスト
            await self.get_basic_account_data(instagram_user_id, access_token)
            
            logger.info(f"Access token validation successful for user: {instagram_user_id}")
            return True
            
        except InstagramAPIError as e:
            logger.error(f"Access token validation failed for user {instagram_user_id}: {str(e)}")
            return False


# クライアントのファクトリー関数
async def create_instagram_client() -> InstagramAPIClient:
    """Instagram API クライアントを作成"""
    return InstagramAPIClient()

# 使用例（開発・テスト用）
async def test_api_client():
    """API クライアントのテスト"""
    async with InstagramAPIClient() as client:
        # テスト用のダミーデータでテスト
        test_user_id = "test_user_id"
        test_token = "test_token"
        
        try:
            # トークン検証テスト
            is_valid = await client.validate_access_token(test_user_id, test_token)
            print(f"Token validation result: {is_valid}")
            
        except Exception as e:
            print(f"Test failed: {str(e)}")

if __name__ == "__main__":
    # テスト実行
    asyncio.run(test_api_client())

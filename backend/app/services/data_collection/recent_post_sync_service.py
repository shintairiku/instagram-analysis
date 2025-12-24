"""
Recent Post Sync Service
選択アカウント（チャンネル）単位で、直近の投稿とメトリクスを更新します。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ...core.database import get_db_sync
from ...core.records import Record
from ...repositories.instagram_account_repository import InstagramAccountRepository
from ...repositories.instagram_post_metrics_repository import InstagramPostMetricsRepository
from ...repositories.instagram_post_repository import InstagramPostRepository
from .data_aggregator_service import DataAggregatorService
from .instagram_api_client import InstagramAPIClient, InstagramAPIError
from .metrics_utils import normalize_post_metrics_for_db

logger = logging.getLogger(__name__)


@dataclass
class AccountRecentSyncResult:
    success: bool
    account_id: str
    instagram_user_id: str
    collected_at: datetime
    posts_processed: int = 0
    metrics_saved: int = 0
    error_message: Optional[str] = None


class RecentPostSyncService:
    """直近投稿の同期サービス"""

    def __init__(self):
        self.db = None
        self.account_repo: Optional[InstagramAccountRepository] = None
        self.post_repo: Optional[InstagramPostRepository] = None
        self.post_metrics_repo: Optional[InstagramPostMetricsRepository] = None
        self.aggregator = DataAggregatorService()

    def init_repositories(self) -> None:
        if self.db:
            return
        self.db = get_db_sync()
        self.account_repo = InstagramAccountRepository(self.db)
        self.post_repo = InstagramPostRepository(self.db)
        self.post_metrics_repo = InstagramPostMetricsRepository(self.db)

    async def get_account(self, account_id: str) -> Optional[Record]:
        assert self.account_repo is not None
        account = await self.account_repo.get_by_instagram_user_id(account_id)
        if account:
            return account
        return await self.account_repo.get_by_id(account_id)

    async def sync_recent_posts(
        self,
        account_id: str,
        window_days: int = 30,
        max_posts: int = 50,
        dry_run: bool = False,
        per_post_delay_seconds: float = 0.2,
    ) -> AccountRecentSyncResult:
        """
        指定アカウントの直近投稿・メトリクスを更新。

        - 投稿は window_days 以内のものだけ（取得は max_posts で上限）
        - メトリクスは投稿ごとに1日1レコード（instagram_post_metrics の create_or_update_daily）
        """
        self.init_repositories()
        assert self.account_repo is not None
        assert self.post_repo is not None
        assert self.post_metrics_repo is not None

        collected_at = datetime.now(timezone.utc)
        account = await self.get_account(account_id)
        if not account:
            return AccountRecentSyncResult(
                success=False,
                account_id=account_id,
                instagram_user_id=account_id,
                collected_at=collected_at,
                error_message=f"Account not found: {account_id}",
            )

        access_token = account.access_token_encrypted
        instagram_user_id = account.instagram_user_id

        since_dt = collected_at - timedelta(days=window_days)

        try:
            async with InstagramAPIClient() as api_client:
                # 基本情報（トークン検証も兼ねる）
                basic_data = await api_client.get_basic_account_data(instagram_user_id, access_token)

                # アカウント基本情報の更新（任意）
                if not dry_run:
                    await self.account_repo.update_basic_info(
                        str(account.id),
                        username=basic_data.get("username"),
                        account_name=basic_data.get("name"),
                        profile_picture_url=basic_data.get("profile_picture_url"),
                    )

                # 直近投稿を取得（ページング対応）
                posts = await api_client.get_posts_since(
                    instagram_user_id=instagram_user_id,
                    access_token=access_token,
                    since_datetime=since_dt,
                    max_posts=max_posts,
                )

                metrics_saved = 0

                for post_data in posts:
                    post_info = self.aggregator.extract_post_info(post_data, str(account.id))

                    saved_post_id = None
                    if not dry_run:
                        saved_post = await self.post_repo.create_or_update(post_info)
                        saved_post_id = str(saved_post.id)

                    try:
                        raw_metrics = await api_client.get_post_insights(
                            post_id=post_data.get("id", ""),
                            access_token=access_token,
                            media_type=post_data.get("media_type", "IMAGE"),
                        )
                        metrics = normalize_post_metrics_for_db(raw_metrics)

                        if not dry_run and saved_post_id:
                            metrics["post_id"] = saved_post_id
                            metrics["recorded_at"] = collected_at
                            await self.post_metrics_repo.create_or_update_daily(metrics)
                            metrics_saved += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to sync metrics for post {post_data.get('id', 'unknown')}: {e}"
                        )

                    if per_post_delay_seconds > 0:
                        await asyncio.sleep(per_post_delay_seconds)

                if not dry_run:
                    await self.account_repo.update_last_sync(str(account.id), collected_at)

                return AccountRecentSyncResult(
                    success=True,
                    account_id=str(account.id),
                    instagram_user_id=instagram_user_id,
                    collected_at=collected_at,
                    posts_processed=len(posts),
                    metrics_saved=metrics_saved,
                )

        except InstagramAPIError as e:
            return AccountRecentSyncResult(
                success=False,
                account_id=str(account.id),
                instagram_user_id=instagram_user_id,
                collected_at=collected_at,
                error_message=f"Instagram API error: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error syncing recent posts for {instagram_user_id}: {e}", exc_info=True)
            return AccountRecentSyncResult(
                success=False,
                account_id=str(account.id),
                instagram_user_id=instagram_user_id,
                collected_at=collected_at,
                error_message=f"Unexpected error: {str(e)}",
            )


def create_recent_post_sync_service() -> RecentPostSyncService:
    return RecentPostSyncService()

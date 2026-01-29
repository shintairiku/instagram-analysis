"""
Post Insight Service
投稿インサイトAPIサービス - フロントエンド向けの投稿データと分析を提供
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from supabase import Client

from ...core.records import Record, to_records
from ...core.supabase_utils import get_data, raise_for_error
from ...repositories.instagram_account_repository import InstagramAccountRepository
from ...repositories.instagram_post_repository import InstagramPostRepository
from ..data_collection.instagram_api_client import InstagramAPIClient, InstagramAPIError

logger = logging.getLogger(__name__)


class PostInsightService:
    """投稿インサイトサービス"""

    _MEDIA_URL_REFRESH_LEEWAY = timedelta(minutes=10)
    _MAX_MEDIA_URL_REFRESH_POSTS = 150

    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.account_repo = InstagramAccountRepository(supabase)
        self.post_repo = InstagramPostRepository(supabase)

    async def get_post_insights(
        self,
        account_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        media_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        投稿インサイトデータを取得

        Args:
            account_id: アカウントID（UUID文字列またはInstagram User ID）
            from_date: 開始日付
            to_date: 終了日付
            media_type: メディアタイプフィルター（IMAGE, VIDEO, CAROUSEL_ALBUM, STORY）
            limit: 最大取得件数

        Returns:
            投稿インサイトデータ
        """
        logger.info(f"Getting post insights for account: {account_id}")

        account = await self._get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")

        posts_with_metrics = await self._get_posts_with_latest_metrics(
            account_uuid=account["id"],
            from_date=from_date,
            to_date=to_date,
            media_type=media_type,
            limit=limit,
        )

        # NOTE: Instagram Graph API の media_url / thumbnail_url は短期間で期限切れ（403）になることがあるため、
        #       返却前に期限切れのURLだけリフレッシュして DB/レスポンス双方を更新する。
        await self._refresh_expired_media_urls(
            account=account,
            posts=[p for p, _ in posts_with_metrics],
            from_date=from_date,
            to_date=to_date,
            media_type=media_type,
        )

        post_insights: list[dict] = []
        for post, metrics in posts_with_metrics:
            post_insights.append(self._convert_to_insight_data(post, metrics))

        summary = self._calculate_summary(post_insights)

        return {
            "posts": post_insights,
            "summary": summary,
            "meta": {
                "account_id": str(account["id"]),
                "instagram_user_id": account.get("instagram_user_id"),
                "username": account.get("username"),
                "total_posts": len(post_insights),
                "date_range": {
                    "from": from_date.isoformat() if from_date else None,
                    "to": to_date.isoformat() if to_date else None,
                },
                "filters": {"media_type": media_type, "limit": limit},
            },
        }

    async def _get_account(self, account_id: str) -> Optional[Record]:
        """アカウント取得（UUIDまたはInstagram User IDで検索）"""
        account = await self.account_repo.get_by_instagram_user_id(account_id)
        if account:
            return account
        return await self.account_repo.get_by_id(account_id)

    async def _get_posts_with_latest_metrics(
        self,
        account_uuid: str,
        from_date: Optional[date],
        to_date: Optional[date],
        media_type: Optional[str],
        limit: Optional[int],
    ) -> List[Tuple[Record, Optional[Record]]]:
        """投稿と最新メトリクスを組み合わせて取得（DB結合は使わず、SDKで段階取得）。"""
        query = (
            self.supabase.table("instagram_posts")
            .select("id,instagram_post_id,media_type,caption,media_url,thumbnail_url,permalink,posted_at")
            .eq("account_id", account_uuid)
            .order("posted_at", desc=True)
        )

        if from_date:
            query = query.gte("posted_at", f"{from_date.isoformat()}T00:00:00+00:00")
        if to_date:
            # inclusive end date
            to_date_exclusive = to_date + timedelta(days=1)
            query = query.lt("posted_at", f"{to_date_exclusive.isoformat()}T00:00:00+00:00")

        if media_type:
            valid_types = {"IMAGE", "VIDEO", "CAROUSEL_ALBUM", "STORY"}
            mt = media_type.upper()
            if mt in valid_types:
                query = query.eq("media_type", mt)

        if limit:
            query = query.limit(limit)

        posts_res = query.execute()
        raise_for_error(posts_res)
        posts = to_records(get_data(posts_res))

        if not posts:
            return []

        post_ids = [p["id"] for p in posts if p.get("id")]

        metrics_res = (
            self.supabase.table("instagram_post_metrics")
            .select("post_id,reach,likes,comments,shares,saved,views,total_interactions,follows,profile_visits,profile_activity,video_view_total_time,avg_watch_time,recorded_at")
            .in_("post_id", post_ids)
            .order("recorded_at", desc=True)
            .execute()
        )
        raise_for_error(metrics_res)

        latest_by_post: dict[str, Record] = {}
        for row in get_data(metrics_res):
            pid = row.get("post_id")
            if not pid or pid in latest_by_post:
                continue
            latest_by_post[pid] = Record(row)

        combined: list[tuple[Record, Optional[Record]]] = []
        for post in posts:
            combined.append((post, latest_by_post.get(post["id"])))
        return combined

    def _convert_to_insight_data(self, post: Record, metrics: Optional[Record]) -> Dict[str, Any]:
        """投稿データをインサイト形式に変換"""
        posted_at = self._parse_datetime(post.get("posted_at"))
        insight_data: dict[str, Any] = {
            "id": post.get("instagram_post_id"),
            "date": posted_at.isoformat() if posted_at else (post.get("posted_at") or ""),
            "thumbnail": self._get_thumbnail_url(post),
            "type": post.get("media_type"),
            "caption": post.get("caption") or "",
            "media_url": post.get("media_url") or "",
            "permalink": post.get("permalink") or "",
        }

        if metrics:
            insight_data.update(
                {
                    "reach": metrics.get("reach") or 0,
                    "likes": metrics.get("likes") or 0,
                    "comments": metrics.get("comments") or 0,
                    "shares": metrics.get("shares") or 0,
                    "saves": metrics.get("saved") or 0,
                    "views": metrics.get("views") or 0,
                    "total_interactions": metrics.get("total_interactions") or 0,
                    "engagement_rate": self._calculate_engagement_rate(metrics),
                    "view_rate": self._calculate_view_rate(metrics)
                    if post.get("media_type") == "VIDEO"
                    else None,
                    "video_view_total_time": metrics.get("video_view_total_time")
                    if post.get("media_type") == "VIDEO"
                    else None,
                    "avg_watch_time": metrics.get("avg_watch_time")
                    if post.get("media_type") == "VIDEO"
                    else None,
                    "follows": metrics.get("follows")
                    if post.get("media_type") in ["CAROUSEL_ALBUM", "STORY"]
                    else None,
                    "profile_visits": metrics.get("profile_visits")
                    if post.get("media_type") in ["CAROUSEL_ALBUM", "STORY"]
                    else None,
                    "profile_activity": metrics.get("profile_activity")
                    if post.get("media_type") in ["CAROUSEL_ALBUM", "STORY"]
                    else None,
                    "recorded_at": metrics.get("recorded_at"),
                }
            )
        else:
            insight_data.update(
                {
                    "reach": 0,
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "saves": 0,
                    "views": 0,
                    "total_interactions": 0,
                    "engagement_rate": 0.0,
                    "view_rate": None,
                    "video_view_total_time": None,
                    "avg_watch_time": None,
                    "follows": None,
                    "profile_visits": None,
                    "profile_activity": None,
                    "recorded_at": None,
                }
            )

        return insight_data

    def _get_thumbnail_url(self, post: Record) -> str:
        return post.get("thumbnail_url") or post.get("media_url") or ""

    def _extract_instagram_cdn_expiry(self, url: str) -> Optional[datetime]:
        if not url:
            return None
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            oe = (qs.get("oe") or qs.get("_nc_oe") or [None])[0]
            if not oe:
                return None
            # Instagram CDN の `oe` は hex の epoch 秒（例: 6975142D）
            expiry_ts = int(oe, 16)
            return datetime.fromtimestamp(expiry_ts, tz=timezone.utc)
        except Exception:
            return None

    def _should_refresh_media_url(self, post: Record) -> bool:
        url = (post.get("thumbnail_url") or post.get("media_url") or "").strip()
        if not url:
            return True

        expiry = self._extract_instagram_cdn_expiry(url)
        if not expiry:
            return False

        now = datetime.now(timezone.utc)
        return expiry <= now + self._MEDIA_URL_REFRESH_LEEWAY

    async def _refresh_expired_media_urls(
        self,
        account: Record,
        posts: List[Record],
        from_date: Optional[date],
        to_date: Optional[date],
        media_type: Optional[str],
    ) -> None:
        if not posts:
            return

        access_token = (account.get("access_token_encrypted") or "").strip()
        instagram_user_id = (account.get("instagram_user_id") or "").strip()
        if not access_token or not instagram_user_id:
            return

        # 安全のため、1リクエストでのリフレッシュ対象件数を制限
        considered = posts[: self._MAX_MEDIA_URL_REFRESH_POSTS]
        to_refresh = [p for p in considered if self._should_refresh_media_url(p)]
        if not to_refresh:
            return

        try:
            # フィルタが無い場合は「最新N件」なので、User media をまとめて取得して差し替える（API呼び出しを抑える）。
            if from_date is None and to_date is None and media_type is None:
                await self._refresh_media_urls_from_latest_posts(
                    instagram_user_id=instagram_user_id,
                    access_token=access_token,
                    all_considered=considered,
                    to_refresh=to_refresh,
                )
                return

            await self._refresh_media_urls_per_post(
                access_token=access_token,
                posts=to_refresh,
            )
        except Exception as e:
            logger.warning(f"Failed to refresh media URLs (continuing): {e}")

    async def _refresh_media_urls_from_latest_posts(
        self,
        instagram_user_id: str,
        access_token: str,
        all_considered: List[Record],
        to_refresh: List[Record],
    ) -> None:
        max_posts = max(1, len(all_considered))
        since_dt = datetime.fromtimestamp(0, tz=timezone.utc)

        async with InstagramAPIClient() as api_client:
            api_posts = await api_client.get_posts_since(
                instagram_user_id=instagram_user_id,
                access_token=access_token,
                since_datetime=since_dt,
                max_posts=max_posts,
            )

        api_by_id: dict[str, dict] = {
            (p.get("id") or ""): p for p in api_posts if p.get("id")
        }

        refreshed = 0
        for post in to_refresh:
            ig_post_id = post.get("instagram_post_id") or ""
            api_post = api_by_id.get(ig_post_id)
            if not api_post:
                continue

            update_data: dict[str, Any] = {}
            new_media_url = (api_post.get("media_url") or "").strip()
            new_thumb_url = (api_post.get("thumbnail_url") or "").strip()

            if new_media_url and new_media_url != (post.get("media_url") or ""):
                update_data["media_url"] = new_media_url
                post["media_url"] = new_media_url
            if new_thumb_url and new_thumb_url != (post.get("thumbnail_url") or ""):
                update_data["thumbnail_url"] = new_thumb_url
                post["thumbnail_url"] = new_thumb_url

            if update_data and post.get("id"):
                await self.post_repo.update(str(post["id"]), update_data)
                refreshed += 1

        if refreshed:
            logger.info(f"Refreshed media URLs for {refreshed} posts (batch)")

    async def _refresh_media_urls_per_post(
        self,
        access_token: str,
        posts: List[Record],
    ) -> None:
        semaphore = asyncio.Semaphore(5)

        async with InstagramAPIClient() as api_client:
            async def fetch_media(post: Record) -> tuple[Record, Optional[dict]]:
                ig_post_id = (post.get("instagram_post_id") or "").strip()
                if not ig_post_id:
                    return (post, None)

                async with semaphore:
                    try:
                        media = await api_client.get_media(
                            media_id=ig_post_id,
                            access_token=access_token,
                            fields="id,media_url,thumbnail_url",
                        )
                        return (post, media)
                    except InstagramAPIError as e:
                        logger.warning(f"Failed to refresh media URL for {ig_post_id}: {e}")
                        return (post, None)

            results = await asyncio.gather(*(fetch_media(p) for p in posts))

        refreshed = 0
        for post, media in results:
            if not media:
                continue

            update_data: dict[str, Any] = {}
            new_media_url = (media.get("media_url") or "").strip()
            new_thumb_url = (media.get("thumbnail_url") or "").strip()

            if new_media_url and new_media_url != (post.get("media_url") or ""):
                update_data["media_url"] = new_media_url
                post["media_url"] = new_media_url
            if new_thumb_url and new_thumb_url != (post.get("thumbnail_url") or ""):
                update_data["thumbnail_url"] = new_thumb_url
                post["thumbnail_url"] = new_thumb_url

            if update_data and post.get("id"):
                await self.post_repo.update(str(post["id"]), update_data)
                refreshed += 1

        if refreshed:
            logger.info(f"Refreshed media URLs for {refreshed} posts (per-post)")

    def _calculate_engagement_rate(self, metrics: Record) -> float:
        reach = metrics.get("reach") or 0
        if reach == 0:
            return 0.0
        total_engagement = (
            (metrics.get("likes") or 0)
            + (metrics.get("comments") or 0)
            + (metrics.get("shares") or 0)
            + (metrics.get("saved") or 0)
        )
        return round((total_engagement / reach) * 100, 2)

    def _calculate_view_rate(self, metrics: Record) -> Optional[float]:
        reach = metrics.get("reach") or 0
        views = metrics.get("views") or 0
        if reach == 0 or views == 0:
            return None
        return round((views / reach) * 100, 2)

    def _calculate_summary(self, post_insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not post_insights:
            return {
                "total_posts": 0,
                "avg_engagement_rate": 0.0,
                "total_reach": 0,
                "total_engagement": 0,
                "best_performing_post": None,
                "media_type_distribution": {},
            }

        total_reach = sum(post.get("reach", 0) for post in post_insights)
        total_engagement = sum(
            post.get("likes", 0) + post.get("comments", 0) + post.get("shares", 0) + post.get("saves", 0)
            for post in post_insights
        )

        engagement_rates = [
            post.get("engagement_rate", 0) for post in post_insights if post.get("engagement_rate") is not None
        ]
        avg_engagement_rate = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0

        best_post = max(post_insights, key=lambda x: x.get("engagement_rate", 0)) if post_insights else None

        distribution: dict[str, int] = {}
        for post in post_insights:
            mt = post.get("type", "UNKNOWN")
            distribution[mt] = distribution.get(mt, 0) + 1

        return {
            "total_posts": len(post_insights),
            "avg_engagement_rate": round(avg_engagement_rate, 2),
            "total_reach": total_reach,
            "total_engagement": total_engagement,
            "best_performing_post": {
                "id": best_post.get("id"),
                "engagement_rate": best_post.get("engagement_rate"),
                "type": best_post.get("type"),
            }
            if best_post
            else None,
            "media_type_distribution": distribution,
        }

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None


def create_post_insight_service(db: Client) -> PostInsightService:
    return PostInsightService(db)

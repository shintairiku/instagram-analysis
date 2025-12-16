"""
Instagram Post Repository
Supabase (PostgREST) 経由で instagram_posts を操作するデータアクセス層
"""
from typing import List, Optional
from datetime import date, datetime, time, timedelta, timezone

from supabase import Client

from ..core.records import Record, to_record, to_records
from ..core.supabase_utils import get_data, get_count, get_single_data, prepare_record, raise_for_error


class InstagramPostRepository:
    """Instagram 投稿専用リポジトリ"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    async def get_all(self, account_id: str = None, limit: int = None) -> List[Record]:
        """投稿一覧取得"""
        query = self.supabase.table("instagram_posts").select("*")
        if account_id:
            query = query.eq("account_id", account_id)
        query = query.order("posted_at", desc=True)
        if limit:
            query = query.limit(limit)
        res = query.execute()
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_by_id(self, post_id: str) -> Optional[Record]:
        """ID による投稿取得"""
        res = self.supabase.table("instagram_posts").select("*").eq("id", post_id).limit(1).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_by_instagram_post_id(self, instagram_post_id: str) -> Optional[Record]:
        """Instagram Post ID による投稿取得"""
        res = (
            self.supabase.table("instagram_posts")
            .select("*")
            .eq("instagram_post_id", instagram_post_id)
            .limit(1)
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_by_account(self, account_id: str, limit: int = None) -> List[Record]:
        """アカウント別投稿取得"""
        return await self.get_all(account_id=account_id, limit=limit)
    
    async def get_by_date_range(
        self, 
        account_id: str,
        start_date: date,
        end_date: date
    ) -> List[Record]:
        """日付範囲による投稿取得"""
        start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)
        res = (
            self.supabase.table("instagram_posts")
            .select("*")
            .eq("account_id", account_id)
            .gte("posted_at", start_dt.isoformat())
            .lt("posted_at", end_dt.isoformat())
            .order("posted_at", desc=True)
            .execute()
        )
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_by_specific_date(self, account_id: str, target_date: date) -> List[Record]:
        """特定日の投稿取得"""
        return await self.get_by_date_range(account_id, target_date, target_date)
    
    async def get_by_media_type(
        self, 
        account_id: str, 
        media_type: str,
        limit: int = None
    ) -> List[Record]:
        """メディアタイプ別投稿取得"""
        query = (
            self.supabase.table("instagram_posts")
            .select("*")
            .eq("account_id", account_id)
            .eq("media_type", media_type)
            .order("posted_at", desc=True)
        )
        if limit:
            query = query.limit(limit)
        res = query.execute()
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def create(self, post_data: dict) -> Record:
        """新規投稿作成"""
        res = self.supabase.table("instagram_posts").insert(prepare_record(post_data)).execute()
        raise_for_error(res)
        return to_record(get_single_data(res)) or Record(post_data)
    
    async def create_or_update(self, post_data: dict) -> Record:
        """投稿作成または更新（Instagram Post ID で判定）"""
        res = (
            self.supabase.table("instagram_posts")
            .upsert(prepare_record(post_data), on_conflict="instagram_post_id")
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res)) or Record(post_data)
    
    async def update(self, post_id: str, post_data: dict) -> Optional[Record]:
        """投稿情報更新"""
        res = self.supabase.table("instagram_posts").update(prepare_record(post_data)).eq("id", post_id).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def delete(self, post_id: str) -> bool:
        """投稿削除"""
        res = self.supabase.table("instagram_posts").delete().eq("id", post_id).execute()
        raise_for_error(res)
        return bool(get_data(res))
    
    async def get_posts_without_metrics(
        self, 
        account_id: str, 
        cutoff_date: date
    ) -> List[Record]:
        """メトリクスが未取得の投稿を取得"""
        cutoff_dt = datetime.combine(cutoff_date, time.min).replace(tzinfo=timezone.utc)
        posts_res = (
            self.supabase.table("instagram_posts")
            .select("id,account_id,instagram_post_id,media_type,caption,media_url,thumbnail_url,permalink,posted_at,created_at")
            .eq("account_id", account_id)
            .gte("posted_at", cutoff_dt.isoformat())
            .order("posted_at", desc=True)
            .execute()
        )
        raise_for_error(posts_res)
        posts = get_data(posts_res)
        if not posts:
            return []

        post_ids = [p["id"] for p in posts if p.get("id")]
        metrics_res = self.supabase.table("instagram_post_metrics").select("post_id").in_("post_id", post_ids).execute()
        raise_for_error(metrics_res)
        post_ids_with_metrics = {m["post_id"] for m in get_data(metrics_res) if m.get("post_id")}

        without_metrics = [p for p in posts if p.get("id") not in post_ids_with_metrics]
        return to_records(without_metrics)
    
    async def get_latest_by_account(self, account_id: str) -> Optional[Record]:
        """アカウントの最新投稿取得"""
        res = (
            self.supabase.table("instagram_posts")
            .select("*")
            .eq("account_id", account_id)
            .order("posted_at", desc=True)
            .limit(1)
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def count_by_account(self, account_id: str) -> int:
        """アカウント別投稿数カウント"""
        res = self.supabase.table("instagram_posts").select("id", count="exact").eq("account_id", account_id).execute()
        raise_for_error(res)
        return get_count(res) or len(get_data(res))
    
    async def count_by_date_range(
        self, 
        account_id: str,
        start_date: date,
        end_date: date
    ) -> int:
        """日付範囲での投稿数カウント"""
        start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)
        res = (
            self.supabase.table("instagram_posts")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .gte("posted_at", start_dt.isoformat())
            .lt("posted_at", end_dt.isoformat())
            .execute()
        )
        raise_for_error(res)
        return get_count(res) or len(get_data(res))
    
    async def get_media_type_distribution(self, account_id: str) -> dict:
        """メディアタイプ別分布取得"""
        res = self.supabase.table("instagram_posts").select("media_type").eq("account_id", account_id).execute()
        raise_for_error(res)
        distribution: dict[str, int] = {}
        for row in get_data(res):
            media_type = row.get("media_type") or "UNKNOWN"
            distribution[media_type] = distribution.get(media_type, 0) + 1
        return distribution

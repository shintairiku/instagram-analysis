"""
Instagram Post Metrics Repository
Supabase (PostgREST) 経由で instagram_post_metrics を操作するデータアクセス層
"""
from typing import List, Optional, Dict, Any
from datetime import date, datetime, time, timedelta, timezone

from supabase import Client

from ..core.records import Record, to_record, to_records
from ..core.supabase_utils import get_data, get_single_data, prepare_record, raise_for_error


class InstagramPostMetricsRepository:
    """Instagram 投稿メトリクス専用リポジトリ"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    async def get_all(self, post_id: str = None) -> List[Record]:
        """メトリクス一覧取得"""
        query = self.supabase.table("instagram_post_metrics").select("*")
        if post_id:
            query = query.eq("post_id", post_id)
        res = query.order("recorded_at", desc=True).execute()
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_by_id(self, metrics_id: str) -> Optional[Record]:
        """ID によるメトリクス取得"""
        res = self.supabase.table("instagram_post_metrics").select("*").eq("id", metrics_id).limit(1).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_by_post(self, post_id: str) -> List[Record]:
        """投稿別メトリクス取得"""
        return await self.get_all(post_id=post_id)
    
    async def get_latest_by_post(self, post_id: str) -> Optional[Record]:
        """投稿の最新メトリクス取得"""
        res = (
            self.supabase.table("instagram_post_metrics")
            .select("*")
            .eq("post_id", post_id)
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_by_date_range(
        self,
        post_id: str,
        start_date: date,
        end_date: date
    ) -> List[Record]:
        """日付範囲によるメトリクス取得"""
        start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)
        res = (
            self.supabase.table("instagram_post_metrics")
            .select("*")
            .eq("post_id", post_id)
            .gte("recorded_at", start_dt.isoformat())
            .lt("recorded_at", end_dt.isoformat())
            .order("recorded_at", desc=True)
            .execute()
        )
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_by_specific_date(self, post_id: str, target_date: date) -> Optional[Record]:
        """特定日のメトリクス取得"""
        start_dt = datetime.combine(target_date, time.min).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(target_date + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)
        res = (
            self.supabase.table("instagram_post_metrics")
            .select("*")
            .eq("post_id", post_id)
            .gte("recorded_at", start_dt.isoformat())
            .lt("recorded_at", end_dt.isoformat())
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def create(self, metrics_data: dict) -> Record:
        """新規メトリクス作成"""
        # エンゲージメント率を計算
        if 'engagement_rate' not in metrics_data or metrics_data['engagement_rate'] == 0:
            metrics_data['engagement_rate'] = self._calculate_engagement_rate(metrics_data)
        
        res = self.supabase.table("instagram_post_metrics").insert(prepare_record(metrics_data)).execute()
        raise_for_error(res)
        return to_record(get_single_data(res)) or Record(metrics_data)
    
    async def create_or_update_daily(self, metrics_data: dict) -> Record:
        """日別メトリクス作成または更新"""
        post_id = metrics_data['post_id']
        today = date.today()
        
        existing_metrics = await self.get_by_specific_date(post_id, today)
        
        if existing_metrics:
            # 今日のメトリクスが既に存在する場合は更新
            return await self.update(existing_metrics.id, metrics_data) or existing_metrics
        else:
            # 存在しない場合は新規作成
            return await self.create(metrics_data)
    
    async def update(self, metrics_id: str, metrics_data: dict) -> Optional[Record]:
        """メトリクス更新"""
        # エンゲージメント率を再計算
        if any(key in metrics_data for key in ['likes', 'comments', 'saved', 'shares', 'reach']):
            existing = await self.get_by_id(metrics_id)
            combined_data = {**(existing or {}), **metrics_data}
            metrics_data['engagement_rate'] = self._calculate_engagement_rate(combined_data)

        res = self.supabase.table("instagram_post_metrics").update(prepare_record(metrics_data)).eq("id", metrics_id).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def delete(self, metrics_id: str) -> bool:
        """メトリクス削除"""
        res = self.supabase.table("instagram_post_metrics").delete().eq("id", metrics_id).execute()
        raise_for_error(res)
        return bool(get_data(res))
    
    async def get_top_performing_posts(
        self,
        account_id: str = None,
        metric: str = 'engagement_rate',
        limit: int = 10
    ) -> List[Record]:
        """高パフォーマンス投稿取得"""
        query = self.supabase.table("instagram_post_metrics").select("*")
        if account_id:
            posts_res = self.supabase.table("instagram_posts").select("id").eq("account_id", account_id).execute()
            raise_for_error(posts_res)
            post_ids = [p["id"] for p in get_data(posts_res) if p.get("id")]
            if not post_ids:
                return []
            query = query.in_("post_id", post_ids)

        allowed_metrics = {
            "engagement_rate",
            "reach",
            "likes",
            "comments",
            "saved",
            "shares",
            "views",
            "total_interactions",
            "recorded_at",
        }
        order_metric = metric if metric in allowed_metrics else "engagement_rate"

        query = query.order(order_metric, desc=True).limit(limit)
        res = query.execute()
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_metrics_summary(self, post_ids: List[str]) -> Dict[str, Any]:
        """メトリクス集計取得"""
        if not post_ids:
            return {}
        
        # 各投稿の最新メトリクスを Python 側で集約
        res = (
            self.supabase.table("instagram_post_metrics")
            .select("post_id,likes,comments,saved,shares,views,reach,engagement_rate,recorded_at")
            .in_("post_id", post_ids)
            .order("recorded_at", desc=True)
            .execute()
        )
        raise_for_error(res)
        rows = get_data(res)
        if not rows:
            return {}

        latest_by_post: dict[str, dict] = {}
        for row in rows:
            pid = row.get("post_id")
            if not pid or pid in latest_by_post:
                continue
            latest_by_post[pid] = row

        latest_metrics = list(latest_by_post.values())
        
        # 集計計算
        total_likes = sum((m.get("likes") or 0) for m in latest_metrics)
        total_comments = sum((m.get("comments") or 0) for m in latest_metrics)
        total_saved = sum((m.get("saved") or 0) for m in latest_metrics)
        total_shares = sum((m.get("shares") or 0) for m in latest_metrics)
        total_views = sum((m.get("views") or 0) for m in latest_metrics)
        total_reach = sum((m.get("reach") or 0) for m in latest_metrics)

        avg_engagement_rate = (
            sum((m.get("engagement_rate") or 0) for m in latest_metrics) / len(latest_metrics)
            if latest_metrics
            else 0
        )
        
        return {
            'total_posts': len(latest_metrics),
            'total_likes': total_likes,
            'total_comments': total_comments,
            'total_saved': total_saved,
            'total_shares': total_shares,
            'total_views': total_views,
            'total_reach': total_reach,
            'avg_likes_per_post': total_likes / len(latest_metrics),
            'avg_comments_per_post': total_comments / len(latest_metrics),
            'avg_engagement_rate': round(avg_engagement_rate, 2)
        }
    
    def _calculate_engagement_rate(self, metrics_data: dict) -> float:
        """エンゲージメント率計算"""
        likes = metrics_data.get('likes', 0) or 0
        comments = metrics_data.get('comments', 0) or 0
        saved = metrics_data.get('saved', 0) or 0
        shares = metrics_data.get('shares', 0) or 0
        reach = metrics_data.get('reach', 0) or 0
        
        if reach == 0:
            return 0.0
        
        total_engagement = likes + comments + saved + shares
        engagement_rate = (total_engagement / reach) * 100
        
        return round(engagement_rate, 2)

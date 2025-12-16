"""
Instagram Daily Stats Repository
Supabase (PostgREST) 経由で instagram_daily_stats を操作するデータアクセス層
"""
from typing import List, Optional
from datetime import date, datetime

from supabase import Client

from ..core.records import Record, to_record, to_records
from ..core.supabase_utils import get_data, get_single_data, prepare_record, raise_for_error


class InstagramDailyStatsRepository:
    """Instagram 日次統計専用リポジトリ"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    async def get_all(self, account_id: str = None, limit: int = None) -> List[Record]:
        """日次統計一覧取得"""
        query = self.supabase.table("instagram_daily_stats").select("*")
        if account_id:
            query = query.eq("account_id", account_id)
        query = query.order("stats_date", desc=True)
        if limit:
            query = query.limit(limit)
        res = query.execute()
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_by_id(self, stats_id: str) -> Optional[Record]:
        """ID による日次統計取得"""
        res = self.supabase.table("instagram_daily_stats").select("*").eq("id", stats_id).limit(1).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_by_account(self, account_id: str, limit: int = None) -> List[Record]:
        """アカウント別日次統計取得"""
        return await self.get_all(account_id=account_id, limit=limit)
    
    async def get_by_date_range(
        self, 
        account_id: str,
        start_date: date,
        end_date: date
    ) -> List[Record]:
        """日付範囲による日次統計取得"""
        res = (
            self.supabase.table("instagram_daily_stats")
            .select("*")
            .eq("account_id", account_id)
            .gte("stats_date", start_date.isoformat())
            .lte("stats_date", end_date.isoformat())
            .order("stats_date", desc=True)
            .execute()
        )
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_by_specific_date(self, account_id: str, target_date: date) -> Optional[Record]:
        """特定日の日次統計取得"""
        res = (
            self.supabase.table("instagram_daily_stats")
            .select("*")
            .eq("account_id", account_id)
            .eq("stats_date", target_date.isoformat())
            .limit(1)
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def create(self, stats_data: dict) -> Record:
        """新規日次統計作成"""
        res = self.supabase.table("instagram_daily_stats").insert(prepare_record(stats_data)).execute()
        raise_for_error(res)
        return to_record(get_single_data(res)) or Record(stats_data)
    
    async def create_or_update(self, stats_data: dict) -> Record:
        """日次統計作成または更新（アカウントIDと日付で判定）"""
        # on_conflict はDB側のユニーク制約 (account_id, stats_date) に依存
        res = (
            self.supabase.table("instagram_daily_stats")
            .upsert(prepare_record(stats_data), on_conflict="account_id,stats_date")
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res)) or Record(stats_data)

    async def save_daily_stats(self, stats_data: dict) -> Record:
        """収集処理向けの保存API（create_or_updateのエイリアス）"""
        return await self.create_or_update(stats_data)
    
    async def update(self, stats_id: str, stats_data: dict) -> Optional[Record]:
        """日次統計情報更新"""
        res = self.supabase.table("instagram_daily_stats").update(prepare_record(stats_data)).eq("id", stats_id).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def delete(self, stats_id: str) -> bool:
        """日次統計削除"""
        res = self.supabase.table("instagram_daily_stats").delete().eq("id", stats_id).execute()
        raise_for_error(res)
        return bool(get_data(res))
    
    async def get_latest_by_account(self, account_id: str) -> Optional[Record]:
        """アカウントの最新日次統計取得"""
        res = (
            self.supabase.table("instagram_daily_stats")
            .select("*")
            .eq("account_id", account_id)
            .order("stats_date", desc=True)
            .limit(1)
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_follower_growth_trend(
        self, 
        account_id: str, 
        days: int = 30
    ) -> List[Record]:
        """フォロワー成長トレンド取得"""
        return await self.get_all(account_id=account_id, limit=days)
    
    async def calculate_growth_metrics(
        self, 
        account_id: str, 
        start_date: date, 
        end_date: date
    ) -> dict:
        """成長指標計算"""
        stats_list = await self.get_by_date_range(account_id, start_date, end_date)
        
        if not stats_list:
            return {
                'follower_growth': 0,
                'avg_daily_engagement': 0.0,
                'total_posts': 0,
                'avg_posts_per_day': 0.0
            }
        
        # 最新と最古のデータ
        latest = stats_list[0]
        oldest = stats_list[-1]
        
        follower_growth = (latest.get("followers_count") or 0) - (oldest.get("followers_count") or 0)
        total_posts = sum((stats.get("posts_count") or 0) for stats in stats_list)
        avg_posts_per_day = total_posts / len(stats_list) if stats_list else 0
        
        # 平均エンゲージメント計算
        total_likes = sum((stats.get("total_likes") or 0) for stats in stats_list)
        total_comments = sum((stats.get("total_comments") or 0) for stats in stats_list)
        avg_daily_engagement = (total_likes + total_comments) / len(stats_list) if stats_list else 0
        
        return {
            'follower_growth': follower_growth,
            'avg_daily_engagement': avg_daily_engagement,
            'total_posts': total_posts,
            'avg_posts_per_day': round(avg_posts_per_day, 2)
        }
    
    async def get_data_quality_score(self, account_id: str, target_date: date) -> float:
        """データ品質スコア取得"""
        stats = await self.get_by_specific_date(account_id, target_date)
        
        if not stats:
            return 0.0
        
        score = 0.0
        max_score = 100.0
        
        # フォロワー数データ（30点）
        if (stats.get("followers_count") or 0) > 0:
            score += 30
        
        # 投稿データ（25点）
        if (stats.get("posts_count") or 0) > 0:
            score += 25
        
        # エンゲージメントデータ（25点）
        if (stats.get("total_likes") or 0) > 0 or (stats.get("total_comments") or 0) > 0:
            score += 25
        
        # メディア数データ（20点）
        if (stats.get("media_count") or 0) > 0:
            score += 20
        
        return round(min(score, max_score), 2)
    
    async def bulk_create(self, stats_list: List[dict]) -> List[Record]:
        """一括作成"""
        if not stats_list:
            return []
        res = self.supabase.table("instagram_daily_stats").insert([prepare_record(s) for s in stats_list]).execute()
        raise_for_error(res)
        return to_records(get_data(res))

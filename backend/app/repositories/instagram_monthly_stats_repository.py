"""
Instagram Monthly Stats Repository
Supabase (PostgREST) 経由で instagram_monthly_stats を操作するデータアクセス層
"""
from typing import List, Optional
from datetime import date

from supabase import Client

from ..core.records import Record, to_record, to_records
from ..core.supabase_utils import get_data, get_single_data, prepare_record, raise_for_error


class InstagramMonthlyStatsRepository:
    """Instagram 月次統計専用リポジトリ"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    async def get_all(self, account_id: str = None, limit: int = None) -> List[Record]:
        """月次統計一覧取得"""
        query = self.supabase.table("instagram_monthly_stats").select("*")
        if account_id:
            query = query.eq("account_id", account_id)
        query = query.order("stats_month", desc=True)
        if limit:
            query = query.limit(limit)
        res = query.execute()
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_by_id(self, stats_id: str) -> Optional[Record]:
        """ID による月次統計取得"""
        res = self.supabase.table("instagram_monthly_stats").select("*").eq("id", stats_id).limit(1).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_by_account(self, account_id: str, limit: int = None) -> List[Record]:
        """アカウント別月次統計取得"""
        return await self.get_all(account_id=account_id, limit=limit)
    
    async def get_by_month_range(
        self, 
        account_id: str,
        start_month: date,
        end_month: date
    ) -> List[Record]:
        """月範囲による月次統計取得"""
        res = (
            self.supabase.table("instagram_monthly_stats")
            .select("*")
            .eq("account_id", account_id)
            .gte("stats_month", start_month.isoformat())
            .lte("stats_month", end_month.isoformat())
            .order("stats_month", desc=True)
            .execute()
        )
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_by_specific_month(self, account_id: str, target_month: date) -> Optional[Record]:
        """特定月の月次統計取得"""
        res = (
            self.supabase.table("instagram_monthly_stats")
            .select("*")
            .eq("account_id", account_id)
            .eq("stats_month", target_month.isoformat())
            .limit(1)
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def create(self, stats_data: dict) -> Record:
        """新規月次統計作成"""
        res = self.supabase.table("instagram_monthly_stats").insert(prepare_record(stats_data)).execute()
        raise_for_error(res)
        return to_record(get_single_data(res)) or Record(stats_data)
    
    async def create_or_update(self, stats_data: dict) -> Record:
        """月次統計作成または更新（アカウントIDと月で判定）"""
        res = (
            self.supabase.table("instagram_monthly_stats")
            .upsert(prepare_record(stats_data), on_conflict="account_id,stats_month")
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res)) or Record(stats_data)
    
    async def update(self, stats_id: str, stats_data: dict) -> Optional[Record]:
        """月次統計情報更新"""
        res = self.supabase.table("instagram_monthly_stats").update(prepare_record(stats_data)).eq("id", stats_id).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def delete(self, stats_id: str) -> bool:
        """月次統計削除"""
        res = self.supabase.table("instagram_monthly_stats").delete().eq("id", stats_id).execute()
        raise_for_error(res)
        return bool(get_data(res))
    
    async def get_latest_by_account(self, account_id: str) -> Optional[Record]:
        """アカウントの最新月次統計取得"""
        res = (
            self.supabase.table("instagram_monthly_stats")
            .select("*")
            .eq("account_id", account_id)
            .order("stats_month", desc=True)
            .limit(1)
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_yearly_trend(
        self, 
        account_id: str, 
        year: int
    ) -> List[Record]:
        """年間トレンド取得"""
        start_month = date(year, 1, 1)
        end_month = date(year, 12, 1)
        
        return await self.get_by_month_range(account_id, start_month, end_month)
    
    async def calculate_year_over_year_growth(
        self, 
        account_id: str, 
        target_month: date
    ) -> dict:
        """前年同月比成長率計算"""
        current_stats = await self.get_by_specific_month(account_id, target_month)
        
        # 前年同月
        previous_year_month = date(target_month.year - 1, target_month.month, 1)
        previous_stats = await self.get_by_specific_month(account_id, previous_year_month)
        
        if not current_stats or not previous_stats:
            return {
                'follower_growth_yoy': 0.0,
                'engagement_growth_yoy': 0.0,
                'posts_growth_yoy': 0.0
            }
        
        # フォロワー成長率
        follower_growth_yoy = 0.0
        if (previous_stats.get("avg_followers_count") or 0) > 0:
            follower_growth_yoy = (
                ((current_stats.get("avg_followers_count") or 0) - (previous_stats.get("avg_followers_count") or 0))
                / (previous_stats.get("avg_followers_count") or 1)
                * 100
            )
        
        # エンゲージメント成長率
        engagement_growth_yoy = 0.0
        if (previous_stats.get("avg_engagement_rate") or 0) > 0:
            engagement_growth_yoy = (
                ((current_stats.get("avg_engagement_rate") or 0) - (previous_stats.get("avg_engagement_rate") or 0))
                / (previous_stats.get("avg_engagement_rate") or 1)
                * 100
            )
        
        # 投稿数成長率
        posts_growth_yoy = 0.0
        if (previous_stats.get("total_posts") or 0) > 0:
            posts_growth_yoy = (
                ((current_stats.get("total_posts") or 0) - (previous_stats.get("total_posts") or 0))
                / (previous_stats.get("total_posts") or 1)
                * 100
            )
        
        return {
            'follower_growth_yoy': round(follower_growth_yoy, 2),
            'engagement_growth_yoy': round(engagement_growth_yoy, 2),
            'posts_growth_yoy': round(posts_growth_yoy, 2)
        }
    
    async def get_top_performing_months(
        self, 
        account_id: str, 
        limit: int = 12,
        metric: str = 'avg_engagement_rate'
    ) -> List[Record]:
        """トップパフォーマンス月取得"""
        allowed_metrics = {
            "avg_engagement_rate",
            "avg_followers_count",
            "follower_growth",
            "follower_growth_rate",
            "total_posts",
            "total_likes",
            "total_comments",
            "total_reach",
            "stats_month",
            "created_at",
        }
        order_metric = metric if metric in allowed_metrics else "avg_engagement_rate"

        res = (
            self.supabase.table("instagram_monthly_stats")
            .select("*")
            .eq("account_id", account_id)
            .order(order_metric, desc=True)
            .limit(limit)
            .execute()
        )
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def calculate_seasonal_trends(
        self, 
        account_id: str, 
        years: int = 2
    ) -> dict:
        """季節トレンド分析"""
        # 過去N年のデータを取得
        end_date = date.today().replace(day=1)
        start_date = date(end_date.year - years, 1, 1)
        
        stats_list = await self.get_by_month_range(account_id, start_date, end_date)
        
        # 季節別グルーピング
        seasons = {
            'spring': [3, 4, 5],    # 春
            'summer': [6, 7, 8],    # 夏
            'autumn': [9, 10, 11],  # 秋
            'winter': [12, 1, 2]    # 冬
        }
        
        seasonal_data = {}
        
        for season_name, months in seasons.items():
            season_stats = [s for s in stats_list if date.fromisoformat(s["stats_month"]).month in months]
            
            if season_stats:
                avg_engagement = sum((s.get("avg_engagement_rate") or 0) for s in season_stats) / len(season_stats)
                avg_followers_growth = sum((s.get("follower_growth") or 0) for s in season_stats) / len(season_stats)
                avg_posts = sum((s.get("total_posts") or 0) for s in season_stats) / len(season_stats)
                
                seasonal_data[season_name] = {
                    'avg_engagement_rate': round(avg_engagement, 2),
                    'avg_followers_growth': round(avg_followers_growth, 2),
                    'avg_posts': round(avg_posts, 2),
                    'months_count': len(season_stats)
                }
        
        return seasonal_data
    
    async def bulk_create(self, stats_list: List[dict]) -> List[Record]:
        """一括作成"""
        if not stats_list:
            return []
        res = self.supabase.table("instagram_monthly_stats").insert([prepare_record(s) for s in stats_list]).execute()
        raise_for_error(res)
        return to_records(get_data(res))

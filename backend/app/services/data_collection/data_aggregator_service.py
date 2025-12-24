"""
Data Aggregator Service
API から取得した生データを DB 保存用に集約・変換するサービス
"""
import json
import logging
from datetime import date, datetime, time, timezone
from typing import Dict, Any, List, Optional

# ログ設定
logger = logging.getLogger(__name__)

class DataAggregatorService:
    """データ集約サービス"""
    
    def aggregate_daily_stats(
        self,
        account_id: str,
        target_date: date,
        basic_data: Dict[str, Any],
        insights_data: Dict[str, Any],
        posts_data: List[Dict[str, Any]],
        collected_at: datetime
    ) -> Dict[str, Any]:
        """
        日次統計データを集約
        
        Args:
            account_id: アカウントID
            target_date: 対象日付
            basic_data: 基本アカウントデータ
            insights_data: インサイトデータ
            posts_data: 投稿データリスト
            collected_at: 収集時刻
            
        Returns:
            Dict[str, Any]: 日次統計データ
        """
        try:
            logger.debug(f"Aggregating daily stats for account {account_id}, date {target_date}")
            
            # 基本アカウント指標
            follower_count = basic_data.get('followers_count', 0)
            following_count = basic_data.get('follows_count', 0)
            media_count = basic_data.get('media_count', 0)
            
            # インサイト指標（followers_countがbasicで取れない場合のフォールバック）
            follower_count_insights = insights_data.get('follower_count', 0)
            
            # フォロワー数の値を決定（basicデータを優先、fallbackでinsights）
            final_follower_count = follower_count if follower_count > 0 else follower_count_insights
            
            # 投稿関連の集約
            posts_stats = self._aggregate_posts_stats(posts_data)
            
            media_type_distribution = posts_stats.get("media_type_distribution", {})
            data_sources = []
            if basic_data:
                data_sources.append("basic_fields")
            if insights_data:
                data_sources.append("insights_api")
            if posts_data is not None:
                data_sources.append("posts_api")

            # 日次統計データ（現在のテーブル定義に合わせる）
            daily_stats = {
                "account_id": account_id,
                "stats_date": target_date,
                "followers_count": final_follower_count,
                "following_count": following_count,
                "media_count": media_count,
                "posts_count": posts_stats["posts_count"],
                "total_likes": posts_stats["total_likes"],
                "total_comments": posts_stats["total_comments"],
                "media_type_distribution": json.dumps(media_type_distribution, ensure_ascii=False),
                "data_sources": json.dumps(data_sources, ensure_ascii=False),
            }
            
            logger.debug(f"Daily stats aggregated successfully - Posts: {posts_stats['posts_count']}, Followers: {final_follower_count}")
            return daily_stats
            
        except Exception as e:
            logger.error(f"Failed to aggregate daily stats for account {account_id}: {str(e)}")
            raise
    
    def _aggregate_posts_stats(self, posts_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        投稿データの集約
        
        Args:
            posts_data: 投稿データリスト
            
        Returns:
            Dict[str, Any]: 集約された投稿統計
        """
        if not posts_data:
            return {
                'posts_count': 0,
                'total_likes': 0,
                'total_comments': 0,
                'total_shares': 0,
                'total_saves': 0,
                'total_video_views': 0,
                "media_type_distribution": {},
            }
        
        stats = {
            'posts_count': len(posts_data),
            'total_likes': 0,
            'total_comments': 0,
            'total_shares': 0,
            'total_saves': 0,
            'total_video_views': 0,
            "media_type_distribution": {},
        }
        
        for post in posts_data:
            # 基本メトリクス（投稿データから取得可能）
            stats['total_likes'] += post.get('like_count', 0)
            stats['total_comments'] += post.get('comments_count', 0)
            
            media_type = post.get("media_type") or "UNKNOWN"
            stats["media_type_distribution"][media_type] = stats["media_type_distribution"].get(media_type, 0) + 1
            
            # その他のメトリクスはインサイトAPIから取得が必要
            # ここではデフォルト値を設定
            # 実際の値は post insights API で取得
        
        logger.debug(f"Posts stats aggregated - {stats}")
        return stats
    
    def _calculate_engagement_rate(
        self,
        follower_count: int,
        total_likes: int,
        total_comments: int
    ) -> float:
        """
        エンゲージメント率計算
        
        Args:
            follower_count: フォロワー数
            total_likes: 総いいね数
            total_comments: 総コメント数
            
        Returns:
            float: エンゲージメント率（%）
        """
        if follower_count == 0:
            return 0.0
        
        total_engagement = total_likes + total_comments
        engagement_rate = (total_engagement / follower_count) * 100
        
        return round(engagement_rate, 2)
    
    def _calculate_avg_per_post(self, total_value: int, posts_count: int) -> float:
        """
        投稿あたりの平均値計算
        
        Args:
            total_value: 総計値
            posts_count: 投稿数
            
        Returns:
            float: 平均値
        """
        if posts_count == 0:
            return 0.0
        
        return round(total_value / posts_count, 2)
    
    def _calculate_data_quality_score(
        self,
        basic_data: Dict[str, Any],
        insights_data: Dict[str, Any],
        posts_data: List[Dict[str, Any]]
    ) -> float:
        """
        データ品質スコア計算
        
        Args:
            basic_data: 基本データ
            insights_data: インサイトデータ
            posts_data: 投稿データ
            
        Returns:
            float: データ品質スコア（0-100）
        """
        score = 0.0
        max_score = 100.0
        
        # 基本データの完全性（40点）
        basic_fields = ['id', 'username', 'followers_count', 'follows_count', 'media_count']
        basic_completeness = sum(1 for field in basic_fields if basic_data.get(field) is not None) / len(basic_fields)
        score += basic_completeness * 40
        
        # インサイトデータの完全性（30点）
        insight_fields = ['reach', 'follower_count']
        insight_completeness = sum(1 for field in insight_fields if insights_data.get(field, 0) > 0) / len(insight_fields)
        score += insight_completeness * 30
        
        # 投稿データの完全性（20点）
        posts_score = min(len(posts_data) / 5.0, 1.0) * 20  # 5投稿以上で満点
        score += posts_score
        
        # データの一貫性（10点）
        # フォロワー数の一貫性チェック
        basic_followers = basic_data.get('followers_count', 0)
        insight_followers = insights_data.get('follower_count', 0)
        
        if basic_followers > 0 and insight_followers > 0:
            # 差が10%以内であれば一貫性があると判定
            diff_ratio = abs(basic_followers - insight_followers) / max(basic_followers, insight_followers)
            if diff_ratio <= 0.1:
                score += 10
            else:
                score += max(0, 10 - (diff_ratio * 50))  # 差が大きいほど減点
        elif basic_followers > 0 or insight_followers > 0:
            score += 5  # 片方だけでも5点
        
        return round(min(score, max_score), 2)
    
    def extract_post_info(self, post_data: Dict[str, Any], account_id: str) -> Dict[str, Any]:
        """
        投稿データから投稿情報を抽出
        
        Args:
            post_data: API から取得した投稿データ
            account_id: アカウントID
            
        Returns:
            Dict[str, Any]: 投稿情報
        """
        try:
            # タイムスタンプの解析
            timestamp_str = post_data.get('timestamp', '')
            posted_at = None
            if timestamp_str:
                try:
                    posted_at = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Failed to parse timestamp: {timestamp_str}")
            
            post_info = {
                'account_id': account_id,
                'instagram_post_id': post_data.get('id', ''),
                'media_type': post_data.get('media_type', 'IMAGE'),
                'caption': post_data.get('caption', '')[:2000] if post_data.get('caption') else '',  # テーブル制限に合わせて切り詰め
                'media_url': post_data.get('media_url', ''),
                'thumbnail_url': post_data.get('thumbnail_url', ''),
                'permalink': post_data.get('permalink', ''),
                # 'shortcode': post_data.get('shortcode', ''),  # モデルにフィールドが存在しないためコメントアウト
                'posted_at': posted_at
                # 'like_count': post_data.get('like_count', 0),  # モデルにフィールドが存在しないためコメントアウト
                # 'comment_count': post_data.get('comments_count', 0),
                # 'is_comment_enabled': post_data.get('is_comment_enabled', True),
                # 'collected_at': datetime.now()
            }
            
            logger.debug(f"Extracted post info for {post_info['instagram_post_id']}")
            return post_info
            
        except Exception as e:
            logger.error(f"Failed to extract post info: {str(e)}")
            raise
    
    def extract_post_metrics(
        self,
        post_id: str,
        insights_data: Dict[str, Any],
        target_date: date
    ) -> Dict[str, Any]:
        """
        投稿メトリクスを抽出
        
        Args:
            post_id: 投稿ID
            insights_data: インサイトデータ
            target_date: 対象日付
            
        Returns:
            Dict[str, Any]: 投稿メトリクス
        """
        try:
            metrics = {
                'post_id': None,  # 保存時に設定
                'recorded_at': datetime.combine(target_date, time.min).replace(tzinfo=timezone.utc),
                'likes': insights_data.get('likes', 0),
                'comments': insights_data.get('comments', 0),
                'shares': insights_data.get('shares', 0),
                'saved': insights_data.get('saved', 0),  # saves → saved に修正
                'reach': insights_data.get('reach', 0),
                'views': insights_data.get('views', 0),  # impressions → views に修正（モデルに合わせて）
                'video_view_total_time': insights_data.get('ig_reels_video_view_total_time', 0),  # フィールド名修正
                'avg_watch_time': insights_data.get('ig_reels_avg_watch_time', 0),  # フィールド名修正
                'profile_visits': insights_data.get('profile_visits', 0),
                'profile_activity': insights_data.get('profile_activity', 0),  # 追加
                'follows': insights_data.get('follows', 0)
            }
            
            logger.debug(f"Extracted post metrics for {post_id}")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to extract post metrics for {post_id}: {str(e)}")
            raise
    
    def calculate_account_growth(
        self,
        current_stats: Dict[str, Any],
        previous_stats: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        アカウント成長指標計算
        
        Args:
            current_stats: 現在の統計
            previous_stats: 前回の統計
            
        Returns:
            Dict[str, Any]: 成長指標
        """
        if not previous_stats:
            return {
                'follower_growth': 0,
                'follower_growth_rate': 0.0,
                'media_growth': 0,
                'engagement_growth_rate': 0.0
            }
        
        try:
            # フォロワー成長
            current_followers = current_stats.get('follower_count', 0)
            previous_followers = previous_stats.get('follower_count', 0)
            follower_growth = current_followers - previous_followers
            
            follower_growth_rate = 0.0
            if previous_followers > 0:
                follower_growth_rate = (follower_growth / previous_followers) * 100
            
            # メディア成長
            current_media = current_stats.get('media_count', 0)
            previous_media = previous_stats.get('media_count', 0)
            media_growth = current_media - previous_media
            
            # エンゲージメント成長率
            current_engagement = current_stats.get('engagement_rate', 0)
            previous_engagement = previous_stats.get('engagement_rate', 0)
            engagement_growth_rate = current_engagement - previous_engagement
            
            growth_metrics = {
                'follower_growth': follower_growth,
                'follower_growth_rate': round(follower_growth_rate, 2),
                'media_growth': media_growth,
                'engagement_growth_rate': round(engagement_growth_rate, 2)
            }
            
            logger.debug(f"Calculated growth metrics: {growth_metrics}")
            return growth_metrics
            
        except Exception as e:
            logger.error(f"Failed to calculate growth metrics: {str(e)}")
            return {
                'follower_growth': 0,
                'follower_growth_rate': 0.0,
                'media_growth': 0,
                'engagement_growth_rate': 0.0
            }

# サービスインスタンス作成関数
def create_data_aggregator() -> DataAggregatorService:
    """Data Aggregator Service インスタンス作成"""
    return DataAggregatorService()

# 使用例（開発・テスト用）
def test_data_aggregation():
    """データ集約のテスト"""
    aggregator = create_data_aggregator()
    
    # サンプルデータ
    sample_basic_data = {
        'id': '123456789',
        'username': 'test_account',
        'followers_count': 1000,
        'follows_count': 500,
        'media_count': 150
    }
    
    sample_insights_data = {
        'reach': 5000,
        'follower_count': 1000
    }
    
    sample_posts_data = [
        {
            'id': 'post_1',
            'like_count': 50,
            'comments_count': 5,
            'media_type': 'IMAGE',
            'timestamp': '2024-01-20T10:00:00Z'
        },
        {
            'id': 'post_2',
            'like_count': 75,
            'comments_count': 8,
            'media_type': 'VIDEO',
            'timestamp': '2024-01-20T15:00:00Z'
        }
    ]
    
    try:
        # 日次統計集約テスト
        daily_stats = aggregator.aggregate_daily_stats(
            account_id="account_uuid_dummy",
            target_date=date(2024, 1, 20),
            basic_data=sample_basic_data,
            insights_data=sample_insights_data,
            posts_data=sample_posts_data,
            collected_at=datetime.now()
        )
        
        print(f"Daily Stats Aggregation Test:")
        print(f"  Followers: {daily_stats['followers_count']}")
        print(f"  Posts Count: {daily_stats['posts_count']}")
        print(f"  Total Likes: {daily_stats['total_likes']}")
        print(f"  Media Type Distribution: {daily_stats['media_type_distribution']}")
        
        # 投稿情報抽出テスト
        post_info = aggregator.extract_post_info(sample_posts_data[0], "account_uuid_dummy")
        print(f"\nPost Info Extraction Test:")
        print(f"  Instagram Post ID: {post_info['instagram_post_id']}")
        print(f"  Media Type: {post_info['media_type']}")
        print(f"  Posted At: {post_info['posted_at']}")
        
        print("\nData aggregation test completed successfully")
        
    except Exception as e:
        print(f"Test failed: {str(e)}")

if __name__ == "__main__":
    # テスト実行
    test_data_aggregation()

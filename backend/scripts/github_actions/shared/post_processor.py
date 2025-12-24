"""
Post Processor
投稿データとインサイトの保存処理
"""

from datetime import datetime
from typing import Dict, Any, Optional
import logging

from app.repositories.instagram_post_repository import InstagramPostRepository
from app.repositories.instagram_post_metrics_repository import InstagramPostMetricsRepository

class PostProcessor:
    """投稿処理クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def save_post_data(self, account_id: str, post_data: Dict) -> Optional[Any]:
        """投稿データの保存"""
        
        try:
            # 投稿日時の変換
            posted_at = None
            if post_data.get('timestamp'):
                try:
                    posted_at = datetime.fromisoformat(
                        post_data['timestamp'].replace('Z', '+00:00')
                    )
                except ValueError:
                    self.logger.warning(f"Invalid timestamp: {post_data['timestamp']}")
            
            # 投稿データの構築
            post_create_data = {
                'account_id': account_id,
                'instagram_post_id': post_data['id'],
                'media_type': post_data.get('media_type', 'UNKNOWN'),
                'caption': post_data.get('caption', ''),
                'media_url': post_data.get('media_url', ''),
                'thumbnail_url': post_data.get('thumbnail_url', ''),
                'permalink': post_data.get('permalink', ''),
                'posted_at': posted_at
            }
            
            from app.core.database import get_db_sync
            supabase = get_db_sync()
            post_repo = InstagramPostRepository(supabase)
            saved_post = await post_repo.create(post_create_data)

            self.logger.info(f"📝 Saved post data: {post_data['id']}")
            return saved_post
                
        except Exception as e:
            self.logger.error(f"Failed to save post data {post_data.get('id', 'unknown')}: {e}")
            return None
    
    async def save_post_insights(self, post_id: str, insights_data: Dict) -> bool:
        """投稿インサイトの保存"""
        
        try:
            # インサイトデータの構築
            metrics_data = {
                'post_id': post_id,
                'likes': insights_data.get('likes', 0),
                'comments': insights_data.get('comments', 0),
                'saved': insights_data.get('saved', 0),
                'shares': insights_data.get('shares', 0),
                'views': insights_data.get('views', 0),
                'reach': insights_data.get('reach', 0),
                'total_interactions': insights_data.get('total_interactions', 0),
                'follows': insights_data.get('follows', 0),
                'profile_visits': insights_data.get('profile_visits', 0),
                'profile_activity': insights_data.get('profile_activity', 0),
                'video_view_total_time': insights_data.get('ig_reels_video_view_total_time', 0),
                'avg_watch_time': insights_data.get('ig_reels_avg_watch_time', 0),
                'engagement_rate': self._calculate_engagement_rate(insights_data),
                'recorded_at': datetime.now()
            }
            
            from app.core.database import get_db_sync
            supabase = get_db_sync()
            metrics_repo = InstagramPostMetricsRepository(supabase)
            await metrics_repo.create(metrics_data)

            self.logger.info(f"📊 Saved post insights: {post_id}")
            return True
                
        except Exception as e:
            self.logger.error(f"Failed to save post insights for {post_id}: {e}")
            return False
    
    def _calculate_engagement_rate(self, insights_data: Dict) -> float:
        """エンゲージメント率計算"""
        
        try:
            likes = insights_data.get('likes', 0)
            comments = insights_data.get('comments', 0)
            saves = insights_data.get('saved', 0)
            shares = insights_data.get('shares', 0)
            reach = insights_data.get('reach', 0)
            
            total_engagement = likes + comments + saves + shares
            
            if reach > 0:
                return round((total_engagement / reach) * 100, 2)
            else:
                return 0.0
                
        except Exception:
            return 0.0

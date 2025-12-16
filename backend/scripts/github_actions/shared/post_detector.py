"""
Post Detector
新規投稿検出ロジック
"""

from datetime import datetime, timezone
from typing import List, Dict, Any
import logging

from app.repositories.instagram_post_repository import InstagramPostRepository

class PostDetector:
    """投稿検出クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def detect_new_posts(
        self,
        api_posts: List[Dict],
        check_from: datetime,
        account_id: str,
        force_reprocess: bool = False
    ) -> List[Dict]:
        """新規投稿検出"""
        
        new_posts = []
        
        for post in api_posts:
            # タイムスタンプチェック
            if not self._is_within_timeframe(post, check_from):
                continue
            
            # 既存投稿チェック（force_reprocessの場合はスキップ）
            if not force_reprocess:
                if await self._post_exists_in_db(post['id']):
                    continue
            
            new_posts.append(post)
        
        return new_posts
    
    def _is_within_timeframe(self, post: Dict, check_from: datetime) -> bool:
        """投稿が指定時刻以降かチェック"""
        timestamp_str = post.get('timestamp', '')
        if not timestamp_str:
            return False
        
        try:
            # ISO 8601 format: "2025-07-01T10:30:45+0000"
            post_datetime = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            # check_fromがnaiveの場合はUTCに変換
            if check_from.tzinfo is None:
                check_from = check_from.replace(tzinfo=timezone.utc)
            
            return post_datetime >= check_from
        except ValueError:
            self.logger.warning(f"Invalid timestamp format: {timestamp_str}")
            return False
    
    async def _post_exists_in_db(self, instagram_post_id: str) -> bool:
        """投稿がデータベースに存在するかチェック"""
        # 注意: この実装では毎回DBアクセスが発生するため、
        # 実際の実装では事前に既存投稿IDリストを取得して
        # メモリ上でチェックする方が効率的
        
        from app.core.database import get_db_sync
        try:
            supabase = get_db_sync()
            post_repo = InstagramPostRepository(supabase)
            existing_post = await post_repo.get_by_instagram_post_id(instagram_post_id)
            return existing_post is not None
        except Exception as e:
            self.logger.error(f"Database error checking post existence: {e}")
            return False

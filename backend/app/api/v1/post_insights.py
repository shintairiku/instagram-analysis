"""
Post Insights API Endpoints
投稿インサイトAPIエンドポイント
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client
from typing import Optional
from datetime import date
import logging

from ...core.database import get_db
from ...services.api.post_insight_service import create_post_insight_service
from ...schemas.post_insight_schema import PostInsightResponse, ErrorResponse

# ログ設定
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["Post Insights"])

@router.get(
    "/insights",
    response_model=PostInsightResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Account not found"},
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="投稿インサイト取得",
    description="""
    指定されたアカウントの投稿インサイトデータを取得します。
    
    **パラメータ:**
    - `account_id`: アカウントID（UUIDまたはInstagram User ID）
    - `from_date`: 開始日付（YYYY-MM-DD形式、オプション）
    - `to_date`: 終了日付（YYYY-MM-DD形式、オプション）
    - `media_type`: メディアタイプフィルター（IMAGE, VIDEO, CAROUSEL_ALBUM, STORY、オプション）
    - `limit`: 最大取得件数（1-1000、オプション）
    
    **レスポンス:**
    - 投稿データリスト
    - サマリー統計
    - メタデータ
    """
)
async def get_post_insights(
    account_id: str = Query(..., description="アカウントID（UUIDまたはInstagram User ID）"),
    from_date: Optional[date] = Query(None, description="開始日付（YYYY-MM-DD）"),
    to_date: Optional[date] = Query(None, description="終了日付（YYYY-MM-DD）"),
    media_type: Optional[str] = Query(None, description="メディアタイプフィルター", pattern="^(IMAGE|VIDEO|CAROUSEL_ALBUM|STORY)$"),
    limit: Optional[int] = Query(None, description="最大取得件数", ge=1, le=1000),
    db: Client = Depends(get_db)
):
    """投稿インサイトデータを取得"""
    try:
        logger.info(f"POST /api/v1/posts/insights called with account_id: {account_id}")
        
        # パラメータ検証
        if from_date and to_date and from_date > to_date:
            raise HTTPException(
                status_code=400,
                detail="from_date must be earlier than or equal to to_date"
            )
        
        # サービス呼び出し
        service = create_post_insight_service(db)
        result = await service.get_post_insights(
            account_id=account_id,
            from_date=from_date,
            to_date=to_date,
            media_type=media_type,
            limit=limit
        )
        
        logger.info(f"Successfully retrieved {result['meta']['total_posts']} post insights")
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid parameter: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"Failed to get post insights: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching post insights"
        )

# 個別投稿の詳細取得（将来拡張用）
@router.get(
    "/{post_id}/insights",
    summary="個別投稿インサイト取得",
    description="指定された投稿の詳細インサイトを取得します（将来実装予定）"
)
async def get_single_post_insights(
    post_id: str,
    db: Client = Depends(get_db)
):
    """個別投稿のインサイト取得（将来実装）"""
    raise HTTPException(
        status_code=501,
        detail="Single post insights endpoint is not implemented yet"
    )

# メディアタイプ別サマリー取得（将来拡張用）
@router.get(
    "/insights/summary",
    summary="メディアタイプ別サマリー取得",
    description="アカウントのメディアタイプ別パフォーマンスサマリーを取得します（将来実装予定）"
)
async def get_media_type_summary(
    account_id: str = Query(..., description="アカウントID"),
    db: Client = Depends(get_db)
):
    """メディアタイプ別サマリー取得（将来実装）"""
    raise HTTPException(
        status_code=501,
        detail="Media type summary endpoint is not implemented yet"
    )

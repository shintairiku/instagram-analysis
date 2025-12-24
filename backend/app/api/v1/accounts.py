"""
Accounts API Endpoints
アカウント管理用のAPIエンドポイント
"""
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from ...core.database import get_db
from ...services.api.account_service import create_account_service, AccountService
from ...schemas.instagram_account_schema import (
    AccountListResponse,
    AccountDetailResponse,
    TokenValidationResponse
)

# ログ設定
logger = logging.getLogger(__name__)

# ルーター設定
router = APIRouter(tags=["accounts"])

# CORS対応のためのOPTIONSハンドラー
@router.options("/")
@router.options("")
async def options_accounts():
    """CORS プリフライトリクエスト対応"""
    return {}


# trailing slashありとなしの両方に対応
@router.get(
    "/",
    response_model=AccountListResponse,
    summary="アカウント一覧取得",
    description="Instagram アカウントの一覧を取得します。"
)
@router.get(
    "",
    response_model=AccountListResponse,
    summary="アカウント一覧取得",
    description="Instagram アカウントの一覧を取得します。"
)
async def get_accounts(
    active_only: bool = Query(True, description="アクティブアカウントのみ取得"),
    include_metrics: bool = Query(False, description="統計情報を含む"),
    db: Client = Depends(get_db)
) -> AccountListResponse:
    """
    アカウント一覧取得
    
    - **active_only**: アクティブなアカウントのみ取得するか
    - **include_metrics**: フォロワー数などの統計情報を含むか
    """
    try:
        logger.info(f"GET /accounts - active_only={active_only}, include_metrics={include_metrics}")
        
        account_service = create_account_service(db)
        result = await account_service.get_accounts(
            active_only=active_only,
            include_metrics=include_metrics
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get accounts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching accounts"
        )


@router.get(
    "/{account_id}",
    response_model=AccountDetailResponse,
    summary="アカウント詳細取得",
    description="指定されたアカウントの詳細情報を取得します。"
)
async def get_account_details(
    account_id: str,
    db: Client = Depends(get_db)
) -> AccountDetailResponse:
    """
    アカウント詳細取得
    
    - **account_id**: アカウントID (UUID または Instagram User ID)
    """
    try:
        logger.info(f"GET /accounts/{account_id}")
        
        account_service = create_account_service(db)
        result = await account_service.get_account_details(account_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Account not found: {account_id}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get account details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching account details"
        )


@router.post(
    "/{account_id}/validate-token",
    response_model=TokenValidationResponse,
    summary="トークン有効性確認",
    description="指定されたアカウントのアクセストークンの有効性を確認します。"
)
async def validate_account_token(
    account_id: str,
    db: Client = Depends(get_db)
) -> TokenValidationResponse:
    """
    トークン有効性確認
    
    - **account_id**: アカウントID (UUID または Instagram User ID)
    
    Returns:
    - トークンの有効性、期限、警告レベルなどの情報
    """
    try:
        logger.info(f"POST /accounts/{account_id}/validate-token")
        
        account_service = create_account_service(db)
        result = await account_service.validate_token(account_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Account not found: {account_id}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate token: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while validating token"
        )


@router.get(
    "/{account_id}/status",
    summary="アカウント状態確認",
    description="アカウントの接続状態とデータ収集状況を確認します。"
)
async def get_account_status(
    account_id: str,
    db: Client = Depends(get_db)
) -> dict:
    """
    アカウント状態確認
    
    - **account_id**: アカウントID
    
    Returns:
    - アカウント状態、最終同期時刻、データ品質などの情報
    """
    try:
        logger.info(f"GET /accounts/{account_id}/status")
        
        account_service = create_account_service(db)
        
        # アカウント詳細取得
        account_detail = await account_service.get_account_details(account_id)
        if not account_detail:
            raise HTTPException(
                status_code=404,
                detail=f"Account not found: {account_id}"
            )
        
        # トークン検証
        token_validation = await account_service.validate_token(account_id)
        
        # 状態サマリー作成
        status = {
            "account_id": account_detail.id,
            "username": account_detail.username,
            "is_active": account_detail.is_active,
            "connection_status": "connected" if account_detail.is_active else "disconnected",
            "token_status": {
                "is_valid": token_validation.is_valid if token_validation else False,
                "warning_level": token_validation.warning_level if token_validation else "unknown",
                "expires_at": token_validation.expires_at if token_validation else None,
                "days_until_expiry": token_validation.days_until_expiry if token_validation else None,
            },
            "data_status": {
                "total_posts": account_detail.total_posts,
                "last_synced_at": account_detail.last_synced_at,
                "data_quality_score": account_detail.data_quality_score,
            },
            "created_at": account_detail.created_at,
            "updated_at": account_detail.updated_at,
        }
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get account status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching account status"
        )


@router.get(
    "/health/tokens",
    summary="トークン健全性チェック",
    description="全アカウントのトークン状態をチェックします。"
)
async def check_tokens_health(
    days_threshold: int = Query(7, description="警告する期限切れまでの日数"),
    db: Client = Depends(get_db)
) -> dict:
    """
    トークン健全性チェック
    
    - **days_threshold**: 警告する期限切れまでの日数
    
    Returns:
    - 全アカウントのトークン状態サマリー
    """
    try:
        logger.info(f"GET /accounts/health/tokens - threshold={days_threshold} days")
        
        account_service = create_account_service(db)
        
        # 期限切れ近いアカウント取得
        expiring_accounts = await account_service.get_accounts_needing_refresh(days_threshold)
        
        # 全アカウント取得
        all_accounts = await account_service.get_accounts(active_only=False, include_metrics=False)
        
        # 統計計算
        total_accounts = all_accounts.total
        active_accounts = all_accounts.active_count
        expiring_count = len(expiring_accounts)
        
        # 警告レベル別集計
        warning_levels = {"none": 0, "warning": 0, "critical": 0, "expired": 0}
        
        for account in all_accounts.accounts:
            if account.is_token_valid:
                if account.days_until_expiry is None:
                    warning_levels["none"] += 1
                elif account.days_until_expiry <= 1:
                    warning_levels["critical"] += 1
                elif account.days_until_expiry <= 7:
                    warning_levels["warning"] += 1
                else:
                    warning_levels["none"] += 1
            else:
                warning_levels["expired"] += 1
        
        health_status = {
            "overall_health": "healthy" if expiring_count == 0 else "warning" if expiring_count < 3 else "critical",
            "summary": {
                "total_accounts": total_accounts,
                "active_accounts": active_accounts,
                "accounts_needing_refresh": expiring_count,
                "warning_levels": warning_levels,
            },
            "expiring_accounts": [
                {
                    "id": str(acc.get("id")),
                    "username": acc.get("username"),
                    "days_until_expiry": (
                        (
                            datetime.fromisoformat(str(acc.get("token_expires_at")).replace("Z", "+00:00")).replace(tzinfo=None)
                            - datetime.now()
                        ).days
                        if acc.get("token_expires_at")
                        else None
                    ),
                    "expires_at": acc.get("token_expires_at"),
                }
                for acc in expiring_accounts
            ],
            "checked_at": datetime.now().isoformat(),
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Failed to check tokens health: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while checking token health"
        )

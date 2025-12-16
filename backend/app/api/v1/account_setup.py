"""
Account Setup API Endpoints
アカウントセットアップ用のAPIエンドポイント
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from supabase import Client

from ...core.database import get_db
from ...services.api.account_setup_service import create_account_setup_service, AccountSetupService
from ...services.api.account_service import create_account_service
from ...schemas.account_setup_schema import (
    AccountSetupRequest,
    AccountSetupResponse
)
from ...schemas.instagram_account_schema import AccountListResponse

# ログ設定
logger = logging.getLogger(__name__)

# ルーター設定
router = APIRouter(tags=["account-setup"])


@router.post(
    "/",
    response_model=AccountSetupResponse,
    summary="アカウントセットアップ",
    description="Instagram App ID、App Secret、短期トークンからアカウントを自動セットアップします。"
)
async def setup_accounts(
    request: AccountSetupRequest,
    db: Client = Depends(get_db)
) -> AccountSetupResponse:
    """
    アカウントセットアップ
    
    Instagram の App ID、App Secret、短期トークンを使用して以下の処理を実行します：
    1. 短期トークンを長期トークンに変換
    2. 関連するFacebookページを取得
    3. 各ページに接続されているInstagramアカウントを発見
    4. アカウント情報をデータベースに保存
    
    Args:
        request: セットアップリクエスト（App ID、App Secret、短期トークン）
        
    Returns:
        AccountSetupResponse: セットアップ結果
    """
    try:
        logger.info("POST /account-setup - Starting account setup")
        logger.info(f"App ID: {request.app_id}, Token length: {len(request.short_token)}")
        
        account_setup_service = create_account_setup_service(db)
        result = await account_setup_service.setup_accounts(request)
        
        # ログに結果を記録
        if result.success:
            logger.info(
                f"Account setup completed successfully: "
                f"discovered={result.accounts_discovered}, "
                f"created={result.accounts_created}, "
                f"updated={result.accounts_updated}"
            )
        else:
            logger.warning(f"Account setup failed: {result.message}")
            if result.errors:
                logger.warning(f"Errors: {', '.join(result.errors)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to setup accounts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred during account setup"
        )


@router.get(
    "/status",
    summary="セットアップ状況確認",
    description="アカウントセットアップの状況を確認します。"
)
async def get_setup_status(
    db: Client = Depends(get_db)
) -> dict:
    """
    セットアップ状況確認
    
    現在のアカウント登録状況とトークンの健全性を確認します。
    
    Returns:
        dict: セットアップ状況サマリー
    """
    try:
        logger.info("GET /account-setup/status")
        
        account_service = create_account_service(db)
        
        # アカウント一覧を取得
        accounts_response = await account_service.get_accounts(
            active_only=False,
            include_metrics=False
        )
        
        # トークン健全性チェック
        token_health = await account_service.check_tokens_health()
        
        # 統計計算
        total_accounts = accounts_response.total
        active_accounts = accounts_response.active_count
        inactive_accounts = total_accounts - active_accounts
        
        # 最近作成されたアカウント（24時間以内）
        from datetime import datetime, timedelta
        recent_threshold = datetime.now() - timedelta(hours=24)
        recent_accounts = [
            acc for acc in accounts_response.accounts 
            if acc.created_at and acc.created_at >= recent_threshold
        ]
        
        status = {
            "setup_summary": {
                "total_accounts": total_accounts,
                "active_accounts": active_accounts,
                "inactive_accounts": inactive_accounts,
                "recent_accounts_24h": len(recent_accounts),
            },
            "token_health": {
                "overall_status": token_health.get("overall_health", "unknown"),
                "accounts_needing_refresh": len(token_health.get("expiring_accounts", [])),
                "warning_levels": token_health.get("summary", {}).get("warning_levels", {}),
            },
            "setup_recommendations": [],
            "last_checked": datetime.now().isoformat(),
        }
        
        # 推奨事項を追加
        if total_accounts == 0:
            status["setup_recommendations"].append("まだアカウントが登録されていません。アカウントセットアップを実行してください。")
        elif inactive_accounts > 0:
            status["setup_recommendations"].append(f"{inactive_accounts}個の非アクティブアカウントがあります。")
        
        if token_health.get("overall_health") == "warning":
            status["setup_recommendations"].append("期限切れ間近のトークンがあります。トークンの更新を検討してください。")
        elif token_health.get("overall_health") == "critical":
            status["setup_recommendations"].append("緊急: 期限切れまたは間近のトークンがあります。すぐに対応が必要です。")
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get setup status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching setup status"
        )


@router.get(
    "/discovered-accounts",
    response_model=AccountListResponse,
    summary="登録済みアカウント一覧",
    description="セットアップで登録されたアカウントの一覧を取得します。"
)
async def get_discovered_accounts(
    active_only: bool = True,
    include_metrics: bool = False,
    db: Client = Depends(get_db)
) -> AccountListResponse:
    """
    登録済みアカウント一覧取得
    
    セットアップで登録されたInstagramアカウントの一覧を取得します。
    
    Args:
        active_only: アクティブなアカウントのみ取得するか
        include_metrics: 統計情報を含むか
        
    Returns:
        AccountListResponse: アカウント一覧
    """
    try:
        logger.info(f"GET /account-setup/discovered-accounts - active_only={active_only}")
        
        account_service = create_account_service(db)
        result = await account_service.get_accounts(
            active_only=active_only,
            include_metrics=include_metrics
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get discovered accounts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while fetching accounts"
        )


@router.post(
    "/validate-credentials",
    summary="認証情報検証",
    description="App IDとApp Secretの有効性を事前に検証します。"
)
async def validate_credentials(
    app_id: str,
    app_secret: str
) -> dict:
    """
    認証情報検証
    
    App IDとApp Secretの組み合わせが有効かどうかを確認します。
    実際のセットアップを実行する前の事前チェックに使用できます。
    
    Args:
        app_id: Instagram App ID
        app_secret: Instagram App Secret
        
    Returns:
        dict: 検証結果
    """
    try:
        logger.info(f"POST /account-setup/validate-credentials - app_id={app_id}")
        
        # App IDの基本チェック
        if not app_id.isdigit():
            return {
                "valid": False,
                "error": "App ID must be numeric",
                "details": "App IDは数値である必要があります"
            }
        
        # App Secretの基本チェック
        if len(app_secret) < 16:
            return {
                "valid": False,
                "error": "App Secret too short",
                "details": "App Secretは16文字以上である必要があります"
            }
        
        # Facebook Graph APIでアプリ情報を確認
        import requests
        url = f"https://graph.facebook.com/{app_id}"
        params = {
            'access_token': f"{app_id}|{app_secret}",
            'fields': 'name,category'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                app_info = response.json()
                return {
                    "valid": True,
                    "app_name": app_info.get("name"),
                    "app_category": app_info.get("category"),
                    "message": "認証情報は有効です"
                }
            else:
                return {
                    "valid": False,
                    "error": "Invalid credentials",
                    "details": "App IDとApp Secretの組み合わせが無効です"
                }
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to validate credentials with Facebook API: {str(e)}")
            return {
                "valid": None,
                "error": "Cannot verify",
                "details": "Facebook APIでの検証に失敗しました。基本チェックのみ実行されています。"
            }
        
    except Exception as e:
        logger.error(f"Failed to validate credentials: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred during credential validation"
        )

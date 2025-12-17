"""
Collection (Sync) API Endpoints
Cloud Scheduler 等からの定期実行・手動更新を受け付けます。
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from ...services.data_collection.daily_collector_service import create_daily_collector
from ...services.data_collection.recent_post_sync_service import create_recent_post_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collection", tags=["collection"])

_COLLECTION_TOKEN_ENV = "COLLECTION_TRIGGER_TOKEN"

# 1プロセス内の重複実行防止（Railway等の単一インスタンス前提の軽量ロック）
_daily_lock = asyncio.Lock()
_daily_last_status: Dict[str, Any] = {
    "running": False,
    "started_at": None,
    "completed_at": None,
    "last_error": None,
    "last_summary": None,
}

_account_locks: Dict[str, asyncio.Lock] = {}


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].strip(), parts[1].strip()
    if scheme.lower() != "bearer":
        return None
    return token or None


def require_collection_token(
    authorization: Optional[str] = Header(None),
    x_collection_token: Optional[str] = Header(None),
) -> None:
    """定期実行/手動更新用の簡易認証（共有トークン）。"""
    expected = os.getenv(_COLLECTION_TOKEN_ENV)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{_COLLECTION_TOKEN_ENV} is not configured",
        )

    token = _extract_bearer_token(authorization) or (x_collection_token.strip() if x_collection_token else None)
    if token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


class DailyCollectionTriggerRequest(BaseModel):
    target_date: Optional[date] = Field(
        default=None,
        description="収集対象日付（未指定時はサービス側のデフォルト。通常は昨日）",
    )
    account_filter: Optional[List[str]] = Field(
        default=None,
        description="instagram_user_id のリストで対象アカウントを絞り込み",
    )
    dry_run: bool = Field(default=False, description="true の場合DB保存を行わない")


async def _run_daily_collection_job(req: DailyCollectionTriggerRequest) -> None:
    global _daily_last_status
    try:
        _daily_last_status.update(
            {
                "running": True,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "last_error": None,
                "last_summary": None,
            }
        )

        collector = create_daily_collector()
        summary = await collector.collect_daily_data(
            target_date=req.target_date,
            account_filter=req.account_filter,
            dry_run=req.dry_run,
        )

        _daily_last_status["last_summary"] = {
            "target_date": summary.target_date.isoformat(),
            "total_accounts": summary.total_accounts,
            "successful_accounts": summary.successful_accounts,
            "failed_accounts": summary.failed_accounts,
            "started_at": summary.started_at.isoformat(),
            "completed_at": summary.completed_at.isoformat() if summary.completed_at else None,
            "total_duration_seconds": summary.total_duration_seconds,
        }
    except Exception as e:
        logger.error(f"Daily collection job failed: {e}", exc_info=True)
        _daily_last_status["last_error"] = str(e)
    finally:
        _daily_last_status["running"] = False
        _daily_last_status["completed_at"] = datetime.utcnow().isoformat()
        try:
            _daily_lock.release()
        except RuntimeError:
            # 既にrelease済みなど
            pass


@router.post(
    "/daily",
    summary="日次データ収集トリガー（Cloud Scheduler 用）",
    description="バックグラウンドで日次データ収集を開始します。重複実行は拒否します。",
)
async def trigger_daily_collection(
    background_tasks: BackgroundTasks,
    request: DailyCollectionTriggerRequest = Body(default_factory=DailyCollectionTriggerRequest),
    _: None = Depends(require_collection_token),
) -> Dict[str, Any]:
    if _daily_lock.locked():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Daily collection is already running")

    # ここでロックを獲得してからバックグラウンドに渡すことで、同時リクエストの二重起動を防ぐ
    await _daily_lock.acquire()

    background_tasks.add_task(_run_daily_collection_job, request)

    return {
        "accepted": True,
        "job": "daily_collection",
        "queued_at": datetime.utcnow().isoformat(),
        "requested_target_date": request.target_date.isoformat() if request.target_date else None,
        "dry_run": request.dry_run,
    }


@router.get(
    "/daily/status",
    summary="日次データ収集ステータス",
    description="直近の実行状況（同一プロセス内）を返します。",
)
async def get_daily_collection_status(
    _: None = Depends(require_collection_token),
) -> Dict[str, Any]:
    return _daily_last_status


class AccountRefreshRequest(BaseModel):
    window_days: int = Field(default=30, ge=1, le=90, description="直近何日分の投稿を更新対象にするか")
    max_posts: int = Field(default=50, ge=1, le=200, description="更新対象の最大投稿数（レート制限対策）")
    dry_run: bool = Field(default=False, description="true の場合DB保存を行わない")
    force: bool = Field(default=False, description="最終更新からの間隔チェックを無視して実行")


@router.post(
    "/accounts/{account_id}/refresh",
    summary="選択アカウントの手動更新（直近投稿）",
    description="レート制限対策として、直近 window_days の範囲内で最大 max_posts 件まで同期します。",
)
async def refresh_account_recent_posts(
    account_id: str,
    request: AccountRefreshRequest = Body(default_factory=AccountRefreshRequest),
    _: None = Depends(require_collection_token),
) -> Dict[str, Any]:
    # 1アカウント同時実行防止（同一プロセス内）
    lock = _account_locks.setdefault(account_id, asyncio.Lock())
    if lock.locked():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This account refresh is already running")

    # 直近更新の間隔チェック（過度な手動更新を抑制）
    min_interval_seconds = int(os.getenv("MANUAL_REFRESH_MIN_INTERVAL_SECONDS", "60"))

    service = create_recent_post_sync_service()
    service.init_repositories()
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account not found: {account_id}")

    if not request.force and min_interval_seconds > 0:
        last_synced_at = _parse_dt(account.get("last_synced_at"))
        if last_synced_at:
            now_utc = datetime.now(last_synced_at.tzinfo) if last_synced_at.tzinfo else datetime.utcnow()
            elapsed = (now_utc - last_synced_at).total_seconds()
            if elapsed < min_interval_seconds:
                retry_after = int(min_interval_seconds - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too frequent refresh. Retry after {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )

    async with lock:
        result = await service.sync_recent_posts(
            account_id=account_id,
            window_days=request.window_days,
            max_posts=request.max_posts,
            dry_run=request.dry_run,
        )

    if not result.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.error_message or "Sync failed")

    return {
        "success": True,
        "account_id": result.account_id,
        "instagram_user_id": result.instagram_user_id,
        "collected_at": result.collected_at.isoformat(),
        "posts_processed": result.posts_processed,
        "metrics_saved": result.metrics_saved,
    }

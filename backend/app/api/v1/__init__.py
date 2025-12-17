"""
API v1 Router
APIエンドポイントの統合
"""
from fastapi import APIRouter

from .post_insights import router as post_insights_router
from .accounts import router as accounts_router
from .account_setup import router as account_setup_router
from .collection import router as collection_router

# v1 APIルーター
api_v1_router = APIRouter(prefix="/api/v1")

# 各機能のルーターを統合
api_v1_router.include_router(post_insights_router)
api_v1_router.include_router(accounts_router, prefix="/accounts")
api_v1_router.include_router(account_setup_router, prefix="/account-setup")
api_v1_router.include_router(collection_router)

# 将来の拡張用エンドポイント
# api_v1_router.include_router(analytics_router)

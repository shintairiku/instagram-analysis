"""
Instagram Account Repository
Supabase (PostgREST) 経由で instagram_accounts を操作するデータアクセス層
"""
from typing import List, Optional
from datetime import datetime

from supabase import Client

from ..core.records import Record, to_record, to_records
from ..core.supabase_utils import get_data, get_single_data, prepare_record, raise_for_error


class InstagramAccountRepository:
    """Instagram アカウント専用リポジトリ"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    async def get_all(self) -> List[Record]:
        """全アカウント取得"""
        res = self.supabase.table("instagram_accounts").select("*").order("created_at", desc=False).execute()
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_active_accounts(self) -> List[Record]:
        """アクティブなアカウント取得"""
        res = (
            self.supabase.table("instagram_accounts")
            .select("*")
            .eq("is_active", True)
            .order("created_at", desc=False)
            .execute()
        )
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def get_by_id(self, account_id: str) -> Optional[Record]:
        """ID によるアカウント取得"""
        res = self.supabase.table("instagram_accounts").select("*").eq("id", account_id).limit(1).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_by_instagram_user_id(self, instagram_user_id: str) -> Optional[Record]:
        """Instagram User ID によるアカウント取得"""
        res = (
            self.supabase.table("instagram_accounts")
            .select("*")
            .eq("instagram_user_id", instagram_user_id)
            .limit(1)
            .execute()
        )
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def get_by_username(self, username: str) -> Optional[Record]:
        """ユーザーネームによるアカウント取得"""
        res = self.supabase.table("instagram_accounts").select("*").eq("username", username).limit(1).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def create(self, account_data: dict) -> Record:
        """新規アカウント作成"""
        res = self.supabase.table("instagram_accounts").insert(prepare_record(account_data)).execute()
        raise_for_error(res)
        return to_record(get_single_data(res)) or Record(account_data)
    
    async def update(self, account_id: str, account_data: dict) -> Optional[Record]:
        """アカウント情報更新"""
        # 更新時刻を設定
        account_data["updated_at"] = datetime.now().isoformat()
        res = self.supabase.table("instagram_accounts").update(prepare_record(account_data)).eq("id", account_id).execute()
        raise_for_error(res)
        return to_record(get_single_data(res))
    
    async def update_basic_info(
        self, 
        account_id: str, 
        username: str = None,
        account_name: str = None,
        profile_picture_url: str = None
    ) -> Optional[Record]:
        """基本情報の更新"""
        update_data: dict = {"updated_at": datetime.now().isoformat()}
        if username is not None:
            update_data["username"] = username
        if account_name is not None:
            update_data["account_name"] = account_name
        if profile_picture_url is not None:
            update_data["profile_picture_url"] = profile_picture_url
        return await self.update(account_id, update_data)
    
    async def update_token(
        self, 
        account_id: str, 
        access_token_encrypted: str,
        token_expires_at: datetime = None
    ) -> Optional[Record]:
        """アクセストークン更新"""
        update_data: dict = {
            "access_token_encrypted": access_token_encrypted,
            "updated_at": datetime.now().isoformat(),
        }
        if token_expires_at:
            update_data["token_expires_at"] = token_expires_at.isoformat()
        return await self.update(account_id, update_data)
    
    async def deactivate(self, account_id: str) -> Optional[Record]:
        """アカウント非アクティブ化"""
        return await self.update(account_id, {"is_active": False, "updated_at": datetime.now().isoformat()})
    
    async def activate(self, account_id: str) -> Optional[Record]:
        """アカウントアクティブ化"""
        return await self.update(account_id, {"is_active": True, "updated_at": datetime.now().isoformat()})
    
    async def delete(self, account_id: str) -> bool:
        """アカウント削除"""
        res = self.supabase.table("instagram_accounts").delete().eq("id", account_id).execute()
        raise_for_error(res)
        return bool(get_data(res))
    
    async def get_token_expiring_soon(self, days_threshold: int = 7) -> List[Record]:
        """トークン期限切れが近いアカウント取得"""
        from datetime import timedelta
        threshold_date = datetime.now() + timedelta(days=days_threshold)
        
        res = (
            self.supabase.table("instagram_accounts")
            .select("*")
            .eq("is_active", True)
            .lte("token_expires_at", threshold_date.isoformat())
            .execute()
        )
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def update_last_sync(self, account_id: str, sync_time: datetime) -> Optional[Record]:
        """最終同期時刻更新"""
        return await self.update(
            account_id,
            {
                "last_synced_at": sync_time.isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
        )
    
    async def update_collection_status(
        self, 
        account_id: str, 
        collection_success: bool,
        error_message: str = None
    ) -> Optional[Record]:
        """データ収集ステータス更新"""
        update_data = {"updated_at": datetime.now().isoformat()}
        if collection_success:
            update_data["last_synced_at"] = datetime.now().isoformat()
        return await self.update(account_id, update_data)
    
    async def get_accounts_for_collection(self, account_filter: Optional[List[str]] = None) -> List[Record]:
        """データ収集対象アカウント取得"""
        query = self.supabase.table("instagram_accounts").select("*").eq("is_active", True)
        if account_filter:
            query = query.in_("instagram_user_id", account_filter)
        res = query.execute()
        raise_for_error(res)
        return to_records(get_data(res))
    
    async def bulk_update_sync_status(self, account_ids: List[str], sync_time: datetime) -> int:
        """複数アカウントの同期ステータス一括更新"""
        if not account_ids:
            return 0
        update_data = {"last_synced_at": sync_time.isoformat(), "updated_at": datetime.now().isoformat()}
        res = self.supabase.table("instagram_accounts").update(update_data).in_("id", account_ids).execute()
        raise_for_error(res)
        return len(get_data(res))

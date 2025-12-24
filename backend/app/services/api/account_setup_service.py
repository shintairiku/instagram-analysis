"""
Account Setup Service
アカウントセットアップのビジネスロジック
"""
import logging
import requests
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from supabase import Client

from ...schemas.account_setup_schema import (
    AccountSetupRequest,
    AccountSetupResponse,
    DiscoveredAccount,
    TokenExchangeResult,
    FacebookPageInfo,
    InstagramAccountDetails
)
from ...schemas.instagram_account_schema import InstagramAccountResponse
from ...repositories.instagram_account_repository import InstagramAccountRepository

logger = logging.getLogger(__name__)


class AccountSetupService:
    """アカウントセットアップサービス"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.account_repository = InstagramAccountRepository(supabase)
    
    async def setup_accounts(self, request: AccountSetupRequest) -> AccountSetupResponse:
        """
        アカウントセットアップのメイン処理
        
        Args:
            request: セットアップリクエスト
            
        Returns:
            AccountSetupResponse: セットアップ結果
        """
        response = AccountSetupResponse(
            success=False,
            message="アカウントセットアップを開始します"
        )
        
        try:
            # Step 1: 短期トークンを長期トークンに変換
            logger.info("Step 1: Converting short token to long-term token")
            token_result = await self._exchange_token(
                request.app_id, 
                request.app_secret, 
                request.short_token
            )
            
            if not token_result.success:
                response.errors.append(f"長期トークン取得に失敗: {token_result.error_message}")
                return response
            
            # Step 2: Facebookページ一覧を取得
            logger.info("Step 2: Fetching Facebook pages")
            pages = await self._get_facebook_pages(token_result.long_term_token)
            
            if not pages:
                response.errors.append("Facebookページが見つかりませんでした")
                return response
            
            # Step 3: 各ページのInstagramアカウントを取得
            logger.info("Step 3: Fetching Instagram accounts for each page")
            discovered_accounts = []
            
            for page in pages:
                instagram_account = await self._get_instagram_account_for_page(page)
                if instagram_account:
                    # Instagramアカウントの詳細情報を取得（失敗してもフォールバック）
                    account_details = await self._get_instagram_account_details(
                        instagram_account, 
                        page.page_access_token
                    )
                    
                    # account_detailsは常に何らかの値を返すように修正済み
                    discovered_account = DiscoveredAccount(
                        instagram_user_id=account_details.instagram_user_id,
                        username=account_details.username or f"user_{instagram_account[-8:]}",
                        account_name=account_details.name or page.page_name,  # フォールバック
                        profile_picture_url=account_details.profile_picture_url,
                        facebook_page_id=page.page_id,
                        facebook_page_name=page.page_name,
                        access_token=page.page_access_token,
                        is_new=True  # 後で既存チェック
                    )
                    discovered_accounts.append(discovered_account)
                    logger.info(f"Successfully processed Instagram account {account_details.instagram_user_id} for page {page.page_name}")
            
            # Step 4: データベースに保存
            logger.info("Step 4: Saving accounts to database")
            created_accounts = []
            updated_count = 0
            
            for discovered in discovered_accounts:
                try:
                    # 既存アカウントチェック
                    existing_account = await self.account_repository.get_by_instagram_user_id(
                        discovered.instagram_user_id
                    )
                    
                    if existing_account:
                        # 既存アカウントを更新
                        discovered.is_new = False
                        await self._update_existing_account(existing_account, discovered, token_result)
                        updated_count += 1
                        response.warnings.append(
                            f"既存のアカウント @{discovered.username} を更新しました"
                        )
                    else:
                        # 新規アカウントを作成
                        new_account = await self._create_new_account(discovered, token_result)
                        if new_account:
                            created_accounts.append(new_account)
                        
                except Exception as e:
                    logger.error(f"Failed to save account {discovered.username}: {str(e)}")
                    response.errors.append(
                        f"アカウント @{discovered.username} の保存に失敗: {str(e)}"
                    )
            
            # 結果をまとめる
            response.success = len(discovered_accounts) > 0
            response.accounts_discovered = len(discovered_accounts)
            response.accounts_created = len(created_accounts)
            response.accounts_updated = updated_count
            response.discovered_accounts = discovered_accounts
            response.created_accounts = created_accounts
            
            if response.success:
                response.message = f"セットアップ完了: {response.accounts_discovered}個のアカウントを発見し、{response.accounts_created}個を新規作成、{response.accounts_updated}個を更新しました"
                if len(pages) > len(discovered_accounts):
                    response.warnings.append(f"{len(pages) - len(discovered_accounts)}個のFacebookページにはInstagramアカウントが接続されていませんでした")
            else:
                response.message = f"Instagramアカウントが見つかりませんでした。{len(pages)}個のFacebookページを確認しましたが、Instagram Business アカウントに接続されているページがありませんでした。"
            
            return response
            
        except Exception as e:
            logger.error(f"Account setup failed: {str(e)}", exc_info=True)
            response.errors.append(f"セットアップ中にエラーが発生しました: {str(e)}")
            return response
    
    async def _exchange_token(self, app_id: str, app_secret: str, short_token: str) -> TokenExchangeResult:
        """短期トークンを長期トークンに変換"""
        url = "https://graph.facebook.com/v21.0/oauth/access_token"
        
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'fb_exchange_token': short_token
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(f"Token exchange response: {data}")
            expires_in = data.get('expires_in')
            if expires_in:
                logger.info(f"Long-term token expires in {expires_in} seconds ({expires_in/86400:.1f} days)")
            else:
                logger.info("Long-term token does not have expiration time (permanent token)")
            
            return TokenExchangeResult(
                success=True,
                long_term_token=data.get('access_token'),
                expires_in=expires_in
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Token exchange failed: {str(e)}")
            return TokenExchangeResult(
                success=False,
                error_message=f"トークン交換に失敗: {str(e)}"
            )
    
    async def _get_facebook_pages(self, access_token: str) -> List[FacebookPageInfo]:
        """Facebookページ一覧を取得（ページネーション対応）"""
        url = "https://graph.facebook.com/v21.0/me/accounts"
        
        params = {
            'access_token': access_token,
            'fields': 'id,name,access_token,category,category_list',
            'limit': 100  # 一度に取得する最大件数
        }
        
        pages = []
        page_count = 0
        
        try:
            while url:
                page_count += 1
                logger.info(f"Fetching Facebook pages - page {page_count}")
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                current_pages = data.get('data', [])
                
                logger.info(f"Retrieved {len(current_pages)} pages in batch {page_count}")
                
                # 現在のページのデータを処理
                for page_data in current_pages:
                    page = FacebookPageInfo(
                        page_id=page_data['id'],
                        page_name=page_data['name'],
                        page_access_token=page_data['access_token'],
                        category=page_data.get('category')
                    )
                    pages.append(page)
                
                # 次のページのURLを取得
                paging = data.get('paging', {})
                url = paging.get('next')
                if url:
                    # 次のリクエストではparamsをクリア（URLに含まれるため）
                    params = {}
                    logger.info(f"Found next page, continuing pagination...")
                else:
                    logger.info(f"No more pages, pagination complete")
            
            logger.info(f"Total Facebook pages retrieved: {len(pages)}")
            return pages
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Facebook pages: {str(e)}")
            return []
    
    async def _get_instagram_account_for_page(self, page: FacebookPageInfo) -> Optional[str]:
        """ページに接続されているInstagramアカウントIDを取得"""
        url = f"https://graph.facebook.com/v21.0/{page.page_id}"
        
        params = {
            'access_token': page.page_access_token,
            'fields': 'instagram_business_account'
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            instagram_account = data.get('instagram_business_account')
            
            if instagram_account:
                return instagram_account['id']
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Instagram account for page {page.page_id}: {str(e)}")
            return None
    
    async def _get_instagram_account_details(self, instagram_account_id: str, access_token: str) -> InstagramAccountDetails:
        """Instagramアカウントの詳細情報を取得（フォールバック機能付き）"""
        url = f"https://graph.facebook.com/v21.0/{instagram_account_id}"
        
        # 段階的にフィールドを減らして試行（詳細なものから基本的なものへ）
        field_sets = [
            'id,username,name,profile_picture_url,biography,followers_count,media_count',  # 最も詳細
            'id,username,name,profile_picture_url,biography,followers_count',  # より詳細
            'id,username,name,profile_picture_url,biography',  # さらに詳細
            'id,username,name,profile_picture_url',  # 基本情報
            'id,username,name',  # ID + ユーザー名 + 表示名  
            'id,username',  # ID + ユーザー名
            'id',  # 最小限（IDのみ）
        ]
        
        for i, fields in enumerate(field_sets):
            params = {
                'access_token': access_token,
                'fields': fields
            }
            
            try:
                logger.info(f"Trying to get Instagram account {instagram_account_id} with fields: {fields}")
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Successfully got Instagram account details for {instagram_account_id} with fields: {fields}")
                
                # 成功した場合、取得できたデータでInstagramAccountDetailsを作成
                return InstagramAccountDetails(
                    instagram_user_id=data.get('id', instagram_account_id),
                    username=data.get('username', f"user_{instagram_account_id[-8:]}"),
                    name=data.get('name'),
                    profile_picture_url=data.get('profile_picture_url'),
                    biography=None,  # 基本フィールドには含めない
                    website=None,
                    followers_count=None,
                    media_count=None,
                    account_type=None
                )
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to get Instagram account details for {instagram_account_id} with fields '{fields}': {str(e)}")
                if i == len(field_sets) - 1:  # 最後の試行の場合
                    logger.warning(f"All API attempts failed for {instagram_account_id}, using fallback data")
                continue
        
        # すべて失敗した場合、最小限の情報で作成
        logger.warning(f"Using minimal fallback data for Instagram account {instagram_account_id}")
        return InstagramAccountDetails(
            instagram_user_id=instagram_account_id,
            username=f"user_{instagram_account_id[-8:]}",  # IDの末尾8桁を使用
            name=None,
            profile_picture_url=None,
            biography=None,
            website=None,
            followers_count=None,
            media_count=None,
            account_type=None
        )
    
    async def _create_new_account(self, discovered: DiscoveredAccount, token_result: TokenExchangeResult) -> Optional[InstagramAccountResponse]:
        """新規アカウントを作成"""
        try:
            # トークン有効期限を計算
            token_expires_at = None
            if token_result.expires_in:
                token_expires_at = datetime.now() + timedelta(seconds=token_result.expires_in)
                logger.info(f"Token expires in {token_result.expires_in} seconds, expires at: {token_expires_at}")
            else:
                # 長期トークンのデフォルト有効期限（60日）
                token_expires_at = datetime.now() + timedelta(days=60)
                logger.info(f"Using default 60-day expiration: {token_expires_at}")
            
            # 辞書形式でデータを準備
            account_data = {
                'instagram_user_id': discovered.instagram_user_id,
                'username': discovered.username,
                'account_name': discovered.account_name,
                'profile_picture_url': discovered.profile_picture_url,
                'access_token_encrypted': discovered.access_token,  # 暗号化は未実装
                'token_expires_at': token_expires_at,
                'facebook_page_id': discovered.facebook_page_id,
                'is_active': True
            }
            
            created_account = await self.account_repository.create(account_data)
            
            # レスポンス用にマッピング
            return InstagramAccountResponse(
                id=created_account.get("id"),
                instagram_user_id=created_account.get("instagram_user_id"),
                username=created_account.get("username"),
                account_name=created_account.get("account_name"),
                profile_picture_url=created_account.get("profile_picture_url"),
                facebook_page_id=created_account.get("facebook_page_id"),
                is_active=created_account.get("is_active", True),
                token_expires_at=created_account.get("token_expires_at"),
                created_at=created_account.get("created_at"),
                updated_at=created_account.get("updated_at"),
                is_token_valid=True,
                days_until_expiry=(token_expires_at - datetime.now()).days if token_expires_at else None
            )
            
        except Exception as e:
            logger.error(f"Error creating account {discovered.username}: {str(e)}")
            return None
    
    async def _update_existing_account(self, existing_account: dict, discovered: DiscoveredAccount, token_result: TokenExchangeResult) -> None:
        """既存アカウントを更新"""
        try:
            # トークン有効期限を計算
            token_expires_at = None
            if token_result.expires_in:
                token_expires_at = datetime.now() + timedelta(seconds=token_result.expires_in)
                logger.info(f"Updating existing account with token expires in {token_result.expires_in} seconds")
            else:
                # 長期トークンのデフォルト有効期限（60日）
                token_expires_at = datetime.now() + timedelta(days=60)
                logger.info(f"Updating existing account with default 60-day expiration")
            
            update_data = {
                "username": discovered.username,
                "account_name": discovered.account_name,
                "profile_picture_url": discovered.profile_picture_url,
                "access_token_encrypted": discovered.access_token,
                "token_expires_at": token_expires_at,
                "facebook_page_id": discovered.facebook_page_id,
                "is_active": True,
            }
            await self.account_repository.update(str(existing_account.get("id")), update_data)
            
        except Exception as e:
            logger.error(f"Error updating account {discovered.username}: {str(e)}")
            raise


def create_account_setup_service(db: Client) -> AccountSetupService:
    """アカウントセットアップサービスのファクトリ"""
    return AccountSetupService(db)

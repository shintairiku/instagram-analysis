"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { InstagramAccount, AccountContextValue, AccountSummary, TokenWarningLevel } from '../types/account';
import { accountApi } from '../services/accountApi';

// Context作成
const AccountContext = createContext<AccountContextValue | undefined>(undefined);

// Provider Props
interface AccountProviderProps {
  children: ReactNode;
  defaultAccountId?: string;  // 初期選択アカウント（Instagram User ID）
}

// Local Storage Keys
const STORAGE_KEYS = {
  SELECTED_ACCOUNT: 'instagram_analysis_selected_account',
  ACCOUNTS_CACHE: 'instagram_analysis_accounts_cache',
  CACHE_TIMESTAMP: 'instagram_analysis_cache_timestamp',
} as const;

// キャッシュ時間（5分）
const CACHE_DURATION = 5 * 60 * 1000;

export function AccountProvider({ children, defaultAccountId }: AccountProviderProps) {
  const [selectedAccount, setSelectedAccount] = useState<InstagramAccount | null>(null);
  const [accounts, setAccounts] = useState<InstagramAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // アカウント一覧のキャッシュ確認
  const isValidCache = useCallback((): boolean => {
    try {
      if (typeof window === 'undefined') return false;
      
      const cacheTimestamp = localStorage.getItem(STORAGE_KEYS.CACHE_TIMESTAMP);
      if (!cacheTimestamp) return false;
      
      const now = Date.now();
      const cached = parseInt(cacheTimestamp, 10);
      
      return (now - cached) < CACHE_DURATION;
    } catch {
      return false;
    }
  }, []);


  // アカウント一覧をキャッシュに保存
  const saveToCache = useCallback((accounts: InstagramAccount[]): void => {
    try {
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEYS.ACCOUNTS_CACHE, JSON.stringify(accounts));
        localStorage.setItem(STORAGE_KEYS.CACHE_TIMESTAMP, Date.now().toString());
      }
    } catch (error) {
      console.warn('Failed to save accounts to cache:', error);
    }
  }, []);

  // 選択アカウントをLocal Storageに保存
  const saveSelectedAccount = useCallback((account: InstagramAccount | null): void => {
    try {
      if (account) {
        localStorage.setItem(STORAGE_KEYS.SELECTED_ACCOUNT, account.instagram_user_id);
      } else {
        localStorage.removeItem(STORAGE_KEYS.SELECTED_ACCOUNT);
      }
    } catch (error) {
      console.warn('Failed to save selected account:', error);
    }
  }, []);

  // 選択アカウントをLocal Storageから復元
  const loadSelectedAccount = useCallback((accounts: InstagramAccount[]): InstagramAccount | null => {
    try {
      // デフォルトアカウントIDが指定されている場合
      if (defaultAccountId) {
        const account = accounts.find(acc => acc.instagram_user_id === defaultAccountId);
        if (account) return account;
      }
      
      // Local Storageから復元
      const savedAccountId = localStorage.getItem(STORAGE_KEYS.SELECTED_ACCOUNT);
      if (savedAccountId) {
        const account = accounts.find(acc => acc.instagram_user_id === savedAccountId);
        if (account) return account;
      }
      
      // フォールバック：最初のアクティブアカウント
      const activeAccount = accounts.find(acc => acc.is_active);
      return activeAccount || accounts[0] || null;
    } catch (error) {
      console.warn('Failed to load selected account:', error);
      return accounts[0] || null;
    }
  }, [defaultAccountId]);

  // アカウント一覧を取得
  const refreshAccounts = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      console.log('Fetching accounts from API...');
      
      const response = await accountApi.getAccounts({
        active_only: false,
        include_metrics: true,
      });

      setAccounts(response.accounts);
      saveToCache(response.accounts);

      // 選択アカウントの設定（現在の値を参照するためstateのコールバック形式を使用）
      setSelectedAccount(currentSelected => {
        if (!currentSelected) {
          const newSelectedAccount = loadSelectedAccount(response.accounts);
          saveSelectedAccount(newSelectedAccount);
          return newSelectedAccount;
        }

        const updatedSelected = response.accounts.find(acc => acc.id === currentSelected.id);
        if (updatedSelected) {
          return updatedSelected;
        }

        const fallbackSelected = loadSelectedAccount(response.accounts);
        saveSelectedAccount(fallbackSelected);
        return fallbackSelected;
      });

      console.log(`Successfully loaded ${response.accounts.length} accounts`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch accounts';
      setError(errorMessage);
      console.error('Failed to refresh accounts:', err);
    } finally {
      setLoading(false);
    }
  }, [loadSelectedAccount, saveToCache, saveSelectedAccount]);

  // アカウント選択
  const selectAccount = useCallback((account: InstagramAccount): void => {
    setSelectedAccount(account);
    saveSelectedAccount(account);
    console.log('Selected account:', account.username);
  }, [saveSelectedAccount]);

  // エラークリア
  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  // IDでアカウント取得
  const getAccountById = useCallback((id: string): InstagramAccount | undefined => {
    return accounts.find(account => account.id === id || account.instagram_user_id === id);
  }, [accounts]);

  // 有効なアカウント取得
  const getValidAccounts = useCallback((): InstagramAccount[] => {
    return accounts.filter(account => account.is_active && account.is_token_valid);
  }, [accounts]);

  // アカウントサマリー作成
  const getAccountSummary = useCallback((account: InstagramAccount): AccountSummary => {
    // プロフィール画像のフォールバック
    const getAvatarUrl = (url?: string): string => {
      const placeholder = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTYiIGN5PSIxNiIgcj0iMTYiIGZpbGw9IiNGM0Y0RjYiLz4KPHBhdGggZD0iTTggMjRDOCAyMC42ODYzIDEwLjY4NjMgMTggMTQgMThIMTRDMTcuMzEzNyAxOCAyMCAyMC42ODYzIDIwIDI0VjI0SDhWMjRaIiBmaWxsPSIjOUNBM0FGIi8+CjxjaXJjbGUgY3g9IjE2IiBjeT0iMTIiIHI9IjQiIGZpbGw9IiM5Q0EzQUYiLz4KPC9zdmc+Cg==';
      
      if (!url || url.includes('example.com')) {
        return placeholder;
      }
      
      return url;
    };

    // 警告レベル計算
    const getTokenWarning = (): TokenWarningLevel => {
      if (!account.is_token_valid) return 'expired';
      if (account.days_until_expiry === undefined) return 'none';
      if (account.days_until_expiry <= 1) return 'critical';
      if (account.days_until_expiry <= 7) return 'warning';
      return 'none';
    };

    return {
      id: account.id,
      username: account.username,
      displayName: account.account_name || account.username,
      avatar: getAvatarUrl(account.profile_picture_url),
      isActive: account.is_active,
      tokenWarning: getTokenWarning(),
      daysUntilExpiry: account.days_until_expiry,
    };
  }, []);

  // 初期化
  useEffect(() => {
    const initializeAccounts = async () => {
      // キャッシュから読み込み試行
      const isCache = isValidCache();
      let cachedAccounts: InstagramAccount[] | null = null;
      
      if (isCache) {
        try {
          const cachedData = localStorage.getItem(STORAGE_KEYS.ACCOUNTS_CACHE);
          if (cachedData) {
            cachedAccounts = JSON.parse(cachedData) as InstagramAccount[];
            console.log('Loaded accounts from cache:', cachedAccounts.length);
          }
        } catch (error) {
          console.warn('Failed to load accounts from cache:', error);
        }
      }
      
      if (cachedAccounts && cachedAccounts.length > 0) {
        setAccounts(cachedAccounts);
        
        // 選択アカウントの復元
        let selectedAcc: InstagramAccount | null = null;
        try {
          if (defaultAccountId) {
            selectedAcc = cachedAccounts.find(acc => acc.instagram_user_id === defaultAccountId) || null;
          }
          if (!selectedAcc) {
            const savedAccountId = localStorage.getItem(STORAGE_KEYS.SELECTED_ACCOUNT);
            if (savedAccountId) {
              selectedAcc = cachedAccounts.find(acc => acc.instagram_user_id === savedAccountId) || null;
            }
          }
          if (!selectedAcc) {
            selectedAcc = cachedAccounts.find(acc => acc.is_active) || cachedAccounts[0] || null;
          }
        } catch (error) {
          console.warn('Failed to load selected account:', error);
          selectedAcc = cachedAccounts[0] || null;
        }
        
        setSelectedAccount(selectedAcc);
        console.log('Initialized with cached accounts');
        
        // バックグラウンドで更新
        setTimeout(async () => {
          try {
            const response = await accountApi.getAccounts({
              active_only: false,
              include_metrics: true,
            });
            setAccounts(response.accounts);
            saveToCache(response.accounts);
            setSelectedAccount(currentSelected => {
              if (!currentSelected) return loadSelectedAccount(response.accounts);
              return response.accounts.find(acc => acc.id === currentSelected.id) || currentSelected;
            });
          } catch (error) {
            console.error('Background refresh failed:', error);
          }
        }, 100);
      } else {
        // キャッシュなしの場合は即座に取得
        setLoading(true);
        setError(null);
        try {
          const response = await accountApi.getAccounts({
            active_only: false,
            include_metrics: true,
          });
          setAccounts(response.accounts);
          saveToCache(response.accounts);
          
          // 選択アカウントの設定
          let selectedAcc: InstagramAccount | null = null;
          if (defaultAccountId) {
            selectedAcc = response.accounts.find(acc => acc.instagram_user_id === defaultAccountId) || null;
          }
          if (!selectedAcc) {
            const savedAccountId = localStorage.getItem(STORAGE_KEYS.SELECTED_ACCOUNT);
            if (savedAccountId) {
              selectedAcc = response.accounts.find(acc => acc.instagram_user_id === savedAccountId) || null;
            }
          }
          if (!selectedAcc) {
            selectedAcc = response.accounts.find(acc => acc.is_active) || response.accounts[0] || null;
          }
          
          setSelectedAccount(selectedAcc);
          if (selectedAcc) {
            saveSelectedAccount(selectedAcc);
          }
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to fetch accounts';
          setError(errorMessage);
          console.error('Failed to initialize accounts:', err);
        } finally {
          setLoading(false);
        }
      }
    };

    initializeAccounts();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 初回のみ実行（依存関係を意図的に無視）

  // Context値
  const contextValue: AccountContextValue = {
    selectedAccount,
    accounts,
    loading,
    error,
    selectAccount,
    refreshAccounts,
    clearError,
    getAccountById,
    getValidAccounts,
    getAccountSummary,
  };

  return (
    <AccountContext.Provider value={contextValue}>
      {children}
    </AccountContext.Provider>
  );
}

// Context Hook
export function useAccountContext(): AccountContextValue {
  const context = useContext(AccountContext);
  if (context === undefined) {
    throw new Error('useAccountContext must be used within an AccountProvider');
  }
  return context;
}

// デフォルトエクスポート
export default AccountContext;

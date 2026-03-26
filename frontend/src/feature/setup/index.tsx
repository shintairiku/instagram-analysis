"use client";

import { useState, useEffect, useCallback } from "react";
import { SetupForm } from "./components/SetupForm";
import { AccountTable } from "./components/AccountTable";
import { setupApi } from "./services/setupApi";
import {
  SetupFormData,
  SetupFormErrors,
  SetupStatus,
  AccountTableRow,
  CreatedAccount,
} from "./types/setup";

export default function Setup() {
  const [status, setStatus] = useState<SetupStatus>('idle');
  const [errors, setErrors] = useState<SetupFormErrors>({});
  const [accounts, setAccounts] = useState<AccountTableRow[]>([]);
  const [loading, setLoading] = useState(false);

  const loadAccounts = useCallback(async () => {
    try {
      setLoading(true);
      const response = await setupApi.getAccounts(true);
      const mappedAccounts: AccountTableRow[] = response.accounts.map(transformAccountToTableRow);
      setAccounts(mappedAccounts);
    } catch (error) {
      console.error('Failed to load accounts:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // 初期データ読み込み
  useEffect(() => {
    const loadAccountsOnMount = async () => {
      try {
        setLoading(true);
        const response = await setupApi.getAccounts(true);
        const mappedAccounts: AccountTableRow[] = response.accounts.map(transformAccountToTableRow);
        setAccounts(mappedAccounts);
      } catch (error) {
        console.error('Failed to load accounts:', error);
      } finally {
        setLoading(false);
      }
    };
    
    loadAccountsOnMount();
  }, []); // 依存配列を空にして無限ループを防ぐ

  const transformAccountToTableRow = (account: CreatedAccount): AccountTableRow => {
    // トークン状態を判定
    let tokenStatus: 'valid' | 'warning' | 'expired' = 'valid';
    if (!account.is_token_valid) {
      tokenStatus = 'expired';
    } else if (account.days_until_expiry !== undefined && account.days_until_expiry <= 7) {
      tokenStatus = 'warning';
    }

    return {
      id: account.id,
      instagram_user_id: account.instagram_user_id,
      username: account.username,
      account_name: account.account_name,
      profile_picture_url: account.profile_picture_url,
      facebook_page_id: account.facebook_page_id,
      is_active: account.is_active,
      token_status: tokenStatus,
      days_until_expiry: account.days_until_expiry,
      created_at: account.created_at,
    };
  };

  const validateForm = (data: SetupFormData): SetupFormErrors => {
    const newErrors: SetupFormErrors = {};

    // App ID validation
    if (!data.app_id) {
      newErrors.app_id = 'App IDは必須です';
    } else if (!data.app_id.match(/^\d+$/)) {
      newErrors.app_id = 'App IDは数値である必要があります';
    }

    // App Secret validation
    if (!data.app_secret) {
      newErrors.app_secret = 'App Secretは必須です';
    } else if (data.app_secret.length < 16) {
      newErrors.app_secret = 'App Secretは16文字以上である必要があります';
    }

    // Short Token validation
    if (!data.short_token) {
      newErrors.short_token = '短期トークンは必須です';
    } else if (data.short_token.length < 50) {
      newErrors.short_token = '短期トークンが短すぎます';
    } else if (!data.short_token.startsWith('EAA')) {
      newErrors.short_token = '短期トークンはEAAで始まる必要があります';
    }

    return newErrors;
  };

  const handleFormSubmit = async (data: SetupFormData) => {
    try {
      // フォームバリデーション
      const formErrors = validateForm(data);
      if (Object.keys(formErrors).length > 0) {
        setErrors(formErrors);
        return;
      }

      setStatus('loading');
      setErrors({});

      // アカウントセットアップAPI呼び出し
      const response = await setupApi.setupAccounts(data);

      if (response.success) {
        setStatus('success');
        
        // 成功メッセージを表示（少し後に消す）
        setTimeout(() => {
          if (status === 'success') {
            setStatus('idle');
          }
        }, 3000);

        // アカウント一覧を再読み込み
        await loadAccounts();

        // エラーまたは警告がある場合は表示
        if (response.errors.length > 0) {
          setErrors({
            general: `セットアップ完了（一部エラーあり）: ${response.errors.join(', ')}`
          });
        } else if (response.warnings.length > 0) {
          setErrors({
            general: `セットアップ完了（警告あり）: ${response.warnings.join(', ')}`
          });
        }
      } else {
        setStatus('error');
        setErrors({
          general: response.message || 'アカウントセットアップに失敗しました'
        });

        if (response.errors.length > 0) {
          setErrors(prev => ({
            ...prev,
            general: response.errors.join(', ')
          }));
        }
      }
    } catch (error) {
      setStatus('error');
      setErrors({
        general: error instanceof Error ? error.message : 'ネットワークエラーが発生しました'
      });
    }
  };

  const handleRefresh = async () => {
    await loadAccounts();
  };

  return (
    <div className="h-full min-h-0 overflow-y-auto overflow-x-hidden p-4 md:p-6">
      {/* ヘッダー */}
      <div className="border-b pb-4">
        <h1 className="text-3xl font-bold">Instagram アカウントセットアップ</h1>
        <p className="text-muted-foreground mt-2">
          Instagram App の認証情報を使用してアカウントを自動登録し、データ収集の準備を行います
        </p>
      </div>

      {/* メインコンテンツ - 2カラムレイアウト */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 左カラム: セットアップフォーム */}
        <div className="min-w-0 space-y-4">
          <SetupForm
            onSubmit={handleFormSubmit}
            status={status}
            errors={errors}
          />
        </div>

        {/* 右カラム: アカウント一覧テーブル */}
        <div className="min-w-0 space-y-4">
          <AccountTable
            accounts={accounts}
            loading={loading}
            onRefresh={handleRefresh}
          />
        </div>
      </div>

    </div>
  );
}

"use client";

import { useState } from "react";
import { RefreshCw, CheckCircle, AlertTriangle, XCircle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { AccountTableRow } from "../types/setup";

interface AccountTableProps {
  accounts: AccountTableRow[];
  loading: boolean;
  onRefresh: () => void;
}

export function AccountTable({ accounts, loading, onRefresh }: AccountTableProps) {
  const [sortBy, setSortBy] = useState<keyof AccountTableRow>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const handleSort = (field: keyof AccountTableRow) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  const sortedAccounts = [...accounts].sort((a, b) => {
    const aValue = a[sortBy];
    const bValue = b[sortBy];
    
    if (aValue == null && bValue == null) return 0;
    if (aValue == null) return 1;
    if (bValue == null) return -1;
    
    let comparison = 0;
    if (typeof aValue === 'string' && typeof bValue === 'string') {
      comparison = aValue.localeCompare(bValue);
    } else if (typeof aValue === 'number' && typeof bValue === 'number') {
      comparison = aValue - bValue;
    } else {
      comparison = String(aValue).localeCompare(String(bValue));
    }
    
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  const getTokenStatusBadge = (tokenStatus: string, daysUntilExpiry?: number) => {
    switch (tokenStatus) {
      case 'valid':
        return (
          <Badge variant="outline" className="text-green-700 border-green-300 bg-green-50">
            <CheckCircle className="mr-1 h-3 w-3" />
            有効
            {daysUntilExpiry && ` (${daysUntilExpiry}日)`}
          </Badge>
        );
      case 'warning':
        return (
          <Badge variant="outline" className="text-orange-700 border-orange-300 bg-orange-50">
            <AlertTriangle className="mr-1 h-3 w-3" />
            警告
            {daysUntilExpiry && ` (${daysUntilExpiry}日)`}
          </Badge>
        );
      case 'expired':
        return (
          <Badge variant="outline" className="text-red-700 border-red-300 bg-red-50">
            <XCircle className="mr-1 h-3 w-3" />
            期限切れ
          </Badge>
        );
      default:
        return (
          <Badge variant="outline">
            不明
          </Badge>
        );
    }
  };

  const getActiveStatusBadge = (isActive: boolean) => {
    return isActive ? (
      <Badge variant="outline" className="text-green-700 border-green-300 bg-green-50">
        アクティブ
      </Badge>
    ) : (
      <Badge variant="outline" className="text-gray-700 border-gray-300 bg-gray-50">
        非アクティブ
      </Badge>
    );
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ja-JP', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              📊 登録済みアカウント一覧
            </CardTitle>
            <CardDescription>
              セットアップで登録されたInstagramアカウントの一覧です
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={loading}
          >
            {loading ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            更新
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {accounts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <div className="text-6xl mb-4">📭</div>
            <h3 className="text-lg font-medium mb-2">アカウントが登録されていません</h3>
            <p className="text-sm text-center">
              左側のフォームから Instagram App ID、App Secret、短期トークンを入力して<br />
              アカウントを自動登録してください
            </p>
          </div>
        ) : (
          <>
            {/* 統計サマリー */}
            <div className="mb-4 flex flex-wrap gap-4 text-sm text-muted-foreground">
              <span>📈 取得済み: <strong>{accounts.length}</strong>件</span>
              <span>✅ アクティブ: <strong>{accounts.filter(a => a.is_active).length}</strong>件</span>
              <span>⚠️ 要注意: <strong>{accounts.filter(a => a.token_status === 'warning').length}</strong>件</span>
            </div>

            {/* テーブル */}
            <div className="overflow-hidden rounded-md border">
              <Table className="min-w-[940px]">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[300px]">アカウント</TableHead>
                    <TableHead 
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('facebook_page_id')}
                    >
                      Facebook Page ID
                    </TableHead>
                    <TableHead>ステータス</TableHead>
                    <TableHead>トークン状態</TableHead>
                    <TableHead 
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('created_at')}
                    >
                      登録日時
                    </TableHead>
                    <TableHead className="w-[100px]">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedAccounts.map((account) => (
                    <TableRow key={account.id}>
                      <TableCell>
                        <div className="flex min-w-0 items-center gap-3">
                          <Avatar className="h-10 w-10">
                            <AvatarImage 
                              src={account.profile_picture_url} 
                              alt={`@${account.username}`}
                            />
                            <AvatarFallback>
                              {account.username.slice(0, 2).toUpperCase()}
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0">
                            <div className="font-medium">@{account.username}</div>
                            {account.account_name && (
                              <div className="truncate text-sm text-muted-foreground">
                                {account.account_name}
                              </div>
                            )}
                            <div className="truncate font-mono text-xs text-muted-foreground">
                              ID: {account.instagram_user_id}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="font-mono text-xs">
                          {account.facebook_page_id}
                        </div>
                      </TableCell>
                      <TableCell>
                        {getActiveStatusBadge(account.is_active)}
                      </TableCell>
                      <TableCell>
                        {getTokenStatusBadge(account.token_status, account.days_until_expiry)}
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          {formatDate(account.created_at)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm" asChild>
                          <a
                            href={`https://www.instagram.com/${account.username}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`@${account.username} をInstagramで開く`}
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

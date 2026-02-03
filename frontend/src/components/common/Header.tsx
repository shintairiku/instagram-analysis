"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  ChevronDown,
  Check,
  Download,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { exportToPDF } from "@/lib/pdfExport";
import { useAccount } from "@/hooks/useAccount";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function Header() {
  const {
    selectedAccount,
    accounts,
    loading,
    error,
    selectAccount,
    refreshAccounts,
    clearError,
    getAccountSummary,
  } = useAccount();

  const [isOpen, setIsOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [accountSearch, setAccountSearch] = useState("");

  const handleAccountSelect = (accountId: string) => {
    selectAccount(accountId);
    setIsOpen(false);
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportToPDF();
    } finally {
      setIsExporting(false);
    }
  };

  const handleRefresh = async () => {
    clearError();
    await refreshAccounts();
  };

  const normalizedQuery = accountSearch.trim().toLowerCase().normalize("NFKC");
  const filteredAccounts = normalizedQuery
    ? accounts.filter((account) => {
        const username = account.username.toLowerCase().normalize("NFKC");
        const usernameWithAt = `@${account.username}`.toLowerCase().normalize("NFKC");
        const accountName = (account.account_name ?? "").toLowerCase().normalize("NFKC");

        return (
          username.includes(normalizedQuery) ||
          usernameWithAt.includes(normalizedQuery) ||
          accountName.includes(normalizedQuery)
        );
      })
    : accounts;

  return (
    <header className="flex justify-between items-center p-4 border-b" style={{ backgroundColor: '#c0b487', color: '#ffffff' }}>
      <nav className="flex items-center gap-2">
        {/* <Button variant="ghost" asChild>
          <Link href="/">ホーム</Link>
        </Button> */}
        {/* <Button variant="outline" asChild className="border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white">
          <Link href="/yearly-insight">年間分析</Link>
        </Button> */}
        {/* <Button variant="ghost" asChild>
          <Link href="/media-type-insight">メディアタイプ分析</Link>
        </Button> */}
        {/* <Button variant="outline" asChild className="border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white">
          <Link href="/monthly-insight">月間分析</Link>
        </Button> */}
        <Button variant="outline" asChild className="border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white">
          <Link href="/post_insight">投稿分析</Link>
        </Button>
      </nav>
      <div className="flex items-center gap-2">
        <Button 
          variant="outline" 
          size="sm"
          onClick={handleExport}
          disabled={isExporting}
          className="border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white"
        >
          <Download className="h-4 w-4 mr-2" />
          {isExporting ? 'エクスポート中...' : 'PDF エクスポート'}
        </Button>
        <Popover
          open={isOpen}
          onOpenChange={(open) => {
            setIsOpen(open);
            if (!open) setAccountSearch("");
          }}
        >
            <PopoverTrigger asChild>
            <Button 
                variant="outline" 
                className="flex items-center gap-2 h-10 px-3 border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white"
                disabled={loading && !selectedAccount}
            >
                {loading && !selectedAccount ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="font-medium">読み込み中...</span>
                  </>
                ) : selectedAccount ? (
                  <>
                    <Avatar className="w-6 h-6">
                      <AvatarImage 
                        src={getAccountSummary(selectedAccount).avatar} 
                        alt={getAccountSummary(selectedAccount).displayName} 
                      />
                      <AvatarFallback>
                        {getAccountSummary(selectedAccount).displayName.charAt(0).toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex flex-col items-start">
                      <span className="font-medium text-sm">@{selectedAccount.username}</span>
                      {/* トークン警告表示 */}
                      {getAccountSummary(selectedAccount).tokenWarning !== 'none' && (
                        <div className="flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3 text-orange-500" />
                          <span className="text-xs text-orange-600">
                            {getAccountSummary(selectedAccount).tokenWarning === 'expired' ? '期限切れ' :
                             getAccountSummary(selectedAccount).tokenWarning === 'critical' ? '期限間近' :
                             '要注意'}
                          </span>
                        </div>
                      )}
                    </div>
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  </>
                ) : (
                  <>
                    <Avatar className="w-6 h-6">
                      <AvatarFallback>?</AvatarFallback>
                    </Avatar>
                    <span className="font-medium">アカウント未選択</span>
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  </>
                )}
            </Button>
            </PopoverTrigger>
            <PopoverContent className="w-80 p-2" align="start">
                <ScrollArea className="h-[80vh]">
                <div className="space-y-1">
                    <div className="flex items-center justify-between px-2 py-1.5">
                    <span className="text-sm font-medium text-muted-foreground">
                        アカウントを選択
                    </span>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleRefresh}
                        disabled={loading}
                        className="h-6 w-6 p-0"
                    >
                        <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    </div>
                    
                    {/* エラー表示 */}
                    {error && (
                    <Alert variant="destructive" className="mx-2 mb-2">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertDescription className="text-xs">
                        {error}
                        </AlertDescription>
                    </Alert>
                    )}
                    
                    {/* 検索 */}
                    <div className="px-2 pb-2">
                      <div className="relative">
                        <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          value={accountSearch}
                          onChange={(e) => setAccountSearch(e.target.value)}
                          placeholder="会社名 / @アカウント名で検索"
                          className="h-8 pl-8 pr-8 text-sm"
                          autoFocus
                        />
                        {accountSearch.trim().length > 0 && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="absolute right-1 top-1/2 h-6 w-6 -translate-y-1/2 p-0"
                            onClick={() => setAccountSearch("")}
                            aria-label="検索をクリア"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* アカウント一覧 */}
                    {filteredAccounts.length === 0 && !loading ? (
                    <div className="px-2 py-4 text-center text-sm text-muted-foreground">
                        {accounts.length === 0
                          ? "アカウントが見つかりません"
                          : "一致するアカウントがありません"}
                    </div>
                    ) : (
                    filteredAccounts.map((account) => {
                        const summary = getAccountSummary(account);
                        return (
                        <Button
                            key={account.id}
                            variant="ghost"
                            className="w-full justify-start h-auto p-2"
                            onClick={() => handleAccountSelect(account.id)}
                        >
                            <div className="flex items-center gap-3 w-full">
                            <Avatar className="w-8 h-8">
                                <AvatarImage src={summary.avatar} alt={summary.displayName} />
                                <AvatarFallback>
                                {summary.displayName.charAt(0).toUpperCase()}
                                </AvatarFallback>
                            </Avatar>
                            <div className="flex-1 text-left">
                                <div className="font-medium text-sm">@{account.username}</div>
                                <span className="text-xs text-muted-foreground">{account.account_name && account.account_name.length > 20 ? account.account_name.slice(0, 20) + '...' : account.account_name}</span>
                                {/* ステータス表示 */}
                                <div className="flex items-center gap-2 mt-1">
                                <div className={`w-2 h-2 rounded-full ${
                                    account.is_active ? 'bg-green-500' : 'bg-gray-400'
                                }`} />
                                <span className="text-xs text-muted-foreground">
                                    {account.is_active ? 'アクティブ' : '無効'}
                                </span>
                                {summary.tokenWarning !== 'none' && (
                                    <>
                                    <AlertTriangle className="w-3 h-3 text-orange-500" />
                                    <span className="text-xs text-orange-600">
                                        {summary.daysUntilExpiry !== undefined ? 
                                        `${summary.daysUntilExpiry}日後期限切れ` : 
                                        '期限切れ'}
                                    </span>
                                    </>
                                )}
                                </div>
                            </div>
                            {selectedAccount?.id === account.id && (
                                <Check className="w-4 h-4 text-primary" />
                            )}
                            </div>
                        </Button>
                        );
                    })
                    )}
                </div>
                </ScrollArea>
            </PopoverContent>
        </Popover>
    </div>
    </header>
  );
}

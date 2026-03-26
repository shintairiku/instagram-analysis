"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useMemo } from "react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  FileBarChart,
  Settings,
  Download,
  ChevronDown,
  Check,
  Loader2,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { exportToPDF } from "@/lib/pdfExport";
import { useAccount } from "@/hooks/useAccount";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

const navItems = [
  { title: "投稿分析", href: "/", icon: FileBarChart },
  { title: "設定", href: "/setup", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const {
    selectedAccount,
    accounts,
    loading,
    selectAccount,
    refreshAccounts,
    getAccountSummary,
  } = useAccount();

  const [isExporting, setIsExporting] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [accountSearch, setAccountSearch] = useState("");

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportToPDF();
    } finally {
      setIsExporting(false);
    }
  };

  const handleAccountSelect = (accountId: string) => {
    selectAccount(accountId);
    setIsOpen(false);
    setAccountSearch("");
  };

  const filteredAccounts = useMemo(() => {
    const q = accountSearch.trim().toLowerCase().normalize("NFKC");
    if (!q) return accounts;
    return accounts.filter((a) => {
      const u = a.username.toLowerCase().normalize("NFKC");
      const n = (a.account_name ?? "").toLowerCase().normalize("NFKC");
      return u.includes(q) || `@${u}`.includes(q) || n.includes(q);
    });
  }, [accountSearch, accounts]);

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg flex items-center justify-center text-white font-bold text-sm" style={{ backgroundColor: '#c0b487' }}>
            IG
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold">Instagram Analytics</span>
            <span className="text-[10px] text-muted-foreground">新大陸</span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        {/* Account Selector */}
        <SidebarGroup>
          <SidebarGroupLabel>アカウント</SidebarGroupLabel>
          <SidebarGroupContent className="px-2">
            <Popover open={isOpen} onOpenChange={(o) => { setIsOpen(o); if (!o) setAccountSearch(""); }}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className="w-full justify-start h-auto py-2 px-3 overflow-hidden"
                  disabled={loading && !selectedAccount}
                >
                  {loading && !selectedAccount ? (
                    <><Loader2 className="w-4 h-4 animate-spin mr-2" /><span className="text-sm">読み込み中...</span></>
                  ) : selectedAccount ? (
                    <div className="flex items-center gap-2 w-full min-w-0 overflow-hidden">
                      <Avatar className="w-6 h-6 shrink-0">
                        <AvatarImage src={getAccountSummary(selectedAccount).avatar} />
                        <AvatarFallback className="text-[10px]">
                          {selectedAccount.username.charAt(0).toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <span className="text-xs truncate flex-1 min-w-0">@{selectedAccount.username}</span>
                      <ChevronDown className="w-3 h-3 shrink-0 text-muted-foreground" />
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground">アカウント未選択</span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-64 p-2" align="start" side="bottom">
                <ScrollArea className="max-h-[60vh]">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between px-2 py-1">
                      <span className="text-xs font-medium text-muted-foreground">アカウントを選択</span>
                      <Button variant="ghost" size="sm" onClick={refreshAccounts} disabled={loading} className="h-5 w-5 p-0">
                        <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
                      </Button>
                    </div>
                    <div className="px-1 pb-1">
                      <div className="relative">
                        <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          value={accountSearch}
                          onChange={(e) => setAccountSearch(e.target.value)}
                          placeholder="検索..."
                          className="h-7 pl-7 pr-7 text-xs"
                          autoFocus
                        />
                        {accountSearch && (
                          <Button variant="ghost" size="sm" className="absolute right-0.5 top-1/2 h-5 w-5 -translate-y-1/2 p-0" onClick={() => setAccountSearch("")}>
                            <X className="h-3 w-3" />
                          </Button>
                        )}
                      </div>
                    </div>
                    {filteredAccounts.map((account) => (
                      <Button
                        key={account.id}
                        variant="ghost"
                        className="w-full justify-start h-auto py-1.5 px-2"
                        onClick={() => handleAccountSelect(account.id)}
                      >
                        <div className="flex items-center gap-2 w-full">
                          <Avatar className="w-6 h-6 shrink-0">
                            <AvatarImage src={getAccountSummary(account).avatar} />
                            <AvatarFallback className="text-[10px]">{account.username.charAt(0).toUpperCase()}</AvatarFallback>
                          </Avatar>
                          <div className="flex-1 text-left min-w-0">
                            <div className="text-xs font-medium truncate">@{account.username}</div>
                            {account.account_name && (
                              <div className="text-[10px] text-muted-foreground truncate">{account.account_name}</div>
                            )}
                          </div>
                          {selectedAccount?.id === account.id && <Check className="w-3 h-3 text-primary shrink-0" />}
                        </div>
                      </Button>
                    ))}
                  </div>
                </ScrollArea>
              </PopoverContent>
            </Popover>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Navigation */}
        <SidebarGroup>
          <SidebarGroupLabel>メニュー</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton asChild isActive={pathname === item.href}>
                    <Link href={item.href}>
                      <item.icon className="w-4 h-4" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t p-3">
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={handleExport}
          disabled={isExporting}
        >
          <Download className="h-4 w-4 mr-2" />
          {isExporting ? "エクスポート中..." : "PDF エクスポート"}
        </Button>
      </SidebarFooter>
    </Sidebar>
  );
}

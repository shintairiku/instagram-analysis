"use client";

import { useState, useCallback } from "react";
import { format, subMonths } from "date-fns";
import { Calendar as CalendarIcon, AlertCircle, Loader2, Eye, Heart, Bookmark, Share2, MessageCircle, TrendingUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { DateRange } from "react-day-picker";
import { PostInsightTable } from "./components/PostInsightTable";
import { PostInsightChart } from "./components/PostInsightChart";
import { usePostInsights } from "./hooks/usePostInsights";
import { useAccount } from "../../hooks/useAccount";
import { ContentType, contentTypes, MediaType } from "./types/postInsight";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

const JST_TIME_ZONE = "Asia/Tokyo";

function toJstYmd(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: JST_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function formatJstMdHm(iso: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("ja-JP", {
    timeZone: JST_TIME_ZONE,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

export default function PostInsight() {
  // デフォルト期間：日本時間の「本日」〜「1ヶ月前」
  const getDefaultJstRange = useCallback((): DateRange => {
    const now = new Date();
    const [y, m, d] = toJstYmd(now).split("-").map(Number);
    const jstToday = new Date(y, (m || 1) - 1, d || 1);
    return { from: subMonths(jstToday, 1), to: jstToday };
  }, []);

  const [date, setDate] = useState<DateRange | undefined>(() => getDefaultJstRange());
  const [selectedType, setSelectedType] = useState<ContentType>("All");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  // 選択されたアカウントを取得
  const { selectedAccount, refreshAccounts } = useAccount();

  // APIからデータを取得（期間フィルタなし）
  const {
    data: apiData,
    posts,
    loading,
    error,
    filterByMediaType,
    clearError,
    refresh
  } = usePostInsights({
    account_id: selectedAccount?.instagram_user_id || "", // 選択アカウントのInstagram User ID
    limit: 100 // 全データを取得
  }, {
    autoFetch: !!selectedAccount && !!selectedAccount.instagram_user_id, // アカウントとIDが両方存在する場合のみ自動取得
    cacheTime: 5 * 60 * 1000, // 5分キャッシュ
  });

  // フィルタリングされたデータ（フロントエンドで期間とタイプをフィルタ）
  const getFilteredData = () => {
    let filtered = posts;

    // メディアタイプフィルタ
    if (selectedType !== "All") {
      filtered = filterByMediaType(selectedType as MediaType);
    }

    // 日付フィルタ（日本時間で比較）
    if (date?.from && date?.to) {
      const fromYmd = toJstYmd(date.from);
      const toYmd = toJstYmd(date.to);
      filtered = filtered.filter(post => {
        const postYmd = toJstYmd(new Date(post.date));
        return postYmd >= fromYmd && postYmd <= toYmd;
      });
    }

    // 表示順：投稿日を昇順（古い → 新しい）
    return [...filtered].sort((a, b) => {
      const aTime = Date.parse(a.date);
      const bTime = Date.parse(b.date);

      const aInvalid = Number.isNaN(aTime);
      const bInvalid = Number.isNaN(bTime);
      if (aInvalid && bInvalid) return 0;
      if (aInvalid) return 1;
      if (bInvalid) return -1;

      return aTime - bTime;
    });
  };

  const filteredData = getFilteredData();

  const handleManualRefresh = useCallback(async () => {
    if (!selectedAccount?.instagram_user_id) return;
    setRefreshing(true);
    setRefreshError(null);

    try {
      const res = await fetch(
        `/api/collection/accounts/${encodeURIComponent(
          selectedAccount.instagram_user_id
        )}/refresh`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ window_days: 30, max_posts: 50 }),
        }
      );

      const data = (await res.json().catch(() => ({}))) as { detail?: string };

      if (!res.ok) {
        const retryAfter = res.headers.get("Retry-After");
        const suffix = retryAfter ? `（${retryAfter}秒後に再実行できます）` : "";
        throw new Error(`${data.detail ?? "更新に失敗しました"}${suffix}`);
      }

      await refreshAccounts();
      await refresh();
    } catch (e) {
      setRefreshError(e instanceof Error ? e.message : "更新に失敗しました");
    } finally {
      setRefreshing(false);
    }
  }, [refresh, refreshAccounts, selectedAccount?.instagram_user_id]);

  // Summary calculations
  const totalReach = filteredData.reduce((s, p) => s + p.reach, 0);
  const totalLikes = filteredData.reduce((s, p) => s + p.likes, 0);
  const totalComments = filteredData.reduce((s, p) => s + p.comments, 0);
  const totalSaves = filteredData.reduce((s, p) => s + p.saves, 0);
  const totalShares = filteredData.reduce((s, p) => s + p.shares, 0);
  const avgEgRate = filteredData.length > 0
    ? filteredData.reduce((s, p) => s + p.engagement_rate, 0) / filteredData.length
    : 0;

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] p-4 md:p-6 gap-3">
      {/* Filters - fixed at top */}
      <div className="flex flex-col gap-3 shrink-0">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleManualRefresh}
            disabled={!selectedAccount || refreshing}
          >
            {refreshing ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
            最新情報を取得
          </Button>

          <Popover>
            <PopoverTrigger asChild>
              <Button
                id="date"
                variant="outline"
                size="sm"
                className={cn(
                  "justify-start text-left font-normal",
                  !date && "text-muted-foreground"
                )}
              >
                <CalendarIcon className="mr-1.5 h-3 w-3" />
                {date?.from ? (
                  date.to ? (
                    <span className="text-xs">{format(date.from, "yyyy/MM/dd")} - {format(date.to, "yyyy/MM/dd")}</span>
                  ) : (
                    <span className="text-xs">{format(date.from, "yyyy/MM/dd")}</span>
                  )
                ) : (
                  <span className="text-xs">日付を選択</span>
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar initialFocus mode="range" defaultMonth={date?.from} selected={date} onSelect={setDate} numberOfMonths={2} />
            </PopoverContent>
          </Popover>

          <Tabs value={selectedType} onValueChange={(v) => setSelectedType(v as ContentType)} className="w-auto">
            <TabsList className="h-8">
              {contentTypes.map((type) => (
                <TabsTrigger key={type} value={type} className="text-xs px-2 py-1">
                  {type === "CAROUSEL_ALBUM" ? "Carousel" : type}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {apiData && (
            <span className="text-xs text-muted-foreground ml-auto">
              {filteredData.length}件 / 全{apiData.meta.total_posts}件
              {selectedAccount?.last_synced_at && ` | 更新: ${formatJstMdHm(selectedAccount.last_synced_at)}`}
            </span>
          )}
        </div>
      </div>

      {/* Summary KPI Cards - fixed */}
      {filteredData.length > 0 && (
        <div className="grid grid-cols-3 md:grid-cols-6 gap-2 shrink-0">
          {[
            { label: "リーチ", value: totalReach.toLocaleString(), icon: Eye, color: "#4ade80" },
            { label: "いいね", value: totalLikes.toLocaleString(), icon: Heart, color: "#f472b6" },
            { label: "コメント", value: totalComments.toLocaleString(), icon: MessageCircle, color: "#60a5fa" },
            { label: "保存", value: totalSaves.toLocaleString(), icon: Bookmark, color: "#a78bfa" },
            { label: "シェア", value: totalShares.toLocaleString(), icon: Share2, color: "#fb923c" },
            { label: "平均EG率", value: `${avgEgRate.toFixed(1)}%`, icon: TrendingUp, color: "#f3a522" },
          ].map((item) => (
            <Card key={item.label}>
              <CardContent className="p-3 flex items-center gap-2">
                <item.icon className="h-4 w-4 shrink-0" style={{ color: item.color }} />
                <div className="min-w-0">
                  <p className="text-[10px] text-muted-foreground">{item.label}</p>
                  <p className="text-sm font-bold truncate">{item.value}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* エラー表示 */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex justify-between items-center">
            <span>{error}</span>
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={clearError}
              >
                閉じる
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={refresh}
                disabled={loading}
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                再試行
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}
      {refreshError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex justify-between items-center">
            <span>{refreshError}</span>
            <Button variant="outline" size="sm" onClick={() => setRefreshError(null)}>
              閉じる
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* データ表示 - scrollable area */}
      <div id="post-analysis-content" className="flex-1 min-h-0 overflow-y-auto space-y-6">
        {!selectedAccount ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-center text-muted-foreground">
              <p>アカウントを選択してください</p>
              <p className="text-sm mt-1">サイドバーからInstagramアカウントを選択してください</p>
            </div>
          </div>
        ) : loading && !posts.length ? (
          <div className="flex items-center justify-center h-32">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              投稿データを読み込み中...
            </div>
          </div>
        ) : filteredData.length === 0 ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-center text-muted-foreground">
              <p>選択した条件に一致する投稿がありません</p>
              <p className="text-sm mt-1">日付範囲またはメディアタイプを変更してください</p>
            </div>
          </div>
        ) : (
          <>
            {/* テーブル */}
            <PostInsightTable data={filteredData} />
            
            {/* グラフ */}
            <PostInsightChart data={filteredData} />
          </>
        )}
      </div>
    </div>
  );
}

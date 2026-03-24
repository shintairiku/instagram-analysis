"use client";

import { useAccount } from "@/hooks/useAccount";
import { useAccountInsights } from "./hooks/useAccountInsights";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Users, Eye, Heart, TrendingUp, BarChart3, UserPlus, MousePointerClick } from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
} from "recharts";

const COLORS = {
  primary: "#c0b487",
  accent: "#f3a522",
  blue: "#60a5fa",
  pink: "#f472b6",
  green: "#4ade80",
  purple: "#a78bfa",
  orange: "#fb923c",
  gray: "#94a3b8",
};

const PIE_COLORS = [COLORS.blue, COLORS.pink, COLORS.green, COLORS.purple, COLORS.orange, COLORS.gray, "#fbbf24", "#34d399"];

function KPICard({ title, value, sub, icon: Icon, color }: { title: string; value: string; sub?: string; icon: React.ElementType; color: string }) {
  return (
    <Card>
      <CardContent className="pt-4 pb-3 px-4">
        <div className="flex items-start justify-between">
          <div className="space-y-1 min-w-0">
            <p className="text-xs text-muted-foreground">{title}</p>
            <p className="text-xl font-bold truncate">{value}</p>
            {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
          </div>
          <div className="rounded-lg p-2 shrink-0" style={{ backgroundColor: `${color}18` }}>
            <Icon className="h-4 w-4" style={{ color }} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Overview() {
  const { selectedAccount } = useAccount();
  const { data, loading, error } = useAccountInsights(
    selectedAccount?.instagram_user_id,
    14
  );

  if (!selectedAccount) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center text-muted-foreground">
          <Users className="h-10 w-10 mx-auto mb-3 opacity-40" />
          <p className="font-medium">アカウントを選択してください</p>
          <p className="text-sm mt-1">サイドバーからInstagramアカウントを選択してください</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center text-muted-foreground">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      </div>
    );
  }

  const profile = data?.profile;
  const insights = data?.insights;
  const demographics = data?.demographics;

  // Extract reach breakdown
  const reachTotal = insights?.reach_by_follow_type?.value ?? 0;
  const reachBreakdown = (insights?.reach_by_follow_type?.breakdowns?.[0]?.results ?? []).map(
    (r) => ({ name: r.dimension_values[0] === "FOLLOWER" ? "フォロワー" : r.dimension_values[0] === "NON_FOLLOWER" ? "非フォロワー" : "不明", value: r.value })
  );

  // Extract views breakdown
  const viewsTotal = insights?.views_by_media_type?.value ?? 0;
  const viewsBreakdown = (insights?.views_by_media_type?.breakdowns?.[0]?.results ?? [])
    .map((r) => {
      const labels: Record<string, string> = {
        AD: "広告", STORY: "ストーリー", REEL: "リール",
        CAROUSEL_CONTAINER: "カルーセル", POST: "投稿",
      };
      return { name: labels[r.dimension_values[0]] || r.dimension_values[0], value: r.value };
    })
    .filter((v) => v.value > 0)
    .sort((a, b) => b.value - a.value);

  const interactions = insights?.interactions ?? {};
  const followBreakdown = insights?.follows_and_unfollows?.breakdowns?.[0]?.results ?? [];
  const newFollowers = followBreakdown.find((r) => r.dimension_values[0] === "FOLLOWER")?.value ?? 0;
  const nonFollowerFollows = followBreakdown.find((r) => r.dimension_values[0] === "NON_FOLLOWER")?.value ?? 0;

  // Demographics for pie chart
  const genderData = (demographics?.gender ?? []).map((g) => {
    const labels: Record<string, string> = { F: "女性", M: "男性", U: "不明" };
    return { name: labels[g.key] || g.key, value: g.value };
  });

  const ageData = (demographics?.age ?? []).map((a) => ({
    name: a.key,
    value: a.value,
  }));

  const cityData = (demographics?.city ?? []).slice(0, 8).map((c) => ({
    name: c.key.split(",")[0].replace(/-shi|-ku|-cho|-machi|-gun|-city/gi, "").trim(),
    value: c.value,
  }));

  const fmt = (n: number) => {
    if (n >= 10000) return `${(n / 10000).toFixed(1)}万`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return n.toLocaleString();
  };

  return (
    <div className="p-4 md:p-6 space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPICard
          title="フォロワー"
          value={fmt(profile?.followers_count ?? 0)}
          sub={`フォロー中: ${fmt(profile?.follows_count ?? 0)}`}
          icon={Users}
          color={COLORS.blue}
        />
        <KPICard
          title="リーチ (14日間)"
          value={fmt(reachTotal)}
          sub={reachBreakdown.length > 0 ? `非フォロワー: ${reachBreakdown.find(r => r.name === "非フォロワー")?.value ?? 0}` : undefined}
          icon={Eye}
          color={COLORS.green}
        />
        <KPICard
          title="Views (14日間)"
          value={fmt(viewsTotal)}
          sub={viewsBreakdown.length > 0 ? `最多: ${viewsBreakdown[0]?.name}` : undefined}
          icon={BarChart3}
          color={COLORS.purple}
        />
        <KPICard
          title="エンゲージメント (14日間)"
          value={fmt(interactions.total_interactions ?? 0)}
          sub={`いいね: ${interactions.likes ?? 0} / 保存: ${interactions.saves ?? 0}`}
          icon={Heart}
          color={COLORS.pink}
        />
      </div>

      {/* Row 2: Reach trend + Reach breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Reach Time Series */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2 px-4 pt-4">
            <CardTitle className="text-sm font-medium flex items-center gap-1.5">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              日別リーチ推移
            </CardTitle>
          </CardHeader>
          <CardContent className="px-2 pb-3">
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={insights?.reach_time_series ?? []} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="reachGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={COLORS.accent} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={COLORS.accent} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} width={40} />
                  <Tooltip labelFormatter={(l: string) => `${l}`} formatter={(v: number) => [v.toLocaleString(), "リーチ"]} />
                  <Area type="monotone" dataKey="value" stroke={COLORS.accent} strokeWidth={2} fill="url(#reachGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Reach by Follow Type */}
        <Card>
          <CardHeader className="pb-2 px-4 pt-4">
            <CardTitle className="text-sm font-medium flex items-center gap-1.5">
              <UserPlus className="h-4 w-4 text-muted-foreground" />
              リーチの内訳
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="h-52 flex items-center justify-center">
              {reachBreakdown.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={reachBreakdown} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                      {reachBreakdown.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => [v.toLocaleString(), ""]} />
                    <Legend wrapperStyle={{ fontSize: "11px" }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : <p className="text-xs text-muted-foreground">データなし</p>}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 3: Views by type + Interactions + Follow changes */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Views by Content Type */}
        <Card>
          <CardHeader className="pb-2 px-4 pt-4">
            <CardTitle className="text-sm font-medium flex items-center gap-1.5">
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
              コンテンツ別 Views
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={viewsBreakdown} layout="vertical" margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [v.toLocaleString(), "Views"]} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {viewsBreakdown.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Interactions */}
        <Card>
          <CardHeader className="pb-2 px-4 pt-4">
            <CardTitle className="text-sm font-medium flex items-center gap-1.5">
              <Heart className="h-4 w-4 text-muted-foreground" />
              インタラクション内訳
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="space-y-2.5 pt-2">
              {[
                { label: "いいね", value: interactions.likes ?? 0, color: COLORS.pink },
                { label: "保存", value: interactions.saves ?? 0, color: COLORS.green },
                { label: "シェア", value: interactions.shares ?? 0, color: COLORS.blue },
                { label: "コメント", value: interactions.comments ?? 0, color: COLORS.purple },
                { label: "リポスト", value: interactions.reposts ?? 0, color: COLORS.orange },
                { label: "返信", value: interactions.replies ?? 0, color: COLORS.gray },
              ].map((item) => {
                const total = interactions.total_interactions || 1;
                const pct = (item.value / total) * 100;
                return (
                  <div key={item.label} className="space-y-0.5">
                    <div className="flex justify-between text-xs">
                      <span>{item.label}</span>
                      <span className="font-medium">{item.value.toLocaleString()}</span>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all" style={{ width: `${Math.max(pct, 1)}%`, backgroundColor: item.color }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Follow Changes + Profile Actions */}
        <Card>
          <CardHeader className="pb-2 px-4 pt-4">
            <CardTitle className="text-sm font-medium flex items-center gap-1.5">
              <MousePointerClick className="h-4 w-4 text-muted-foreground" />
              フォロワー変動 / アクション
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="space-y-4 pt-2">
              <div>
                <p className="text-xs text-muted-foreground mb-2">新規フォロー (14日間)</p>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg bg-green-50 p-2 text-center">
                    <p className="text-lg font-bold text-green-700">+{newFollowers}</p>
                    <p className="text-[10px] text-green-600">既存フォロワーから</p>
                  </div>
                  <div className="rounded-lg bg-blue-50 p-2 text-center">
                    <p className="text-lg font-bold text-blue-700">+{nonFollowerFollows}</p>
                    <p className="text-[10px] text-blue-600">新規発見から</p>
                  </div>
                </div>
              </div>

              {/* Demographics Quick View */}
              {genderData.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-2">フォロワー属性</p>
                  <div className="flex gap-1">
                    {genderData.map((g, i) => {
                      const total = genderData.reduce((s, v) => s + v.value, 0);
                      const pct = total ? (g.value / total * 100).toFixed(0) : "0";
                      return (
                        <div key={i} className="flex-1 rounded-md p-1.5 text-center" style={{ backgroundColor: `${PIE_COLORS[i]}18` }}>
                          <p className="text-xs font-semibold" style={{ color: PIE_COLORS[i] }}>{pct}%</p>
                          <p className="text-[10px] text-muted-foreground">{g.name}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Age Quick View */}
              {ageData.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1.5">年齢分布</p>
                  <div className="h-20">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={ageData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                        <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                        <Tooltip formatter={(v: number) => [v.toLocaleString(), "人"]} />
                        <Bar dataKey="value" radius={[2, 2, 0, 0]} fill={COLORS.accent} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 4: Top Cities */}
      {cityData.length > 0 && (
        <Card>
          <CardHeader className="pb-2 px-4 pt-4">
            <CardTitle className="text-sm font-medium">フォロワー 主要都市</CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cityData} layout="vertical" margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [`${v.toLocaleString()}人`, "フォロワー"]} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} fill={COLORS.primary} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

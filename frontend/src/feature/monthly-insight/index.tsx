"use client";

import { useState } from "react";
import { monthlyAnalyticsData } from "./dummy-data/dummy-data";
import { DailyDataTable } from "./components/DailyDataTable";
import { NewFollowersChart } from "./components/NewFollowersChart";
import { ImpressionsReachChart } from "./components/ImpressionsReachChart";
import { ProfileViewsChart } from "./components/ProfileViewsChart";
import { WebsiteClicksChart } from "./components/WebsiteClicksChart";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function MonthlyInsight() {
  const [selectedMonth, setSelectedMonth] = useState("2024-12");

  return (
    <div id="monthly-analysis-content" className="space-y-6 p-6">
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <p className="text-muted-foreground mt-1">
            Instagram アカウントの月間パフォーマンスを日別で詳細分析
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedMonth} onValueChange={setSelectedMonth}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="月を選択" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="2024-12">2024年12月</SelectItem>
              <SelectItem value="2024-11">2024年11月</SelectItem>
              <SelectItem value="2024-10">2024年10月</SelectItem>
              <SelectItem value="2024-09">2024年9月</SelectItem>
              <SelectItem value="2024-08">2024年8月</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* メインコンテンツ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左側: データテーブル */}
        <div className="lg:col-span-1">
          <DailyDataTable data={monthlyAnalyticsData} />
        </div>

        {/* 右側: グラフ縦並び */}
        <div className="lg:col-span-1 space-y-4">
          <NewFollowersChart data={monthlyAnalyticsData} />
          <ImpressionsReachChart data={monthlyAnalyticsData} />
          <ProfileViewsChart data={monthlyAnalyticsData} />
          <WebsiteClicksChart data={monthlyAnalyticsData} />
        </div>
      </div>
    </div>
  );
}
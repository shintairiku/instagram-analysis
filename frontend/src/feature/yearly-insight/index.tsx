"use client";

import { useState } from "react";
import { yearlyAnalyticsData } from "./dummy-data/dummy-data";
import { DataTable } from "./components/DataTable";
// import { FollowerChart } from "./components/FollowerChart";
import { EngagementChart } from "./components/EngagementChart";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function YearlyInsight() {
  const [selectedYear, setSelectedYear] = useState("2024");


  return (
    <div
      id="yearly-analysis-content"
      className="h-full min-h-0 overflow-y-auto overflow-x-hidden p-4 md:p-6"
    >
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <p className="text-muted-foreground mt-1">
            Instagram アカウントの年間パフォーマンスを詳細に分析
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedYear} onValueChange={setSelectedYear}>
            <SelectTrigger className="w-32">
              <SelectValue placeholder="年を選択" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="2024">2024年</SelectItem>
              <SelectItem value="2023">2023年</SelectItem>
              <SelectItem value="2022">2022年</SelectItem>
            </SelectContent>
          </Select>

        </div>
      </div>


      {/* データテーブル */}
      <div className="mt-6 min-w-0">
        <DataTable data={yearlyAnalyticsData} />
      </div>

      {/* グラフセクション */}
      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* <FollowerChart data={yearlyAnalyticsData} /> */}
        <EngagementChart data={yearlyAnalyticsData} />
      </div>
    </div>
  );
}

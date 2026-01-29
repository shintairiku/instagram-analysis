"use client";

import { PostInsightData } from "../types/postInsight";
import { Card, CardContent } from "@/components/ui/card";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface PostInsightChartProps {
  data: PostInsightData[];
}

export function PostInsightChart({ data }: PostInsightChartProps) {
  const getTypeDisplayName = (type: string) => {
    switch (type) {
      case "IMAGE": return "画像";
      case "VIDEO": return "動画";
      case "CAROUSEL_ALBUM": return "カルーセル";
      case "STORY": return "ストーリー";
      default: return type;
    }
  };

  const chartData = data.map((post) => ({
    date: new Date(post.date).toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' }),
    いいね: post.likes,
    コメント: post.comments,
    保存: post.saves,
    シェア: post.shares,
    EG率: post.engagement_rate,
    リーチ: post.reach,
    視聴数: post.views || 0,
    type: getTypeDisplayName(post.type),
    rawType: post.type,
  }));

  const formatTooltipValue = (value: number, name: string) => {
    if (name === "EG率") {
      return [`${value}%`, name];
    }
    return [value.toLocaleString(), name];
  };

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ color: string; name: string; value: number; payload: { date: string; type: string } }>; label?: string }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-card border border-border rounded-lg p-3 shadow-lg">
          <p className="font-medium">{`${data.date} (${data.type})`}</p>
          {payload.map((entry: { color: string; name: string; value: number }, index: number) => (
            <p key={index} style={{ color: entry.color }} className="text-sm">
              {entry.name}: {formatTooltipValue(entry.value, entry.name)[0]}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <Card className="w-full">
      <CardContent>
        <div className="h-96 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartData}
              margin={{
                top: 20,
                right: 30,
                left: 20,
                bottom: 5,
              }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis 
                dataKey="date" 
                className="text-sm"
                tick={{ fontSize: 12 }}
                angle={-45}
                textAnchor="end"
                height={60}
              />
              <YAxis 
                yAxisId="left" 
                className="text-sm"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => value.toLocaleString()}
              />
              <YAxis 
                yAxisId="right" 
                orientation="right" 
                className="text-sm"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => `${value}%`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend 
                wrapperStyle={{ fontSize: "12px" }}
              />
              
              {/* 積み上げ棒グラフ */}
              <Bar 
                yAxisId="left" 
                dataKey="いいね" 
                stackId="engagement" 
                fill="#ffc9d0" 
                radius={[0, 0, 0, 0]}
                name="いいね"
              />
              <Bar 
                yAxisId="left" 
                dataKey="コメント" 
                stackId="engagement" 
                fill="#c7e0f4" 
                radius={[0, 0, 0, 0]}
                name="コメント"
              />
              <Bar 
                yAxisId="left" 
                dataKey="保存" 
                stackId="engagement" 
                fill="#bfe5bf" 
                radius={[0, 0, 0, 0]}
                name="保存"
              />
              <Bar 
                yAxisId="left" 
                dataKey="シェア" 
                stackId="engagement" 
                fill="#ffe6a3" 
                radius={[2, 2, 0, 0]}
                name="シェア"
              />
              
              {/* エンゲージメント率の折線グラフ */}
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="EG率"
                stroke="#f3a522"
                strokeWidth={3}
                dot={{ fill: "#f3a522", strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, fill: "#f3a522" }}
                name="EG率"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

"use client";

import { DailyAnalytics } from "../dummy-data/dummy-data";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface DailyDataTableProps {
  data: DailyAnalytics[];
}

export function DailyDataTable({ data }: DailyDataTableProps) {
  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  return (
    <Card className="w-full h-fit">
      <CardHeader>
        <CardTitle className="text-xl font-semibold">日別データテーブル</CardTitle>
      </CardHeader>
      <CardContent>
        <Table className="min-w-[720px]">
          <TableHeader className="sticky top-0 bg-background">
            <TableRow>
              <TableHead className="w-16 text-center">日</TableHead>
              <TableHead className="text-right">新規フォロワー数</TableHead>
              <TableHead className="text-right">インプレッション</TableHead>
              <TableHead className="text-right">リーチ</TableHead>
              <TableHead className="text-right">プロフィールアクセス数</TableHead>
              <TableHead className="text-right">ウェブサイトタップ数</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <TableRow key={row.date}>
                <TableCell className="text-center font-medium">{row.date}日</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.new_followers)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.impressions)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.reach)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.profile_views)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.website_clicks)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

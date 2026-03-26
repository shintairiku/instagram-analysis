"use client";

import { MonthlyAnalytics } from "../dummy-data/dummy-data";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface DataTableProps {
  data: MonthlyAnalytics[];
}

export function DataTable({ data }: DataTableProps) {
  const formatNumber = (num: number | null): string => {
    if (num === null) return "---";
    return num.toLocaleString();
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-xl font-semibold">月別データテーブル</CardTitle>
      </CardHeader>
      <CardContent>
        <Table className="min-w-[960px]">
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">月</TableHead>
              <TableHead className="text-right">フォロワー数</TableHead>
              <TableHead className="text-right">フォロー数</TableHead>
              <TableHead className="text-right">リーチ数</TableHead>
              <TableHead className="text-right">インプレッション数</TableHead>
              <TableHead className="text-right">プロフィール閲覧</TableHead>
              <TableHead className="text-right">ウェブサイトタップ</TableHead>
              <TableHead className="text-right">いいね数</TableHead>
              <TableHead className="text-right">コメント数</TableHead>
              <TableHead className="text-right">保存数</TableHead>
              <TableHead className="text-right">シェア数</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <TableRow key={row.month}>
                <TableCell className="font-medium">{row.month}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.follower_count)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.following_count)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.reach)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.impressions)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.profile_views)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.website_clicks)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.likes)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.comments)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.saves)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(row.shares)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

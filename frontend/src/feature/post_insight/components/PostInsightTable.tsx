"use client";

import { PostInsightData } from "../types/postInsight";
import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ExternalLink, Info } from "lucide-react";

// Meta Instagram Graph API 公式定義に基づくメトリクス説明
const metricDescriptions: Record<string, string> = {
  "投稿日": "投稿がInstagramに公開された日時 (posted_at / timestamp)",
  "サムネイル": "投稿のメディアサムネイル画像。クリックでInstagramの投稿ページを開きます",
  "タイプ": "メディアタイプ: IMAGE(画像), VIDEO(動画/リール), CAROUSEL_ALBUM(複数枚投稿), STORY(ストーリー) — media_type フィールド",
  "リーチ": "この投稿を閲覧したユニークアカウント数。同一ユーザーが複数回見ても1回とカウント — Meta API: reach (lifetime)",
  "いいね": "この投稿に付けられた「いいね」の総数 — Meta API: likes (lifetime)",
  "コメント": "この投稿に付けられたコメントの総数 — Meta API: comments (lifetime)",
  "シェア": "この投稿がDM等で他のユーザーに共有された回数。2026年のアルゴリズムで最も強力なシグナル — Meta API: shares (lifetime)",
  "保存": "この投稿がブックマーク保存された回数。アルゴリズムにおける強力なランキングシグナル — Meta API: saved (lifetime)",
  "EG率(%)": "エンゲージメント率 = (いいね + コメント + シェア + 保存) / リーチ x 100。投稿の反応率を示す総合指標",
  "視聴数": "動画・リールの総再生回数（リプレイ含む）。2025年4月にimpressions/playsから統一された指標 — Meta API: views (lifetime)",
  "視聴率(%)": "視聴率 = 視聴数 / リーチ x 100。動画がリーチしたユーザーにどれだけ再生されたかを示す",
};

interface PostInsightTableProps {
  data: PostInsightData[];
}

export function PostInsightTable({ data }: PostInsightTableProps) {
  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ja-JP', {
      month: 'short',
      day: 'numeric'
    });
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case "IMAGE":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300";
      case "VIDEO":
        return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300";
      case "CAROUSEL_ALBUM":
        return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300";
      case "STORY":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300";
    }
  };

  const getTypeDisplayName = (type: string) => {
    switch (type) {
      case "IMAGE": return "画像";
      case "VIDEO": return "動画";
      case "CAROUSEL_ALBUM": return "カルーセル";
      case "STORY": return "ストーリー";
      default: return type;
    }
  };

  const placeholderSvg = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiBmaWxsPSIjRjNGNEY2Ii8+CjxwYXRoIGQ9Ik0yNCAzNkMzMC42Mjc0IDM2IDM2IDMwLjYyNzQgMzYgMjRDMzYgMTcuMzcyNiAzMC42Mjc0IDEyIDI0IDEyQzE3LjM3MjYgMTIgMTIgMTcuMzcyNiAxMiAyNEMxMiAzMC42Mjc0IDE3LjM3MjYgMzYgMjQgMzZaIiBzdHJva2U9IiM5Q0EzQUYiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPg==';

  const getThumbnailUrl = (post: PostInsightData): string => {
    const isValidUrl = (url: string): boolean => {
      if (!url || url.trim() === '') return false;
      if (url.startsWith('data:')) return true;
      if (url.includes('example.com')) return false;
      try { new URL(url); return true; } catch { return false; }
    };
    if (isValidUrl(post.thumbnail)) return post.thumbnail;
    if (isValidUrl(post.media_url)) return post.media_url;
    return placeholderSvg;
  };

  function MetricLabel({ label }: { label: string }) {
    const description = metricDescriptions[label];
    if (!description) return <span>{label}</span>;
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center gap-1 cursor-help">
            {label}
            <Info className="h-3 w-3 text-muted-foreground" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="right" className="max-w-xs text-xs leading-relaxed">
          {description}
        </TooltipContent>
      </Tooltip>
    );
  }

  const rows = [
    {
      label: "投稿日",
      cells: data.map(post => formatDate(post.date))
    },
    {
      label: "サムネイル",
      cells: data.map(post => (
        <div key={post.id} className="relative w-12 h-12 rounded-md overflow-hidden mx-auto group">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={getThumbnailUrl(post)}
            alt=""
            className="w-full h-full object-cover"
            loading="lazy"
            onError={(e) => { (e.target as HTMLImageElement).src = placeholderSvg; }}
          />
          {post.permalink && (
            <a
              href={post.permalink}
              target="_blank"
              rel="noopener noreferrer"
              className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100"
            >
              <ExternalLink className="h-4 w-4 text-white" />
            </a>
          )}
        </div>
      ))
    },
    {
      label: "タイプ",
      cells: data.map(post => (
        <Badge key={post.id} variant="secondary" className={getTypeColor(post.type)}>
          {getTypeDisplayName(post.type)}
        </Badge>
      ))
    },
    { label: "リーチ", cells: data.map(post => formatNumber(post.reach)) },
    { label: "いいね", cells: data.map(post => formatNumber(post.likes)) },
    { label: "コメント", cells: data.map(post => formatNumber(post.comments)) },
    { label: "シェア", cells: data.map(post => formatNumber(post.shares)) },
    { label: "保存", cells: data.map(post => formatNumber(post.saves)) },
    {
      label: "EG率(%)",
      cells: data.map(post => (
        <span key={post.id} className={post.engagement_rate >= 8 ? "text-green-600" :
                                     post.engagement_rate >= 5 ? "text-yellow-600" : "text-red-600"}>
          {post.engagement_rate}%
        </span>
      ))
    },
    {
      label: "視聴数",
      cells: data.map(post =>
        post.views > 0 ? formatNumber(post.views) :
        <span key={post.id} className="text-muted-foreground">---</span>
      )
    },
    {
      label: "視聴率(%)",
      cells: data.map(post => (
        post.view_rate && post.view_rate > 0 ? (
          <span key={post.id} className={post.view_rate >= 70 ? "text-green-600" :
                                       post.view_rate >= 50 ? "text-yellow-600" : "text-red-600"}>
            {post.view_rate}%
          </span>
        ) : (
          <span key={post.id} className="text-muted-foreground">---</span>
        )
      ))
    }
  ];

  return (
    <TooltipProvider delayDuration={200}>
      <Card className="w-full">
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableBody>
                {rows.map((row, rowIndex) => (
                  <TableRow key={rowIndex}>
                    <TableCell className="font-medium sticky left-0 bg-background border-r z-10 whitespace-nowrap">
                      <MetricLabel label={row.label} />
                    </TableCell>
                    {row.cells.map((cell, cellIndex) => (
                      <TableCell key={cellIndex} className="text-center">
                        {cell}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </TooltipProvider>
  );
}

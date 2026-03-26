"use client";

import type { ReactNode } from "react";
import { PostInsightData } from "../types/postInsight";
import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

const JST_TIME_ZONE = "Asia/Tokyo";

const dateFormatter = new Intl.DateTimeFormat("ja-JP", {
  timeZone: JST_TIME_ZONE,
  month: "2-digit",
  day: "2-digit",
});

const timeFormatter = new Intl.DateTimeFormat("ja-JP", {
  timeZone: JST_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const placeholderSvg =
  "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiBmaWxsPSIjRjNGNEY2Ii8+CjxwYXRoIGQ9Ik0yNCAzNkMzMC42Mjc0IDM2IDM2IDMwLjYyNzQgMzYgMjRDMzYgMTcuMzcyNiAzMC42Mjc0IDEyIDI0IDEyQzE3LjM3MjYgMTIgMTIgMTcuMzcyNiAxMiAyNEMxMiAzMC42Mjc0IDE3LjM3MjYgMzYgMjQgMzZaIiBzdHJva2U9IiM5Q0EzQUYiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPg==";

interface PostInsightTableProps {
  data: PostInsightData[];
}

type RowDefinition = {
  label: string;
  cells: ReactNode[];
  labelClassName?: string;
  cellClassName?: string;
};

function isValidMediaUrl(url: string): boolean {
  if (!url || url.trim() === "") return false;
  if (url.startsWith("data:")) return true;
  if (url.includes("example.com")) return false;

  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

function getThumbnailUrl(post: PostInsightData): string {
  if (isValidMediaUrl(post.thumbnail)) return post.thumbnail;
  if (isValidMediaUrl(post.media_url)) return post.media_url;
  return placeholderSvg;
}

function getTypeColor(type: string) {
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
}

function getTypeDisplayName(type: string) {
  switch (type) {
    case "IMAGE":
      return "画像";
    case "VIDEO":
      return "動画";
    case "CAROUSEL_ALBUM":
      return "カルーセル";
    case "STORY":
      return "ストーリー";
    default:
      return type;
  }
}

function formatNumber(num: number): string {
  return num.toLocaleString("ja-JP");
}

function formatDate(dateString: string): string {
  return dateFormatter.format(new Date(dateString));
}

function formatTime(dateString: string): string {
  return timeFormatter.format(new Date(dateString));
}

function getRateToneClass(value: number) {
  if (value >= 8) return "text-emerald-600";
  if (value >= 5) return "text-amber-600";
  return "text-rose-600";
}

function ThumbnailCell({ post }: { post: PostInsightData }) {
  const image = (
    <div className="mx-auto h-10 w-10 overflow-hidden rounded-md border bg-muted">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={getThumbnailUrl(post)}
        alt={`${formatDate(post.date)}の${getTypeDisplayName(post.type)}サムネイル`}
        width={40}
        height={40}
        className="h-full w-full object-cover"
        loading="lazy"
        onError={(event) => {
          event.currentTarget.src = placeholderSvg;
        }}
      />
    </div>
  );

  if (!post.permalink) {
    return image;
  }

  return (
    <a
      href={post.permalink}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Instagramで ${formatDate(post.date)} の投稿を開く`}
      className="inline-block"
    >
      {image}
    </a>
  );
}

export function PostInsightTable({ data }: PostInsightTableProps) {
  const rows: RowDefinition[] = [
    {
      label: "投稿日",
      labelClassName: "h-14",
      cellClassName: "h-14 align-top",
      cells: data.map((post) => (
        <div key={post.id} className="flex items-start justify-between gap-1">
          <div className="min-w-0">
            <div className="text-xs font-semibold tabular-nums">{formatDate(post.date)}</div>
            <div className="mt-0.5 text-[10px] text-muted-foreground tabular-nums">
              {formatTime(post.date)}
            </div>
          </div>
          {post.permalink ? (
            <a
              href={post.permalink}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Instagramで ${formatDate(post.date)} の投稿を開く`}
              className="rounded-sm p-0.5 text-muted-foreground transition-colors hover:bg-muted"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            </a>
          ) : null}
        </div>
      )),
    },
    {
      label: "サムネイル",
      labelClassName: "h-16",
      cellClassName: "h-16",
      cells: data.map((post) => <ThumbnailCell key={post.id} post={post} />),
    },
    {
      label: "タイプ",
      labelClassName: "h-12",
      cellClassName: "h-12",
      cells: data.map((post) => (
        <Badge
          key={post.id}
          variant="secondary"
          className={cn("px-2 py-0.5 text-[10px]", getTypeColor(post.type))}
        >
          {getTypeDisplayName(post.type)}
        </Badge>
      )),
    },
    {
      label: "リーチ",
      labelClassName: "h-11",
      cellClassName: "h-11 font-medium tabular-nums",
      cells: data.map((post) => formatNumber(post.reach)),
    },
    {
      label: "いいね",
      labelClassName: "h-11",
      cellClassName: "h-11 font-medium tabular-nums",
      cells: data.map((post) => formatNumber(post.likes)),
    },
    {
      label: "コメント",
      labelClassName: "h-11",
      cellClassName: "h-11 font-medium tabular-nums",
      cells: data.map((post) => formatNumber(post.comments)),
    },
    {
      label: "シェア",
      labelClassName: "h-11",
      cellClassName: "h-11 font-medium tabular-nums",
      cells: data.map((post) => formatNumber(post.shares)),
    },
    {
      label: "保存",
      labelClassName: "h-11",
      cellClassName: "h-11 font-medium tabular-nums",
      cells: data.map((post) => formatNumber(post.saves)),
    },
    {
      label: "EG率(%)",
      labelClassName: "h-11",
      cellClassName: "h-11 font-semibold tabular-nums",
      cells: data.map((post) => (
        <span key={post.id} className={getRateToneClass(post.engagement_rate)}>
          {post.engagement_rate}%
        </span>
      )),
    },
    {
      label: "視聴数",
      labelClassName: "h-11",
      cellClassName: "h-11 font-medium tabular-nums",
      cells: data.map((post) => (post.views > 0 ? formatNumber(post.views) : "---")),
    },
  ];

  return (
    <Card className="w-full overflow-hidden">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <p className="text-sm font-medium">投稿一覧</p>
        <p className="text-xs text-muted-foreground">左右にスクロール</p>
      </div>
      <CardContent className="p-0">
        <Table className="w-max min-w-full table-fixed">
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.label}>
                <TableCell
                  className={cn(
                    "sticky left-0 z-20 w-[6.5rem] min-w-[6.5rem] border-r bg-background px-4 text-left text-xs font-medium whitespace-nowrap text-muted-foreground",
                    row.labelClassName
                  )}
                >
                  {row.label}
                </TableCell>
                {row.cells.map((cell, index) => (
                  <TableCell
                    key={`${row.label}-${data[index]?.id ?? index}`}
                    className={cn(
                      "w-[6.5rem] min-w-[6.5rem] px-2 text-center whitespace-nowrap",
                      row.cellClassName
                    )}
                  >
                    {cell}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

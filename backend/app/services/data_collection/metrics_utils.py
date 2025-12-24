"""
Metrics utilities for data collection.
Instagram Graph API の返却形式を DB 保存形式へ正規化します。
"""

from __future__ import annotations

from typing import Any, Dict


def normalize_post_metrics_for_db(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Instagram Graph API のメトリクス名 → DBカラム名へ正規化。

    - ig_reels_video_view_total_time -> video_view_total_time
    - ig_reels_avg_watch_time -> avg_watch_time
    """
    metrics = dict(raw or {})

    if "ig_reels_video_view_total_time" in metrics:
        metrics["video_view_total_time"] = metrics.get("ig_reels_video_view_total_time") or 0
        metrics.pop("ig_reels_video_view_total_time", None)

    if "ig_reels_avg_watch_time" in metrics:
        metrics["avg_watch_time"] = metrics.get("ig_reels_avg_watch_time") or 0
        metrics.pop("ig_reels_avg_watch_time", None)

    return metrics


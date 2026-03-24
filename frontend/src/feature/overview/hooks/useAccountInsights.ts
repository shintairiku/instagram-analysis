"use client";

import { useState, useEffect, useCallback } from "react";

interface BreakdownItem {
  key: string;
  value: number;
}

interface InsightsData {
  reach_by_follow_type: {
    value: number;
    breakdowns: { results: { dimension_values: string[]; value: number }[] }[];
  } | null;
  views_by_media_type: {
    value: number;
    breakdowns: { results: { dimension_values: string[]; value: number }[] }[];
  } | null;
  interactions: Record<string, number>;
  follows_and_unfollows: {
    breakdowns: { results: { dimension_values: string[]; value: number }[] }[];
  } | null;
  reach_time_series: { date: string; value: number }[];
}

interface DemographicsData {
  gender: BreakdownItem[];
  age: BreakdownItem[];
  city: BreakdownItem[];
  country: BreakdownItem[];
}

interface ProfileData {
  id: string;
  username: string;
  name: string;
  biography: string;
  followers_count: number;
  follows_count: number;
  media_count: number;
  website: string;
  profile_picture_url: string;
}

export interface AccountInsights {
  profile: ProfileData | null;
  insights: InsightsData | null;
  demographics: DemographicsData | null;
}

export function useAccountInsights(instagramUserId: string | undefined, days = 7) {
  const [data, setData] = useState<AccountInsights | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!instagramUserId) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(
        `/api/insights/${encodeURIComponent(instagramUserId)}?type=all&days=${days}`
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error || `HTTP ${res.status}`);
      }
      const json = await res.json();
      setData(json as AccountInsights);
    } catch (e) {
      setError(e instanceof Error ? e.message : "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [instagramUserId, days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refresh: fetchData };
}

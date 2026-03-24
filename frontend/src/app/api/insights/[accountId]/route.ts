import { NextRequest, NextResponse } from "next/server";

const GRAPH_API = "https://graph.facebook.com/v22.0";

// Fetch Instagram access token from Supabase
async function getAccessToken(instagramUserId: string): Promise<string | null> {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;

  const res = await fetch(
    `${url}/rest/v1/instagram_accounts?select=access_token_encrypted&instagram_user_id=eq.${encodeURIComponent(instagramUserId)}&is_active=eq.true&limit=1`,
    { headers: { apikey: key, Authorization: `Bearer ${key}` } }
  );
  if (!res.ok) return null;
  const rows = (await res.json()) as { access_token_encrypted: string }[];
  return rows[0]?.access_token_encrypted ?? null;
}

// Helper: call Instagram Graph API
async function igFetch(path: string, token: string) {
  const sep = path.includes("?") ? "&" : "?";
  const res = await fetch(`${GRAPH_API}${path}${sep}access_token=${token}`);
  return res.json();
}

// ── User Insights (reach, views, interactions, etc.) ───────────
async function fetchUserInsights(igId: string, token: string, days: number) {
  const now = Math.floor(Date.now() / 1000);
  const since = now - days * 86400;

  const [reachFollowType, viewsMediaType, interactions, followsData, reachTimeSeries] =
    await Promise.all([
      igFetch(`/${igId}/insights?metric=reach&period=day&metric_type=total_value&breakdown=follow_type&since=${since}&until=${now}`, token),
      igFetch(`/${igId}/insights?metric=views&period=day&metric_type=total_value&breakdown=media_product_type&since=${since}&until=${now}`, token),
      igFetch(`/${igId}/insights?metric=total_interactions,likes,comments,saves,shares,reposts,replies&period=day&metric_type=total_value&since=${since}&until=${now}`, token),
      igFetch(`/${igId}/insights?metric=follows_and_unfollows&period=day&metric_type=total_value&breakdown=follow_type&since=${since}&until=${now}`, token),
      igFetch(`/${igId}/insights?metric=reach&period=day&metric_type=time_series&since=${since}&until=${now}`, token),
    ]);

  return {
    reach_by_follow_type: reachFollowType?.data?.[0]?.total_value ?? null,
    views_by_media_type: viewsMediaType?.data?.[0]?.total_value ?? null,
    interactions: Object.fromEntries(
      (interactions?.data ?? []).map((d: { name: string; total_value: { value: number } }) => [
        d.name,
        d.total_value?.value ?? 0,
      ])
    ),
    follows_and_unfollows: followsData?.data?.[0]?.total_value ?? null,
    reach_time_series: (reachTimeSeries?.data?.[0]?.values ?? []).map(
      (v: { end_time: string; value: number }) => ({
        date: v.end_time.slice(0, 10),
        value: v.value,
      })
    ),
  };
}

// ── Demographics ───────────────────────────────────────────────
async function fetchDemographics(igId: string, token: string) {
  const [gender, age, city, country] = await Promise.all([
    igFetch(`/${igId}/insights?metric=follower_demographics&period=lifetime&timeframe=last_30_days&metric_type=total_value&breakdown=gender`, token),
    igFetch(`/${igId}/insights?metric=follower_demographics&period=lifetime&timeframe=last_30_days&metric_type=total_value&breakdown=age`, token),
    igFetch(`/${igId}/insights?metric=follower_demographics&period=lifetime&timeframe=last_30_days&metric_type=total_value&breakdown=city`, token),
    igFetch(`/${igId}/insights?metric=follower_demographics&period=lifetime&timeframe=last_30_days&metric_type=total_value&breakdown=country`, token),
  ]);

  const extractBreakdown = (data: { data?: { total_value?: { breakdowns?: { results?: { dimension_values: string[]; value: number }[] }[] } }[] }) =>
    (data?.data?.[0]?.total_value?.breakdowns?.[0]?.results ?? []).map(
      (r: { dimension_values: string[]; value: number }) => ({
        key: r.dimension_values[0],
        value: r.value,
      })
    );

  return {
    gender: extractBreakdown(gender),
    age: extractBreakdown(age),
    city: extractBreakdown(city).sort((a: { value: number }, b: { value: number }) => b.value - a.value).slice(0, 20),
    country: extractBreakdown(country).sort((a: { value: number }, b: { value: number }) => b.value - a.value).slice(0, 10),
  };
}

// ── Account Profile ────────────────────────────────────────────
async function fetchProfile(igId: string, token: string) {
  return igFetch(
    `/${igId}?fields=id,username,name,biography,followers_count,follows_count,media_count,website,profile_picture_url`,
    token
  );
}

// ── Route Handler ──────────────────────────────────────────────
export async function GET(
  req: NextRequest,
  context: { params: Promise<{ accountId: string }> }
) {
  const { accountId } = await context.params;
  const type = req.nextUrl.searchParams.get("type") ?? "profile";
  const days = parseInt(req.nextUrl.searchParams.get("days") ?? "7", 10);

  const token = await getAccessToken(accountId);
  if (!token) {
    return NextResponse.json(
      { error: "Token not found for account" },
      { status: 404 }
    );
  }

  try {
    let data: unknown;
    switch (type) {
      case "profile":
        data = await fetchProfile(accountId, token);
        break;
      case "insights":
        data = await fetchUserInsights(accountId, token, days);
        break;
      case "demographics":
        data = await fetchDemographics(accountId, token);
        break;
      case "all": {
        const [profile, insights, demographics] = await Promise.all([
          fetchProfile(accountId, token),
          fetchUserInsights(accountId, token, days),
          fetchDemographics(accountId, token),
        ]);
        data = { profile, insights, demographics };
        break;
      }
      default:
        return NextResponse.json({ error: `Unknown type: ${type}` }, { status: 400 });
    }

    return NextResponse.json(data, {
      headers: { "Cache-Control": "private, max-age=300" },
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

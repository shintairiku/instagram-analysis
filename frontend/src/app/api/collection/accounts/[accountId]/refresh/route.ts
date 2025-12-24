import { NextRequest, NextResponse } from "next/server";

type RefreshRequestBody = {
  window_days?: number;
  max_posts?: number;
  force?: boolean;
};

export async function POST(
  req: NextRequest,
  context: { params: Promise<{ accountId: string | string[] | undefined }> }
) {
  const { accountId } = await context.params;
  const accountIdStr = Array.isArray(accountId) ? accountId[0] : accountId;
  if (!accountIdStr) {
    return NextResponse.json({ detail: "accountId is required" }, { status: 400 });
  }

  const backendBaseUrl =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const token = process.env.COLLECTION_TRIGGER_TOKEN;

  if (!token) {
    return NextResponse.json(
      { detail: "COLLECTION_TRIGGER_TOKEN is not configured" },
      { status: 500 }
    );
  }

  let body: RefreshRequestBody = {};
  try {
    body = (await req.json()) as RefreshRequestBody;
  } catch {
    body = {};
  }

  const upstream = await fetch(
    `${backendBaseUrl}/api/v1/collection/accounts/${encodeURIComponent(
      accountIdStr
    )}/refresh`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        window_days: body.window_days ?? 30,
        max_posts: body.max_posts ?? 50,
        dry_run: false,
        force: !!body.force,
      }),
    }
  );

  const retryAfter = upstream.headers.get("Retry-After");
  const headers = new Headers();
  if (retryAfter) headers.set("Retry-After", retryAfter);

  let data: unknown = null;
  try {
    data = await upstream.json();
  } catch {
    data = { detail: upstream.statusText };
  }

  return NextResponse.json(data, { status: upstream.status, headers });
}

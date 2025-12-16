-- Initial schema for shintairiku-ig-4 (Supabase CLI migration)

create extension if not exists "pgcrypto";

-- updated_at trigger helper
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- instagram_accounts
create table public.instagram_accounts (
  id uuid primary key default gen_random_uuid(),
  instagram_user_id varchar(50) not null unique,
  username varchar(100) not null,
  account_name varchar(200),
  profile_picture_url text,
  access_token_encrypted text not null,
  token_expires_at timestamptz,
  facebook_page_id varchar(50),
  is_active boolean not null default true,
  last_synced_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_instagram_accounts_instagram_user_id on public.instagram_accounts(instagram_user_id);
create index idx_instagram_accounts_active on public.instagram_accounts(is_active) where is_active = true;
create index idx_instagram_accounts_created_at on public.instagram_accounts(created_at);

create trigger set_instagram_accounts_updated_at
before update on public.instagram_accounts
for each row execute function public.set_updated_at();

alter table public.instagram_accounts enable row level security;

-- instagram_posts
create table public.instagram_posts (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.instagram_accounts(id) on delete cascade,
  instagram_post_id varchar(50) not null unique,
  media_type varchar(20) not null,
  caption text,
  media_url text,
  thumbnail_url text,
  permalink text,
  posted_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index idx_instagram_posts_account_id on public.instagram_posts(account_id);
create index idx_instagram_posts_instagram_post_id on public.instagram_posts(instagram_post_id);
create index idx_instagram_posts_account_posted on public.instagram_posts(account_id, posted_at desc);
create index idx_instagram_posts_media_type on public.instagram_posts(account_id, media_type);
create index idx_instagram_posts_posted_at on public.instagram_posts(posted_at desc);

alter table public.instagram_posts enable row level security;

-- instagram_post_metrics
create table public.instagram_post_metrics (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.instagram_posts(id) on delete cascade,

  likes integer not null default 0,
  comments integer not null default 0,
  saved integer not null default 0,
  shares integer not null default 0,
  views integer not null default 0,
  reach integer not null default 0,
  total_interactions integer not null default 0,

  follows integer not null default 0,
  profile_visits integer not null default 0,
  profile_activity integer not null default 0,

  video_view_total_time bigint not null default 0,
  avg_watch_time integer not null default 0,

  engagement_rate numeric(5,2) not null default 0,
  recorded_at timestamptz not null default now()
);

create index idx_instagram_post_metrics_post_id on public.instagram_post_metrics(post_id);
create index idx_instagram_post_metrics_recorded_at on public.instagram_post_metrics(recorded_at desc);
create index idx_instagram_post_metrics_engagement_rate on public.instagram_post_metrics(engagement_rate desc);
create index idx_instagram_post_metrics_likes on public.instagram_post_metrics(likes desc);
create index idx_instagram_post_metrics_reach on public.instagram_post_metrics(reach desc);

alter table public.instagram_post_metrics enable row level security;

-- instagram_daily_stats (simplified)
create table public.instagram_daily_stats (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.instagram_accounts(id) on delete cascade,
  stats_date date not null,

  followers_count integer not null default 0,
  following_count integer not null default 0,
  media_count integer not null default 0,

  posts_count integer not null default 0,
  total_likes integer not null default 0,
  total_comments integer not null default 0,

  media_type_distribution text,
  data_sources text,

  created_at timestamptz not null default now(),

  constraint uq_account_daily_stats unique (account_id, stats_date)
);

create index idx_daily_stats_account_id on public.instagram_daily_stats(account_id);
create index idx_daily_stats_date on public.instagram_daily_stats(stats_date);
create index idx_daily_stats_followers on public.instagram_daily_stats(followers_count);

alter table public.instagram_daily_stats enable row level security;

-- instagram_monthly_stats
create table public.instagram_monthly_stats (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.instagram_accounts(id) on delete cascade,
  stats_month date not null,

  avg_followers_count integer not null default 0,
  avg_following_count integer not null default 0,

  follower_growth integer not null default 0,
  follower_growth_rate numeric(5,2) not null default 0.0,

  total_posts integer not null default 0,
  total_likes integer not null default 0,
  total_comments integer not null default 0,
  total_reach integer not null default 0,
  avg_engagement_rate numeric(5,2) not null default 0.0,

  best_performing_day date,
  engagement_trend text,
  content_performance text,

  created_at timestamptz not null default now(),

  constraint uq_account_monthly_stats unique (account_id, stats_month)
);

create index idx_monthly_stats_account_id on public.instagram_monthly_stats(account_id);
create index idx_monthly_stats_month on public.instagram_monthly_stats(stats_month);
create index idx_monthly_stats_followers on public.instagram_monthly_stats(avg_followers_count);
create index idx_monthly_stats_growth on public.instagram_monthly_stats(follower_growth_rate);
create index idx_monthly_stats_engagement on public.instagram_monthly_stats(avg_engagement_rate);

alter table public.instagram_monthly_stats enable row level security;

-- Optional: view + function for reporting (kept from existing design)
create or replace view public.monthly_stats_summary as
select
  to_char(ms.stats_month, 'YYYY-MM') as month_year,
  acc.username,
  ms.avg_followers_count,
  ms.follower_growth,
  ms.follower_growth_rate,
  ms.total_posts,
  ms.total_likes,
  ms.total_comments,
  ms.total_reach,
  ms.avg_engagement_rate,
  ms.best_performing_day,
  ms.created_at
from public.instagram_monthly_stats ms
join public.instagram_accounts acc on ms.account_id = acc.id
order by ms.stats_month desc, acc.username;

create or replace function public.calculate_yoy_growth(
  p_account_id uuid,
  p_target_month date
) returns table (
  follower_growth_yoy numeric(5,2),
  engagement_growth_yoy numeric(5,2),
  posts_growth_yoy numeric(5,2)
) language plpgsql as $$
declare
  current_stats record;
  previous_stats record;
begin
  select * into current_stats
  from public.instagram_monthly_stats
  where account_id = p_account_id
    and stats_month = date_trunc('month', p_target_month)::date;

  select * into previous_stats
  from public.instagram_monthly_stats
  where account_id = p_account_id
    and stats_month = date_trunc('month', (p_target_month - interval '1 year'))::date;

  if current_stats is null or previous_stats is null then
    return query select 0.0::numeric(5,2), 0.0::numeric(5,2), 0.0::numeric(5,2);
  else
    return query select
      case
        when previous_stats.avg_followers_count > 0 then
          round(((current_stats.avg_followers_count - previous_stats.avg_followers_count)::numeric / previous_stats.avg_followers_count * 100), 2)
        else 0.0
      end::numeric(5,2),
      case
        when previous_stats.avg_engagement_rate > 0 then
          round(((current_stats.avg_engagement_rate - previous_stats.avg_engagement_rate) / previous_stats.avg_engagement_rate * 100), 2)
        else 0.0
      end::numeric(5,2),
      case
        when previous_stats.total_posts > 0 then
          round(((current_stats.total_posts - previous_stats.total_posts)::numeric / previous_stats.total_posts * 100), 2)
        else 0.0
      end::numeric(5,2);
  end if;
end;
$$;


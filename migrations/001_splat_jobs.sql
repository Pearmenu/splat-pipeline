-- Splat pipeline (video → .splat) job tracking.
-- Isolated table — removing the feature is just: drop table public.splat_jobs cascade;
-- Server routes use the service role (RLS bypassed); the policy below is a safety
-- net so only admins/staff can ever read these rows via the anon key.

create table if not exists public.splat_jobs (
  id             uuid primary key default gen_random_uuid(),
  restaurant_id  uuid not null references public.restaurants (id) on delete cascade,
  user_id        uuid not null references auth.users (id) on delete cascade,
  name           text not null,
  status         text not null default 'created'
                 check (status in ('created','uploading','queued','processing','ready','error')),
  video_key      text,
  video_url      text,
  splat_url      text,
  ply_url        text,
  model_id       uuid references public.models (id) on delete set null,
  runpod_id      text,
  callback_token text not null,
  gaussians      integer,
  error          text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index if not exists splat_jobs_restaurant_idx on public.splat_jobs (restaurant_id);
create index if not exists splat_jobs_status_idx on public.splat_jobs (status);

alter table public.splat_jobs enable row level security;

drop policy if exists splat_jobs_admin_all on public.splat_jobs;
create policy splat_jobs_admin_all on public.splat_jobs
  for all
  using (
    exists (
      select 1 from public.profiles p
      where p.user_id = auth.uid() and p.role in ('admin','staff')
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.user_id = auth.uid() and p.role in ('admin','staff')
    )
  );

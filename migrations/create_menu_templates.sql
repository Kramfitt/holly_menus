-- Drop existing table if it exists
drop table if exists public.menu_templates;

-- Create table with updated constraints
create table if not exists public.menu_templates (
    id uuid default uuid_generate_v4() primary key,
    season text not null check (season in ('summer', 'winter', 'dates')),
    week integer not null check (
        (season = 'dates' and week = 0) or
        (season in ('summer', 'winter') and week between 1 and 4)
    ),
    file_path text not null,
    template_url text not null,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique(season, week)
);

-- Add indexes for performance
create index idx_menu_templates_season_week on public.menu_templates(season, week);
create index idx_menu_templates_created_at on public.menu_templates(created_at desc); 
create table if not exists public.menu_templates (
    id uuid default uuid_generate_v4() primary key,
    season text not null check (season in ('summer', 'winter')),
    week integer not null check (week between 1 and 4),
    template_url text not null,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique(season, week)
); 
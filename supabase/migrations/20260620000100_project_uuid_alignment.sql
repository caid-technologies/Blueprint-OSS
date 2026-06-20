-- Enforce canonical UUID project ids and keep stored IR/Supabase Storage metadata aligned.

create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;

alter table public.generated_projects
  alter column project_id set default extensions.gen_random_uuid()::text;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'generated_projects_project_id_uuid_text'
      and conrelid = 'public.generated_projects'::regclass
  ) then
    alter table public.generated_projects
      add constraint generated_projects_project_id_uuid_text
      check (
        project_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
      )
      not valid;
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'generated_projects_hardware_ir_project_id_matches'
      and conrelid = 'public.generated_projects'::regclass
  ) then
    alter table public.generated_projects
      add constraint generated_projects_hardware_ir_project_id_matches
      check (
        hardware_ir #>> '{assembly_metadata,project_id}' is null
        or hardware_ir #>> '{assembly_metadata,project_id}' = project_id
      )
      not valid;
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'generated_projects_image_keys_match_project_id'
      and conrelid = 'public.generated_projects'::regclass
  ) then
    alter table public.generated_projects
      add constraint generated_projects_image_keys_match_project_id
      check (
        (
          hardware_ir #>> '{assembly_metadata,reference_image_s3_key}' is null
          or hardware_ir #>> '{assembly_metadata,reference_image_s3_key}' like ('images/' || project_id || '/%')
        )
        and (
          hardware_ir #>> '{assembly_metadata,product_image_s3_key}' is null
          or hardware_ir #>> '{assembly_metadata,product_image_s3_key}' like ('images/' || project_id || '/%')
        )
      )
      not valid;
  end if;
end $$;

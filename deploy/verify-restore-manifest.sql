-- psql -XqAt -v ON_ERROR_STOP=1 -f verify-restore-manifest.sql
-- Run against a stable source snapshot and its restore. Prints counts and SHA-256 only.
\set ON_ERROR_STOP on
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL TIME ZONE 'UTC';
SET LOCAL bytea_output = 'hex';
SET LOCAL DateStyle = 'ISO, YMD';

-- Hash each complete canonical row, then hash its table's sorted, fixed-length row hashes.
-- Include empty tables, archived rows, attachment bytea, ACLs and polymorphic links.
SELECT format(
    'SELECT %L, count(*), encode(sha256(convert_to(coalesce(string_agg(h, '''' ORDER BY h COLLATE "C"), ''''), ''UTF8'')), ''hex'')
       FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text, ''UTF8'')), ''hex'') AS h FROM %I.%I AS t) AS rows',
    tablename, schemaname, tablename)
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename COLLATE "C"
\gexec
COMMIT;

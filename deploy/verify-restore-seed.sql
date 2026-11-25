-- Synthetic fixtures for the disposable PostgreSQL CI service only.
\set ON_ERROR_STOP on
BEGIN;
CREATE FUNCTION pg_temp.fixture_id(n integer) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT '70570000-0000-4000-8000-' || lpad(n::text, 12, '0')
$$;
INSERT INTO users (id, account_type, nickname) VALUES
    (pg_temp.fixture_id(1), 'google', 'Organizer'),
    (pg_temp.fixture_id(2), 'guest', 'File author'),
    (pg_temp.fixture_id(3), 'guest', 'Authorized reader');
INSERT INTO trips
    (id, owner_id, title, description, destinations, cover, currency, status, archived, created_at, version)
VALUES
    (pg_temp.fixture_id(10), pg_temp.fixture_id(1), 'Attachment restore fixture', '',
     '["Taipei"]', '', 'TWD', 'planning', false, '2026-01-01T00:00Z', 1);
INSERT INTO trip_members (id, trip_id, user_id, role, joined_at)
SELECT pg_temp.fixture_id(10+n), pg_temp.fixture_id(10), pg_temp.fixture_id(n),
       CASE WHEN n=1 THEN 'owner' ELSE 'member' END, '2026-01-01T00:00Z'::timestamptz
FROM generate_series(1,3) AS n;
INSERT INTO trip_days (id, trip_id, day_number, title, timezone)
VALUES (pg_temp.fixture_id(20), pg_temp.fixture_id(10), 1, 'Departure', 'Asia/Taipei');
INSERT INTO itinerary_items
    (id, trip_id, day_id, created_by, editable_by, title, item_type, position, notes, version)
VALUES
    (pg_temp.fixture_id(21), pg_temp.fixture_id(10), pg_temp.fixture_id(20),
     pg_temp.fixture_id(2), pg_temp.fixture_id(2), 'Museum visit', 'custom', 0, '', 1);
WITH documents (n, name, mime, payload, preview, removed_at) AS (VALUES
    (31, 'museum.png', 'image/png',
     decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4R8AAAAASUVORK5CYII=', 'base64'),
     '', NULL::timestamptz),
    (32, 'previous.txt', 'text/plain', convert_to(E'recycled fixture\n', 'UTF8'),
     E'recycled fixture\n', '2026-01-02T00:00Z'::timestamptz)
)
INSERT INTO files (id, trip_id, owner_id, filename, mime, category, size, private, data,
                   preview_text, version, created_at, removed_at)
SELECT pg_temp.fixture_id(n), pg_temp.fixture_id(10), pg_temp.fixture_id(2), name, mime,
       'Restore fixture', octet_length(payload), true, payload, preview,
       CASE WHEN removed_at IS NULL THEN 1 ELSE 2 END, '2026-01-01T00:00Z', removed_at
FROM documents;
INSERT INTO file_permissions (id, file_id, user_id) VALUES
    (pg_temp.fixture_id(41), pg_temp.fixture_id(31), pg_temp.fixture_id(3)),
    (pg_temp.fixture_id(42), pg_temp.fixture_id(32), pg_temp.fixture_id(3));
INSERT INTO file_links (id, file_id, kind, target_id) VALUES
    (pg_temp.fixture_id(51), pg_temp.fixture_id(31), 'trip', pg_temp.fixture_id(10)),
    (pg_temp.fixture_id(52), pg_temp.fixture_id(31), 'item', pg_temp.fixture_id(21)),
    (pg_temp.fixture_id(53), pg_temp.fixture_id(32), 'trip', pg_temp.fixture_id(10));
COMMIT;

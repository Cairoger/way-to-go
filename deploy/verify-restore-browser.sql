-- Assert the private image actually uploaded by frontend/tests/live-files.spec.ts survived.
\set ON_ERROR_STOP on
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM files AS f
        JOIN file_links AS link ON link.file_id = f.id AND link.kind = 'booking'
        JOIN bookings AS b ON b.id = link.target_id AND b.trip_id = f.trip_id
        WHERE f.filename = 'PRIVATEFILE771.png'
          AND f.private AND f.removed_at IS NULL
          AND f.mime = 'image/png' AND f.size = octet_length(f.data) AND f.size = 69
          AND encode(sha256(f.data), 'hex') =
              'd3a67710b6bcc7b5cb13cfa10d2fd256d372a44903e1c4056f00fabba1a073c0'
          AND NOT EXISTS (SELECT 1 FROM file_permissions AS grants WHERE grants.file_id = f.id)
    ) THEN
        RAISE EXCEPTION 'Browser-uploaded private booking attachment, payload or ACL missing from restored database';
    END IF;
END;
$$;

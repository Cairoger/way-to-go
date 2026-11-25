#!/bin/sh
set -eu
umask 077
export LC_ALL=C

restore_archive() {
    archive=$1
    work=$(mktemp -d /tmp/waytogo-restore.XXXXXX)
    export PGHOST="$work" PGUSER=waytogo PGDATABASE=restore_check
    cleanup() {
        if [ -f "$work/data/postmaster.pid" ]; then
            gosu postgres pg_ctl -D "$work/data" -m fast -w stop >/dev/null || return 1
        fi
        rm -r "$work"
    }
    trap cleanup EXIT
    trap 'exit 1' INT TERM
    chown postgres:postgres "$work"
    gosu postgres initdb -D "$work/data" -U "$PGUSER" --encoding=UTF8 --locale=C \
        --auth-local=trust --auth-host=reject >/dev/null
    gosu postgres pg_ctl -D "$work/data" -l "$work/server.log" \
        -o "-c listen_addresses='' -c unix_socket_directories='$work'" -w start >/dev/null
    createdb --template=template0 "$PGDATABASE"
    if ! pg_restore --exit-on-error --single-transaction --dbname="$PGDATABASE" "$archive" 2>"$work/restore.log"; then
        echo "ERROR: pg_restore failed for ${archive##*/}." >&2
        exit 1
    fi
    # Restoring post-data recreates the foreign keys and checks them against the loaded rows.
    # Report aggregate counts only. Some retained archives predate the attachment tables.
    if ! summary=$(psql -XqAt -v ON_ERROR_STOP=1 2>"$work/check.log" <<'SQL'
DO $$
BEGIN
    IF (SELECT count(*) FROM alembic_version) <> 1 OR EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE connamespace = 'public'::regnamespace AND NOT convalidated
    ) THEN
        RAISE EXCEPTION 'Invalid schema version or constraints';
    END IF;
    IF to_regclass('public.files') IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM files WHERE size <> octet_length(data)) THEN
            RAISE EXCEPTION 'Attachment size mismatch';
        END IF;
    END IF;
END $$;
SELECT 'revision=' || version_num ||
       ' tables=' || (SELECT count(*) FROM pg_tables WHERE schemaname = 'public') ||
       ' constraints=' || (SELECT count(*) FROM pg_constraint WHERE connamespace = 'public'::regnamespace) ||
       ' users=' || (SELECT count(*) FROM users) ||
       ' trips=' || (SELECT count(*) FROM trips) ||
       ' memberships=' || (SELECT count(*) FROM trip_members)
FROM alembic_version;
SQL
    ); then
        echo "ERROR: post-restore validation failed for ${archive##*/}." >&2
        exit 1
    fi
    echo "Restore verified: ${archive##*/} $summary"
}

case "${1:-watch}" in
    --archive)
        restore_archive "${2:?Supply the archive path inside /backup}"
        ;;
    --all)
        found=0
        for archive in /backup/waytogo-[0-9]*T[0-9]*Z.dump; do
            [ -f "$archive" ] || continue
            found=1
            sh "$0" --archive "$archive"
        done
        [ "$found" -eq 1 ] || { echo "No scheduled backup available." >&2; exit 1; }
        ;;
    watch)
        last_verified=''
        while true; do
            latest=''
            for archive in /backup/waytogo-[0-9]*T[0-9]*Z.dump; do
                [ ! -f "$archive" ] || latest=$archive
            done
            if [ -n "$latest" ] && [ "$latest" != "$last_verified" ]; then
                if sh "$0" --archive "$latest"; then last_verified=$latest; fi
            fi
            sleep 3600
        done
        ;;
    *) echo "Usage: restore-drill.sh [--archive PATH | --all]" >&2; exit 2 ;;
esac

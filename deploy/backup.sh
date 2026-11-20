#!/bin/sh
set -eu
umask 077
while true; do
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    partial="/backup/waytogo-$stamp.partial"
    final="/backup/waytogo-$stamp.dump"
    if pg_dump --format=custom --file="$partial" && pg_restore --list "$partial" >/dev/null; then
        mv "$partial" "$final"
        find /backup -maxdepth 1 -name 'waytogo-*.dump' -type f -mmin +10080 -delete
        echo "Backup ready: $stamp"
    else
        echo "ERROR: database backup failed; check PostgreSQL and free space." >&2
        exit 1
    fi
    free_kb=$(df -Pk /backup | awk 'NR==2 {print $4}')
    if [ "$free_kb" -lt 524288 ]; then echo "WARNING: less than 512 MiB available in /backup" >&2; fi
    sleep 86400
done

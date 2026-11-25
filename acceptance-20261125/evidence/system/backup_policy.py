"""Exercise unmodified backup.sh in a disposable container, simulating the clock and disk space."""
import secrets,tempfile
from pathlib import Path
from run_system import repo,run
with tempfile.TemporaryDirectory(prefix="wtg-backup-") as t:
    root=Path(t)
    (root/"compose.yaml").write_text('services:\n  audit:\n    image: postgres:17-alpine\n    volumes:\n      - "'+(repo/"deploy/backup.sh").as_posix()+':/backup-verify.sh:ro"\n',encoding="utf8")
    cli=[repo/".local/docker-compose-v2.exe","-f",root/"compose.yaml","-p","backupqa"+secrets.token_hex(6)]
    script="""set -eu
mkdir /backup /sim
touch -t 202001010000 /backup/waytogo-old.dump
touch /backup/waytogo-recent.dump
printf '#!/bin/sh\\nfor a in "$@"; do case "$a" in --file=*) f=$(echo "$a" | cut -c8-); echo synthetic > "$f";; esac; done\\n' > /sim/pg_dump
printf '#!/bin/sh\\nexit 0\\n' > /sim/pg_restore
printf '#!/bin/sh\\necho "filesystem 1K-blocks used available capacity mount"; echo "qa 999999 999995 4 99%% /backup"\\n' > /sim/df
printf '#!/bin/sh\\necho "Requested interval: $1"; exit 42\\n' > /sim/sleep
chmod +x /sim/*
set +e
PATH=/sim:$PATH sh /backup-verify.sh
code=$?
set -e
echo "scheduled stop: $code"
test "$code" = 42
test ! -f /backup/waytogo-old.dump
test -f /backup/waytogo-recent.dump
echo "Expired removed; recent retained; files:"
ls -1 /backup
"""
    try:
        rc=run("backup-policy",cli+["run","--rm","-T","--entrypoint","sh","audit","-c",script],root)
        if rc:raise SystemExit(rc)
    finally:run("backup-policy-clean",cli+["down","--volumes"],root)

"""Run a fresh build under a random Compose project; touches only its own containers/volume."""
from run_system import repo, out, source_paths, stage, run, freeport, env
from pathlib import Path
import json, os, secrets, subprocess, sys, tempfile, time, urllib.request
with tempfile.TemporaryDirectory(prefix="wtg-compose-") as temp:
    root=Path(temp)
    stage(root,source_paths())
    port=freeport()
    project="wtgaudit"+secrets.token_hex(8)
    cli=[str(repo/".local/docker-compose-v2.exe"),"--project-directory",str(root),"-f",str(root/"compose.yaml"),"-p",project]
    run("docker-init",[sys.executable,"deploy/init_env.py"],root,required=True)
    config=(root/".env").read_text(encoding="utf8")
    cfg=dict(env,HTTP_PORT=str(port),PUBLIC_ORIGIN=f"http://127.0.0.1:{port}",BACKUP_DIR=str(root/"backups"),BIND_ADDRESS="127.0.0.1")
    (root/"backups").mkdir()
    def dc(name,*args,required=True):
        return run("docker-"+name,cli+list(args),root,cfg,required)
    try:
        dc("up","up","-d","--build","--wait","--wait-timeout","180")
        dc("services","ps","--format","table {{.Service}}\t{{.State}}\t{{.Health}}")
        data={}
        for route in ["/","/docs","/openapi.json","/health","/manifest.webmanifest"]:
            with urllib.request.urlopen(cfg["PUBLIC_ORIGIN"]+route,timeout=12) as r:
                content=r.read()
                data[route]=[r.status,r.headers["Content-Type"],len(content),content[:60].decode("utf8","ignore")]
        (out/"docker-http.json").write_text(json.dumps(data,indent=2),encoding="utf8")
        dc("pgversion","exec","-T","db","postgres","--version")
        dc("alembic","exec","-T","api","alembic","current")
        # Seed without printing a usable invite token.
        dc("seed","exec","-T","api","python","-c","from seed_demo import seed_demo; print('seeded trip',seed_demo()['trip_id'])")
        def checks(label):
            dc(label,"exec","-T","db","psql","-U","waytogo","-d","waytogo","-Atc","select (select count(*) from trips),(select count(*) from itinerary_items)")
        checks("before-restart")
        dc("recreate","up","-d","--force-recreate","--wait","db","api","frontend","web","backup")
        checks("after-restart")
        (out/"docker-backup-files.txt").write_text("\n".join(f"{f.name}: {f.stat().st_size} bytes" for f in (root/"backups").glob("*.dump")),encoding="utf8")
        dc("backup-log","logs","--no-color","backup")
        # Restore the newest backup created by the actual backup service on this private project.
        dumps=sorted((root/"backups").glob("*.dump"))
        if dumps:
            dc("create-restore","exec","-T","db","createdb","-U","waytogo","qa_restore")
            dc("restore-cp","cp",str(dumps[-1]),"db:/tmp/qa.dump")
            dc("restore","exec","-T","db","pg_restore","--exit-on-error","-U","waytogo","-d","qa_restore","/tmp/qa.dump")
            dc("restored-counts","exec","-T","db","psql","-U","waytogo","-d","qa_restore","-Atc","select (select count(*) from trips),(select count(*) from itinerary_items)")
    finally:
        dc("down","down","--volumes","--rmi","local",required=False)

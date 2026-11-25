"""Run from any directory with this checkout's .venv Python. Uses a fresh cluster and source copy."""
import asyncio
import hashlib
from importlib.metadata import version
import json
import math
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

out = Path(__file__).resolve().parent
repo = out.parents[2]
pgbin = repo / ".local/pgtools/pgserver/pginstall/bin"
pgctl = pgbin / "pg_ctl.exe"
python = sys.executable
env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
for key in ("TEST_DATABASE_URL","DATABASE_URL","GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","LOCAL_TEST_USERNAME","LOCAL_TEST_PASSWORD_HASH","PGPASSWORD","PGHOST","PGPORT","PGUSER","PGSERVICE","VAPID_PRIVATE_KEY"):
    env.pop(key,None)

def run(name,args,cwd,local_env=None,required=False):
    log=out/(name+".txt")
    with log.open("wb") as stream:
        proc = subprocess.run(list(map(str,args)),cwd=cwd,env=local_env or env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=480)
    msg=log.read_bytes().decode("utf8","replace").replace("\r\r\n","\n").replace("\r\n","\n")
    log.write_text(msg+f"\nexit={proc.returncode}\n",encoding="utf8")
    print(name, proc.returncode,flush=True)
    if required and proc.returncode:
        raise RuntimeError(name)
    return proc.returncode

def git(*args):
    return subprocess.check_output(["git","-C",str(repo),*args]).decode("utf8").splitlines()

def source_paths():
    return git("ls-files")

def fingerprint():
    return {p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in sorted(source_paths())}

def writejson(name,data):
    (out/(name+".json")).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")

def freeport():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]

def stage(root,paths):
    for p in paths:
        target=root/p
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(repo/p,target)

def compose(root):
    runner=repo/".local/docker-compose-v2.exe"
    settings=root/"isolation.env"
    settings.write_text("POSTGRES_PASSWORD="+secrets.token_hex(32)+"\nHTTP_PORT="+str(freeport())+"\nBACKUP_DIR=./audit-backup\n",encoding="utf8")
    cli=[runner,"--env-file",settings,"-f",root/"compose.yaml","-p","wtgaudit"+secrets.token_hex(4)]
    run("compose-version",[runner,"version"],root)
    run("compose-config",cli+["config","--quiet"],root)
    run("compose-services",cli+["config","--services"],root)
    run("compose-daemon",cli+["ps","-q"],root)

async def measure(origin,trip,invite):
    import httpx, websockets
    clients=[httpx.AsyncClient(base_url=origin,headers={"Origin":origin},trust_env=False) for _ in range(5)]
    sockets=[]; reads=[]; events=[]
    path="/api/v1/trips/"+trip
    try:
        for i,c in enumerate(clients):
            r=await c.post("/api/v1/auth/guest",json={"code":invite,"nickname":f"observer {i}"})
            r.raise_for_status()
            sockets.append(await websockets.connect(origin.replace("http://","ws://")+"/ws/trips/"+trip,origin=origin,additional_headers={"Cookie":"wtg_session="+c.cookies["wtg_session"]},proxy=None))
        async def read(c):
            for suffix in ["/days","/places","/comments","/polls"]*3:
                start=time.perf_counter()
                (await c.get(path+suffix)).raise_for_status()
                reads.append(round((time.perf_counter()-start)*1000,2))
        await asyncio.gather(*(read(c) for c in clients))
        for i in range(12):
            start=time.perf_counter()
            r=await clients[i%5].post(path+"/comments",json={"content":f"event-{i}"})
            r.raise_for_status()
            async def observe(c,s):
                while json.loads(await asyncio.wait_for(s.recv(),8)).get("id")!=r.json()["id"]:
                    pass
                got=await c.get(path+"/comments")
                assert r.json()["id"] in [row["id"] for row in got.json()]
                events.append(round((time.perf_counter()-start)*1000,2))
            await asyncio.gather(*(observe(c,s) for c,s in zip(clients,sockets)))
        writejson("latency",{"clients":5,"members_including_seed_owner":6,"network":"loopback, Uvicorn / PostgreSQL; elapsed through refetch, excludes paint","percentile":"nearest rank","read_ms":reads,"read_p95":sorted(reads)[math.ceil(.95*len(reads))-1],"event_to_read_ms":events,"event_to_read_p95":sorted(events)[math.ceil(.95*len(events))-1]})
    finally:
        for s in sockets: await s.close()
        for c in clients: await c.aclose()

def inspect_runtime(root,pg_env):
    code=out/"inspect_runtime.py"
    run("inspect-runtime",[python,code,out],root/"backend",dict(pg_env,PYTHONPATH=str(root/"backend")),True)

def main():
    before=fingerprint()
    writejson("source-sha256",before)
    status=[x for x in git("status","--short","--branch","--untracked-files=all") if not any(w in x for w in ("acceptance-20261125/","acceptance-retest-cada651/"))]
    (out/"git-before.txt").write_text("\n".join(status+git("remote","-v")+git("rev-parse","HEAD"))+"\n",encoding="utf8")
    packages={p:version(p) for p in ["fastapi","sqlalchemy","psycopg","alembic","pytest","websockets","starlette","anyio","httpx"]}
    writejson("system-run-environment",{"platform":platform.platform(),"python":sys.version,"packages":packages,"spec_sha256":before["docs/spec.md"],"cwd":str(repo),"tracked_modified":sum(x.startswith(" M") for x in status),"untracked_source":sum(x.startswith("??") for x in status)})
    with tempfile.TemporaryDirectory(prefix="wtg-sys-",dir=repo/".local") as td:
        root=Path(td)
        stage(root,before)
        b=root/"backend"
        compose(root)
        run("sqlite-suite",[python,"-m","pytest","-v","-p","no:cacheprovider","--basetemp",root/"sql-tests"],b)
        for args,name in [(["check","."],"ruff"),(["format","--check","."],"format")]:
            run(name,[python,"-m","ruff",*args],b)
        port=freeport()
        passwd=secrets.token_hex(24)
        pwdfile=root/"pgpass"
        pwdfile.write_text(passwd,encoding="ascii")
        d=root/"pg"
        run("pg-version",[pgbin/"postgres","--version"],root)
        run("initdb",[pgbin/"initdb","-D",d,"-U","tester","-A","scram-sha-256","--pwfile",pwdfile,"--locale=C","--encoding=UTF8"],root,required=True)
        # Use only the previously unused temporary data directory and a loopback listener.
        run("pg-start",[pgctl,"-D",d,"-o",f"-h 127.0.0.1 -p {port}","-l",root/"postgres.log","-w","start"],root,required=True)
        try:
            pg_env=dict(env,PGHOST="127.0.0.1",PGPORT=str(port),PGUSER="tester",PGPASSWORD=passwd)
            url=f"postgresql+psycopg://tester:{passwd}@127.0.0.1:{port}/audit"
            ap=freeport(); origin=f"http://127.0.0.1:{ap}"
            pg_env.update(INVITATION_SIGNING_KEY=secrets.token_hex(32),DATABASE_URL=url,TEST_DATABASE_URL=url,PUBLIC_ORIGIN=origin,WIKI_API_URL="",OPEN_METEO_URL="",FRANKFURTER_URL="")
            for name in ("audit","audit_restore"):
                run("create-"+name,[pgbin/"createdb",name],root,pg_env,True)
            run("migrate",[python,"-m","alembic","upgrade","head"],b,pg_env,True)
            run("alembic-check",[python,"-m","alembic","check"],b,pg_env)
            run("postgres-suite",[python,"-m","pytest","-v","-p","no:cacheprovider","--basetemp",root/"pg-tests"],b,pg_env)
            inspect_runtime(root,pg_env)
            seed_code="import json; from seed_demo import seed_demo; print(json.dumps(seed_demo()))"
            seed=json.loads(subprocess.check_output([python,"-c",seed_code],cwd=b,env=pg_env))
            from urllib.parse import urlsplit,parse_qs
            invite=parse_qs(urlsplit(seed["url"]).query)["invite"][0]
            import httpx
            with open(root/"api.log","w") as stream:
                svc=subprocess.Popen([python,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port",str(ap),"--no-access-log"],cwd=b,env=pg_env,stdout=stream,stderr=stream)
                try:
                    for _ in range(80):
                        try:
                            if httpx.get(origin+"/health",trust_env=False).is_success:break
                        except httpx.HTTPError:pass
                        time.sleep(.25)
                    asyncio.run(measure(origin,seed["trip_id"],invite))
                finally:
                    svc.terminate();svc.wait(timeout=20)
            dump=root/"audit.dump"
            run("backup",[pgbin/"pg_dump","-Fc","-f",dump,"audit"],root,pg_env,True)
            run("restore",[pgbin/"pg_restore","--exit-on-error","-d","audit_restore",dump],root,pg_env,True)
            for dbname in ("audit","audit_restore"):
                run("counts-"+dbname,[pgbin/"psql","-At","-d",dbname,"-c","select version_num,(select count(*) from trips),(select count(*) from trip_members),(select count(*) from comments),(select count(*) from itinerary_items) from alembic_version"],root,pg_env,True)
        finally:
            run("pg-stop",[pgctl,"-D",d,"-m","fast","-w","stop"],root)
    assert fingerprint()==before

if __name__=="__main__":
    main()

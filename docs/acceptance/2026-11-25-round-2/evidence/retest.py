"""Second independent audit. Every runtime directory, account, port and database is disposable."""
from pathlib import Path
from datetime import datetime, timezone
import os, sys, json, re, subprocess as sp, shutil, io, zipfile, hashlib, secrets, socket, base64, time
R=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
ART=OUT.parent
LAB=R/".local"/ART.name
SRC=LAB/"source"
API=SRC/"backend"
WEB=SRC/"frontend"
PY=Path(sys.executable)
NODE=shutil.which("node")
OLD=R/"acceptance-20261125/evidence"
DC=R/".local/docker-compose-v2.exe"
CHROME=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
EDGE=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8", NEXT_TELEMETRY_DISABLED="1", NO_COLOR="1", PLAYWRIGHT_BROWSERS_PATH=str(R/".local/validation-browsers"))
for key in ["DATABASE_URL","TEST_DATABASE_URL","GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","VAPID_PRIVATE_KEY","LOCAL_TEST_PASSWORD_HASH","LOCAL_TEST_USERNAME","PGPASSWORD","PGHOST","PGPORT","PGUSER","PGSERVICE","PUBLIC_ORIGIN","INVITATION_SIGNING_KEY","E2E_POSTGRES_TEST_URL"]:
    env.pop(key,None)
def write(name,data): 
    path=OUT/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
def cfg():return json.loads((LAB/"runtime.json").read_text(encoding="utf-8"))
def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        return s.getsockname()[1]
def capture(args,cwd=R,ev=None):
    return sp.check_output(list(map(str,args)),cwd=cwd,env=ev or env).decode("utf-8","replace").strip()
def run(name,args,cwd=R,ev=None,timeout=900,stdin=None,check=False):
    beg=time.time()
    fp=OUT/(name+".txt"); fp.parent.mkdir(parents=True,exist_ok=True)
    with fp.open("w",encoding="utf-8") as f:
        f.write("cwd="+str(cwd)+"\ncommand="+sp.list2cmdline(list(map(str,args)))+"\n");f.flush()
        try:
            res=sp.run(list(map(str,args)),cwd=cwd,env=ev or env,input=stdin,stdout=f,stderr=sp.STDOUT,timeout=timeout)
            rc=res.returncode
        except (OSError,sp.TimeoutExpired) as exc:
            rc=124;f.write("\n"+str(exc)+"\n")
        f.write(f"\nexit={rc} elapsed={time.time()-beg:.2f}s\n")
    print(name,rc,flush=True)
    if check and rc:raise RuntimeError(name)
    return rc
def stage():
    if LAB.exists():raise RuntimeError("This audit staging folder already exists")
    LAB.mkdir(parents=True);SRC.mkdir()
    for f in ["system","core","modules","browser"]:(OUT/f).mkdir(exist_ok=True)
    archive=sp.check_output(["git","archive","--format=zip","HEAD"],cwd=R)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:z.extractall(SRC)
    paths=capture(["git","ls-files"]).splitlines()
    write("system/source-hashes.json",{p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths})
    refs=capture(["git","show-ref","--heads"])
    conf=(R/".env").read_text(encoding="utf-8-sig") if (R/".env").is_file() else ""
    google=all(bool(re.search("^"+k+r"=(?!\s*$).+",conf,re.M) or env.get(k) or os.getenv(k)) for k in ["GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET"])
    from importlib.metadata import version
    import platform
    write("system/environment.json",dict(date=datetime.now().astimezone().isoformat(),head=capture(["git","rev-parse","HEAD"]),branch=capture(["git","branch","--show-current"]),remote=capture(["git","remote","get-url","origin"]),refs=refs,tracked=len(paths),tracked_diff=capture(["git","diff","--stat","HEAD"]),spec_hash=hashlib.sha256((SRC/"docs/spec.md").read_bytes()).hexdigest(),google_configured=google,os=platform.platform(),python=sys.version,packages={k:version(k) for k in ["fastapi","sqlalchemy","psycopg","alembic","pytest","websockets","pypdf","httpx"]},node=capture([NODE,"-v"])))
    with (OUT/"system/git-initial.txt").open("w",encoding="utf-8") as f:
        f.write(capture(["git","status","--short","--branch"])+"\n"+refs+"\n")
    # Dependencies already installed in the workspace. Test outputs stay in the staging directory.
    sp.run(["powershell","-NoProfile","-Command","New-Item -ItemType Junction -Path $env:WTG_DEST -Target $env:WTG_SOURCE | Out-Null"],env=env|{"WTG_DEST":str(WEB/"node_modules"),"WTG_SOURCE":str(R/"frontend/node_modules")},check=True)
    ps=set()
    while len(ps)<3:ps.add(port())
    ports=sorted(ps)
    sys.path.insert(0,str(SRC/"deploy"))
    from create_test_login import provision
    sp.run([str(PY),"deploy/init_env.py"],cwd=SRC,env=env,stdout=sp.DEVNULL,check=True)
    pw=provision(SRC/".env")
    from cryptography.hazmat.primitives.asymmetric import ec
    vapid=base64.urlsafe_b64encode(ec.generate_private_key(ec.SECP256R1()).private_numbers().private_value.to_bytes(32,"big")).decode().rstrip("=")
    private=dict(origin=f"http://127.0.0.1:{ports[0]}",sqliteorigin=f"http://127.0.0.1:{ports[1]}",upstream=f"http://127.0.0.1:{ports[2]}",ports=ports,username="tester",password=pw,project="wtgrerun"+secrets.token_hex(5),vapid=vapid)
    (LAB/"runtime.json").write_text(json.dumps(private),encoding="utf-8")
    for folder,names in {"core":["test_acceptance_core.py","browser.cjs","browser-lifecycle.cjs","firefox-release.py"],"modules":["test_module_probes.py","test_cross_checks.py","test_own_comments.py","provider_probe.py","module_ui.cjs","map_online.cjs"],"browser":["collaboration.cjs","experience.cjs","sections.cjs","pdf-private.cjs","pdf-private-text.py"],"system":["inspect_runtime.py","extra_checks.py","check_policies.py","mixed_api.py","run_system.py","backup_policy.py"]}.items():
        for name in names:
            shutil.copyfile(OLD/folder/name,OUT/folder/name)
    # Original audit scripts get the new isolated inputs and logs. Test assertions are untouched.
    p=OUT/"system/run_system.py";t=p.read_text(encoding="utf-8")
    a=t.index("    return [p for p in git(",t.index("def source_paths():"));b=t.index("\n",a)
    t=t[:a]+'    return git("ls-files")'+t[b:]
    t=t.replace('if "acceptance-20261125/" not in x','if not any(w in x for w in ("acceptance-20261125/","acceptance-retest-cada651/"))')
    t=t.replace('tracked_modified=26,untracked_source=44','tracked_modified=0,untracked_source=0')
    t=t.replace('out/"environment.json"','out/"system-run-environment.json"').replace('writejson("environment",','writejson("system-run-environment",')
    t=t.replace('pg_env.update(DATABASE_URL=url,','pg_env.update(INVITATION_SIGNING_KEY=secrets.token_hex(32),DATABASE_URL=url,')
    p.write_text(t,encoding="utf-8")
    print("source",len(paths),"compose",private["origin"],"sqlite",private["sqliteorigin"],flush=True)
def dc():
    c=cfg()
    opts=dict(env,HTTP_PORT=str(c["ports"][0]),BIND_ADDRESS="127.0.0.1",PUBLIC_ORIGIN=c["origin"],BACKUP_DIR="./backups",VAPID_PRIVATE_KEY=c["vapid"],VAPID_SUBJECT="mailto:qa@example.test")
    return [DC,"--project-directory",SRC,"-f",SRC/"compose.yaml","-p",c["project"]],opts
def up():
    cmd,ev=dc()
    run("system/compose-config",cmd+["config","--quiet"],SRC,ev,check=True)
    run("system/compose-up",cmd+["up","-d","--build","--wait","--wait-timeout","240"],SRC,ev,timeout=780,check=True)
    run("system/compose-services",cmd+["ps","--format","table {{.Service}}\t{{.State}}\t{{.Health}}"],SRC,ev,check=True)
    run("system/compose-pg",cmd+["exec","-T","db","postgres","--version"],SRC,ev)
    run("system/compose-alembic",cmd+["exec","-T","api","alembic","current"],SRC,ev)
    seed=json.loads(capture(cmd+["exec","-T","api","python","-c","import json;from seed_demo import seed_demo;print(json.dumps(seed_demo()))"],SRC,ev))
    from urllib.parse import urlsplit,parse_qs
    (LAB/"pg-ui.json").write_text(json.dumps(cfg()|{"invite":parse_qs(urlsplit(seed["url"]).query)["invite"][0],"trip":seed["trip_id"]}),encoding="utf-8")
def probes():
    ev=env|{"PYTHONPATH":os.pathsep.join(map(str,(API,API/"tests"))),"INVITATION_SIGNING_KEY":secrets.token_hex(32)}
    for folder,files in [("core",["test_acceptance_core.py"]),("modules",["test_module_probes.py","test_cross_checks.py","test_own_comments.py"])]:
        run(folder+"/supplement",[PY,"-m","pytest","-p","no:cacheprovider","-p","conftest","-vv","-s","--tb=short",*[(OUT/folder/f) for f in files]],API,ev,600)
    for n in range(5):
        run("core/socket-repeat-"+str(n+1),[PY,"-m","pytest","-p","no:cacheprovider","-q","tests/test_core.py::test_five_connected_clients_receive_committed_edits_and_revocation"],API,ev,100)
def frontqa():
    for name,args in [("unit",["vitest/vitest.mjs","run","--reporter=verbose"]),("lint",["eslint/bin/eslint.js","app","components","lib","tests"]),("format",["prettier/bin/prettier.cjs","--check","app","components","lib","tests","*.ts","*.mts","*.js","*.mjs"])]:
        run("browser/"+name,[NODE,WEB/"node_modules"/args[0],*args[1:]],WEB,env)
def down():
    cli,ev=dc()
    run("system/compose-down",cli+["down","--volumes","--rmi","local"],SRC,ev,check=True)
if __name__=="__main__":globals()[sys.argv[1]]()


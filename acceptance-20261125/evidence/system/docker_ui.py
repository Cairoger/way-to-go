"""Run the five browser acceptance story against a separate Compose deployment."""
import json,os,secrets,shutil,sys,tempfile
from pathlib import Path
from run_system import repo,out,source_paths,stage,freeport,env,run
sys.path.insert(0,str(repo/"deploy"))
from create_test_login import provision
feature="pdf" if sys.argv[1:]==["pdf"] else "five"
probe="pdf-private.cjs" if feature=="pdf" else "collaboration.cjs"
with tempfile.TemporaryDirectory(prefix="wtg-five-ui-") as t:
    root=Path(t)
    stage(root,source_paths())
    run(feature+"-init",[sys.executable,"deploy/init_env.py"],root,required=True)
    pw=provision(root/".env")
    port=freeport();origin="http://127.0.0.1:"+str(port)
    config=root/"runtime.json"
    config.write_text(json.dumps({"origin":origin,"username":"tester","password":pw}),encoding="utf8")
    project="wtgui"+secrets.token_hex(8)
    cli=[str(repo/".local/docker-compose-v2.exe"),"-f",str(root/"compose.yaml"),"-p",project]
    cen=dict(env,HTTP_PORT=str(port),PUBLIC_ORIGIN=origin,BACKUP_DIR="./backup-isolated",BIND_ADDRESS="127.0.0.1")
    try:
        run(feature+"-up",cli+["up","-d","--build","--wait","--wait-timeout","180"],root,cen,True)
        res=out.parent/"browser"/"collaboration-postgres.json"
        ce=dict(cen,WTG_AUDIT_SETUP=str(config),WTG_AUDIT_STACK="Docker Compose nginx / Next / FastAPI / PostgreSQL 17, same-origin loopback")
        if feature=="five":
            ce["WTG_AUDIT_RESULT"]=str(res)
        run(feature+"-browser",[shutil.which("node"),out.parent/"browser"/probe],repo,ce)
    finally:
        run(feature+"-down",cli+["down","--volumes","--rmi","local"],root,cen)

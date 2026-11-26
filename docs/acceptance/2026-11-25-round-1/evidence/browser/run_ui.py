"""Reproduce this local Chrome/Edge audit using only disposable data and a staged UI."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import time
from urllib.request import urlopen

EVID = Path(__file__).resolve().parent
ROOT = EVID.parents[2]
LAB = Path(os.environ.get("WTG_UI_LAB", ROOT / ".local" / "audit-ui-20261125"))
WEB = LAB / "web"
NODE = shutil.which("node")
API = "http://127.0.0.1:18732"
ORIGIN = "http://127.0.0.1:18731"
BASE = os.environ | {"API_UPSTREAM": API, "NEXT_TELEMETRY_DISABLED": "1", "PYTHONIOENCODING":"utf-8", "PYTHONDONTWRITEBYTECODE":"1", "NO_COLOR":"1", "FORCE_COLOR":"0"}
MOD = WEB / "node_modules"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

def invoke(name, args, env=BASE, cwd=WEB):
    with (EVID / (name+".txt")).open("w",encoding="utf-8") as out:
        out.write("Command: " + subprocess.list2cmdline([str(x) for x in args])+"\n")
        out.flush()
        p = subprocess.run(args, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT)
        out.write("\nExit: "+str(p.returncode)+"\n")
        return p.returncode

def cli(name, rel, *args):
    return invoke(name,[NODE, MOD / rel,*args])

def server(args, cwd, env, log):
    return subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))

def ready(url, proc, seconds=160):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline and proc.poll() is None:
        try:
            with urlopen(url,timeout=3) as res:
                if res.status==200:
                    return
        except OSError:
            time.sleep(.5)
    raise RuntimeError("Readiness failed: "+url)

def main():
    for local_port in (18731, 18732):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1",local_port))
    if (LAB/"runtime.json").exists() or (LAB/"stop").exists():
        raise RuntimeError("Choose a clean, disposable WTG_UI_LAB before starting a new audit.")
    if not WEB.is_dir():
        WEB.mkdir(parents=True)
        front = ROOT / "frontend"
        for directory in ("app","components","lib","public","tests"):
            shutil.copytree(front/directory,WEB/directory)
        for f in front.iterdir():
            if f.is_file() and f.name not in ("tsconfig.tsbuildinfo","next-env.d.ts"):
                shutil.copy(f, WEB/f.name)
        subprocess.run(["powershell","-NoProfile","-Command","New-Item -ItemType Junction -Path $env:WTG_LINK -Target $env:WTG_TARGET | Out-Null"],env=BASE|{"WTG_LINK":str(MOD),"WTG_TARGET":str(front/"node_modules")},check=True)
    password = secrets.token_urlsafe(25)
    salt = secrets.token_bytes(16)
    password_hash=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,600000).hex()
    db=LAB/("ui-"+secrets.token_hex(5)+".sqlite")
    env=BASE|{"DATABASE_URL":"sqlite:///"+db.as_posix(),"PUBLIC_ORIGIN":ORIGIN,"LOCAL_TEST_USERNAME":"audit-browser","LOCAL_TEST_PASSWORD_HASH":f"pbkdf2_sha256$600000${salt.hex()}${password_hash}","WIKI_API_URL":"","FRANKFURTER_URL":"","OPEN_METEO_URL":"","GOOGLE_CLIENT_ID":"","GOOGLE_CLIENT_SECRET":""}
    assert invoke("migrate",[sys.executable,"-m","alembic","upgrade","head"],env,ROOT/"backend")==0
    seed=subprocess.check_output([sys.executable,"seed_demo.py"],cwd=ROOT/"backend",env=env).decode("utf-8").strip()
    code=seed.split("?invite=")[-1]
    runenv=BASE|{"E2E_ORIGIN":ORIGIN,"E2E_DISPOSABLE":"1","E2E_LOCAL_USERNAME":"audit-browser","E2E_LOCAL_PASSWORD":password,"E2E_INVITE":code,"CHROME_EXECUTABLE":CHROME}
    runtime=LAB/"runtime.json"
    runtime.write_text(json.dumps({"origin":ORIGIN,"username":"audit-browser","password":password,"invite":code,"trip":seed.split()[1]}))
    pending=[]
    try:
        with (LAB/"api.log").open("w",encoding="utf-8") as ao, (LAB/"web.log").open("w",encoding="utf-8") as wo, ThreadPoolExecutor(max_workers=3) as pool:
            api=server([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","18732","--no-access-log"],ROOT/"backend",env,ao)
            pending.append(api)
            ready(API+"/api/v1/auth/local-test",api)
            fut=pool.submit(cli,"unit","vitest/vitest.mjs","run","--reporter=verbose")
            lint=pool.submit(cli,"lint","eslint/bin/eslint.js",".")
            fmt=pool.submit(cli,"format","prettier/bin/prettier.cjs","--check","app","components","lib","tests","*.ts","*.mts","*.mjs","*.js")
            build=cli("build","next/dist/bin/next","build","--webpack")
            if not build:
                start="start"
            else:
                start="dev"
            web=server([NODE,MOD/"next/dist/bin/next", start,*(["--webpack"] if start=="dev" else []),"--hostname","127.0.0.1","--port","18731"],WEB,BASE,wo)
            pending.append(web)
            ready(ORIGIN,web)
            (LAB/"ready.txt").write_text(start)
            t1=cli("typegen","next/dist/bin/next","typegen")
            t2=cli("typecheck","typescript/bin/tsc","--noEmit","--incremental","false")
            cfg=[NODE,MOD/"@playwright/test/cli.js","test","--reporter=list","--trace=off"]
            invoke("chrome-playwright",cfg+["--output="+str(LAB/"chrome-results")],runenv)
            invoke("edge-playwright",cfg+["--output="+str(LAB/"edge-results")],runenv|{"CHROME_EXECUTABLE":EDGE})
            print("checks",build,fut.result(),lint.result(),fmt.result(),t1,t2,flush=True)
            for i in range(5400):
                if (LAB/"stop").exists(): break
                time.sleep(1)
    finally:
        for p in reversed(pending):
            if p.poll() is None:
                subprocess.run(["taskkill","/pid",str(p.pid),"/t","/f"],stdout=subprocess.DEVNULL)
        runtime.unlink(missing_ok=True)
        (LAB/"ready.txt").unlink(missing_ok=True)
if __name__=="__main__": main()

from retest import *
from urllib.request import urlopen
from urllib.parse import urlsplit,parse_qs
from contextlib import ExitStack
def serve():
    c=cfg()
    lines=(SRC/".env").read_text(encoding="utf-8").splitlines()
    dot=dict(x.split("=",1) for x in lines if "=" in x and not x.startswith("#"))
    ev=env|{"DATABASE_URL":"sqlite:///"+(LAB/os.getenv("WTG_SQLITE_DB","validated-ui.sqlite")).as_posix(),"PUBLIC_ORIGIN":c["sqliteorigin"],"LOCAL_TEST_USERNAME":c["username"],"LOCAL_TEST_PASSWORD_HASH":dot["LOCAL_TEST_PASSWORD_HASH"].strip("'"),"INVITATION_SIGNING_KEY":secrets.token_hex(32),"WIKI_API_URL":"","FRANKFURTER_URL":"","OPEN_METEO_URL":"","VAPID_PRIVATE_KEY":c["vapid"],"VAPID_SUBJECT":"mailto:qa@example.test"}
    run("browser/sqlite-migrate",[PY,"-m","alembic","upgrade","head"],API,ev,check=True)
    seed=json.loads(capture([PY,"-c","import json;from seed_demo import seed_demo;print(json.dumps(seed_demo()))"],API,ev))
    sc=c|{"origin":c["sqliteorigin"],"trip":seed["trip_id"],"invite":parse_qs(urlsplit(seed["url"]).query)["invite"][0]}
    we=env|{"API_UPSTREAM":c["upstream"]}
    run("browser/build",[NODE,WEB/"node_modules/next/dist/bin/next","build","--webpack"],WEB,we,check=True)
    run("browser/typegen",[NODE,WEB/"node_modules/next/dist/bin/next","typegen"],WEB,we)
    run("browser/typecheck",[NODE,WEB/"node_modules/typescript/bin/tsc","--noEmit","--incremental","false"],WEB,we)
    with ExitStack() as st:
        for kind,args,cwd,evv,url in [("api",[PY,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port",str(c["ports"][2]),"--no-access-log"],API,ev,c["upstream"]+"/health"),("web",[NODE,WEB/"node_modules/next/dist/bin/next","start","--hostname","127.0.0.1","--port",str(c["ports"][1])],WEB,we,c["sqliteorigin"]+"/")]:
            log=st.enter_context((LAB/(kind+".log")).open("w",encoding="utf-8"))
            p=sp.Popen(list(map(str,args)),cwd=cwd,env=evv,stdout=log,stderr=sp.STDOUT,creationflags=getattr(sp,"CREATE_NO_WINDOW",0))
            def stop(p=p):
                if p.poll() is None:p.terminate();p.wait(timeout=20)
            st.callback(stop)
            for _ in range(120):
                if p.poll() is not None:raise RuntimeError(kind+" exited")
                try:
                    if urlopen(url,timeout=2).status==200:break
                except OSError:time.sleep(.25)
            else:raise RuntimeError(kind+" not ready")
        (LAB/"sqlite-ui.json").write_text(json.dumps(sc),encoding="utf-8")
        print("SQLite browser origin",sc["origin"],flush=True)
        for _ in range(5400):
            if (LAB/os.getenv("WTG_STOP_MARKER","stop-v2")).exists():break
            time.sleep(1)
def browser(stack,engine,*selection):
    label=stack+"-"+engine+("-"+"-".join(x.replace(".spec.ts","").replace("tests/","") for x in selection) if selection else "-all")
    label+=os.getenv("WTG_RUN_TAG","")
    info=json.loads((LAB/(stack+"-ui.json")).read_text(encoding="utf-8"))
    pw=WEB/"node_modules/@playwright/test/cli.js"
    binary={"chrome":CHROME,"edge":EDGE}.get(engine,"")
    browser_family=engine if engine in ["webkit","firefox"] else "chromium"
    push=any("live-push" in s for s in selection)
    ev=env|{"E2E_ORIGIN":info["origin"],"E2E_INVITE":info["invite"],"E2E_LOCAL_USERNAME":info["username"],"E2E_LOCAL_PASSWORD":info["password"],"E2E_PYTHON":str(PY),"E2E_DISPOSABLE":"1","E2E_BROWSER":browser_family,"E2E_PUSH_PROBE":"1" if push else "0","CHROME_EXECUTABLE":binary,"E2E_METRICS_PATH":str(OUT/"browser"/(label+"-metrics.json")),"E2E_PUSH_RESULT":str(OUT/"browser"/(label+"-push.json")),"PLAYWRIGHT_JSON_OUTPUT_FILE":str(LAB/(label+".json"))}
    rc=run("browser/"+label,[NODE,pw,"test",*selection,"--browser="+browser_family,"--reporter=list,json","--trace=off","--output="+str(LAB/(label+"-results"))],WEB,ev,1350)
    jp=LAB/(label+".json")
    if jp.exists():
        j=json.loads(jp.read_text(encoding="utf-8")); rows=[]
        def collect(s):
            for n in s.get("specs",[]):
                for t in n["tests"]:
                    x=t["results"][-1]
                    err=re.sub(r"\x1b\[[0-9;]+m","",(x.get("error") or {}).get("message",""))
                    rows.append({"spec":n["file"],"title":n["title"],"result":x["status"],"duration_ms":x["duration"],"reason":err[:800] or str(t.get("annotations",""))})
            for ch in s.get("suites",[]):collect(ch)
        collect(j)
        write("browser/"+label+"-cases.json",{"stats":j.get("stats"),"tests":rows})
    return rc
def extras():
    e=env|{"PYTHONPATH":str(API),"INVITATION_SIGNING_KEY":secrets.token_hex(32)}
    run("system/extra-run",[PY,OUT/"system/extra_checks.py"],SRC,e)
    run("system/policy-run",[PY,OUT/"system/check_policies.py"],SRC,e)
    run("modules/provider-run",[PY,OUT/"modules/provider_probe.py"],SRC,e)
def addons(stack,mode):
    conf=LAB/(stack+"-ui.json")
    info=json.loads(conf.read_text(encoding="utf-8"))
    e=env|{"WTG_CORE_ORIGIN":info["origin"],"WTG_AUDIT_SETUP":str(conf),"WTG_UI_CONFIG":str(conf),"CHROME_EXECUTABLE":CHROME}
    if mode=="story":
        for f in ["core/browser.cjs","core/browser-lifecycle.cjs","modules/module_ui.cjs","modules/map_online.cjs","browser/pdf-private.cjs"]:
            run(str(Path(f).with_suffix("")).replace("\\","/")+"-run",[NODE,OUT/f,str(conf)],R,e,180)
        run("browser/pdf-text-run",[PY,OUT/"browser/pdf-private-text.py"],R,e)
    elif mode=="visual":
        for f in ["experience","sections"]:
            p=OUT/"browser"/(f+".cjs");t=p.read_text(encoding="utf-8").replace("path.join(root,'.local/audit-ui-20261125/runtime.json')","process.env.WTG_UI_CONFIG").replace("path.join(lab,'runtime.json')","process.env.WTG_UI_CONFIG")
            p.write_text(t,encoding="utf-8")
            run("browser/"+f+"-run",[NODE,p],R,e,220)
    elif mode=="soak":
        run("browser/soak-"+stack,[NODE,OUT/"browser/collaboration.cjs"],R,e|{"WTG_AUDIT_CLIENTS":"2","WTG_AUDIT_STACK":stack,"WTG_AUDIT_RESULT":"soak-"+stack+".json"},470)
if __name__=="__main__":
    x=sys.argv[1]
    if x=="serve":serve()
    if x=="browser":sys.exit(browser(*sys.argv[2:]))
    if x=="extra":extras()
    if x=="addons":addons(*sys.argv[2:])


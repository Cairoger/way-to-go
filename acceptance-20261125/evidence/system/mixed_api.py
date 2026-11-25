"""Representative read/write latency through nginx with 1 owner / 4 active members and isolated PG."""
import asyncio,json,math,secrets,sys,tempfile,time
from pathlib import Path
import httpx
from run_system import repo,out,source_paths,stage,freeport,env,run
sys.path.insert(0,str(repo/"deploy"))
from create_test_login import provision
async def observe(origin,password):
    clients=[httpx.AsyncClient(base_url=origin,headers={"Origin":origin},timeout=15,trust_env=False) for i in range(5)]
    readings=[]; setup=clients[0]
    try:
        login=await setup.post("/api/v1/auth/local-test",json={"username":"tester","password":password});login.raise_for_status()
        trip=await setup.post("/api/v1/trips",json={"title":"Mixed read write"});trip.raise_for_status()
        base="/api/v1/trips/"+trip.json()["id"]
        inv=await setup.post(base+"/invitations",json={});inv.raise_for_status()
        for i,c in enumerate(clients[1:],1):
            (await c.post("/api/v1/auth/guest",json={"code":inv.json()["code"],"nickname":f"qa-{i}"})).raise_for_status()
        async def journey(i,c):
            async def timed(method,p,route,**kwargs):
                start=time.perf_counter();r=await c.request(method,p,**kwargs)
                payload=r.json()
                readings.append({"actor":i,"method":method,"endpoint":route,"code":r.status_code,"ms":round(1000*(time.perf_counter()-start),2)})
                r.raise_for_status()
                return payload
            for iteration in range(2):
                for suffix in ["","/days","/places","/polls"]:
                    await timed("GET",base+suffix,"/trips/{id}"+suffix)
                comment=await timed("POST",base+"/comments","/trips/{id}/comments",json={"content":f"QA note {i}-{iteration}"})
                await timed("PATCH","/api/v1/comments/"+comment["id"],"/comments/{id}",json={"version":comment["version"],"content":f"Updated {i}-{iteration}"})
                task=await timed("POST",base+"/tasks","/trips/{id}/tasks",json={"title":f"QA task {i}-{iteration}"})
                for suffix in ["/tasks","/comments"]:
                    await timed("GET",base+suffix,"/trips/{id}"+suffix)
        await asyncio.gather(*(journey(i,c) for i,c in enumerate(clients)))
        def stats(rs):
            ms=sorted(r["ms"] for r in rs)
            return {"n":len(ms),"p95_ms":ms[math.ceil(len(ms)*.95)-1],"max_ms":ms[-1]}
        report={"stack":"loopback nginx / FastAPI / PostgreSQL17 via isolated Docker Compose, no external API or browser repaint in timing","members":5,"methodology":"each client runs two ordinary sequential user journeys; five journeys concurrently; warm signed-in clients; nearest rank; json decoding included","all":stats(readings),"reads":stats([r for r in readings if r["method"]=="GET"]),"writes":stats([r for r in readings if r["method"]!="GET"]),"observations":readings}
        (out/"mixed-api.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    finally:
        for c in clients:await c.aclose()
with tempfile.TemporaryDirectory(prefix="wtg-mixed-") as tmp:
    root=Path(tmp);stage(root,source_paths())
    run("mixed-init",[sys.executable,"deploy/init_env.py"],root,required=True)
    password=provision(root/".env");port=freeport();origin=f"http://127.0.0.1:{port}"
    cli=[repo/".local/docker-compose-v2.exe","-f",root/"compose.yaml","-p","wtgmix"+secrets.token_hex(8)]
    local=dict(env,HTTP_PORT=str(port),PUBLIC_ORIGIN=origin,BACKUP_DIR="./audit-backup",BIND_ADDRESS="127.0.0.1")
    try:
        run("mixed-up",cli+["up","-d","--build","--wait","--wait-timeout","180"],root,local,True)
        asyncio.run(observe(origin,password))
    finally:run("mixed-down",cli+["down","--volumes","--rmi","local"],root,local)

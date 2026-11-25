from retest import *
import asyncio, httpx
def comparison():
    old=LAB/"default-main"
    old.mkdir(exist_ok=True)
    archive=sp.check_output(["git","archive","--format=zip","refs/heads/main"],cwd=R)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:z.extractall(old)
    p=OLD/"core/clean-head-check.py"; j={}
    for k,src in [("main",old),("candidate",SRC)]:
        ev=env|{"INVITATION_SIGNING_KEY":secrets.token_hex(32)}
        j[k]=json.loads(capture([PY,p,"--inspect",src/"backend",LAB/(k+"-compare.sqlite")],src,ev))
    write("system/branch-comparison.json",j)
    run("core/default-main-pytest",[PY,"-m","pytest","-p","no:cacheprovider","-q","--basetemp",LAB/"pytest-old-main"],old/"backend")
def checks():
    ci=json.loads((LAB/"pg-ui.json").read_text(encoding="utf-8"));origin=ci["origin"]
    with httpx.Client(base_url=origin,headers={"Origin":origin},timeout=22,trust_env=False) as h:
        stats={}
        for url in ["/","/docs","/openapi.json","/health","/manifest.webmanifest","/offline.html","/sw.js"]:
            r=h.get(url);stats[url]={"status":r.status_code,"bytes":len(r.content),"type":r.headers.get("content-type")}
        write("system/deployed.json",stats)
        assert h.post("/api/v1/auth/local-test",json={"username":ci["username"],"password":ci["password"]}).is_success
        trip=h.post("/api/v1/trips",json={"title":"Private fixture for file-size boundaries"}).json()
        route=f'/api/v1/trips/{trip["id"]}/files'; limit=h.get(route+"/limits").json()
        result={"configured":limit,"samples":[]}
        for size in [1024**2+1,10*1024**2,10*1024**2+1]:
            from PIL import Image, PngImagePlugin
            def image(n):
                text=PngImagePlugin.PngInfo();text.add_text("Description","a"*n)
                b=io.BytesIO();Image.new("RGB",(8,8),"blue").save(b,format="PNG",pnginfo=text)
                return b.getvalue()
            data=image(size-len(image(0)));assert len(data)==size
            r=h.post(route,files={"files":("ordinary-picture-"+str(size)+".png",data,"image/png")},data={"kind":"trip","category":"行程"})
            result["samples"].append({"bytes":size,"status":r.status_code,"returned_error":r.json().get("code") if isinstance(r.json(),dict) else None})
        write("modules/nginx-quotas.json",result)
    p=OUT/"system/mixed_api.py"
    # Only import the existing signed-in 5-person read/write workload, against the test deployment above.
    import ast
    tree=ast.parse(p.read_text(encoding="utf-8"));tree.body=[n for n in tree.body if not isinstance(n,ast.With)]
    sys.path.insert(0,str(OUT/"system"))
    namespace={"__name__":"mixed_measure"}
    exec(compile(tree,str(p),"exec"),namespace)
    asyncio.run(namespace["observe"](origin,ci["password"]))
def restore():
    cli,ev=dc()
    assert cfg()["project"].startswith("wtgrerun") and SRC.is_relative_to(LAB) and LAB.is_relative_to(R/".local")
    run("system/restore-services",cli+["ps","--format","table {{.Service}}\t{{.State}}\t{{.Health}}"],SRC,ev,check=True)
    def sql(name,db,sqlbytes):
        return run("system/"+name,cli+["exec","-T","db","psql","-XqAt","-U","waytogo","-d",db,"-v","ON_ERROR_STOP=1"],SRC,ev,stdin=sqlbytes,check=True)
    manifest=(SRC/"deploy/verify-restore-manifest.sql").read_bytes()
    before=set((SRC/"backups").glob("*.dump"))
    sql("manifest-before","waytogo",manifest)
    run("system/restart-backup",cli+["restart","backup"],SRC,ev,check=True)
    new=set()
    for _ in range(150):
        new=set((SRC/"backups").glob("*.dump"))-before
        if new:break
        time.sleep(.25)
    if not new:raise RuntimeError("no new completed backup")
    dump=max(new,key=lambda t:t.stat().st_mtime)
    db="restore_"+secrets.token_hex(5)
    run("system/create-restore",cli+["exec","-T","db","createdb","-U","waytogo",db],SRC,ev,check=True)
    run("system/restore-real-dump",cli+["exec","-T","db","pg_restore","--exit-on-error","-U","waytogo","-d",db],SRC,ev,stdin=dump.read_bytes(),check=True)
    sql("manifest-restored",db,manifest)
    sql("restore-browser-private",db,(SRC/"deploy/verify-restore-browser.sql").read_bytes())
    count=b"select count(*) from files; select count(*) from file_links; select count(*) from file_permissions; select count(*) from trips; select count(*) from itinerary_items;"
    sql("restore-counts",db,count)
    run("system/volume-recreate",cli+["up","-d","--force-recreate","--no-deps","--wait","db"],SRC,ev,check=True)
    sql("manifest-after-db-recreate","waytogo",manifest)
    def lines(n):return [x for x in (OUT/("system/"+n+".txt")).read_text(encoding="utf-8").splitlines() if re.fullmatch(r"[a-z_]+\|\d+\|[0-9a-f]{64}",x)]
    a,b,c=map(lines,["manifest-before","manifest-restored","manifest-after-db-recreate"])
    write("system/restore-proof.json",dict(tables=len(a),same_after_restore=a==b,same_after_container_recreation=a==c,diverged=sorted(set(a)^set(b)),dump_size=dump.stat().st_size,dump_sha256=hashlib.sha256(dump.read_bytes()).hexdigest(),content_acl_probe="restored private browser-uploaded PNG, size, bytes, hash, visibility and booking link checked by deploy/verify-restore-browser.sql"))
    assert len(a)==42 and a==b==c
if __name__=="__main__":globals()[sys.argv[1]]()


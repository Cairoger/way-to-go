"""Exercise the published 500 MiB per-trip limit via ordinary authenticated HTTP uploads."""
from retest import *
import httpx
from PIL import Image, PngImagePlugin
def png(n):
    meta=PngImagePlugin.PngInfo()
    meta.add_text("Description", "a"*n)
    buf=io.BytesIO()
    Image.new("RGB",(8,8),"blue").save(buf,format="PNG",pnginfo=meta)
    return buf.getvalue()
base=len(png(0))
def sized(n):
    payload=png(n-base)
    assert len(payload)==n
    return payload
c=cfg()
assert c["origin"].startswith("http://127.0.0.1:") and c["project"].startswith("wtgrerun")
with httpx.Client(base_url=c["origin"],headers={"Origin":c["origin"]},timeout=120,trust_env=False) as h:
    r=h.post("/api/v1/auth/local-test",json={"username":c["username"],"password":c["password"]});r.raise_for_status()
    r=h.post("/api/v1/trips",json={"title":"獨立驗收・旅程配額完整邊界"});r.raise_for_status()
    path="/api/v1/trips/"+r.json()["id"]+"/files"
    limits=h.get(path+"/limits").json()
    maxfile=limits["file_max_bytes"];limit=limits["trip_max_bytes"]
    assert limit==50*maxfile==500*1024**2
    payload=sized(maxfile)
    samples=[];accepted=0
    def upload(parts,expected):
        global accepted
        request_total=sum(len(x) for x in parts)
        obs=h.post(path,files=[("files",(f"批次-{len(samples)}-{i}.png",x,"image/png")) for i,x in enumerate(parts)],data={"kind":"trip"})
        before=accepted
        if obs.status_code==201:
            assert len(obs.json())==len(parts)
            assert sum(x["size"] for x in obs.json())==request_total
            accepted+=request_total
        code=obs.json().get("code") if isinstance(obs.json(),dict) else None
        samples.append({"prior_committed_bytes":before,"files":len(parts),"request_bytes":request_total,"attempted_total_bytes":before+request_total,"status":obs.status_code,"error_code":code,"total_accepted_bytes":accepted})
        write("modules/trip-quota-full.json",{"limits":limits,"batches":samples})
        assert obs.status_code==expected and (expected!=413 or code=="TRIP_FILE_QUOTA"),samples[-1]
    for _ in range(9):
        upload([payload]*5,201)
    upload([payload]*4,201)
    upload([sized(maxfile-1000)],201)
    upload([sized(1001)],413)
    upload([sized(1000)],201)
    upload([sized(1000)],413)
    assert accepted==limit
    print("500 MiB reached; proposed total limit+1 returned 413; next smaller upload accepted, later upload rejected.")


from retest import *
import httpx
from websockets.sync.client import connect
c=cfg()
origin=c["origin"]
assert origin.startswith("http://127.0.0.1:") and c["project"].startswith("wtgrerun")
codes={}
def record(k,r):
    codes.setdefault(k,{}).setdefault(str(r.status_code),0)
    codes[k][str(r.status_code)]+=1
    r.raise_for_status()
    return r.json() if r.content else {}
with httpx.Client(base_url=origin,headers={"Origin":origin},trust_env=False) as h:
    h.post("/api/v1/auth/local-test",json={"username":c["username"],"password":c["password"]}).raise_for_status()
    tr=h.post("/api/v1/trips",json={"title":"API 明細獨立復測"}).json()
    trip="/api/v1/trips/"+tr["id"]
    assert any(t["id"]==tr["id"] for t in record("GET /api/v1/trips",h.get("/api/v1/trips")))
    p=h.post(trip+"/places",json={"name":"集合點"}).json()
    def lease(row):
        r=h.post("/api/v1/edit-leases",json={"resource_id":row["id"],"resource_type":"place"})
        r.raise_for_status()
        return {"version":row["version"],"lease_id":r.json()["id"]}
    meta=lease(p)
    record("DELETE /api/v1/edit-leases/{lease_id}",h.delete("/api/v1/edit-leases/"+meta["lease_id"]))
    removed=h.request("DELETE",trip+"/candidates/"+p["candidate_id"],json=lease(p))
    removed.raise_for_status()
    new_meta=lease(removed.json())
    returned=record("POST /api/v1/trips/{trip_id}/candidates",h.post(trip+"/candidates",json={"place_id":p["id"],**new_meta}))
    assert returned["candidate"]
    with connect(origin.replace("http://","ws://")+"/ws/trips/"+tr["id"],origin=origin,additional_headers={"Cookie":"wtg_session="+h.cookies["wtg_session"]},proxy=None,open_timeout=12) as sock:
        event=json.loads(sock.recv(timeout=10))
        assert sock.response.status_code==101 and event.get("type")=="presence"
        codes["WS /ws/trips/{trip_id}"]={"101":1}
write("system/extra-observed-api.json",codes)
print(codes)


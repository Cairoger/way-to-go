"""Exercise the remaining published operations in a fresh database and verify read-back after mutations."""
import io, json
from pathlib import Path
from PIL import Image
from test_finance import expense
evidence=Path(__file__).resolve().parent
def test_remaining_five_http_operations(owner, guest, trip):
    b="/api/v1/trips/"+trip["id"]; stem="/api/v1/trips/{trip_id}"; codes={}
    def logged(key,r,status):
        bucket=codes.setdefault(key,{})
        bucket[str(r.status_code)]=bucket.get(str(r.status_code),0)+1
        assert r.status_code==status,(key,r.text)
        return r.json() if r.content else None
    poll=owner.post(b+"/polls",json={"title":"要保留的選項","kind":"place","mode":"single","options":[{"text":"南投"},{"text":"嘉義"}]}).json()
    logged("DELETE /api/v1/polls/{poll_id}",owner.request("DELETE","/api/v1/polls/"+poll["id"],json={"version":poll["version"]}),200)
    assert all(p["id"]!=poll["id"] for p in owner.get(b+"/polls").json())
    task=owner.post(b+"/tasks",json={"title":"合成待辦","scope":"shared"}).json()
    logged("DELETE "+stem+"/tasks/{task_id}",owner.request("DELETE",b+"/tasks/"+task["id"],json={"version":task["version"]}),204)
    assert all(t["id"]!=task["id"] for t in guest.get(b+"/tasks").json())
    name=owner.post(b+"/budgets",json={"scope":"trip","amount":"80"}).json()["id"]
    budget_path=b+"/budgets/"+name; key=stem+"/budgets/{budget_id}"
    first=owner.get(b+"/finance").json()["budgets"][0]
    logged("PATCH "+key,guest.patch(budget_path,json={"version":first["version"],"amount":"90"}),403)
    logged("PATCH "+key,owner.patch(budget_path,json={"version":first["version"],"amount":"90"}),200)
    changed=guest.get(b+"/finance").json()["budgets"][0]
    assert changed["amount"]=="90.00"
    logged("DELETE "+key,owner.delete(budget_path,params={"version":first["version"]}),409)
    logged("DELETE "+key,owner.delete(budget_path,params={"version":changed["version"]}),200)
    assert not owner.get(b+"/finance").json()["budgets"]
    a,g=[c.get("/api/v1/auth/me").json()["id"] for c in [owner,guest]]
    assert owner.post(b+"/expenses",json=expense(a,g)).status_code==201
    state=guest.get(b+"/finance").json()
    before=state["balances"]
    assert guest.post(b+"/settlements",json={"from_user_id":g,"to_user_id":a,"amount":"20","version":state["version"]}).status_code==201
    state=guest.get(b+"/finance").json();one=state["settlements"][0]
    logged("DELETE "+stem+"/settlements/{settlement_id}",guest.delete(b+"/settlements/"+one["id"],params={"version":one["version"]}),200)
    after=owner.get(b+"/finance").json()
    assert not after["settlements"] and after["balances"]==before
    (evidence/"remaining-http.json").write_text(json.dumps(codes,indent=2),encoding="utf8")
def test_all_advertised_image_formats(owner, guest, trip):
    url="/api/v1/trips/"+trip["id"]+"/files"
    result={}
    for ext,fmt in [("png","PNG"),("jpeg","JPEG"),("gif","GIF"),("webp","WEBP")]:
        out=io.BytesIO()
        Image.new("RGB",(12,9),"blue").save(out,format=fmt)
        raw=out.getvalue();mime="image/"+ext
        r=owner.post(url,files={"files":("sample."+ext,raw,mime)})
        assert r.status_code==201,r.text
        route="/api/v1/files/"+r.json()[0]["id"]
        preview=guest.get(route+"/preview"); download=guest.get(route+"/download")
        assert preview.status_code==download.status_code==200 and preview.content==download.content==raw
        result[fmt]={"upload":r.status_code,"preview":preview.status_code,"download":download.status_code,"byte_for_byte_equal":True,"bytes":len(raw)}
    (evidence/"advertised-images.json").write_text(json.dumps(result,indent=2),encoding="utf8")


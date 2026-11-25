import ast,json
from pathlib import Path
from sqlalchemy import event
from app.core import get_engine
from app.main import app

def test_stale_profile_and_sql_binding(owner,trip):
    first=owner.get("/api/v1/auth/me")
    second=owner.get("/api/v1/auth/me")
    assert first.json()==second.json()
    target="O'Brien 二次驗收"
    seen=[]
    eng=get_engine()
    def watch(conn,cursor,stmt,params,ctx,many):
        if target in str(params):
            seen.append({"operation":stmt.split(None,1)[0],"literal_in_statement":target in stmt,"bound_parameter":True})
    event.listen(eng,"before_cursor_execute",watch)
    try:
        a=owner.patch("/api/v1/auth/me",json={"nickname":target})
        middle=owner.get("/api/v1/auth/me")
        b=owner.patch("/api/v1/auth/me",json={"nickname":"第二個已開啟頁面的修改"})
        last=owner.get("/api/v1/auth/me")
        place=owner.post("/api/v1/trips/"+trip["id"]+"/places",json={"name":target})
        listed=owner.get("/api/v1/trips/"+trip["id"]+"/places")
    finally:event.remove(eng,"before_cursor_execute",watch)
    assert a.status_code==200 and middle.json()["nickname"]==target and place.status_code==201 and any(p["name"]==target for p in listed.json())
    assert len(seen)>=2 and all(x["bound_parameter"] and not x["literal_in_statement"] for x in seen)
    raw=[]
    for f in Path(__import__("app").__file__).parent.glob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n,ast.Call) and n.args and (getattr(n.func,"id",None)=="text" or getattr(n.func,"attr",None)=="exec_driver_sql"):
                raw.append([f.name,n.lineno,isinstance(n.args[0],ast.Constant)])
    assert raw and all(it[2] for it in raw)
    outfile=Path(__file__).parent/"binding-profile.json"
    outfile.write_text(json.dumps({"profile":{"initial_etag":first.headers.get("ETag"),"version_in_representation":"version" in first.json(),"update_a":a.status_code,"update_b_from_same_initial_view":b.status_code,"latest_nickname":last.json()["nickname"],"a_overwritten":last.json()["nickname"]!=target},"code_scan_raw_sql_constants":raw,"bound_capture":seen},ensure_ascii=False,indent=2),encoding="utf-8")
    assert b.status_code in [409,412,422,428], "two views read same original profile; both unversioned writes accepted and second overwrote first"

def test_current_task_fields_with_relationship(owner,guest,trip):
    base="/api/v1/trips/"+trip["id"];me=guest.get("/api/v1/auth/me").json()["id"]
    place=owner.post(base+"/places",json={"name":"活動場地"}).json()
    data={"title":"場勘","description":"集合","assignees":[me],"due_date":"2027-06-01","priority":"high","place_id":place["id"],"recurrence":"weekly"}
    r=owner.post(base+"/tasks",json=data)
    assert r.status_code==201
    row=guest.get(base+"/tasks").json()[0]
    for k in data.keys()-{"assignees"}:assert row[k]==data[k]
    assert row["assignees"][0]["user_id"]==me and row["state"]=="todo"


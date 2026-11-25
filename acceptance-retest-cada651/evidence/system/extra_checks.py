"""Synthetic ordinary role / contract tests and read-only release checks. Run with checkout .venv."""
import json, os, re, subprocess, sys, tempfile, uuid
from datetime import timedelta
from pathlib import Path
from contextlib import ExitStack
from run_system import out,repo,git,source_paths
sys.path.insert(0,str(repo/"backend"))
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core import COOKIE,digest,get_engine,make_session,public_origin
from app.models import Base,LoginSession,User,AuditLog,utcnow
from app.main import app
from app.auth import issue_session
from starlette.responses import Response
data={}
def save():
    (out/"extra-checks.json").write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding="utf8")
def signal(name,r):
    obj=r.json() if r.content else {}
    data[name]={"status":r.status_code,"code":obj.get("code") if isinstance(obj,dict) and r.is_error else None,"message":obj.get("message") if isinstance(obj,dict) else None}
    save()
    return obj
with tempfile.TemporaryDirectory(prefix="audit-extra-") as t, ExitStack() as stack:
    os.environ.update(PUBLIC_ORIGIN="https://acceptance.test",DATABASE_URL="sqlite:///"+(Path(t)/"synthetic.db").as_posix(),WIKI_API_URL="")
    public_origin.cache_clear(); get_engine.cache_clear()
    engine=get_engine()
    stack.callback(engine.dispose)
    Base.metadata.create_all(engine)
    origin=os.environ["PUBLIC_ORIGIN"]
    def browser():return stack.enter_context(TestClient(app,base_url=origin,headers={"Origin":origin}))
    owner=browser();guest=browser()
    secret=uuid.uuid4().hex
    with make_session() as db:
        account=User(account_type="google",nickname="Audit")
        db.add(account);db.flush()
        db.add(LoginSession(user_id=account.id,token_hash=digest(secret),expires_at=utcnow()+timedelta(days=1)));db.commit()
    owner.cookies.set(COOKIE,secret)
    trip=signal("two-trips-first",owner.post("/api/v1/trips",json={"title":"one"}))
    signal("two-trips-second",owner.post("/api/v1/trips",json={"title":"two"}))
    data["trip-count"]=len(owner.get("/api/v1/trips").json())
    base="/api/v1/trips/"+trip["id"]
    inv=signal("owner-invite",owner.post(base+"/invitations",json={"days":2},headers={"Idempotency-Key":"repeat-invite"}))
    again=signal("owner-repeat-invite",owner.post(base+"/invitations",json={"days":2},headers={"Idempotency-Key":"repeat-invite"}))
    data["repeated-invite-ids-equal"]=inv["id"]==again["id"]
    r=guest.post("/api/v1/auth/guest",json={"nickname":"member","code":inv["code"]})
    cookie=r.headers["set-cookie"].split(";",1)[1].strip()
    data["https-session-attributes"]=cookie
    guest_id=signal("guest-signin",r)
    uid=guest.get("/api/v1/auth/me").json()["id"]
    outsider=browser()
    r=outsider.post("/api/v1/auth/guest",json={"nickname":"member","code":inv["code"]})
    data["duplicate-nickname-new-identity"]=outsider.get("/api/v1/auth/me").json()["id"]!=uid
    r=guest.post("/api/v1/trips",json={"title":"request"})
    signal("guest-create-denial",r)
    signal("guest-invite-denial",guest.post(base+"/invitations",json={"days":3}))
    signal("guest-archive-denial",guest.post(base+"/archive",json={"version":1}))
    signal("guest-delete-denial",guest.delete(base,params={"version":1}))
    signal("guest-remove-other-denial",guest.delete(base+"/members/"+outsider.get("/api/v1/auth/me").json()["id"]))
    signal("owner-edit-profile",owner.patch("/api/v1/auth/me",json={"nickname":"renamed"}))
    signal("member-edit-other-item",guest.patch("/api/v1/itinerary-items/"+signal("owner-create-item",owner.post("/api/v1/days/"+owner.get(base+"/days").json()[0]["id"]+"/items",json={"title":"author A"}))["id"],json={"title":"changed","lease_id":str(uuid.uuid4()),"version":1}))
    place=signal("owner-place",owner.post(base+"/places",json={"name":"A"}))
    def lease(p):
        v=owner.post("/api/v1/edit-leases",json={"resource_type":"place","resource_id":p["id"]}).json()
        return {"lease_id":v["id"],"version":p["version"]}
    removed=signal("candidate-remove",owner.request("DELETE",base+"/candidates/"+place["candidate_id"],json=lease(place)))
    signal("candidate-restore",owner.post(base+"/candidates",json={"place_id":place["id"],**lease(removed)}))
    private_ref="SYNTHETIC-BOOK-REFERENCE"
    signal("book",owner.post(base+"/bookings",json={"title":"audit stay","kind":"stay","reference":private_ref,"stay":{"check_in":"2027-01-01","check_out":"2027-01-02"}}))
    with make_session() as db:
        logs=db.scalars(select(AuditLog)).all()
        audit_content=json.dumps([[x.action,x.changes] for x in logs])
        data["audit"]={"actions":[x.action for x in logs],"all_have_actor":all(x.actor_id for x in logs),"has_synthetic_secret":secret in audit_content,"has_full_synthetic_booking_ref":private_ref in audit_content}
    signal("member-left",guest.delete(base+"/members/"+uid))
    signal("after-exit",guest.get(base))
    save()
    # Compare all specified method/path pairs with the live OpenAPI route registry.
    routes=owner.get("/openapi.json").json()["paths"]
    normalize=lambda p:re.sub(r"\{[^}]+\}","{id}",p)
    actual={(m.upper(),normalize(p)) for p,ops in routes.items() for m in ops}
    with owner.websocket_connect("/ws/trips/"+trip["id"],headers={"Origin":origin}) as ws:
        if ws.receive_json()["type"]=="presence":
            actual.add(("WS","/ws/trips/{id}"))
    spec=(repo/"docs/spec.md").read_text(encoding="utf8")
    ops=re.findall(r"\x60(GET|POST|PATCH|DELETE|PUT|WS) ([^\x60]+)\x60",spec)
    data["api-contract"]={m+" "+p:(m,normalize(("" if m=="WS" else "/api/v1")+p)) in actual for m,p in ops}
    for p in ["/files","/tasks","/expenses","/settlements","/bookings","/notifications"]:
        data.setdefault("extended-contract",{})[p]=[k for k in routes if k.endswith(p)]
    data["file-feature-probe"]=signal("files-api",owner.get(base+"/files"))
    data["public-config-http-rejected"]=False
    os.environ["PUBLIC_ORIGIN"]="http://public.example.test";public_origin.cache_clear()
    try:public_origin()
    except RuntimeError as e:data["public-config-http-rejected"]=str(e)
    os.environ.pop("DATABASE_URL");get_engine.cache_clear()
    try:get_engine()
    except RuntimeError as e:data["missing-database"]=str(e)
paths=source_paths()
files=[p for p in paths if p.startswith("frontend/") and p.endswith((".ts",".tsx",".js"))]
data["paid-copy-occurrences"]=[p for p in files if "付費功能開發中" in (repo/p).read_text(encoding="utf8")]
data["git-sensitive-file-inventory"]=[p for p in git("log","--all","--format=","--name-only") if p and (p==".env" or p.endswith((".pem",".p12",".key",".pfx")))]
save()
print("Synthetic role, API contract, missing configuration and source inventory saved.")

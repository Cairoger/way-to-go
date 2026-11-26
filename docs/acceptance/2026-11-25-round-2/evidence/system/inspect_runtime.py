"""Inspect an actually migrated database and running ASGI app. Outputs contain only synthetic data."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from datetime import timedelta
from sqlalchemy import inspect
from fastapi.testclient import TestClient
from app.main import app
from app.core import get_engine,make_session,digest,COOKIE
from app.models import User,LoginSession,utcnow
from uuid import uuid4

out=Path(sys.argv[1]).resolve()
def save(name,v):
    (out/(name+".json")).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str),encoding="utf8")
insp=inspect(get_engine())
schema={}
for t in insp.get_table_names():
    schema[t]={"columns":{c["name"]:str(c["type"]) for c in insp.get_columns(t)},"pk":insp.get_pk_constraint(t)["constrained_columns"],"foreign":[[fk["constrained_columns"],fk["referred_table"],fk["referred_columns"]] for fk in insp.get_foreign_keys(t)],"unique":[r["column_names"] for r in insp.get_unique_constraints(t)],"checks":[r["sqltext"] for r in insp.get_check_constraints(t)],"indexes":[r["column_names"] for r in insp.get_indexes(t)]}
save("schema",schema)
origin=os.environ["PUBLIC_ORIGIN"]
with TestClient(app,base_url=origin,headers={"Origin":origin}) as client:
    docs=client.get("/openapi.json").json()
    paths={k:list(v.keys()) for k,v in docs["paths"].items()}
    save("openapi-routes",paths)
    anonymous=client.get("/api/v1/trips")
    def obs(r):
        try:obj=r.json()
        except ValueError:obj=None
        return {"status":r.status_code,"body":obj,"request_id_matches":bool(isinstance(obj,dict) and obj.get("request_id")==r.headers.get("x-request-id"))}
    log={"anonymous":obs(anonymous),"health":obs(client.get("/health")),"oidc_missing":obs(client.post("/api/v1/auth/google"))}
    token=uuid4().hex+uuid4().hex
    with make_session() as db:
        u=User(account_type="google",nickname="system audit")
        db.add(u);db.flush()
        db.add(LoginSession(user_id=u.id,token_hash=digest(token),expires_at=utcnow()+timedelta(hours=1)));db.commit()
    client.cookies.set(COOKIE,token)
    bad=client.post("/api/v1/trips",json={"title":""})
    log["invalid_title"]=obs(bad)
    r=client.post("/api/v1/trips",json={"title":"schema check"})
    log["create_trip"]=obs(r)
    trip=r.json()["id"]; base=f"/api/v1/trips/{trip}"
    for path in ["/files","/bookings","/tasks","/expenses","/settlements","/notifications","/places","/members","/days"]:
        log["GET "+path]=obs(client.get(base+path))
    log["profile-edit"]=obs(client.patch("/api/v1/auth/me",json={"nickname":"updated"}))
    log["metadata"]={"docs_status":client.get("/docs").status_code,"openapi":docs["openapi"],"route_count":len(paths),"websockets":[r.path for r in app.routes if type(r).__name__=="APIWebSocketRoute"]}
    save("http",log)
print("Schema, endpoint inventory and synthetic HTTP observations saved.")

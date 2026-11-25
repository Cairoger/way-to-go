"""Read-only capture of request methods, route templates and response codes during the real backend suite."""
import os, sys, re, json, tempfile, secrets
from pathlib import Path
from collections import Counter, defaultdict
import httpx, pytest
here=Path(__file__).resolve().parent
out=here.parent.parent
lab=out.parent/".local"/out.name
api=lab/"source"/"backend"
assert api.is_dir()
os.chdir(api)
for k in ["DATABASE_URL","TEST_DATABASE_URL","GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET"]:
    os.environ.pop(k,None)
os.environ["INVITATION_SIGNING_KEY"]=secrets.token_hex(32)
sys.path[:0]=[str(api),str(api/"tests")]
paths=json.loads((here/"openapi-routes.json").read_text(encoding="utf-8-sig"))
if isinstance(paths,list):
    names=sorted({p.split(" ",1)[-1] if isinstance(p,str) else p["path"] for p in paths})
else:
    names=list(paths)
patterns=[(p,re.compile(re.sub(r"\{[^}]+\}","[^/]+",p))) for p in sorted(names,key=lambda x: (x.count("{"),-len(x)))]
counter=defaultdict(Counter)
real=httpx.Client.send
def record(self,request,*args,**kwargs):
    response=real(self,request,*args,**kwargs)
    path=request.url.path
    match=next((p for p,rx in patterns if rx.fullmatch(path)),None)
    if match is not None:
        counter[request.method+" "+match][response.status_code]+=1
    return response
httpx.Client.send=record
code=pytest.main(["-q","-p","no:cacheprovider","--basetemp",str(lab/"contract-tmp"),"tests"])
(here/"observed-api.json").write_text(json.dumps(dict(sorted(counter.items())),indent=2)+"\n",encoding="utf-8")
print("recorded",len(counter),"method / route pairs")
sys.exit(int(code))


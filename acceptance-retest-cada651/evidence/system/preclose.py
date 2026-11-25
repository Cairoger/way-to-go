"""Check audit isolation and private values without retaining their contents."""
import json, re, hashlib, socket
from pathlib import Path
here=Path(__file__).resolve().parent
out=here.parent.parent
lab=out.parent/".local"/out.name
items=[]
for name in ["runtime.json","pg-ui.json","sqlite-ui.json"]:
    data=json.loads((lab/name).read_text(encoding="utf-8"))
    for k in ["password","invite","vapid","token","access_token"]:
        if isinstance(data.get(k),str) and len(data[k])>8:items.append(data[k])
for line in (lab/"source/.env").read_text(encoding="utf-8-sig").splitlines():
    k,_,v=line.partition("=")
    if "KEY" in k or "PASSWORD" in k:
        v=v.strip().strip("'").strip('"')
        if len(v)>12:items.append(v)
found=[];checked=0
for p in out.rglob("*"):
    if p.is_file() and p.suffix.lower() in [".json",".md",".txt",".py",".cjs"]:
        checked+=1
        t=p.read_text(encoding="utf-8-sig",errors="replace")
        if any(s in t for s in items) or re.search(r"(?:[?&]invite=)[\w.\-]{16,}|wtg_session=[A-Za-z0-9_-]{20,}",t):
            found.append(p.relative_to(out).as_posix())
config=json.loads((lab/"runtime.json").read_text())
open_ports=[]
for port in config["ports"]:
    with socket.socket() as sock:
        sock.settimeout(.35)
        if sock.connect_ex(("127.0.0.1",port))==0:open_ports.append(port)
canonical=[]
sources=json.loads((here/"source-hashes.json").read_text(encoding="utf8"))
for tracked in sources:
    a=(out.parent/tracked).read_bytes(); b=(lab/"source"/tracked).read_bytes()
    if a!=b and a.replace(b"\r\n",b"\n")!=b.replace(b"\r\n",b"\n"):canonical.append(tracked)
assert not found and not open_ports and not canonical,(found,open_ports,canonical)
(here/"preclose.json").write_text(json.dumps({"private_value_scan":"no matches for exact disposable credentials, substantial invite query values or session cookies","text_files_checked":checked,"ports_checked":config["ports"],"listening_after_shutdown":open_ports,"checked_sources_export_vs_worktree":len(sources),"different_after_line_ending_normalization":canonical},indent=2)+"\n",encoding="utf-8")


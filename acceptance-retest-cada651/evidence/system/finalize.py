"""Verify the revision, both Markdown matrices, every evidence target and the finished ZIP."""
from pathlib import Path
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import datetime,hashlib,json,os,re,shutil,subprocess,zipfile
here=Path(__file__).resolve().parent
out=here.parent.parent
root=out.parent
prior=root/"acceptance-20261125"
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def git(*parts):return subprocess.check_output(["git",*parts],cwd=root).decode("utf-8").strip()
sysinfo=read(here/"environment.json")
before=read(here/"source-hashes.json")
after={f:digest(root/f) for f in git("ls-files").splitlines()}
unchanged=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
assert len(after)==160 and not unchanged and not git("diff","--name-only","HEAD")
assert git("rev-parse","HEAD")==sysinfo["head"] and git("show-ref","--heads")==sysinfo["refs"]
old_zip=next(prior.glob("*.zip"))
with zipfile.ZipFile(old_zip) as z:
    assert not z.testzip()
    legacy_ok=all((prior/n).is_file() and (prior/n).read_bytes()==z.read(n) for n in z.namelist())
    old_entries=len(z.namelist())
assert legacy_ok and old_entries==180
lab=root/".local"/out.name
assert not lab.exists() and (root/"frontend/node_modules/@playwright/test").exists()
source_spec_sha=digest(here/"spec.md")
uploaded=Path.home()/"Downloads/spec.md"
# The sandbox can expose a separate HOME even though the user supplied an absolute attachment path.
if not uploaded.exists():uploaded=Path("C:/Users/a0928/Downloads/spec.md")
assert source_spec_sha==digest(root/"docs/spec.md")==digest(uploaded)
assert set(git("status","--porcelain","--untracked-files=normal").splitlines())=={"?? acceptance-20261125/","?? acceptance-retest-cada651/"}
save(here/"integrity.json",{"checked_at":datetime.datetime.now().astimezone().isoformat(),"head":sysinfo["head"],"branch":sysinfo["branch"],"git_refs_unchanged":True,"tracked_file_count":len(after),"changed_tracked_files":unchanged,"worktree_final_status":git("status","--porcelain","--branch"),"earlier_bundle_entries_compared":old_entries,"earlier_files_equal_to_original_archive":legacy_ok,"earlier_zip_sha256":digest(old_zip),"attachment_and_repo_spec_sha256":source_spec_sha,"working_copy_options":"product source, spec and existing tests were read-only","lab_removed":not lab.exists(),"shared_frontend_dependencies_present":True,"open_test_ports_after_shutdown":read(here/"preclose.json")["listening_after_shutdown"]})
# The full report is self-contained. Keep one copy of its introductory text when this check is rerun.
main=out/"第二輪功能驗收報告.md"
matrix=out/"需求追蹤矩陣.md"
marker="<!-- embedded acceptance matrix -->"
intro=main.read_text(encoding="utf-8").split(marker,1)[0].rstrip()
body=matrix.read_text(encoding="utf-8")
body=body[body.index("## 1　"):].replace("\n## ","\n### ")
body=re.sub(r"^## ","### ",body)
main.write_text(intro+"\n\n"+marker+"\n\n"+body,encoding="utf-8")
report_file=here/"report-verification.json"
sums=here/"checksums.sha256"
if not report_file.exists():save(report_file,{})
sums.touch(exist_ok=True)
class Parsed(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors=[];self.links=[];self.tables=0;self.table_rows=[];self.row=None
    def handle_starttag(self,tag,attributes):
        a=dict(attributes)
        if tag=="table":self.tables+=1
        if tag=="tr":self.row=[]
        if tag in ("td","th") and self.row is not None:self.row.append("")
        if tag=="a":
            if a.get("id","").startswith("r-"):self.anchors.append(a["id"])
            if "href" in a:self.links.append(a["href"])
    def handle_endtag(self,tag):
        if tag=="tr" and self.row is not None:self.table_rows.append(self.row);self.row=None
    def handle_data(self,data):
        if self.row:self.row[-1]+=data
def parse_md(path):
    env=dict(os.environ,WTG_AUDIT_MD=str(path))
    command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);[Console]::Write((ConvertFrom-Markdown -LiteralPath $env:WTG_AUDIT_MD).Html)"
    proc=subprocess.run(["pwsh","-NoProfile","-NonInteractive","-Command",command],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    obj=Parsed();obj.feed(proc.stdout.decode("utf-8-sig"));return obj
rows=read(out/"需求矩陣.json");ids=[r["id"] for r in rows]
previous=read(prior/"需求矩陣.json")
assert len(set(ids))==len(ids)==436 and ids==[r["id"] for r in previous]
evidence_refs=0
for r in rows:
    assert r["evidence"] or r["dependencies"]
    assert r["notes"] and r["condition"] and r["line"]>0
    assert set(r["dependencies"])<=set(ids)
    for f in r["evidence"]:
        assert f.startswith("evidence/") and (out/f).is_file(),f
        evidence_refs+=1
coverage=read(here/"coverage.json")
lines=(here/"spec.md").read_text(encoding="utf8").splitlines()
assert len(lines)==710 and len(coverage)==474
spec_ids=set(re.findall(r"\b(?:FR-[A-Z]+-\d{2}|AC-\d{3}|BR-\d{3})\b","\n".join(lines)))
assert spec_ids=={r["id"] for r in rows if r["id"].startswith(("FR-","BR-","AC-"))}
assert {r["line"] for r in coverage}=={i for i,t in enumerate(lines,1) if t.strip()}
assert set(ids)=={i for x in coverage for i in x["ids"]}
stats=read(here/"statistics.json")
status_counts=dict(Counter(r["result"] for r in rows))
html_checks={}
for name in [matrix,main]:
    parsed=parse_md(name)
    anchors=set(parsed.anchors)
    assert len(parsed.anchors)==len(anchors)==436 and anchors=={"r-"+i.lower() for i in ids},(name,len(anchors))
    rendered=[a for a in parsed.table_rows if len(a)==6 and a[0].strip() in ids]
    assert len(rendered)==len(ids) and [a[0].strip() for a in rendered]==ids,(name,len(rendered))
    assert all(len(a)==6 and a[2].strip()==r["implementation"] and a[3].strip()==r["result"] for a,r in zip(rendered,rows))
    local=0;pinned=0
    for link in set(parsed.links):
        url=urlsplit(link)
        if not url.scheme and not url.netloc:
            if url.path:
                target=(name.parent/unquote(url.path)).resolve()
                assert target.is_file() and target.is_relative_to(out),(name,link)
            elif url.fragment:
                assert url.fragment in anchors,(name,link)
            local+=1
        elif url.netloc=="github.com" and "/blob/"+sysinfo["head"]+"/" in url.path:
            p=root/unquote(url.path.split("/blob/"+sysinfo["head"]+"/",1)[1])
            assert p.is_file(),link
            if re.fullmatch("L[0-9]+",url.fragment): assert 1<=int(url.fragment[1:])<=len(p.read_text(encoding="utf-8").splitlines()),link
            pinned+=1
    if name==main:
        for group,s in stats.items():
            if group=="transitions":continue
            label={"全部":"全部追蹤項目","功能 FR":"原編號功能 FR","P0":"FR 中的 P0","P1":"FR 中的 P1","P2":"FR 中的 P2","核心情境 AC":"核心驗收情境 AC"}.get(group,group)
            found=next(x for x in parsed.table_rows if x[0].strip()==label)
            nums=list(map(int,[z.strip() for z in found[1:]]))
            assert nums==[s["total"],*s["implementation"].values(),*s["result"].values()],(group,nums)
    html_checks[name.name]={"parsed_gfm_tables":parsed.tables,"six_column_requirement_rows":len(rendered),"unique_requirement_anchors":len(anchors),"working_local_links_and_anchors_unique":local,"pinned_source_links_verified_against_the_SHA":pinned}
contract=read(here/"openapi-routes.json")
published={m.upper()+" "+p for p,methods in contract.items() for m in methods}
observed=set(read(here/"observed-api.json"))|set(read(here/"extra-observed-api.json"))|set(read(out/"evidence/modules/remaining-http.json"))
assert len(published)==93 and observed-published=={"WS /ws/trips/{trip_id}"} and published<=observed
assert len(re.findall(r'^\| D\d\d ',intro,re.M))==17
regress=[r["id"] for r in rows if r["previous"]["result"]=="PASS" and r["result"]=="FAIL"]
gains=[r["id"] for r in rows if r["previous"]["result"]!="PASS" and r["result"]=="PASS"]
assert len(gains)==42 and len(regress)==4
save(report_file,{"checked_at":datetime.datetime.now().astimezone().isoformat(),"spec_lines":len(lines),"nonblank_lines":len(coverage),"classified_nonblank":dict(Counter(v["kind"] for v in coverage)),"ids":len(ids),"duplicate_ids":0,"all_rows_have_direct_evidence_or_dependencies":True,"per_row_evidence_links":evidence_refs,"all_109_FR_14_BR_20_AC_in_original_spec_matched":True,"published_http_operations_exercised":len(published),"websocket_handshake":101,"handoff_cards_rechecked":17,"results":stats["全部"],"pass_gain_ids":gains,"prior_pass_now_fails":regress,"rendered":html_checks,"source_integrity":"integrity.json"})
# Publish only the report and diagnostic artifacts. Neither database dumps nor runtime logins live under this tree.
zpath=out/"WayToGo-第二輪驗收證據.zip"
files=sorted(p for p in out.rglob("*") if p.is_file() and p!=zpath)
assert not any(p.suffix.lower() in [".sqlite",".db",".dump",".env",".pyc",".exe"] or p.name in ["runtime.json","pg-ui.json","sqlite-ui.json",".env"] or "__pycache__" in p.parts for p in files)
sums.write_text("".join(digest(p)+"  "+p.relative_to(out).as_posix()+"\n" for p in files if p!=sums),encoding="utf-8")
with zipfile.ZipFile(zpath,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,p.relative_to(out).as_posix())
with zipfile.ZipFile(zpath) as z:
    assert not z.testzip()
    assert set(z.namelist())=={p.relative_to(out).as_posix() for p in files}
    for record in z.read(sums.relative_to(out).as_posix()).decode("utf8").splitlines():
        h,n=record.split("  ",1); assert hashlib.sha256(z.read(n)).hexdigest()==h==digest(out/n)
print(json.dumps({"matrix_rows":len(rows),"report_rows":html_checks[main.name]["six_column_requirement_rows"],"total":stats["全部"],"zip_entries":len(files),"zip_bytes":zpath.stat().st_size,"zip_sha256":digest(zpath)},ensure_ascii=False))


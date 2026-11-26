"""Check all report anchors, linked evidence, counts, spec and source-file hashes."""
from pathlib import Path
import collections,hashlib,json,re,sys,urllib.parse,zipfile
from html.parser import HTMLParser
from run_system import repo,out,fingerprint,git
dest=out.parents[1]
def get(f):return json.loads(f.read_text(encoding="utf8"))
def put(f,v):f.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding="utf8")
bef=get(out/"source-sha256.json");aft=fingerprint()
before=(out/"git-before.txt").read_text(encoding="utf8").splitlines()
now=[x for x in git("status","--short","--branch","--untracked-files=all") if "acceptance-20261125/" not in x]
now+=git("remote","-v")+git("rev-parse","HEAD")
attachment=Path.home()/"Downloads/spec.md"
sampled=(hashlib.sha256(attachment.read_bytes()).hexdigest(),hashlib.sha256((repo/"docs/spec.md").read_bytes()).hexdigest())
ver={"before_product_files":len(bef),"after_product_files":len(aft),"changed_during_audit":[k for k in sorted(set(bef)|set(aft)) if bef.get(k)!=aft.get(k)],"product_git_status_equal":before==now,"excluded_from_git_status":["acceptance-20261125/"],"sha":git("rev-parse","HEAD")[0],"download_and_repository_spec_sha256":sampled,"applicable_agents_files":[p for p in aft if Path(p).name in ("AGENTS.md","AGENTS.override.md")],"line_count":len(attachment.read_text(encoding="utf8").splitlines())}
assert not ver["changed_during_audit"] and ver["product_git_status_equal"] and sampled[0]==sampled[1]
put(out/"integrity.json",ver)
class Check(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.targets=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if "id" in a:self.ids.append(a["id"])
        for k in ("href","src"):
            if k in a:self.targets.append(urllib.parse.unquote(a[k]))
page=dest/"功能驗收報告.html"
c=Check();c.feed(page.read_text(encoding="utf8"))
bad=[]
for t in c.targets:
    if t.startswith("#"):
        if t[1:] not in c.ids:bad.append(t)
    elif not t.startswith(("https://","http://")) and not (dest/t).is_file():bad.append(t)
assert len(set(c.ids))==len(c.ids)
rows=get(dest/"需求矩陣.json");stats=get(out/"statistics.json")
assert len(set(r["id"] for r in rows))==len(rows)==stats["全部"]["total"]
assert all(c.ids.count(r["id"])==1 for r in rows)
for k in ("implementation","result"):
    assert dict(collections.Counter(r[k] for r in rows))==stats["全部"][k]
assert not bad,bad
summary={"matrix_rows_in_rendered_HTML":len(rows),"unique_HTML_ids":len(c.ids),"local_and_remote_link_references":len(c.targets),"broken_local_links_or_anchors":bad,"every_row_has_evidence":all(r["evidence"] and r["notes"] for r in rows),"all_summary_counts_match_matrix":True}
put(out/"report-validation.json",summary)
print(json.dumps(ver|summary,ensure_ascii=False))

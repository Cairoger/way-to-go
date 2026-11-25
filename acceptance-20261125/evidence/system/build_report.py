"""Build the portable Traditional Chinese HTML report from the measured evidence."""
from pathlib import Path
from collections import Counter
import json,re,html,hashlib,sys,zipfile
from shutil import copyfile
from run_system import repo,out,source_paths,fingerprint,git
import matrix_additions,matrix_structure

dest=out.parents[1]
def load(p):return json.loads((dest/p).read_text(encoding="utf-8-sig"))
def store(p,data):(dest/p).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")
copyfile(repo/"docs/spec.md",out/"spec-reference.md")
spec=(out/"spec-reference.md").read_text(encoding="utf8")
L=[""]+spec.splitlines()
R={}; deferred={}; lineids={}; sname={}; current="前言"
for n,txt in enumerate(L):
    if txt.startswith("# "):current=txt[2:].split(" ")[0]
    if txt.startswith("## "):current=txt[3:].split(" ")[0]
    sname[n]=current
def clean(x):
    return re.sub(r"^(?:\d+\.\s+|-\s+)","",x).replace("**","").replace("\x60","").strip()
def append(row,n):
    assert row["id"] not in R,row
    row["line"]=n
    R[row["id"]]=row
    lineids.setdefault(n,[]).append(row["id"])
def d(id,n,im,res,e,note,c=None):
    append(dict(id=id,section="§"+sname[n]+f" L{n}",condition=c or clean(L[n]),implementation=im,result=res,evidence=e,notes=note),n)
def r(id,n,refs,note="",c=None):
    if not c and n in [601,612,622,633,644]:c=clean(L[n]).replace("完成條件：","")
    deferred[id]=(n,refs.split(),note,c)
for folder in ["core","modules"]:
    for row in load("evidence/"+folder+"/rows.json"):
        rid=row["id"]
        if rid.startswith("FR-"):
            n=next(n for n,s in enumerate(L) if s.startswith("**"+rid+" "))
        else:
            ln=re.search(r"L(\d+)",row["section"])
            n=int(ln[1]) if ln else (249 if rid.startswith("EXT-VOTE") else next(n for n,s in enumerate(L) if "所有金額採精確" in s))
        append(row,n)
schema=load("evidence/system/schema.json")
two=load("evidence/browser/two-clients.json")
sample=two["samples"][-1]
duration=sample["seconds"]
long_ok=duration>=355 and all(s["peak"]==1 and s["live"]==1 for s in sample["ws"])
ctx={"PERF-02":("兩人畫面更新 P95 181 ms；五人於 SQLite 與 PostgreSQL 17 均在第一次編輯等待 10 秒逾時。五人沒有足夠的成功樣本可計算 P95。另見 collaboration-postgres.json、two-clients.json。","Partial","FAIL"),
"PERF-03":(f"兩人旅程頁持續 {duration} 秒，每次取樣的連線計數見 two-clients.json；五人長時觀測因同步逾時中止。","Implemented","PASS" if long_ok else "BLOCKED"),
"CHROME":("Chrome 全套 11/11 完成。涵蓋本機 web、真 API 與個別替身案例。","Implemented","PASS"),
"EDGE":("Edge 全套 11/11 完成。","Implemented","PASS"),
"FIREFOX":("Playwright Firefox 10/10；標準 Firefox 發行版與 OS 的其他組合未逐一測。框架限定的 Chromium PDF 另計。","Implemented","PASS"),
"SAFARI":("Windows 可測 Playwright WebKit 引擎，沒有 macOS／iOS 近期正式版 Safari。","Unknown","BLOCKED"),
"ux_states":("Implemented","PASS"),
"ms4":("五名真瀏覽器正常留言，建立的五筆均查回；接著一人編輯，其他頁面在 10 秒內沒有更新。SQLite 及 Docker／PostgreSQL 17.12 得到同樣結果。","Partial","FAIL")}
matrix_additions.populate(R,d,r,L,schema,ctx)
matrix_structure.populate(R,d,r,L,schema,ctx)
# Independent acceptance points in enumerations, with measurements at the field or action level.
for n in range(171,178):
    if L[n].startswith("- "):
        d(f"PLACE-FIELD-{n-170}",n,"Implemented","PASS","evidence/core/probes.log → test_core_places_fields_status_author_days；evidence/core/test_acceptance_core.py","送出後重讀景點、建立者及修改紀錄，逐一比對欄位。")
# Line numbering must reflect the spec, not an assumption about blank lines.
for n,s in enumerate(L):
    if 162<n<180 and s.startswith("- ") and n not in lineids:
        d(f"PLACE-FIELD-L{n}",n,"Implemented","PASS","evidence/core/probes.log → test_core_places_fields_status_author_days","以 API 保存並重讀欄位與歷史。")
extra=[
("COPY-PLAN","FR-TRIP-08","複製景點、每日項目、公開連結與安排","test_copy_planning_snapshot_to_own_trip_only、test_copy_linked_travel_arrangements_without_private_booking_or_assignees","副本使用新 ID，交通與住宿回到規劃狀態。"),
("COPY-OMIT","FR-TRIP-08","複本排除成員、投票、分帳和私人訂位資訊","test_copy_linked_travel_arrangements_without_private_booking_or_assignees、test_copy_planning_snapshot_to_own_trip_only","確認原成員、投票、財務等未帶入，預訂清除乘客與代碼。"),
("BOOK-REF","FR-BOOK-05","預訂代號僅獲授權的人可讀","test_reservation_privacy_and_edits","相關乘客可讀，旁觀成員的回應沒有代號。"),
("VOTE-PRIVATE","FR-VOTE-07","開放期間只能看自己的選票","test_secret_ballots_and_review_after_new_option","投票中不公開選擇，補選項後有重新檢視提示。"),
("VOTE-PUBLIC","FR-VOTE-07","結束後可看個別選票與統計","test_rating_ballot_requirements_privacy_review_and_result","評分各票與結算按預期顯示。")]
for id,ref,c,t,msg in extra:d(id,R[ref]["line"],"Implemented","PASS","evidence/system/postgres-suite.txt → "+t,msg,c)
for id,ref,cond in [("COPY-FILES","FR-TRIP-08","副本排除原旅程私人文件"),("BOOK-FILES","FR-BOOK-05","私人文件由授權成員存取")]:
    d(id,R[ref]["line"],"Unknown" if id=="COPY-FILES" else "Missing","BLOCKED","evidence/modules/probes.txt → test_file_contract_and_comment_images","沒有可建立的私人附件，無法放入檔案再做正反驗證。",cond)
for id,c,detail in [
    ("PDF-BOOKING","預設及詳細 PDF 排除預訂代號","實際建立預訂並回讀。同旅程的兩種輸出均有公開活動，DOM 及兩個 PDF 文字層都沒有該筆訂位代號。"),
    ("PDF-FINANCE","預設及詳細 PDF 排除分帳細節","實際記帳 125.79 並分攤 91.23 與 34.56。兩份 PDF 與列印 DOM 皆無費用名、分攤旅伴名及相關金額。")]:
    d(id,R["FR-PDF-02"]["line"],"Implemented","PASS","evidence/browser/pdf-private.json；evidence/browser/pdf-private-text.json",detail,c)
d("PDF-FILES",R["FR-PDF-02"]["line"],"Unknown","BLOCKED","evidence/browser/pdf-private-text.json；evidence/modules/probes.txt","沒有私人檔案物件可加入匯出的旅程；單元測試中的文字哨兵通過。","PDF 排除實際私人文件")
R["FR-PDF-02"].update(evidence="evidence/browser/pdf-private.json；evidence/browser/pdf-private-text.json；evidence/browser/unit.txt；evidence/modules/probes.txt",notes="兩份真 PDF 的文字層及列印 DOM 均排除同旅程已保存的訂位代號、分攤明細等六個標記；公開活動存在。無法建立真實私人文件，因此整項保留受阻。")
# Normalize ids and order by the original requirement line. Resolve cross-references recursively.
def resolve(id,path=()):
    if id in R:return R[id]
    assert id not in path,(id,path)
    n,ids,note,c=deferred[id]
    children=[resolve(i,path+(id,)) for i in ids]
    rs=[x["result"] for x in children]; ims={x["implementation"] for x in children}
    result=next(x for x in ["FAIL","BLOCKED","NOT TESTED","PASS"] if x in rs)
    imp=next(iter(ims)) if len(ims)==1 else "Partial" if ("Partial" in ims or "Missing" in ims) else "Unknown"
    d(id,n,imp,result,"、".join(ids),note or "各條件的觀察值及測試輸出見所列關聯列。",c)
    return R[id]
for key in deferred:resolve(key)
# Carry execution evidence discovered by the full cross-module runs.
R["AC-008"].update(evidence="evidence/core/timeout-merge.log → test_core_expiration_after_editor_disappears；evidence/core/probes.log",notes="編輯者離開後沒有釋鎖或續租；先取得 423，實等 90.5 秒後重新取鎖成功。")
R["ROLE-12"].update(evidence="evidence/modules/own-comments.txt；evidence/system/postgres-suite.txt → test_comment_moderation_and_preserved_replies",notes="Owner 與 Member 各自刪自己的留言均回 200。兩方重讀原留言已清空、deleted=true、版本升為 2；子回覆和 parent_id 保留。")
R["PERF-01"].update(evidence="evidence/system/mixed-api.json；evidence/system/latency.json",notes="Compose／PostgreSQL 的 5 位旅伴並行進行常見業務操作：60 個讀取與 30 個留言／任務寫入，90 筆混合 P95 75.71 ms（讀取 75.45、寫入 79.00）。另一次 60 筆四路徑純讀 P95 56.30 ms。均為本機 loopback，不含外部服務。")
R["PERF-02"]["evidence"]+="；evidence/browser/collaboration-postgres.json；evidence/browser/two-clients.json"
R["PERF-03"]["evidence"]="evidence/browser/two-clients.json；evidence/browser/collaboration-postgres.json"
R["MS4-DONE"]["evidence"]+="；evidence/browser/collaboration-postgres.json"
R["TECH-02"]["notes"]+=" 規格以本機組合的 shadcn/ui 模式驗收，未要求第三方 CLI 產生檔案。"
for i in range(1,16):
    row=R[f"ROLE-{i:02}"]
    fields=[s.strip() for s in L[row["line"]].strip("|").split("|")]
    row["condition"]=f"{fields[0]}。Owner：{fields[1]}；Member：{fields[2]}。"
R["UX-01"]["evidence"]=R["UX-01"]["evidence"].replace("→ mobile","→ rwd")
R["UX-SAFARI"]["notes"]+=" Windows WebKit 27.2 正常重跑 8/10；兩個失敗案例的對照見 ui.md，無法據此歸因於 Safari 正式版。"
R["UX-FIREFOX"].update(implementation="Implemented",result="PASS",evidence="evidence/core/firefox-release.log；evidence/core/firefox-release.png；evidence/browser/firefox-playwright.txt",notes="Mozilla Firefox 161.0 Windows 正式版以獨立 profile 操作登入、建立旅程、重載、保存活動及產生邀請連結／QR。另以 Playwright 的 Firefox 159.0 測試組建通過 10/10。")
R["UX-01"]["evidence"]+="；evidence/browser/sections.json"
R["UX-01"]["notes"]+=" 兩種寬度各打開十個旅程模組，20/20 標題可見且無整頁溢位。"
R["UX-05"]["evidence"]+="；evidence/browser/sections.json"
R["UX-05"]["notes"]+=" 桌面和手機十個模組皆觀察到對比違規，其中包括共用元件。"
# Documentation headings and repeated introductory text link to existing rows without new counts.
for n,ids in {7:["UX-01","FR-OFFLINE-01"],8:["DEV-WORKFLOW"],9:["OPS-01","FREE-01"],17:["VALUE-01","VALUE-02","VALUE-03"],19:["OV-01"],69:["ROLE-00"],121:["FR-TRIP-02"],402:["PERF-01","PERF-02"],482:["ARCH-08"],646:["MS5-DONE"],691:["OUT-07"]}.items():
    lineids.setdefault(n,[]).extend(ids)
for row in R.values():
    assert row["implementation"] in ["Implemented","Partial","Missing","Unknown"] and row["result"] in ["PASS","FAIL","BLOCKED","NOT TESTED"] and row["evidence"] and row["notes"],row
fr=set(re.findall(r"^\*\*(FR-[A-Z]+-\d+) \[",spec,re.M));br=set(re.findall(r"^\| (BR-\d+) \|",spec,re.M));ac=set(re.findall(r"^\| (AC-\d+) \|",spec,re.M))
for prefix,group in [("FR-",fr),("BR-",br),("AC-",ac)]:assert {i for i in R if i.startswith(prefix)}==group
rows=sorted(R.values(),key=lambda x:(x["line"],x["id"]))
def counts(ls):
    return {"total":len(ls),"implementation":dict(Counter(x["implementation"] for x in ls)),"result":dict(Counter(x["result"] for x in ls))}
prior={m[1]:m[2] for m in re.finditer(r"\*\*(FR-[A-Z]+-\d+) \[(P\d)\]",spec)}
for row in rows:row["priority"]=prior.get(row["id"],"")
stat={key:counts(group) for key,group in [("全部",rows),("原編號功能",[R[i] for i in fr]),("業務規則",[R[i] for i in br]),("核心驗收",[R[i] for i in ac])]+[(pri,[R[i] for i in fr if prior[i]==pri]) for pri in ("P0","P1","P2")]}
# Each normative sentence, rule table row and milestone entry gets a source index.
coverage=[]
for n,t in enumerate(L):
    if not t.strip():continue
    ids=list(dict.fromkeys(lineids.get(n,[])))
    if not ids and n<694 and (t.startswith("- ") or re.match(r"^\d+\. ",t) or re.match(r"^\| (?!操作 |編號 |Layer |Entity |模組 |ID )",t) or t.startswith("**完成條件")):raise RuntimeError(f"unmapped normative line {n}: {t}")
    coverage.append({"line":n,"spec":t,"ids":ids,"kind":"可驗收／追蹤" if ids else ("參考資料" if n>=695 else "文件結構／說明")})
store("需求矩陣.json",rows)
store("evidence/system/coverage.json",coverage)
store("evidence/system/statistics.json",stat)
print(json.dumps(stat,ensure_ascii=False))


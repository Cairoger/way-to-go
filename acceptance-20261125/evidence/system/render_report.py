"""Create a self-contained local report with a filterable matrix, links, and no network dependencies."""
from build_report import *
from issues_catalog import issues
import urllib.parse
esc=lambda x:html.escape(str(x),quote=True)
def link(p,label=None):
    return '<a href="'+esc(urllib.parse.quote(p,safe="/#:-._"))+'">'+esc(label or Path(p).name)+'</a>'
def req(id):
    return '<a href="#'+esc(id)+'" class="idref">'+esc(id)+'</a>'
links_by_name={}
for p in (dest/"evidence").rglob("*"):
    if p.is_file():
        k=p.name
        if k not in links_by_name:links_by_name[k]=p.relative_to(dest).as_posix()
        else:links_by_name[k]=None
def refs(txt):
    pat=r"evidence/[a-z]+/[A-Za-z0-9_.-]+|(?<![\w/])(?:[A-Za-z0-9_.-]+\.(?:json|log|txt|png|cjs|pdf|md))(?![\w/])|(?<![\w/-])[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+(?![\w-])"
    parts=[];last=0
    for m in re.finditer(pat,txt):
        parts.append(esc(txt[last:m.start()]));s=m[0]
        if s in R:val=req(s)
        elif s.startswith("evidence/") and (dest/s).is_file():val=link(s,s)
        elif s in links_by_name and links_by_name[s]:val=link(links_by_name[s],s)
        else:val=esc(s)
        parts.append(val);last=m.end()
    return "".join(parts)+esc(txt[last:])
def el(tag,content,attrs=""):return "<"+tag+(" "+attrs if attrs else "")+">"+content+"</"+tag+">"
def p(txt):return el("p",refs(txt))
def tr(vals,t="td"):return el("tr","".join(el(t,x) for x in vals))
def table(head,rs):
    return '<div class="scroll"><table><thead>'+tr(head,"th")+'</thead><tbody>'+''.join(tr(x) for x in rs)+'</tbody></table></div>'
def section(anch,title,body):
    return '<section id="'+anch+'"><h2>'+title+"</h2>"+body+"</section>"
def badge(x):
    return '<span class="badge '+x.lower().replace(" ","-")+'">'+esc(x)+'</span>'
def block(id,title,txt):
    return '<article><h3>'+req(id)+'　'+esc(title)+'</h3>'+p(txt)+'</article>'
def evidence_links(paths):
    return ' · '.join(link(x) for x in paths.split())
fr_stat=stat["原編號功能"];tot=fr_stat["total"];passed=fr_stat["result"]["PASS"];failed=fr_stat["result"]["FAIL"];impl=fr_stat["implementation"]["Implemented"]
ss=stat["全部"]; sha="f398d983b5a2769ca2d06285cbece4fbabc176ab"
header="""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WayToGo 功能驗收報告</title><style>
*{box-sizing:border-box}body{margin:0;color:#21332c;background:#f7f8f5;font:16px/1.72 "Microsoft JhengHei","Noto Sans TC",system-ui,sans-serif}main{max-width:1520px;margin:auto;padding:30px clamp(16px,4.6vw,76px) 80px}p,li,dt,dd,td,code{overflow-wrap:anywhere}h1,h2,h3{line-height:1.32;color:#142e25}h1{font-size:clamp(32px,5vw,56px);margin:6px 0 10px}h2{font-size:26px;margin:0 0 18px}h3{font-size:19px;margin:18px 0 8px}p{max-width:105ch;margin:9px 0 14px}a{color:#075c53;text-underline-offset:3px;overflow-wrap:anywhere}header{border-top:7px solid #255744;padding:24px 0 16px}.dat{color:#495c52;font-size:14px}.lead{font-size:20px;max-width:85ch}.tabs{display:flex;flex-wrap:wrap;gap:8px 22px;border-block:1px solid #becdc1;padding:12px 0}.tabs a{font-weight:bold}section{padding:30px 0;border-bottom:1px solid #bdccbf}article{background:white;margin:14px 0;padding:12px 20px;border:1px solid #cdd9cf;border-radius:5px}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid #d4ddd6;text-align:left;vertical-align:top;padding:9px 10px}th{background:#e3ebe5;white-space:nowrap}thead th{color:#213e32}tbody tr:nth-child(even){background:#f1f4f1}td.mono,.idref,code{font-family:Consolas,"Microsoft JhengHei",monospace;font-size:.94em}.badge{font:bold 12px/1.4 Consolas,monospace;display:inline-block;padding:3px 6px;background:#e1e7e2;border-radius:3px;white-space:nowrap}.pass,.implemented{color:#115138;background:#dbefde}.fail,.missing{color:#882526;background:#f9e0de}.blocked,.partial{color:#684700;background:#f4e9c8}.not-tested,.unknown{color:#414c56;background:#e1e6ea}td.ev{font-size:13px;line-height:1.55;word-break:break-word}.ctl{display:flex;align-items:end;gap:14px;flex-wrap:wrap;margin:16px 0}.ctl label{display:flex;flex-direction:column;font-weight:bold;font-size:14px}.ctl input,.ctl select,.ctl button{font:inherit;padding:6px;border:1px solid #7d9384;background:white;border-radius:3px}.ctl input{min-width:20ch}.results{color:#435a4c}.matrix{min-width:930px;table-layout:fixed}.matrix th:nth-child(1){width:14%}.matrix th:nth-child(2){width:20%}.matrix th:nth-child(3){width:8%}.matrix th:nth-child(4){width:8%}.matrix th:nth-child(5){width:24%}.matrix td{overflow-wrap:anywhere}.matrix tr:target{outline:3px solid #9d6625;background:#fff7e7}.id{font:600 13px Consolas,monospace}small{display:block;color:#4c6154}.hits{font-weight:bold}.figs{display:flex;gap:18px;flex-wrap:wrap}.figs figure{margin:10px 0;flex:1 1 220px;max-width:420px}.figs img{width:100%;max-height:225px;object-fit:contain;background:#e6ebe6;border:1px solid #c7d1c9}.figs figcaption{font-size:14px}.issue dt{font-weight:bold;color:#294f3e}.issue dd{margin:0 0 9px;max-width:110ch}pre{padding:13px;background:#e7ede7;overflow:auto;font-size:13px}.issue h3 a{text-decoration:none;color:inherit}details{margin:12px 0}summary{cursor:pointer;font-weight:bold}.note{border-left:3px solid #ca8d36;padding:2px 12px}.small{font-size:14px}@media print{main{max-width:none;padding:0}.tabs,.ctl{display:none}.scroll{overflow:visible}.matrix{min-width:0}th,td{padding:3px;font-size:9px}.matrix td.ev{font-size:9px}.badge{font-size:8px}article{break-inside:avoid}a{color:inherit}} 
</style></head><body><main>"""
body=[header]
body.append('<header><div class="dat">2026 年 11 月 25 日 · Asia/Taipei · PRD / SRS v1.0</div><h1>WayToGo 功能驗收報告</h1><p class="lead"><strong>適合展示雙人規劃與分帳流程。五人協作尚未達到 MVP 驗收條件，履歷上的 GitHub 版本也少了本機的進階功能。</strong></p></header>')
body.append('<nav class="tabs" aria-label="報告章節">'+''.join(link("#"+k,v) for k,v in [("summary","驗收摘要"),("version","版本與環境"),("observations","實測結果"),("issues","缺陷與重現"),("matrix","需求追蹤矩陣"),("verdict","最終評估"),("coverage","規格核對與重跑")])+'</nav>')
def stats_table():
    imkeys=["Implemented","Partial","Missing","Unknown"];outkeys=["PASS","FAIL","BLOCKED","NOT TESTED"]
    return table(["範圍","列數"]+list(map(badge,imkeys+outkeys)),[[esc(k),str(v["total"])]+[str(v["implementation"].get(x,0)) for x in imkeys]+[str(v["result"].get(x,0)) for x in outkeys] for k in ["全部","原編號功能","P0","P1","P2","業務規則","核心驗收"] for v in [stat[k]]])
summary=p(f"原規格有 {tot} 個 FR。工作樹有 {impl} 項完整實作（{impl/tot:.1%}），{passed} 項有實測通過證據（占全部 FR 的 {passed/tot:.1%}）。在已得出 PASS 或 FAIL 的 {passed+failed} 項中，通過率為 {passed/(passed+failed):.1%}。其餘受阻的功能保留在分母 {tot} 中，部分實作沒有折算成半項。")
summary+=stats_table()
labels={"AUTH":"帳號驗證","TRIP":"旅程管理","INV":"邀請","PLACE":"景點","PLAN":"每日行程","COLLAB":"即時協作","VOTE":"投票","DATE":"日期協調","COMMENT":"留言","TASK":"任務","FIN":"預算與分帳","BOOK":"交通與住宿","FILE":"文件與附件","MAP":"地圖","WEATHER":"天氣","NOTIFY":"通知","PDF":"PDF 匯出","OFFLINE":"離線","HISTORY":"歷史與復原"}
groups=[]
for group,title in labels.items():
    part=[row for row in rows if row["id"].startswith("FR-"+group+"-")]
    c=counts(part);exceptions=[req(x["id"]) for x in part if x["result"]!="PASS"]
    groups.append([esc(title),str(len(part)),str(c["result"].get("PASS",0)),str(c["result"].get("FAIL",0)),str(c["result"].get("BLOCKED",0)),"、".join(exceptions) if exceptions else "全部通過"])
summary+='<details><summary>依功能模組查看 109 個 FR 的通過、失敗與受阻項目</summary>'+table(["模組","FR 數","通過","失敗","受阻","需重查的編號"],groups)+'</details>'
summary+=p(f"全部共有 {ss['total']} 個可追蹤驗收列。109 個 FR、14 個 BR、20 個 AC 沿用原編號；其餘是補充條款、獨立子條件、角色、非功能、架構、資料表、API、里程碑及排除範圍。多個章節可能要求同一能力，因此「全部」是規格追蹤列數，完成度採 FR 口徑。P0–P2 是 109 個 FR 的分組，BR、AC 與 FR 的數字不能相加解讀為互斥的產品功能。")
summary+=p("完整實作表示程式、資料與必要介面已接通；執行時仍可能有缺陷。FAIL 必須觀察到不符，BLOCKED 是缺少必要條件或證據無法覆蓋整段流程，NOT TESTED 記錄尚未執行的測試。混合條件中已證實的不符優先列 FAIL，其次才是受阻；依賴列可連回原測例。資料表與排除範圍的驗收對象分別是實際遷移結構及交付物清單。")
body.append(section("summary","驗收摘要",summary))
source=load("evidence/system/environment.json")
version=table(["基準","此次驗收的事實"],[
["Repository 與分支",link("https://github.com/Cairoger/way-to-go","Cairoger/way-to-go")+f" · main · <code>{sha}</code>。匿名 GitHub 查詢與唯讀遠端分支比對見 "+link("evidence/core/clean-head.md")],
["工作區",f"主矩陣驗收 {source['tracked_modified']} 個已修改及 {source['untracked_source']} 個未追蹤產品檔在內的工作樹。"+evidence_links("evidence/system/git-before.txt evidence/system/source-sha256.json evidence/system/integrity.json")],
["規格與專案指引",f"下載附件和 docs/spec.md 的 SHA-256 同為 <code>{source['spec_sha256']}</code>。已核對專案、上層及子目錄，未發現適用的 AGENTS.md。README 的歷史測試數字另行重測。"],
["前後端","Windows 11 build 22631、Node 24.22.3、Next.js 16.4.6、React／TypeScript、Tailwind／Radix 元件、Python 3.12.14、FastAPI 0.165.0、SQLAlchemy 2.0.58、Alembic 1.20.1。"+evidence_links("evidence/system/environment.json evidence/browser/ui.md")],
["部署與資料","Docker Compose v2.39.4、PostgreSQL 17.12；另用獨立 PostgreSQL 16.2 與 SQLite 驗證完整後端套件。容器、新資料卷、隨機 loopback 埠與合成身分均為驗收專用。"],
["呼叫路徑","瀏覽器經 nginx 存取 Next.js、FastAPI REST 及 WebSocket。API 單體處理權限、版本、租約與交易；PostgreSQL 保存旅程、投票、歷史和財務。背景備份程序另掛載備份目錄。查地點、天氣與匯率分別使用 MediaWiki、Open-Meteo、Frankfurter。"],
["可公開取得的版本","乾淨 HEAD 為遷移 0002、HTTP 操作 50 個、資料表 22 張。驗收工作樹為 0007、83 個操作、38 張表；操作數包含同一 URL 的不同 HTTP 方法，表數包含 alembic_version。公開版和工作版的各模組 HTTP 回應見 "+link("evidence/core/clean-head.json")+"。"],
])
body.append(section("version","版本、執行環境與公開展示差異",version))
observ=table(["實測範圍","預期與觀察","可重查證據"],[
["後端與資料庫","工作樹全部 47 個 pytest 在 SQLite 與 PostgreSQL 各通過一次。兩套完整執行都有 Starlette 測試套件棄用警示。分組跑的五連線收尾曾偶發失敗，單獨重跑成功。Alembic 升至 0007 並通過模型一致性檢查。",evidence_links("evidence/system/sqlite-suite.txt evidence/system/postgres-suite.txt evidence/system/alembic-check.txt evidence/core/ws-retry.log")],
["瀏覽器與前端","Vitest 5/5，typecheck、lint、format、production build 通過。Chrome、Edge 各 11/11；Playwright Firefox 159.0 為 10/10，Windows WebKit 27.2 為 8/10。Mozilla Firefox 161.0 Windows 正式版另通過登入、建立、重載與邀請。沒有近期正式版 Safari 的實機結果。",evidence_links("evidence/browser/ui.md evidence/browser/unit.txt evidence/browser/chrome-playwright.txt evidence/browser/edge-playwright.txt evidence/core/firefox-release.log evidence/browser/firefox-playwright.txt evidence/browser/webkit-playwright.txt")],
["雙人完整規劃","以本機 Owner 建旅程，訪客加入；建立、編輯、移除活動，持鎖、同日與跨日實際拖曳、對方頁面更新，斷線期間未收到的活動在重連後自動出現。編輯者離開，實等 90.5 秒可重新取鎖。",evidence_links("evidence/core/browser.log evidence/core/browser-lifecycle.log evidence/core/timeout-merge.log")],
["五人與效能","正式 Compose 的五人混合 60 讀＋30 寫，90 筆請求 P95 75.71 ms。另一次五個協定客戶端、60 筆唯讀 P95 56.30 ms；12 次留言 × 5 次收件再讀取，60 個觀測的 P95 90.06 ms。兩個真瀏覽器的 20 次編輯至對方 DOM 可見 P95 181 ms。五個真瀏覽器未通過同一討論情境，兩種資料庫都在下一次編輯等候 10 秒逾時。",evidence_links("evidence/system/mixed-api.json evidence/system/latency.json evidence/browser/two-clients.json evidence/browser/five-clients.json evidence/browser/collaboration-postgres.json")],
["決策與協調","實測景點／日期、單複選、評分／排序、重新檢視選票、結果公開、平票重投及手動採用。日期可用區間與正式投票分離；套用或改日期時保留活動。",evidence_links("evidence/modules/probes.txt evidence/modules/module-ui-final.txt evidence/modules/cross-checks.txt")],
["任務、預訂、分帳與通知","真實雙人流程涵蓋私人／共用任務、旅客可見訂位欄位、留言提及與已讀、外幣支出、超額警告及兩次還款。API 另驗多付款人、子集合分攤、尾差及離開成員的歷史。",evidence_links("evidence/browser/chrome-playwright.txt evidence/modules/pytest.txt evidence/modules/probes.txt")],
["第三方服務、地圖與 PDF","實際查到台北 101 座標、Open-Meteo 氣溫 15.8–19.7 °C／降雨 31%、Frankfurter USD/TWD 32.956，亦觀察到正常 OSM 圖磚。中止圖磚後文字、地址、外連與順序線仍在。實際匯出 A4 PDF 核對日期與詳略；另在同旅程保存預訂與分攤，兩種 PDF 抽字均無訂位代號、分攤者及金額。實際私人檔案物件無法建立，整項 FR-PDF-02 受阻。天氣成功 UI 畫面使用實查數值重播。",evidence_links("evidence/core/wiki-retry.log evidence/modules/providers-network.txt evidence/modules/map-network.txt evidence/browser/itinerary-details.pdf evidence/browser/itinerary-brief.pdf evidence/browser/pdf-private-text.json evidence/browser/pdf-private-details.pdf")],
["部署與復原","Docker 的首頁、/health、/docs、/openapi.json 與 PWA manifest 均回 200。強制重建容器仍有 1 趟旅程、4 個活動。將實際備份服務產物還原至空資料庫得到相同數量。另測同一備份腳本的週期、過期刪除與低容量告警。",evidence_links("evidence/system/docker-http.json evidence/system/docker-after-restart.txt evidence/system/docker-restored-counts.txt evidence/system/backup-policy.txt")],
["RWD 與無障礙","讀取 320、390、768、1280 px 的行程頁無水平溢出；390 px 可完成選單與登入操作。桌面與手機各打開十個模組均無整頁溢位，20 個畫面均驗出對比缺失；首頁另有標籤問題。手機尺寸來自瀏覽器視窗，實機 Safari 與完整人工 WCAG 仍待驗。",evidence_links("evidence/browser/experience.json evidence/browser/sections.json evidence/browser/live-mobile.png")],
])
observ+=p("首頁三本示範手札使用固定樣本，明示唯讀，沒有連到該旅程的 WebSocket。Chrome 套件的 11 個案例有 6 個攔截部分或全部 API，2 個操作樣本或表單，3 個使用真後端與獨立身分。另有真 API、真瀏覽器補測。OIDC 交換與 Web Push 服務商替身僅用於驗證站內邏輯。詳見 evidence/modules/coverage-notes.md。")
figs=[("evidence/core/planner-cross-day.png","實際跨日拖曳後的旅程頁"),("evidence/browser/live-map-fallback.png","圖磚失效時仍可讀取地址與導航"),("evidence/browser/live-mobile.png","已登入旅程的手機尺寸畫面")]
observ+='<div class="figs">'+''.join('<figure><a href="'+f+'"><img loading="lazy" src="'+f+'" alt="'+esc(c)+'"></a><figcaption>'+esc(c)+'</figcaption></figure>' for f,c in figs)+'</div>'
body.append(section("observations","實際跑過的流程與結果",observ))
issue_html=p("依對求職展示及旅伴操作的影響排序。受阻項目另標示驗證界線；同一根因可能影響數個規格編號。")
webkit=("D17","中・相容性待釐清","Windows WebKit 的兩個端對端案例尚未穩定通過","UX-SAFARI","在隔離站台以 Windows WebKit 27.2 執行十個可跨引擎的既有案例，另跑真帳號簡化對照。","完成登入重載、行前任務與提及通知的既有流程。","獨立重跑仍為 8/10。行前流程超時，使用替身的本機登入重載找不到「我的旅程」；真服務的簡化登入重載有成功紀錄。","位置見 frontend/tests/live-preparations.spec.ts:7、frontend/tests/local-login.spec.ts:47 與 evidence/browser/ui.md。仍須釐清測例、引擎或實機行為。","優先在近期正式版 Safari 對照同流程，再檢查各步的頁面狀態與導覽等待。","evidence/browser/webkit-playwright.txt evidence/browser/ui.md")
for ix in [0,1,2,3,4,6,8,9,16,14,5,7,10,11,12,13,15]:
    id,sev,title,ids,steps,expect,actual,cause,fix,evi=(issues+[webkit])[ix]
    issue_html+='<article class="issue" id="'+id+'"><h3><a href="#'+id+'">'+esc(id+"　"+sev+"　"+title)+'</a></h3><p>'+''.join(req(i)+" " for i in ids.split())+'</p><dl>'
    for label,txt in [("重現",steps),("預期",expect),("實際",actual),("原因與程式位置",cause),("建議修復或補驗",fix)]:issue_html+="<dt>"+label+"</dt><dd>"+refs(txt)+"</dd>"
    issue_html+="</dl><p>"+evidence_links(evi)+"</p></article>"
issue_html+=p("其餘驗證界線包括 API／授權抽測未涵蓋所有攻擊類型、正式 HTTPS 網域、任意格式秘密的完整掃描、正式站的定期還原紀錄與免費服務實際部署用途。限制及已做的檢查分別列於 SEC-01、SEC-04、DEF-1、DEF-3、OPS-03、FREE-04。")
body.append(section("issues","問題、缺陷與待補驗項目",issue_html))
matrixintro=p("每列列出驗收條件、狀態及實際觀察。點需求 ID 可直接定位，關聯編號可跳到對應證據列；輸入關鍵字或選擇狀態可縮小範圍。")
ctl='<form class="ctl" id="filters"><label>關鍵字<input id="q" type="search" placeholder="例如 FR-PLAN 或 五人"></label>'
for tag,lab,arr in [("im","實作狀態",["Implemented","Partial","Missing","Unknown"]),("res","測試結果",["PASS","FAIL","BLOCKED","NOT TESTED"]),("pri","功能優先級",["P0","P1","P2"])]:
    ctl+='<label>'+lab+'<select id="'+tag+'"><option value="">全部</option>'+''.join(el("option",x) for x in arr)+'</select></label>'
ctl+='<button type="reset">清除篩選</button><output id="shown" class="results" aria-live="polite"></output></form>'
matrix=matrixintro+ctl+'<div class="scroll"><table class="matrix" id="rtm"><thead>'+tr(["需求 ID","規格位置與驗收條件","實作狀態","測試結果","驗證證據","實際結果、問題或界線"],"th")+'</thead><tbody>'
for x in rows:
    rid=x["id"]
    matrix+='<tr id="'+rid+'" data-res="'+x["result"]+'" data-im="'+x["implementation"]+'" data-pri="'+x["priority"]+'"><td>'+req(rid)+'</td><td><small>'+esc(x["section"]+" "+x["priority"])+'</small>'+esc(x["condition"])+'</td><td>'+badge(x["implementation"])+'</td><td>'+badge(x["result"])+'</td><td class="ev">'+refs(x["evidence"])+'</td><td>'+refs(x["notes"])+'</td></tr>'
matrix+="</tbody></table></div>"
body.append(section("matrix","需求追蹤矩陣",matrix))
verdict=p("工作樹已有足夠的真實流程展示全端能力：兩位旅伴可從邀請開始，共同安排多日行程、投票、接收提醒、管理行前任務及預訂，最後以實際分帳與還款資料完成結算。可以選一趟新建旅程作為面試展示，現場重載兩個瀏覽器並確認資料持久化。")
verdict+=p("目前不宜宣稱 MVP 全數通過。51 個 P0 中有 48 項通過、2 項失敗、1 項受阻。五人留言更新與原始景點移除均有可重現落差；真實 Google 授權流程仍需部署者的測試身分。P2 的附件及離線閱讀不列為 MVP 完成的前置條件。")
verdict+=el("ol","".join(el("li",refs(s)) for s in ["展示前先解決五人討論同步，並確認履歷連結與展示版本一致。修正後在同一 Compose 組態重跑五人端到端，而非只重跑 API 測試。","以受控 Google 帳號完成首次登入、邀請及訪客升級。補正原始景點移除、夏令時間及已測出的無障礙問題；同時補驗 WebKit 失敗的兩個流程與正式版 Safari。","若展示內容含進階功能，應揭示私人文件、離線閱讀與重複任務的現況。真機推播成功、附件存取／回收／配額及正式站復原仍需各自的證據。"]))
body.append(section("verdict","最終評估與展示順序",verdict))
cov=p(f"逐行核對附件 710 行，從編號到矩陣、從矩陣回查規格。109 個 FR、14 個 BR、20 個 AC 均只出現一次；每個原編號都有測試結果、實作狀態、證據及註記。全文索引指出每一個非空行對應的 ID 或文件性質；§11 的九個排除項以約束驗收，§12 的參考連結不計為功能。")
cov+=evidence_links("需求矩陣.json evidence/system/spec-reference.md evidence/system/coverage.json evidence/system/statistics.json evidence/system/integrity.json")
cov+=el("h3","判讀採用的假設")+el("ul","".join(el("li",refs(t)) for t in [
"當 Owner／Member 是既有旅程中的角色時，建立新旅程的權限由帳號類型決定。Google 類型及僅限本機的測試身分可以建立，訪客不可。真實 Google 授權另列受阻。",
"30 天是使用者可復原的期限；測試 29 天仍可復原與 31 天不可復原。單筆歷史復原按現有可辨識的景點與活動驗收，其他實體未提供通用回溯。",
"兩個以上日期、時間模式、六種行程項目、金額與分攤子情境在明細腳本及逐條索引內。路線最佳化按條件式規格驗收，沒有免費且穩定的路由供應商時保持停用，FR-MAP-04 的 PASS 不代表有路線引擎。",
"資料模型先接受同義欄位（例如 coordinates 由經緯度兩欄組成），指定實體表或關係位置不同則標記結構偏差；業務行為另列。個人資料維護按能更新暱稱驗收；原建立者採成員可查的解讀。",
"效能採最近秩 P95。API 計至回應、協定事件計至重新讀取、瀏覽器計至其他頁面 DOM 可見。單機 loopback 與限定時間的取樣不代表對外服務 SLA 或持續運作保證。",
"零付費限本次自架組態，未使用付費 API 金鑰；用量與合法用途仍取決於實際部署。Open-Meteo 的免費方案有非商業用途及流量限制；OSM 公用圖磚有署名及快取要求。"
]))
cov+='<p>'+link("https://open-meteo.com/en/terms","Open-Meteo 使用條款")+" · "+link("https://operations.osmfoundation.org/policies/tiles/","OSM 圖磚政策")+" · "+link("https://frankfurter.dev/","Frankfurter 官方服務說明")+'</p>'
cov+=el("h3","隔離重跑入口")+table(["用途","可重跑程式／紀錄"],[
["來源範圍與兩版差異",evidence_links("evidence/core/clean-head-check.py evidence/core/clean-head.md")],
["後端雙資料庫、遷移與網路效能",evidence_links("evidence/system/run_system.py evidence/system/inspect_runtime.py evidence/system/extra_checks.py")],
["Compose、Volume、備份還原、五人前端",evidence_links("evidence/system/run_compose.py evidence/system/backup_policy.py evidence/system/docker_ui.py")],
["前端、API 補測及外部供應商",evidence_links("evidence/browser/run_ui.py evidence/browser/ui.md evidence/core/issues.md evidence/modules/issues.md evidence/modules/coverage-notes.md")],
])
cov+=p("後端腳本使用本機現成 .venv。Compose 重跑程式要求可用的 Docker Engine；本地 PostgreSQL 重跑程式使用本機已安裝的 pgtools。環境專屬的執行檔、連接埠與目錄記在腳本內。所有業務測資均在新資料庫建立，沒有對正式資料執行測試；未進行 commit、push 或 PR。")
body.append(section("coverage","規格覆核、假設與重跑方式",cov))
body.append("""<script>
const form=document.querySelector('#filters'), rows=Array.from(document.querySelectorAll('#rtm tbody tr'));
function apply(){const q=document.querySelector('#q').value.trim().toLowerCase(),i=document.querySelector('#im').value,s=document.querySelector('#res').value,p=document.querySelector('#pri').value;let count=0;for(const r of rows){const ok=(!q||r.textContent.toLowerCase().includes(q))&&(!i||r.dataset.im===i)&&(!s||r.dataset.res===s)&&(!p||r.dataset.pri===p);r.hidden=!ok;if(ok)count++}document.querySelector('#shown').textContent='顯示 '+count+' / '+rows.length+' 列'}
form.addEventListener('input',apply);form.addEventListener('submit',e=>e.preventDefault());form.addEventListener('reset',()=>setTimeout(apply,0));window.addEventListener('hashchange',()=>{const t=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(t&&t.hidden){form.reset();setTimeout(()=>{apply();t.scrollIntoView()},1)}});apply();
</script></main></body></html>""")
(dest/"功能驗收報告.html").write_text("\n".join(body),encoding="utf8")


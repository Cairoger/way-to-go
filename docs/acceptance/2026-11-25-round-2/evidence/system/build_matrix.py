"""Reconcile individual evidence in this run with the unchanged PRD and its original trace IDs."""
from pathlib import Path
from collections import Counter
import json, re, hashlib, shutil
from functools import lru_cache
here=Path(__file__).resolve().parent
out=here.parent.parent
root=out.parent
old=root/"acceptance-20261125"
def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def save(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
prior=read(old/"需求矩陣.json")
by={r["id"]:r for r in prior}
snap=(root/"docs/spec.md").read_bytes()
assert hashlib.sha256(snap).hexdigest()=="40d4681ff59734558d220dce5ce54eb9f7366ff46aa4978f51609ac0d0242376"
(here/"spec.md").write_bytes(snap)
for src in ["data-model.md","review-fixes.md"]:
    # Preserve the revision's text and make source references usable after extracting the evidence bundle.
    t=(root/"docs"/src).read_text(encoding="utf-8")
    t=re.sub(r"\]\(\.\./([^)]*)\)",lambda m:"](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/"+m.group(1)+")",t)
    (here/src).write_text(t,encoding="utf-8")
coverage=read(old/"evidence/system/coverage.json")
spec=snap.decode().splitlines()
assert len(spec)==710 and set(c["line"] for c in coverage)=={i for i,s in enumerate(spec,1) if s.strip()}
assert all(c["spec"].strip()==spec[c["line"]-1].strip() and set(c["ids"])<=by.keys() for c in coverage)
assert {i for c in coverage for i in c["ids"]}==set(by)
save(here/"coverage.json",coverage)
schema=read(here/"schema.json")
extra=read(here/"extra-checks.json")
C="browser/pg-chrome-all-cases.json";E="browser/pg-edge-all-cases.json";W="browser/pg-webkit-all-cases.json";F="browser/sqlite-firefox-all-native-cases.json";S="system/sqlite-suite.txt";P="system/postgres-suite.txt"
D="system/schema.json";A="system/extra-checks.json";X="system/public-release.json";G="system/restore-grants.json";H="system/restore-proof.json"
U="core/supplement.txt";M="modules/supplement.txt";B="core/browser-run.txt";N="modules/module_ui-run.txt";Q="modules/nginx-quotas.json";T="modules/trip-quota-full.json"
PG="browser/pg-chrome-all-metrics.json";SQ="browser/sqlite-chrome-all-retest-metrics.json";SO="browser/soak-sqlite.json";NF="core/firefox-offline-confirmed.json";FH="core/firefox-release.txt"
LC="browser/walk-chromium.json";LW="browser/walk-webkit.json";LP="browser/literal-text.json";BP="modules/binding-profile.json"
MAP={"core/pytest.log":S,"modules/pytest.txt":P,"core/probes.log":U,"core/timeout-merge.log":U,"core/test_acceptance_core.py":U,"core/wiki-retry.log":"core/wiki-live.txt","core/browser.log":B,"core/browser-lifecycle.log":"core/lifecycle-retest.txt","core/browser-lifecycle.cjs":"core/lifecycle-retest.txt","core/firefox-release.log":FH,"modules/probes.txt":M,"modules/cross-checks.txt":M,"modules/own-comments.txt":M,"modules/module-ui.txt":N,"modules/module-ui-final.txt":N,"modules/providers-network.txt":"modules/providers-live.txt","modules/push-network.txt":"browser/pg-edge-live-push-push.json","browser/chrome-playwright.txt":C,"browser/edge-playwright.txt":E,"browser/firefox-playwright.txt":F,"browser/webkit-playwright.txt":W,"browser/ui.md":C,"browser/two-clients.json":SO,"browser/collaboration.json":SQ,"browser/collaboration-postgres.json":PG,"system/docker-http.json":"system/deployed.json","system/docker-pgversion.txt":"system/compose-pg.txt","system/docker-services.txt":"system/restore-services.txt","system/docker-before-restart.txt":H,"system/docker-backup-files.txt":H,"system/docker-backup-log.txt":H,"system/docker-seed.txt":"browser/manual-ui.json","system/backup-policy.txt":"system/backup-policy-clean.txt"}
alltests=(here/"sqlite-suite.txt").read_text(encoding="utf-8-sig")
# Accept a direct result only if a named test or the mapped new observation exists.
def uniq(seq):return list(dict.fromkeys(seq))
MAP["system/backup-policy.txt"]="system/backup-policy.txt"
def paths(e):return uniq(MAP.get(k,k) for k in re.findall(r'(?:core|modules|browser|system)/[\w.\-]+',e))
def folderpath(f):return here.parent/f
def successful(f,name):
    if not folderpath(f).is_file() or folderpath(f).suffix not in [".txt",".log"]:return False
    t=folderpath(f).read_text(encoding="utf-8-sig",errors="replace")
    for m in re.finditer(r"::"+re.escape(name)+r"(?=\s|\[)",t):
        block=t[m.end():]
        end=re.search(r"(?:^.*?::test_|^={3,})",block,re.M)
        if re.search(r"\bPASSED\b",block[:end.start() if end else None]):return True
    return False
over={}
def put(ids,note,files,tests=(),impl="Implemented",result="PASS"):
    for i in ids.split():
        assert i in by and i not in over,i
        over[i]=(impl,result,note,uniq(files),list(tests))
def blocked(ids,why,files,tests=(),impl="Implemented"):put(ids,why,files,tests,impl,"BLOCKED")
def fail(ids,why,files,tests=()):put(ids,why,files,tests,"Partial","FAIL")
blocked("FR-AUTH-01","登入啟動請求回 503 OIDC_NOT_CONFIGURED。替身的 state、回呼與 Session 輪替通過。本機未配置專用 Google OAuth，真人首登與建立旅程待驗。",["system/http.json",S,"system/environment.json"],["test_google_oidc_cookie_rotation_and_state_binding"])
blocked("FR-AUTH-04","有選票、留言及旅程的合成訪客在替代回呼後保留資料，舊 Session 撤銷。實際 Google 同意及升級回呼缺測試用戶端。",[S,U,"system/environment.json"],["test_merge_keeps_owner_authorization_finances_and_private_travel_data","test_core_merge_comment_ownership"])
blocked("TECH-07","伺服器 Session 與 Google OIDC 替代交換已測。本機缺專用提供者設定，真實授權尚未完成。",[S,"system/http.json","system/environment.json"],["test_google_oidc_cookie_rotation_and_state_binding"])
put("IDENT-03","本人在 UI 改暱稱、重登後保留，另一個帳戶獨立。舊頁面覆寫另見 API-RULE-04。",[C,S,A],["test_profile_is_self_only_and_creator_survives_transfer"])
put("TRIP-OPT-06","更換 Owner 後，API 回傳原始 created_by、建立時間及新 owner_id，旅程頁仍顯示建立者。",[S,C,U],["test_profile_is_self_only_and_creator_survives_transfer"])
put("FR-PLACE-07","原編輯者獲鎖並提供版本後移除成功；其他人不能移除。重載候選清單後景點消失，既有活動仍顯示封存名稱、地址。",[S,C,U],["test_original_place_delete_is_versioned_and_preserves_reference"])
put("FR-PLAN-09","紐約春季不存在的 02:30 回 422，秋季重複小時採第一次並在 UI 標示。一般跨區為紐約 09:00、台北 21:00。",[S,C,"core/lifecycle-retest.txt"],["test_dst_gap_fold_and_date_changes","test_time_suggestions_and_local_zones"])
put("FR-COMMENT-03 MS4-DONE","五個獨立瀏覽器身分建立五筆留言。20 次編輯各有四頁實際呈現，兩組各 80 筆、零逾時，PostgreSQL P95 191 ms，SQLite P95 260 ms。另測過期版本與撤權。",[PG,SQ,C,P],["test_five_connected_clients_receive_committed_edits_and_revocation","test_lease_contention_renewal_timeout_and_stale_version"])
put("FR-COMMENT-05","以瀏覽器上傳圖片並發表留言。草稿只供作者使用；發表後圖片與留言 ID 相連；讀取與錯誤附件條件由後端驗證。",[C,S],["test_comment_images_draft_visibility_and_rejections"])
put("FR-TASK-02 FR-TASK-05","新建任務逐欄讀回名稱、說明、期限、優先及指派，另讀回景點、行程關聯。已刪活動拒絕新關聯。舊探針的歷史缺陷預期另列報告。",["modules/binding-profile.txt",P],["test_current_task_fields_with_relationship","test_existing_task_and_booking_links_survive_item_removal"])
put("FR-TASK-06","每日、每週、每月各走兩期，完成紀錄保留，次期的進度獨立，附件仍可讀。瀏覽器另走每期任務與關聯檔案。",[S,P,C],["test_repeat_two_periods_with_persistent_files"])
put("FR-TRIP-08 COPY-FILES","建立含私人檔的原旅程再複製；副本查無原檔，公開景點、安排保留。另以真資料核對成員、投票、財務與私人訂位排除。",[S,P],["test_attachment_permissions_revocation_copy_and_restore","test_copy_planning_snapshot_to_own_trip_only","test_copy_linked_travel_arrangements_without_private_booking_or_assignees"])
put("FR-BOOK-05 BOOK-FILES","本人與相關旅客可讀預訂的私密欄位、關聯文件；以不同登入身分讀回，未授權成員遭拒。",[C,P],["test_bound_targets_and_private_booking","test_reservation_privacy_and_edits"])
put("FR-FILE-01","PNG、JPEG、GIF、WebP 逐一上傳，再以另一個身分預覽與下載，位元完全相符。另上傳 PDF、DOCX、XLSX、PPTX 核對預覽與下載。無法辨識或內容不符則拒絕。",["modules/advertised-images.json","modules/remaining-run.txt",S,C],["test_all_advertised_image_formats","test_batch_types_previews_and_all_or_nothing"])
put("FR-FILE-02","真檔批次、分類、預覽、下載成功；混入不合規檔案時整批不寫入。",[S,C],["test_batch_types_previews_and_all_or_nothing"])
put("FR-FILE-03","對旅程、活動、任務、費用等關聯實際上傳並讀回；不同旅程的關聯被拒。瀏覽器另走留言與預訂入口。",[C,P],["test_bound_targets_and_private_booking"])
put("FR-FILE-04 BR-013 AC-018 SEC-06","使用私檔實測本人、獲授權讀者、未授權旅程成員及未登入者。下載/預覽的授權與撤權生效；檔案由資料庫按 ID 取回，檔名欄位拒絕路徑。",[P,C,G,"system/grants-restored-api.txt"],["test_attachment_permissions_revocation_copy_and_restore","test_batch_types_previews_and_all_or_nothing"])
put("FR-FILE-05","刪除先進回收區，原下載不可用；作者可依版本復原並讀回原始位元，還原後同樣成立。",[P,G],["test_attachment_permissions_revocation_copy_and_restore"])
put("FR-FILE-06","nginx 後單檔 10,485,760 B 收 201，多 1 B 收 413。以真 PNG 將旅程填至 524,288,000 B 收 201；先測預計超出 1 B 回 413 且未占空間。另測回收計量與兩人競爭剩餘容量。",[Q,T,P],["test_file_quota_counts_recycle_and_rate_limit","test_concurrent_uploads_respect_last_available_space"])
put("FR-PDF-02 PDF-FILES","以同旅程的實際私人檔與訂位、費用建立列印來源，兩種 PDF 均能讀到公開活動且排除私人檔名、訂位代號及財務內容。",[C,"browser/pdf-private-text.json","browser/pdf-private.json","browser/unit.txt"])
put("FR-OFFLINE-01","明確儲存後關原分頁。Chrome、Edge、Windows WebKit 的真後端案例通過。正式 Firefox 關閉測試站後新分頁顯示活動、地址、10:30、零編輯按鈕。其測試組建有兩個離線案例失敗。",[C,E,W,NF,F])
put("FR-OFFLINE-02 OUT-05","離線嘗試新增活動，畫面提示連線中斷；重連與重載後後端查無草稿。另驗唯讀副本沒有編輯按鈕。",[N,NF])
blocked("FR-NOTIFY-02","Edge 關閉所有站內分頁後 1,053 ms 觀測到相符裝置通知。Chrome 兩次允許權限仍在訂閱逾時；兩瀏覽器的合成點擊定位通過。Windows 真實橫幅點擊待驗。",["browser/pg-edge-live-push-push.json","browser/pg-chrome-live-push-push.json","browser/pg-chrome-live-push-retry-push.json","browser/pg-edge-live-push-cases.json","browser/pg-chrome-live-push-retry-cases.json"])
put("PERF-01","5 位旅伴經 nginx 發出 60 讀、30 寫；90 筆混合 P95 314.41 ms，讀 396.62、寫 292.02，均低於 500 ms。排除外部服務。",["system/mixed-api.json","system/latency.json"])
put("PERF-02","5 位瀏覽器身分，20 次提交 × 4 個觀察頁。PostgreSQL 的 80 筆 P95 191 ms、SQLite 的 80 筆 P95 260 ms，均零逾時，門檻 2,000 ms。",[PG,SQ])
put("PERF-03","兩個旅程頁實際開啟 360 秒，從起點與每分鐘取樣，每頁均僅一條活躍 WebSocket。",[SO])
blocked("SEC-01","公開來源設成 HTTP 會被拒。正式 TLS 網域與憑證未提供，本機可實測的部署入口為 loopback HTTP。",[A,"system/deployed.json"])
blocked("SEC-04","讀取三個可達 commit，四類可辨識憑證及敏感檔名均無命中。自訂格式及站外歷史無完整盤點依據。",["system/policies.json",A],impl="Unknown")
put("RATE-4","使用正常有效上傳路徑重複送出，超額時 HTTP 429；另有合法檔上傳的 201 對照。",[S,Q],["test_file_quota_counts_recycle_and_rate_limit"])
put("DEF-1","一般文字 O'Brien、& 及字面 <em> 在行程、留言、Leaflet 彈窗、列印與離線閱讀均原樣顯示，五處皆無新增 em 元素。此判定限上述使用者輸出情境。",[LP,LC,LW])
put("DEF-3","以含單引號的一般姓名寫入，實際擷取 UPDATE 與 INSERT 的 SQL 和參數；文字以綁定值傳送。掃描 app 內三處明示原生 SQL 呼叫，參數皆為固定 SQL 字面。",[BP,"modules/test_binding_profile.py"])
put("UX-01","320、390、768、1280 px 檢查寬度；11 個模組各於 390/1280 px 實際開啟，共 22 個畫面無整頁水平溢出。",["browser/sections.json","browser/experience.json",C])
put("UX-CHROME UX-EDGE","安裝的正式瀏覽器跑完預設 20 個案例，兩個推播案例由獨立流程處理，見 FR-NOTIFY-02；驗收主流程含真服務與分身分操作。",[C,E,PG])
put("UX-FIREFOX","正式 Firefox 161 登入、建立、重載、活動與邀請 QR 成功，測試站確實停止後新分頁可離線閱讀。Playwright Firefox 159 的另外兩項失敗另列測試相容性缺口。",[FH,NF,F])
blocked("UX-SAFARI","Windows WebKit 主流程已跑。機器沒有 Apple 正式 Safari，無法就近期正式版給出驗收結論。",[W,"browser/pg-webkit-coordination-offline-planner-isolated-cases.json",LW],impl="Unknown")
blocked("UX-05","舊對比及名稱問題未重現；首頁與行程頁鍵盤及 axe 案例通過，22 個模組/尺寸組合零自動違規。axe 在首頁、行程各有 2 條待人工判斷；完整適用 AA 條款與輔助工具操作仍未全覆核。",["browser/experience.json","browser/sections.json",C],impl="Unknown")
put("MS5-3","里程碑要求基本檢查。四種寬度、桌/手機的鍵盤焦點、可存取名稱及 22 次模組檢查均已執行。§5.3 全面符合性另追 UX-05。",["browser/sections.json","browser/experience.json",C])
put("OPS-01","在本次獨立 Compose 重建資料庫容器後，持久化 volume 中 42 張表的筆數、內容 SHA-256 均與重建前相同。",[H,"system/volume-recreate.txt","system/restore-services.txt"])
blocked("OPS-03","資料與備份分開掛載。兩次本機空庫還原成功，且目前 SHA 的 CI 有還原步驟與成功紀錄。本機單次驗收無正式環境持續定期演練的記錄。",[H,G,X,"system/backup-policy.txt"],impl="Partial")
put("OPS-04","從產品備份還原含真瀏覽器上傳的 PNG 及預訂關聯。第二次含 22 份檔案、2 筆明確授權、1 份回收檔，42 張表逐表雜湊相符，還原後以各角色做下載及復原。",[H,G,"system/grants-restored-api.txt"])
blocked("FREE-04","本機可驗地圖出處、按需載入及免費供應商；實際營運用途、長期流量與配額紀錄不在本次本機環境。",["modules/map-network.txt","modules/providers-live.txt","browser/experience.json"],impl="Partial")
fail("FREE-05","保留上輪 D13 的地圖與航班兩入口標準。地圖有指定文字；Chrome 與 WebKit 的航班清單和新增表單均為 0 處，手動輸入可用。",[LC,LW,"system/review-fixes.md"])
put("TECH-05","從空資料庫完成 0009，Alembic check 報告無新升級操作。",["system/migrate.txt","system/alembic-check.txt","system/compose-alembic.txt"])
put("TECH-12 DEV-WORKFLOW","公開分支 HEAD 與目前 SHA 相同；PR #1 為 open draft，該 SHA 的 push 與 PR Actions 均成功。可證明工作流程曾實際執行。",[X])
fail("FR-COLLAB-06 AC-009 API-RULE-04","兩個真正 Chrome 分頁先讀同一暱稱，第二個舊表單覆寫第一個的更新；另一位旅伴讀到先後兩個名字。兩次 PATCH 均 200，輸入欄位只有 nickname；另送明確不匹配的 If-Match 仍 200。景點及行程的舊版請求正常回 409。",["browser/profile-tabs.json",BP,"modules/binding-profile.txt",P],["test_lease_contention_renewal_timeout_and_stale_version"])
fail("API-RULE-03","已實測旅程未授權 403、行程版本衝突 409、占鎖 423。帳戶暱稱在已確定過期的視圖與明確不匹配的 If-Match 仍回 200，故整項規範部分符合。",["browser/profile-tabs.json",BP,A,P],["test_lease_contention_renewal_timeout_and_stale_version"])
put("EDIT-3 EDIT-4 EDIT-B3","§6.3 的項目鎖流程以景點、每日行程驗證：取得租約、提交資料版本、交易更新，過期後再寫以 409 拒絕。本次另發現跳過此保護的帳戶資料，見 API-RULE-04。",[U,P,B],["test_lease_contention_renewal_timeout_and_stale_version"])
put("API-RULE-05","相同 Idempotency-Key 重送邀請得到同一個 id 與可用邀請碼；不同內容共用 key 回衝突。旅程與財務重送得同一筆結果。",[A,S,P],["test_invitation_retries_preserve_one_working_code","test_budgets_settlements_and_idempotence"])
put("DEV-TOOLS","Ruff、完整 ESLint、實際工作樹的 Prettier、TypeScript、Vitest 及後端測試已執行。Windows git archive 的換行會造成另外的格式差異。",["system/ruff.txt","system/format.txt","browser/lint-full.txt","browser/format-worktree.txt","browser/format.txt","browser/typecheck.txt","browser/unit.txt",P])
put("DEV-DOC","依專案流程啟動 Compose，實際打開台南公開範例、進入第二天並讀到兩個有時間的景點。文件與交付 SHA 可重現。",["browser/manual-ui.json","system/deployed.json",C])
put("DEV-E2E","里程碑列出的 E2E 已配置並實際執行。Chrome/Edge 預設每組 20 過；Windows WebKit 有 5 個失敗，Playwright Firefox 有 2 個，細節見報告。",[C,E,W,F])
put("MS5-DONE","指定 SHA 可在乾淨目錄建置、部署、跑測試及實際展示，文件列出 Google 與 Safari 限制。履歷若只給 main 仍取得舊版，D13 的航班說明亦須更正。",["system/branch-comparison.json",X,"system/review-fixes.md","browser/manual-ui.json",PG])
put("FR-MAP-01","OSM 實際 1 個圖磚回 200、1 張可見且附署名。另中斷圖磚後，三種景點分類標記及地址仍可見。",["modules/map-network.txt","modules/live-map-online.png","browser/experience.json"])
put("OUT-06","檢查實際受控 Service Worker 的 Cache Storage 及離線讀者，快取含本機資產與離線頁，沒有 OSM 圖磚。",["browser/experience.json",NF])
db_equiv={"DB-POLLS":"投票類型、截止與結束狀態在 poll_rounds。","DB-POLL-ROUNDS":"round_number 對應 number，狀態由 closed_at/deadline 推導。","DB-POLL-OPTIONS":"poll_options.round_id 透過 poll_rounds 連回 poll，沒有直接的 poll_id。","DB-TASK-LISTS":"個人/共用清單依 tasks.scope 和 created_by 分組。","DB-FLIGHTS":"航班使用 bookings.kind=flight 及 segments JSON。","DB-FLIGHT-PASSENGERS":"旅客逐段置於 bookings.segments[].passengers。","DB-ACCOMMODATIONS":"住宿使用 bookings.kind=stay 及 stay JSON。","DB-ACCOMMODATION-GUESTS":"住客置於 bookings.stay.guests[]。"}
for k,n in db_equiv.items():fail(k,n+" 遷移實表與原規格具名結構不同；擁有者已記錄採用的等價設計。",[D,"system/data-model.md",P])
for i in ["DB-FILES","DB-FILE-PERMISSIONS","DB-FILE-LINKS"]:
    table=i[3:].replace("-","_").lower()
    put(i,"0009 遷移可見實表 "+table+"；獨立還原後以非空資料核對內容、授權及關聯。",[D,G,"system/grants-restored-api.txt"])
for i,col in [("DDL-CHECKS","checks"),("DDL-FOREIGN","foreign"),("DDL-INDEXES","indexes"),("DDL-UNIQUE","unique")]:
    n=sum(len(v[col]) for v in schema.values());put(i,f"PostgreSQL Inspector 在遷移後實際數出 {n} 個 {col}，另執行模型／遷移差異檢查。",[D,"system/alembic-check.txt"])
impl_order=["Implemented","Partial","Missing","Unknown"]
result_order=["PASS","FAIL","BLOCKED","NOT TESTED"]
@lru_cache(maxsize=None)
def resolve(i):
    r=by[i]
    tests=[]; deps=[]; observed={}
    if i in over:
        impl,result,note,files,tests=over[i]
    elif all(k in by for k in r["evidence"].split("、")):
        deps=r["evidence"].split("、")
        children=[resolve(k) for k in deps]
        result=next((v for v in ["FAIL","BLOCKED","NOT TESTED"] if any(c["result"]==v for c in children)),"PASS")
        outcomes={c["implementation"] for c in children}
        impl=next(iter(outcomes)) if len(outcomes)==1 else ("Unknown" if outcomes<= {"Implemented","Unknown"} else "Partial")
        note="子條件本輪分別為 "+"、".join(k["id"]+" "+k["result"] for k in children)+"。"
        files=[]
    else:
        # These expectation descriptions concern stable fixtures. Their assertions must pass afresh.
        if r["result"]!="PASS" or r["implementation"]!="Implemented":
            raise ValueError(("unreconciled historical nonpass",i))
        impl,result="Implemented","PASS";note=r["notes"]
        files=paths(r["evidence"])
        tests=uniq(re.findall(r"\b(test_[a-z0-9_]+)\b(?!\.py)",r["evidence"]))
        if i.startswith("API-") and re.match(r"API-\d",i):
            assert extra["api-contract"][r["condition"]]
            requested=r["condition"].split(" ",1);norm=lambda s:re.sub(r"\{[^}]*\}","{}",s)
            path=requested[1] if requested[0]=="WS" else "/api/v1"+requested[1]
            sources=[]
            for source in ["system/observed-api.json","system/extra-observed-api.json"]:
                for key,codes in read(folderpath(source)).items():
                    if norm(key)==norm(requested[0]+" "+path):
                        for k,v in codes.items():observed[k]=observed.get(k,0)+v
                        sources.append(source)
            assert observed,(i,r["condition"])
            files=uniq(sources+files)
            note="此次實際連線至該路徑，狀態碼與次數為 "+"、".join(f"{s} × {n}" for s,n in sorted(observed.items()))+"。"
        if i.startswith("DB-"):
            table=i[3:].lower().replace("-","_")
            assert table in schema,(i,table)
        if i=="FR-COLLAB-04":note="實際租約約 90 秒，續租延長到期，UI 編輯期間定時續租。"
        if i=="FR-PLACE-01":note="沙箱首次無法連外；放行後實際維基百科搜尋返回 200 且取得座標，手動景點可寫入並重讀。"
        if i in ("FR-PDF-01",):note="勾選第一天另存兩份真正 PDF，詳表含地址、簡表略去，兩者皆排除第二天。"
        if i=="PERF-04":files=uniq(files+["modules/map-network.txt"])
        if i in ["FR-FIN-01","FR-FIN-08","FR-VOTE-04","FR-TASK-01"]:
            files=uniq(files+["modules/remaining-http.json","modules/remaining-run.txt"])
    if not deps:
        assert files and all(folderpath(f).is_file() for f in files),(i,files)
        for t in tests:
            assert any(successful(f,t) for f in files),(i,t,files)
    cond="每次修改都須檢查資料版本，避免過期請求覆蓋最新資料。涵蓋景點、行程與會發布給旅程成員的個人暱稱更新。" if i=="FR-COLLAB-06" else r["condition"]
    return dict(id=i,section=r["section"],line=r["line"],condition=cond,priority=r["priority"],implementation=impl,result=result,evidence=["evidence/"+f for f in files],tests=list(tests),dependencies=deps,notes=note.replace("；","。"),observed_http=observed,previous={"implementation":r["implementation"],"result":r["result"]})
def md(s):return str(s).replace("|","\\|").replace("\n"," ").replace("<em>","&lt;em&gt;").replace("</em>","&lt;/em&gt;")
def cell_ev(x):
    a=["["+f.split("/")[-1]+"]("+f+")" for f in x["evidence"]]
    if x["dependencies"]:a += ["["+k+"](#r-"+k.lower()+")" for k in x["dependencies"]]
    return " · ".join(a)
def group(line):
    if line<42:return "1　目標與成功條件"
    chapters=[(2,"身分與權限"),(3,"功能"),(4,"業務規則"),(5,"非功能需求"),(6,"系統架構與技術"),(7,"資料模型"),(8,"API 契約"),(9,"開發里程碑"),(10,"驗收情境"),(11,"排除範圍")]
    marks={}
    for number,_ in chapters:
        marks[number]=next(i+1 for i,s in enumerate(spec) if re.match(r"^# "+str(number)+r"\.\s",s))
    for number,title in reversed(chapters):
        if line>=marks[number]:return str(number)+"　"+title
    return "1　目標與成功條件"
rows=[resolve(r["id"]) for r in prior]
save(out/"需求矩陣.json",rows)
def stats(rs):return {"total":len(rs),"implementation":{k:sum(x["implementation"]==k for x in rs) for k in impl_order},"result":{k:sum(x["result"]==k for x in rs) for k in result_order}}
groups={"全部":rows,"功能 FR":[x for x in rows if x["id"].startswith("FR-")]}
for p in ["P0","P1","P2"]:groups[p]=[x for x in groups["功能 FR"] if x["priority"]==p]
for k,prefix in [("業務規則 BR","BR-"),("核心情境 AC","AC-")]:groups[k]=[x for x in rows if x["id"].startswith(prefix)]
st={k:stats(v) for k,v in groups.items()}
st["transitions"]={s:dict(Counter(r["previous"][s]+" → "+r[s] for r in rows)) for s in ["implementation","result"]}
save(here/"statistics.json",st)
lines=["# WayToGo 第二輪需求追蹤矩陣","","版本 `cada651b990923166e8efa6ee20f72885a9c2b92`。436 個需求 ID 沿用原規格索引。每列的條件是預期結果，右欄為本輪實際結果或受阻原因。彙總列可點入構成條件。","","[驗收報告](第二輪功能驗收報告.md) · [規格](evidence/system/spec.md) · [非空行逐行覆核](evidence/system/coverage.json) · [機器可讀矩陣](需求矩陣.json)",""]
last=None
for x in rows:
    g=group(x["line"])
    if g!=last:
        lines+=["## "+g,"","| 需求 ID | 規格位置與驗收條件 | 實作狀態 | 測試結果 | 本輪驗證證據 | 實際結果、問題或備註 |","|---|---|---|---|---|---|"]
        last=g
    label='<a id="r-'+x["id"].lower()+'"></a>'+x["id"]
    loc=x["section"].replace("§Milestone","§9 Milestone")
    if x["priority"] and x["priority"] not in loc:loc+=" "+x["priority"]
    note=x["notes"]
    if x["tests"]:note+=" 案例 "+"、".join("`"+t+"`" for t in x["tests"])+"。"
    lines+=["| "+" | ".join([label,md(loc.strip()+"　"+x["condition"]),x["implementation"],"**"+x["result"]+"**",cell_ev(x),md(note)])+" |"]
    # Blank line between different GFM tables.
    if x!=rows[-1] and group(rows[rows.index(x)+1]["line"])!=g:lines.append("")
(out/"需求追蹤矩陣.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print(json.dumps(st,ensure_ascii=False,indent=2))



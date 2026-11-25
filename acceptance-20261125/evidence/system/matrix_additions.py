"""Other spec sections. r() inherits the cited evidence; d() supplies direct observations."""
def populate(R,d,r,L,schema,ctx):
    db="evidence/system/schema.json"
    pg="evidence/system/postgres-suite.txt"
    ext="evidence/system/extra-checks.json"
    http="evidence/system/http.json"
    xp="evidence/browser/experience.json"
    perf="evidence/system/latency.json"
    five="evidence/browser/collaboration.json"
    dc="evidence/system/docker-http.json"
    se="evidence/system/docker-services.txt"
    ck="evidence/system/alembic-check.txt"
    pol="evidence/system/policies.json"
    b="evidence/core/browser.log"
    prep="evidence/modules/probes.txt"
    demo="evidence/browser/chrome-playwright.txt"
    def T(test):return pg+" → test_"+test
    def direct(id,n,e,note,im="Implemented",res="PASS",c=None):
        d(id,n,im,res,e,note,c)
    def inherit(id,n,refs,note="",c=None):r(id,n,refs,note,c)
    # §1 and §2. Product-level claims have their own acceptance boundaries.
    direct("OV-01",21,perf,"五個訪客成功加入同一位示範 Owner 的旅程，共六位有效成員。")
    for ix,(n,refs) in enumerate([(25,"FR-PLACE-01 FR-PLAN-03"),(26,"FR-VOTE-01 FR-DATE-03"),(27,"FR-COLLAB-01 FR-COMMENT-03"),(28,"FR-PLACE-03 FR-BOOK-03 FR-TASK-01 FR-FIN-02"),(29,"FR-AUTH-02"),(30,"FREE-01 FREE-02")],1):
        inherit(f"VALUE-{ix:02}",n,refs)
    for ix,(n,refs) in enumerate([(36,"FR-AUTH-01 FR-TRIP-01"),(37,"FR-AUTH-02"),(38,"MS4-DONE"),(39,"FR-PLACE-01 FR-VOTE-01 FR-PLAN-03"),(40,"FR-COLLAB-01 FR-COMMENT-03 AC-004 AC-009"),(41,"UX-01"),(42,"OPS-01")],1):
        inherit(f"SUCCESS-{ix:02}",n,refs)
    inherit("IDENT-01",52,"FR-AUTH-01")
    direct("IDENT-02",53,ext+" → trip-count；"+T("trip_versions_archives_and_idempotency"),"Google 類型測試帳號持有並列出兩趟旅程；真實登入另見 FR-AUTH-01。")
    direct("IDENT-03",54,ext+" → owner-edit-profile；backend/app/auth.py:62；frontend/components/AccessDialog.tsx","帳戶 UI 供查看；修改暱稱回 405，無對應的更新 API。","Missing","FAIL","使用者可自行更新個人資料")
    inherit("IDENT-04",54,"FR-NOTIFY-01","通知偏好可寫回並重讀。","使用者可管理自己的通知偏好")
    for ix,(n,ref) in enumerate([(58,"FR-AUTH-02"),(59,"FR-INV-06"),(60,"ROLE-06 ROLE-10 ROLE-11"),(61,"FR-AUTH-05"),(62,"FR-AUTH-03"),(63,"FR-AUTH-04")],5):inherit(f"IDENT-{ix:02}",n,ref)
    direct("IDENT-11",65,ext+" → duplicate-nickname-new-identity；frontend/components/AccessDialog.tsx；"+b,"表單明示清除資料可能失去身分；相同暱稱在新工作階段取得不同 user ID。")
    inherit("ROLE-00",69,"BR-001")
    for ix,(n,ev,note) in enumerate([
        (73,ext+" → guest-create-denial、two-trips-first","解讀為 Google 建立新旅程時成為 Owner。訪客建立 403，Google 類型帳號建立 201。"),
        (74,T("trip_versions_archives_and_idempotency"),"Owner 可更改基本設定；一般成員 PATCH 回 403。"),
        (75,ext+" → guest-invite-denial、guest-remove-other-denial；"+T("member_removal_transfers_poll_control_and_transfer_owner"),"Owner 可邀請、移除；Member 嘗試兩項皆 403。"),
        (76,ext+" → owner-invite、guest-invite-denial；evidence/core/probes.log","Owner 自訂兩天、預設七天；Member 設定期限被拒。"),
        (77,T("member_removal_transfers_poll_control_and_transfer_owner"),"Member 轉移回 403；Owner 轉移成功。"),
        (78,T("place_retained_after_candidate_removal")+"；"+b,"Owner 與 Member 均建立資料並由其他人讀回。"),
        (79,b+"；"+T("restore_changed_place_and_deleted_item"),"合法編輯者修改成功，兩方看見新版。"),
        (80,ext+" → member-edit-other-item；"+T("place_retained_after_candidate_removal"),"Member 改他人活動 403，Owner 取他人景點鎖 403。"),
        (81,b+" → DRAG_SAME_DAY、DRAG_CROSS_DAY","兩頁看到順序同步。"),
        (82,prep+" → test_four_kind_mode_combinations_and_options；"+T("secret_ballots_and_review_after_new_option"),"兩種角色可發起、補選項和投票。"),
        (83,T("five_connected_clients_receive_committed_edits_and_revocation"),"五位作者送出五筆，各連線收齊，查回五筆。"),
        (84,T("comment_moderation_and_preserved_replies"),"個人留言 CRUD 和保留回覆；Owner 管理行為見下一列。"),
        (85,T("comment_moderation_and_preserved_replies"),"Member 刪他人留言 403，Owner 可刪。"),
        (86,ext+" → guest-archive-denial、guest-delete-denial；"+T("trip_versions_archives_and_idempotency"),"一般成員兩操作 403，Owner 封存、刪除、復原成功。"),
        (87,ext+" → member-left、after-exit；"+T("member_removal_transfers_poll_control_and_transfer_owner"),"成員退出 204，後續存取 403；Owner 未交接不能退出。")],1):
        direct(f"ROLE-{ix:02}",n,ev,note,c="、".join(L[n].strip("|").split(" | ")[:1])+f"（Owner／Member 依表列角色）")
    for i,(n,refs) in enumerate([(91,"AC-015"),(92,"BR-005"),(93,"API-RULE-01 API-RULE-02"),(94,"BR-007 BR-008 BR-010")],1):inherit(f"ROLE-R{i}",n,refs)
    br=[
        (T("member_removal_transfers_poll_control_and_transfer_owner")+"；backend/app/trips.py:288","轉移更新既有成員與旅程 Owner；原角色不能繼續管理。"),
        (T("member_removal_transfers_poll_control_and_transfer_owner"),"Owner 刪除自己的成員資格回 409，轉移後可退出。"),
        (T("five_connected_clients_receive_committed_edits_and_revocation"),"撤權後 WS 4403，原 Cookie 的 HTTP 403。"),
        (T("place_retained_after_candidate_removal"),"取消候選後活動和 place_id 仍相同。"),
        (T("move_overlap_and_passive_order")+"；"+T("merge_keeps_owner_authorization_finances_and_private_travel_data")+"；"+db,"行程保留 created_by 和 editable_by；轉交更新編輯權。"),
        (T("move_overlap_and_passive_order")+"；"+b,"他人操作回 403；合法拖曳成功。"),
        (T("lease_contention_renewal_timeout_and_stale_version")+"；"+T("place_retained_after_candidate_removal"),"驗證授權、租約及過期版本。"),
        (T("manual_adoption_keeps_item_after_revote")+"；backend/app/decisions.py:448","採用會新增項目，重試沿用已採用項目。"),
        (T("ranked_ballots_and_tie_round"),"重開保留原結果，另建新輪。"),
        (T("time_suggestions_and_local_zones"),"計算建議後保留另一成員手動時間。"),
        (T("budgets_settlements_and_idempotence")+"；evidence/browser/chrome-playwright.txt","還款更新帳本餘額；流程中無支付請求。"),
        (T("trip_versions_archives_and_idempotency")+"；evidence/core/probes.log","旅程狀態、封存旗標及回收日期可獨立變更。"),
        (prep+" → test_file_contract_and_comment_images","缺少附件可供授權比較，功能入口 404。"),
        (xp+" → map；"+T("search_outage_preserves_saved_content"),"中止圖磚後仍見名稱、地址、導航與每日安排。")]
    for i,(e,msg) in enumerate(br,1):
        direct(f"BR-{i:03}",380+i,e,msg,* (("Missing","BLOCKED") if i==13 else ()),c=L[380+i].split("|")[2].strip())
    ac_tests=[
        (ext+" → guest-create-denial","403 GOOGLE_REQUIRED，訊息明示 Google 登入。"),
        (T("guest_invite_lifecycle"),"重接受邀請前後都只有兩位成員。"),
        (T("guest_invite_lifecycle"),"過期碼拒絕，既有旅伴仍取得 200。"),
        (ext+" → member-edit-other-item","用另一人的角色正常送出修改，403 not_editor。"),
        (b+" → DRAG_SAME_DAY、DRAG_CROSS_DAY","實際拖曳同日及跨日，兩頁都看到結果。"),
        (br[3][0],br[3][1]),
        (b+" → EDIT_AND_LOCK_VISIBLE_ON_PEER；"+T("lease_contention_renewal_timeout_and_stale_version"),"合法編輯者持鎖，另一成員看見正在編輯者。再次取鎖回 423。"),
        (T("lease_contention_renewal_timeout_and_stale_version")+"；evidence/core/browser.log；evidence/core/probes.log","不續租；在專用資料庫將到期點推至過去，再取得新鎖成功。"),
        (T("lease_contention_renewal_timeout_and_stale_version"),"舊版 409，讀回仍是新版值。"),
        (T("secret_ballots_and_review_after_new_option"),"投票中無其他人選擇及統計。"),
        (T("rating_ballot_requirements_privacy_review_and_result"),"結束後可查每位投票者與得票結果。"),
        (T("ranked_ballots_and_tie_round"),"平票重投建立新輪、保留原輪。"),
        (T("manual_adoption_keeps_item_after_revote"),"已採用活動的 ID 維持不變。"),
        (T("place_retained_after_candidate_removal"),"Owner 對他人景點取得編輯鎖回 403。"),
        (ext+" → member-left、after-exit；"+T("member_removal_transfers_poll_control_and_transfer_owner")+"；"+T("fx_snapshot_precision_and_departed_history"),"退出後禁止讀取；原始作者及歷史仍在，Owner 接管編輯。"),
        (b+" → OVERLAP","兩個重疊活動均保存，各顯示警告。"),
        (xp+" → map；evidence/browser/live-map-fallback.png","中止圖磚；仍讀到地址、行程和地圖外連。"),
        (prep+" → test_file_contract_and_comment_images","建立附件得到 404，無有效私人文件可比較允許與拒絕。"),
        (T("budgets_settlements_and_idempotence")+"；"+demo,"超預算後可記帳，看到警告並能繼續還款。"),
        (http+" → oidc_missing；"+ext+" → missing-database、public-config-http-rejected；compose.yaml:9","缺 OIDC 回 503 OIDC_NOT_CONFIGURED；無資料庫網址被拒；初始化採隨機密碼。")]
    for i,(e,msg) in enumerate(ac_tests,1):
        direct(f"AC-{i:03}",653+i,e,msg,*(("Missing","BLOCKED") if i==18 else ()),c=" → ".join(x.strip() for x in L[653+i].split("|")[2:4]))
    direct("PERF-01",404,perf,"五個並行客戶端、60 筆請求、P95 56.30 ms，低於 500 ms。")
    for id,n in [("PERF-02",405),("PERF-03",406)]:direct(id,n,five,ctx[id][0],*ctx[id][1:])
    direct("PERF-04",407,xp+"；"+T("weather_success_and_provider_failure")+"；"+T("search_outage_preserves_saved_content"),"圖磚失敗仍可使用頁面；搜尋、天氣供應商失效提供手動操作或空狀態。")
    direct("SEC-01",411,ext+" → public-config-http-rejected；deploy/nginx.conf:5；README.md","公開 HTTP 配置被拒。Compose 僅示範 loopback HTTP；沒有指定可測試的對外 TLS 網域。","Implemented","BLOCKED")
    direct("SEC-02",412,ext+" → https-session-attributes；evidence/core/probes.log","HTTPS 測試來源的 Set-Cookie 有 Secure、HttpOnly、SameSite=Lax；同 Session 能再讀取。")
    direct("SEC-03",413,T("google_oidc_cookie_rotation_and_state_binding"),"模擬 Google 回應後舊 cookie 401，新 cookie 可用。")
    direct("SEC-04",414,pol+"；"+ext+" → git-sensitive-file-inventory；.gitignore","對本機可達的 Git 歷史查四種已知金鑰格式和敏感檔名，沒有命中。任意格式的秘密無法靠此檢查證明排除。","Unknown","BLOCKED")
    inherit("SEC-05",415,"API-RULE-01 API-RULE-02","涵蓋要求的 Session／成員檢查與 WebSocket。")
    for i,(name,needle) in enumerate([("邀請","invitations"),("登入","auth/google、auth/local-test"),("地點搜尋","place-search")],1):direct("RATE-"+str(i),416,pol+" → limiter_unit；backend/app/main.py:92","測試限流函式，路徑 "+needle+"，檢查首次超限與之前允許的呼叫。",c=name+"限流")
    direct("RATE-4",416,prep+"；backend/app/main.py:92","附件上傳未實作，未能送合法上傳觀測 429。","Missing","BLOCKED",c="上傳限流")
    for i,(nm,im,res,e,msg) in enumerate([
        ("XSS 防禦","Unknown","NOT TESTED","frontend/components/PlannerMap.tsx:68；frontend/components/PlannerTools.tsx","已檢視文字節點與列印輸出處理；本次無完整輸出點安全驗證。"),
        ("CSRF 防禦","Implemented","PASS",T("missing_oidc_settings_and_request_origin"),"同源操作可執行，既有測試的異源寫入回 403。"),
        ("SQL Injection 防禦","Unknown","NOT TESTED","backend/app/core.py:138；backend/app/main.py:29","靜態檢視 ORM 查詢及固定 SQL；未做完整 SQL 安全測試。"),
        ("未授權物件存取防禦","Implemented","PASS",T("reservation_privacy_and_edits")+"；"+ext,"已測涵蓋預訂欄位隔離、移除成員及他人活動。")],1):direct(f"DEF-{i}",417,e,msg,im,res,nm)
    direct("SEC-06",418,prep,"沒有可下載的私人文件，無法實測下載授權與儲存路徑界線。","Missing","BLOCKED")
    direct("SEC-07",419,ext+" → audit；deploy/nginx.conf:10；backend/Dockerfile","抽查建立、加入、編輯及預訂事件含操作者；測試 token、完整訂位碼未出現在上述稽核內容，預設 access log 關閉。")
    direct("UX-01",423,xp+" → mobile；"+demo+"；evidence/browser/live-mobile.png","390px 與桌面操作實際使用頁面、表單及導覽；視窗與裝置明細見瀏覽器紀錄。")
    for tag,nm in [("CHROME","Chrome"),("EDGE","Edge"),("FIREFOX","Firefox"),("SAFARI","Safari")]:
        msg,im,res=ctx[tag]
        direct("UX-"+tag,424,"evidence/browser/ui.md；evidence/browser/"+({"CHROME":"chrome","EDGE":"edge","FIREFOX":"firefox","SAFARI":"webkit"}[tag])+"-playwright.txt",msg,im,res,c=nm+" 近期正式版的主要流程")
    direct("UX-03",425,xp+" → form；"+b+"；evidence/core/browser-lifecycle.cjs；frontend/components/PlannerTools.tsx:72","實測錯誤訊息、儲存後兩頁可見、編輯占用提示；天氣提供載入及失敗狀態。",*ctx["ux_states"])
    direct("UX-04",426,xp+" → form；"+http+" → invalid_title","必填提示、錯誤帳密與 API 錯誤提供繁中訊息。")
    direct("UX-05",427,xp+" → a11y.home；frontend/app/globals.css；frontend/components/Workspace.tsx","axe 在首頁發現對比 3.88:1（要求 4.5:1）與按鈕名稱問題；完整人工 AA 審查仍待執行。","Partial","FAIL")
    direct("OPS-01",431,se+"；evidence/system/docker-before-restart.txt、docker-after-restart.txt","Compose 完整啟動。強制重建 db、api 等容器後，旅程 1、行程項目 4 保留。")
    direct("OPS-02",432,"evidence/system/docker-backup-log.txt；evidence/system/backup-policy.txt；deploy/backup.sh:4","實際 pg_dump 成功。獨立容器模擬低容量、跨七天檔案，原腳本刪舊留新、發警示並要求等待 86400 秒。")
    direct("OPS-03",433,"evidence/system/docker-backup-files.txt、docker-restored-counts.txt；.github/workflows/ci.yml","備份位於獨立掛載目錄；還原演練讀到 1 旅程、4 項目。CI 每次 push/PR 會還原；正式部署的持續演練紀錄未提供。","Partial","BLOCKED")
    direct("OPS-04",434,prep+"；deploy/backup.sh:8","只有資料庫備份，無附件儲存與一致性流程。","Missing","BLOCKED")
    direct("OPS-05",435,"README.md 部署與備份；evidence/system/docker-backup-files.txt","已檢核部署說明明列同機備份無法涵蓋主機遺失，支援 BACKUP_DIR。")
    for i,n in enumerate([439,440,441],1):
        direct(f"FREE-{i:02}",n,se+"；evidence/modules/providers-network.txt；evidence/core/wiki-retry.log；compose.yaml","沒有填付費 API 金鑰即可自架、查天氣與匯率；檢視預設供應商設定。限此次組態。")
    direct("FREE-04",442,"backend/app/planning_weather.py:28；frontend/components/PlannerMap.tsx:51；evidence/browser/experience.json；README.md:84","已檢查圖磚出處、按需載入、天氣速率保護及服務條款；實際站點用途、跨日流量與供應商授權適用性須由部署方確認。","Partial","BLOCKED")
    direct("FREE-05",443,ext+" → paid-copy-occurrences；evidence/browser/experience.json → map；frontend/components/PlannerMap.tsx:95","停用收費路由，但介面沒有規格指定的「付費功能開發中」文字。","Partial","FAIL")
    inherit("FREE-06",444,"FR-PLACE-02 FR-NOTIFY-03 BR-014")
    tech=[(demo+"；evidence/browser/build.txt","Next.js 實際建置，React/TypeScript 通過編譯。"),(demo+"；frontend/components/ui/dialog.tsx；frontend/components/ui/button.tsx","Tailwind 與本機 shadcn 風格 Radix 元件，已渲染並操作對話框。"),(http,"FastAPI 收到 API 請求並回應。"),(pg+"；"+db,"SQLAlchemy 連 PostgreSQL 寫入、讀回。"),(ck,"升至 0007，alembic check 無差異。"),(se+"；evidence/system/docker-pgversion.txt","部署 PostgreSQL 17.12，另有 PostgreSQL 16.2 驗證。"),(T("google_oidc_cookie_rotation_and_state_binding")+"；"+ext,"OIDC adapter 使用替身驗證；真實 Google 登入尚缺憑證與可授權帳號。"),(b,"兩個瀏覽器收到 WebSocket 更新。"),(xp+" → map","Leaflet 標記、順序線、出處與故障時的地址已檢驗。"),(se,"五個服務實際啟動。"),(pg+"；evidence/browser/unit.txt；"+demo,"三種測試工具都已執行。"),(".github/workflows/ci.yml；"+ext+" → git-policy","已在本機執行對應工作；未提交工作樹無對應 GitHub Actions run。"),(dc,"可讀 Swagger UI 和 OpenAPI 3.1 JSON。")]
    for i,(e,msg) in enumerate(tech,1):
        direct(f"TECH-{i:02}",453+i,e,msg,*(("Implemented","BLOCKED") if i in (7,12) else ()),c=" 使用 ".join(x.strip() for x in L[453+i].split("|")[1:3]))
    arch=[(470,se+"；backend/app/main.py:35","單一 FastAPI app 掛載各模組 router。"),(472,dc+"；evidence/system/docker-before-restart.txt","對部署入口發 HTTP，由反向代理分送並在 PostgreSQL 確認資料。"),(474,b,"視圖由瀏覽器狀態及訂閱刷新。"),(475,T("trip_versions_archives_and_idempotency"),"後端拒絕一般成員更改設定並檢查版本。"),(476,pg+"；evidence/system/counts-audit_restore.txt","交易持久化並可還原。"),(477,T("five_connected_clients_receive_committed_edits_and_revocation")+"；"+perf,"五名客戶收到的 ID 可從資料庫讀回。"),(478,"backend/app/place_search.py:17、planning_weather.py:13、finance_money.py；evidence/modules/providers-network.txt；"+T("weather_success_and_provider_failure"),"搜尋、天氣及匯率各有供應商函式及可配置端點。"),(480,se+"；backend/Dockerfile","Compose 單 API，單 Uvicorn 執行個體；無 Redis 或訊息服務。")]
    for i,(n,e,msg) in enumerate(arch,1):direct(f"ARCH-{i:02}",n,e,msg)
    for i,ref in enumerate(["FR-COLLAB-03","BR-007","FR-COLLAB-06","AC-009","ARCH-06","FR-COLLAB-01"],1):inherit(f"EDIT-{i}",487+i,ref)
    for i,ref in enumerate(["AC-007","AC-008","AC-009"],1):inherit(f"EDIT-B{i}",495,ref,c=["鎖被占用時告知目前編輯者","租約逾時可再取得","過期請求不能覆蓋新版"][i-1])

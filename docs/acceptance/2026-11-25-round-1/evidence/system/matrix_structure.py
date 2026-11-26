def populate(R,d,r,L,schema,ctx):
    S="evidence/system/schema.json"
    Q="evidence/system/postgres-suite.txt"
    X="evidence/system/extra-checks.json"
    ui="evidence/browser/chrome-playwright.txt"
    http="evidence/system/http.json"
    five="evidence/browser/collaboration.json"
    def add(id,n,e,msg,im="Implemented",res="PASS",cond=None):d(id,n,im,res,e,msg,cond)
    add("DATA-UUID",501,S+"；backend/app/models.py:20；"+http,"業務表使用 UUID 字串或參照同一 UUID 的 user_id 作主鍵；VARCHAR(36)，範例 ID 為 UUID。未要求 PostgreSQL 原生 uuid 型別。",cond="主要資料表採 UUID 主鍵")
    add("DATA-UTC",501,S+"；backend/app/models.py:24；"+http+" → create_trip","SQLAlchemy 產生 UTC、PostgreSQL 遷移採含時區欄位，API 樣本時間含 UTC offset。",cond="稽核及系統時間戳記以 UTC 保存")
    r("DATA-IANA",501,"FR-PLAN-09",c="旅遊當地時間採 IANA 時區解讀及呈現")
    for n in range(507,525):
        _,nt,fs,_=L[n].split("|")
        t=nt.strip(); f=fs.strip().split("、"); actual=schema[t]["columns"]
        missing=[col for col in f if col not in actual]
        alt={"places":"coordinates 以 latitude 與 longitude 成對儲存。","polls":"型別、截止與結束狀態移至 poll_rounds；沒有規格所列 polls.type/status/deadline。","poll_rounds":"round_number 改名 number，狀態由 closed_at 和 deadline 推導。","poll_options":"選項以 round_id 關聯輪次，再回到 poll，未直接儲存 poll_id。","ballots":"poll_round_id 的實體欄位名是 round_id，外鍵仍指向 poll_rounds。"}
        delta=t in ("polls","poll_options","poll_rounds")
        add("DB-"+t.upper().replace("_","-"),n,S+" → "+t,alt.get(t,"遷移後實表包含規格所列欄位。"),"Partial" if delta else "Implemented","FAIL" if delta else "PASS",cond=t+" 保存 "+fs.strip())
    equivalent={"task_lists":"tasks.scope 區分個人或共用；無獨立清單表。","flights":"bookings.kind=flight，segments 使用 JSON。","flight_passengers":"乘客位於 bookings.segments[].passengers。","accommodations":"bookings.kind=stay 和 stay JSON 儲存住宿。","accommodation_guests":"住客名單在 bookings.stay.guests。"}
    for n in range(530,541):
        _,ts,what,_=L[n].split("|")
        for t in ts.strip().split("、"):
            exists=t in schema
            add("DB-"+t.upper().replace("_","-"),n,S+"；backend/app/preparation_models.py:20" if t in equivalent else S+" → "+t,("遷移後已建立；用途為"+what.strip()+"。") if exists else equivalent.get(t,"目前的遷移及實表沒有附件模組。"),"Implemented" if exists else "Partial" if t in equivalent else "Missing","PASS" if exists else "FAIL",cond=t+" 實體表支援"+what.strip())
    for i,(n,ds,test) in enumerate([(544,"trip_members.trip_id/user_id","test_guest_invite_lifecycle"),(545,"trip_days/places/polls.trip_id","test_private_demo_membership_and_seeded_itinerary"),(546,"itinerary_items.day_id","test_move_overlap_and_passive_order"),(547,"itinerary_items.place_id","test_place_retained_after_candidate_removal"),(548,"poll_rounds.poll_id","test_ranked_ballots_and_tie_round"),(549,"ballots.round_id","test_secret_ballots_and_review_after_new_option")],1):
        add(f"REL-{i}",n,S+" → "+ds+"；"+Q+" → "+test,"實表外鍵與行為測試相符。")
    for key in ["foreign","unique","checks","indexes"]:
        count=sum(len(t[key]) for t in schema.values())
        add("DDL-"+key.upper(),551,S+" → "+key+"；evidence/system/alembic-check.txt",f"遷移後以 Inspector 讀到 {count} 個此類項目，並核對模型與資料庫。",cond={"foreign":"Migration 設定外鍵","unique":"Migration 設定唯一限制","checks":"Migration 設定檢查條件","indexes":"Migration 設定關聯及查詢索引"}[key])
    add("API-V1",557,http+"；evidence/system/openapi-routes.json","實際收到 /api/v1 的 OpenAPI 與業務回應。")
    import re
    tests={
        561:"test_google_oidc_cookie_rotation_and_state_binding、test_guest_invite_lifecycle、test_server_session_revocation_and_expiry",
        562:"test_trip_versions_archives_and_idempotency",563:"test_trip_versions_archives_and_idempotency",564:"test_guest_invite_lifecycle",
        565:"test_member_removal_transfers_poll_control_and_transfer_owner",566:"test_move_overlap_and_passive_order",567:"test_place_retained_after_candidate_removal",
        568:"extra-checks.json → candidate-restore、candidate-remove",569:"test_move_overlap_and_passive_order、test_restore_changed_place_and_deleted_item",
        570:"evidence/core/probes.log → test_core_lease_duration_and_explicit_release",571:"test_secret_ballots_and_review_after_new_option",
        572:"test_secret_ballots_and_review_after_new_option",573:"test_manual_adoption_keeps_item_after_revote",574:"test_comment_moderation_and_preserved_replies",
        575:"test_five_connected_clients_receive_committed_edits_and_revocation"}
    for n in range(561,576):
        for j,(m,p) in enumerate(re.findall(r"\x60(GET|POST|PATCH|DELETE|PUT|WS) ([^\x60]+)\x60",L[n]),1):
            e=X+" → api-contract；"+(tests[n] if n in (568,570) else Q+" → "+tests[n])
            add(f"API-{n-560:02}-{j}",n,e,"方法與路徑和實際路由吻合。"+("Google 授權端點有執行；外部登入另見 FR-AUTH-01。" if p=="/auth/google" else "業務狀態變化見所引測例。"),cond=m+" "+p)
    for sub,ref in [("tasks","FR-TASK-01"),("expenses","FR-FIN-02"),("settlements","FR-FIN-08"),("bookings","FR-BOOK-01"),("files","FR-FILE-01"),("notifications","FR-NOTIFY-01")]:
        r("API-EXT-"+sub.upper(),577,ref,"路徑盤點見 "+X+" → extended-contract。",c="擴充 /"+sub+" 模組")
    add("API-RULE-01",581,Q+" → test_server_session_revocation_and_expiry；"+http+" → anonymous；backend/app/core.py:127","抽驗失效／撤銷與未登入會被拒，涵蓋一般保護路由；個別資源另見各模組。")
    add("API-RULE-02",582,Q+" → test_five_connected_clients_receive_committed_edits_and_revocation、test_preferences_read_and_membership；backend/app/core.py:138","檢查有效成員，移除後 HTTP/WS 均不再授權；涵蓋主流程與不同資源。")
    add("API-RULE-03",583,X+" → member-edit-other-item；"+Q+" → test_lease_contention_renewal_timeout_and_stale_version","未授權 403、版本衝突 409、鎖定 423。")
    add("API-RULE-04",584,Q+" → test_lease_contention_renewal_timeout_and_stale_version、test_shared_tasks_and_private_lists；backend/app/notices.py:243","對有版本的業務資料以 payload/version 或查詢參數驗證。通知已讀等單向操作視為冪等狀態標記。")
    add("API-RULE-05",585,X+" → repeated-invite-ids-equal；"+Q+" → test_budgets_settlements_and_idempotence；backend/app/trips.py:359","同一 Idempotency-Key 連送兩次相同邀請都得 201，id 不同。建立旅程、記帳與還款的重送已有保護。","Partial","FAIL")
    add("API-RULE-06",586,http+" → invalid_title、oidc_missing、anonymous；backend/app/main.py:52","錯誤有 code、message、request_id，可比對 X-Request-ID。")
    add("API-RULE-07",587,"evidence/system/docker-http.json；frontend/lib/api.ts:9；evidence/browser/typecheck.txt","/openapi.json 返回 200；前端使用泛型 api<T>，型別檢查通過。回應型別由呼叫端宣告。")
    # Milestone checklist is a traceable second view of the stated feature requirements.
    grouped=[
        (1,595,["DEV-WORKFLOW","ARCH-01","OPS-01","TECH-05 TECH-06","DEV-TOOLS"],601,"OPS-01"),
        (2,605,["FR-AUTH-01","FR-AUTH-03","FR-TRIP-01","ROLE-02 ROLE-03 ROLE-05","FR-INV-01 FR-INV-02","ROLE-00 FR-COLLAB-02"],612,"FR-AUTH-01 FR-AUTH-02 API-RULE-02"),
        (3,616,["FR-PLACE-01 FR-PLACE-06","FR-COLLAB-01","FR-PLAN-04","FR-PLAN-06 FR-PLAN-07","FR-MAP-01 FR-MAP-02"],622,"FR-PLAN-03 FR-PLAN-04 AC-004 BR-006"),
        (4,626,["FR-COLLAB-01","FR-COLLAB-02","FR-COLLAB-03","FR-VOTE-01","FR-VOTE-09 FR-VOTE-10","FR-COMMENT-01"],633,None),
        (5,637,["DEV-E2E","DEV-SECURITY","UX-01 UX-05","TECH-13","DEV-DOC","OPS-01"],644,"DEV-E2E DEV-DOC UX-05 MS4-DONE")]
    add("DEV-WORKFLOW",595,X+" → git-policy；README.md 開發與驗證；.github/workflows/ci.yml","有 repo、PR 說明和 PR 觸發設定；本地僅見初始提交，未查到本 SHA 的 PR run，無法驗證實際團隊審核。","Implemented","BLOCKED")
    add("DEV-TOOLS",599,"evidence/system/ruff.txt、format.txt；evidence/browser/lint.txt、format.txt、unit.txt；"+Q,"實際執行 lint、format、build 及三種測試工具；GitHub 遠端執行另見 TECH-12。")
    add("DEV-E2E",637,ui+"；evidence/browser/edge-playwright.txt","有可執行的瀏覽器測試，含實際整合與明示攔截的 UI 案例。")
    add("DEV-SECURITY",638,Q+" → test_server_session_revocation_and_expiry、test_reservation_privacy_and_edits、test_missing_oidc_settings_and_request_origin","已執行既有授權、Session、同源及敏感欄位測試；安全性完整範圍見 §5.2。")
    add("DEV-DOC",641,"README.md；evidence/system/docker-seed.txt、docker-before-restart.txt；"+ui,"README 說明架構、部署及限制；成功產生 1 筆合成行程、4 個每日項目並讀取展示內容。")
    for num,start,refs,n,done in grouped:
        for j,link in enumerate(refs,1):r(f"MS{num}-{j}",start+j-1,link)
        if done:r(f"MS{num}-DONE",n,done)
    add("MS4-DONE",633,five+"；"+Q+" → test_five_connected_clients_receive_committed_edits_and_revocation；evidence/browser/ui.md",ctx["ms4"][0],*ctx["ms4"][1:])
    exclusion=[
        ("公開社群內容","evidence/system/openapi-routes.json；"+ui,"只見必須加入旅程的共用討論。"),
        ("商業訂房或機票購買","evidence/modules/module-ui-final.txt；"+Q,"實際操作保存及外部資訊連結，沒有購買流程。"),
        ("真實轉帳及第三方支付",Q+" → test_budgets_settlements_and_idempotence","費用只影響站內帳本。"),
        ("AI 自動生成完整行程","evidence/system/openapi-routes.json；evidence/system/source-sha256.json","比對交付物及 API inventory，無生成式服務。"),
        ("離線編輯及合併","evidence/modules/module-ui-final.txt","離線儲存失敗，重連後查無離線草稿。"),
        ("自動下載完整離線地圖","evidence/browser/experience.json → offline；frontend/public/sw.js:3","Service Worker 快取只有七個美術／圖示檔，沒有圖磚。"),
        ("依賴付費的景點、路線與航班服務","evidence/modules/providers-network.txt；evidence/core/wiki-retry.log；evidence/browser/experience.json","搜尋與天氣使用免費端點，地圖提供直線和外部導航，航班手動輸入。"),
        ("原生 iOS / Android App","evidence/system/source-sha256.json；evidence/system/docker-http.json","完整交付物是 Web / PWA。"),
        ("微服務與 Kubernetes","evidence/system/docker-services.txt；backend/app/main.py:35","執行清單為 Compose、新增模組掛在單體 API。")]
    for j,(nm,e,msg) in enumerate(exclusion,1):add(f"OUT-{j:02}",680+j,e,msg,cond="目前排除"+nm)

# 第 3.7 至 3.14 節的缺陷與限制

## M-00　五人編輯留言時同步失敗

**影響程度為高，直接影響 MVP 核心展示。** 對應 FR-COMMENT-03、§1.3 及里程碑 4。在隔離部署以五個 Chrome Context 加入同旅程，提交五筆留言，再編輯一筆並等待其他頁面顯示新文字。規格要求所有在線成員即時看見更新。五筆建立都能重新讀取，但等待編輯顯示滿 10 秒仍逾時。雙人實際留言和五條 TestClient 建立事件成功。這些測試涵蓋不同操作與併行條件。

同情境在 SQLite 及 Docker Compose 搭配 PostgreSQL 17.12 皆重現。實際瀏覽器案例見 `../browser/collaboration.cjs`、`../browser/collaboration.json` 及 `../browser/collaboration-postgres.json`。留言提交與廣播位於 `backend/app/decisions.py:535`，頁面接收與重新讀取資料位於 `frontend/components/TripDetail.tsx:115`。請結合總報告中的 API 卡住診斷判斷根因。優先修復多人寫入與事件發布後無法更新的情形，保留五人測試作為回歸門檻。

## M-04　夏令時間切換當日會保存不存在的當地時間

**影響程度為中。** 對應 FR-PLAN-09。將旅程設為 2027 年 3 月 14 日，在第一天新增目的地時區 America/New_York、開始時間 02:30 的活動，重讀行程。這一天紐約從 01:59 跳到 03:00。系統應拒絕不存在的牆上時間，或提示調整並一致地保存新時間。

實際得到 HTTP 201，`start_time` 為 02:30，`start_instant` 為 07:30 UTC，使用同一 IANA 時區反解是 03:30。兩個欄位指向不同時刻。重現案例在 `test_cross_checks.py` 的 `test_iana_dst_gap_round_trip`，輸出在 `cross-checks.txt`。正常夏季時差及跨區呈現另有通過案例。

已確認 `backend/app/planning_time.py:16` 直接把 ZoneInfo 指定給當地日期時間，`backend/app/planning_time.py:61` 寫入推得的 UTC 時刻，期間沒有將結果反解回目的地以辨識不存在的時間。建議驗證轉換來回的一致性，向使用者指出當日可用的時刻，並補充秋季重複小時的選擇策略。

## M-01　私人文件及附件未交付

**影響程度為高，涉及私人資料的驗收受阻。** 涵蓋 FR-FILE-01 至 FR-FILE-06、FR-BOOK-05、FR-COMMENT-05、FR-TASK-06，以及 AC-018、BR-013。私人文件授權與檔案管理是 P2 範圍，但 P1 的訂位需求也明列私人文件。

1. 以合成 Owner 建立旅程，取得應用提供的 OpenAPI。檔案、附件、上傳相關路徑數量為零。
2. 在登入狀態向旅程的檔案集合送出有效 PNG、PDF、DOCX。三種檔案的 multipart POST 都得到 404。對版本化的全站及旅程檔案集合執行 GET 也得到 404。
3. 發表附帶圖片資料欄位的文字留言，得到 201。另一個請求重讀時只取得留言文字與一般欄位，沒有附件。
4. 在獨立旅程建立有訂位代號的航班，分別使用建立者、乘客及其他旅伴讀取。訂位代號及座位的授權測試通過。

**預期與實際**　規格要求檔案上傳、管理、批次操作、關聯、私人授權、刪除後回收，以及可設定的 10 MB／500 MB 配額。檔案入口缺失，私人檔案授權、回收和大小臨界值沒有可操作的前置資料。沒有觀察到未授權取得私人文件。

**已確認原因與建議**　後端掛載路由清單位於 `backend/app/main.py:36`，留言輸入模型位於 `backend/app/decisions.py:76`，兩者均無附件機制。預訂欄位授權在 `backend/app/preparations.py:334`，適用於訂位資訊。README 第 71 行明列附件待開發。建議先完成受授權的檔案存取及配額，繼而串接預訂、留言、任務與費用。實作後以兩個帳號再驗證讀取／下載、刪除、回收及批次上傳邊界。

可重查 `probes.txt` 的 `test_file_contract_and_comment_images`，以及 `pytest.txt` 的 `test_reservation_privacy_and_edits`。Chrome 雙人預訂結果在 `../browser/chrome-playwright.txt` 第 4 個案例。

## M-02　PWA 離線時無法重開已讀旅程

**影響程度為中。** 對應 FR-OFFLINE-01。出遊前看過的地址及文字無法在交通途中離線取用。

1. 在本次 production build 建立三個有地址的景點及兩日活動。啟動 Service Worker，重新載入並確認它控制頁面。
2. 切斷瀏覽器網路，再以新分頁開啟剛讀過的同一旅程。
3. Chrome 回報 `net::ERR_INTERNET_DISCONNECTED`，頁面中找不到測試活動。網路恢復後同一網址正常載入。

**預期與實際**　預期可讀已保存的行程文字、地址與基本資料。實查只快取 7 個圖示或插圖，未快取可離線啟動的旅程頁及可讀資料。另於連線時開好的頁面斷網嘗試新增活動，頁面顯示網路中斷，恢復連線後資料庫沒有該筆資料，符合 FR-OFFLINE-02。

**已確認原因與建議**　`frontend/public/sw.js:3` 列出資產，`frontend/public/sw.js:26` 的 fetch 只回應該清單的 GET。建議提供經使用者選擇保存的唯讀行程快照，涵蓋地址及文字，並在登出或撤銷時清理裝置資料。

可重查 `../browser/experience.json` 的 `offline`，以及 `module-ui.txt` 的 `OFFLINE-02`。

## M-03　任務欠缺重複週期與附件

**影響程度為低。** 對應 FR-TASK-06。FR-TASK-01 至 05 的共用／個人清單、指派、進度與關聯可用。

以已登入的成員建立一筆一般任務，另用相同資料分別加入週期與附件欄位。一般任務回 201，後兩個請求各回 422。畫面只提供單次任務與景點／活動關聯。預期能保存並重複產生任務，並附加檔案。API 的 `TaskInput` 無這兩個欄位且拒絕額外欄位，任務表單也無相關控制項。見 `backend/app/preparations.py:31`、`backend/app/preparations.py:39`、`frontend/components/Preparation.tsx:94`。建議明確定義重複週期、每期完成狀態，並於附件服務完成後接入。重現案例為 `probes.txt` 的 `test_task_all_fields_links_and_repeat`。

## V-01　Web Push 到真實裝置的投遞仍待確認

對應 FR-NOTIFY-02。站內通知、已讀、偏好均通過。Chrome 回報安全來源、PushManager 及 Service Worker 可用。隔離站台未配置 VAPID，介面正確顯示提示。另以臨時 VAPID 金鑰、全新 Chrome 設定檔及獲准的通知權限，實際註冊產品 Service Worker 並要求訂閱。一般環境及允許對外連線後均收到 `AbortError: Registration failed - permission denied`。現有測試驗證簽章、送至模擬供應商及 410 清除失效訂閱。這些結果不足以確認真實裝置接收。

未確定根因，服務商、裝置或自動化瀏覽器均可能影響訂閱。建議在配妥 VAPID 的公開 HTTPS 測試站，以非自動化瀏覽器授權訂閱，切換背景，從另一個帳號提及收件人，核對通知及開啟收件匣。相關程式位於 `frontend/components/NoticeCenter.tsx:102`、`backend/app/notices.py:119` 和 `frontend/public/sw.js:39`。可查 `module-ui.txt`、`push-network.txt`、`pytest.txt` 的 `test_push_permission_delivery_and_gone`。

## 測試指令與證據範圍

FR-PDF-02 已確認 `frontend/components/PlannerTools.tsx` 的匯出欄位採允許清單。Vitest 用合成的訂位欄位、私人備註及景點成本核對輸出。在另一項測試中，透過真實 API 為同旅程保存訂位代號、費用與兩人分攤，讀回確認後匯出詳細及簡表兩份 PDF。獨立解析兩份實體 PDF 均未出現六個敏感標記，見 `../browser/pdf-private-text.json`，這兩類資訊排除通過。私人文件驗證需要具有授權設定的真實檔案，本版的檔案入口回 404，因此整條三類敏感資訊驗收為 BLOCKED。

從 `D:\WayToGo\backend` 執行下列 PowerShell 指令。既有 fixture 會為每個測試建立不同的暫存 SQLite 資料檔。8 個診斷探針中的斷言含「重現缺少的行為」，因此探針通過數不代表規格通過數。

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
Remove-Item Env:\TEST_DATABASE_URL -ErrorAction SilentlyContinue
..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -vv --tb=short tests/test_decisions.py tests/test_availability.py tests/test_finance.py tests/test_preparations.py tests/test_notices.py tests/test_planning_extensions.py tests/test_core.py tests/test_planning.py
$env:PYTHONPATH = 'D:\WayToGo\backend;D:\WayToGo\backend\tests'
..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -p conftest -vv -s --tb=short ..\acceptance-20261125\evidence\modules\test_module_probes.py
```

於專案根目錄使用 `node acceptance-20261125/evidence/modules/module_ui.cjs .local/audit-ui-20261125/runtime.json` 操作本次隔離服務。重跑須先依 `../browser/run_ui.py` 建立新的測試帳號及暫存資料庫。測試程式讀取測試帳號，不會輸出密碼、邀請碼或 Session。真實兩人 UI、通知和郵件連結皆使用後端資料。唯一重播的 UI 回應為天氣成功畫面，其值取自 `providers-network.txt`，另外以受控資料測後端成功及逾時情境。地圖、列印、財務及行前準備的補充 UI 結果在相鄰 browser 目錄。

外部供應商可在 `PYTHONPATH` 包含 backend 時執行 `python acceptance-20261125/evidence/modules/provider_probe.py`。匿名公開查詢在沙箱回報無可用結果，允許連線後取得匯率和當日天氣。測試日期與取得值見 `providers.txt` 和 `providers-network.txt`。Web Push 訂閱診斷另以 `node acceptance-20261125/evidence/modules/push_probe.cjs http://127.0.0.1:18731` 執行，不使用部署者的私人 VAPID 金鑰或真人帳號。

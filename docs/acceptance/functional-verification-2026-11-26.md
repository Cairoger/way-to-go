# WayToGo 功能驗證紀錄 · 2026-11-26

本輪在 `aac83bd` 確認 4 個日常操作錯誤，並發現航班編輯與旅程復原期限有 2 處行為不一致，其中旅程重複建立與同名景點錯綁會直接寫入錯誤資料。測試使用本機正式建置、獨立的資料庫與合成旅客。這份紀錄涵蓋本輪實際操作。各資料庫與瀏覽器會重跑相同案例，表中數字請分開閱讀。

## 可重現的錯誤與差異

| 操作 | 預期結果 | 本輪實際結果 | 程式位置 |
| --- | --- | --- | --- |
| 在 Chrome 建立旅程，讓伺服器完成寫入後中斷回應。出現連線錯誤時，在同一表單再按一次建立 | 同一份草稿只建立一筆旅程 | 兩次請求使用不同的重送識別碼。重新讀取旅程清單，得到同名、不同 ID 的兩筆旅程 | [旅程表單](../../frontend/components/TripForm.tsx)、[API 請求](../../frontend/lib/api.ts) |
| 建立同名但地址不同的兩個景點，發起投票，從清單選第二個景點並送出 | 投票選項連到第二個景點 | 建立投票成功，但回傳的選項指向第一個景點 ID | [建立投票](../../frontend/components/Decisions.tsx) |
| 將勝出的投票選項採用到某日行程，刪除該活動，再對同一天按採用 | 成功時應可在行程中看到活動，或得到說明如何處理已刪除活動的提示 | API 回傳 HTTP 200 與已刪除的活動 ID，重讀當日行程仍為 0 筆 | [採用投票結果](../../backend/app/decisions.py) |
| 替旅伴登記航班座位與行李，讓他離團，再以原預訂建立者開啟「編輯航班」 | 後端允許仍在團內的原建立者讀取既有乘客欄位。編輯畫面如何處理離團旅客，規格未明訂 | API 仍保有座位 18B 與行李 20kg，編輯表單兩者皆未顯示。另用原建立者透過正常 API 改為 21C／23kg 後，重新讀取得到新值 | [航段旅客欄位](../../frontend/components/Reservations.tsx) |
| 在 390 × 844 的 Chrome 視窗聚焦「開啟選單」，依序按 Enter、Tab、Escape | 焦點能進入選單，關閉後可回到開啟按鈕 | 展開後焦點留在遮罩後的「開啟選單」。下一個 Tab 落在同樣被遮住的「使用說明」，Escape 後側欄仍開啟。開啟按鈕也未標示展開狀態 | [手機側欄](../../frontend/components/Workspace.tsx) |
| 合成旅程刪除後，以固定時鐘在剛滿 30 天時，用原建立者帳號查看回收區並呼叫還原 | 回收區顯示與後端可還原期限應一致 | 滿 30 天的精確瞬間，旅程已從列表消失，但以該 ID 還原仍回 HTTP 200。截止前 1 秒可見且可還原，後 1 秒不可見且還原回 404 | [回收區清單](../../backend/app/trips.py)、[還原時限](../../backend/app/core.py) |

航班案例中，離團的是旅客，原預訂建立者仍在團內。預訂卡片會顯示 API 回傳的座位與行李，開啟編輯表單後無法選取該旅客。FR-BOOK-02、FR-BOOK-06 要求記錄座位、行李與手動更新。資料模型要求檢查新指派的旅客身分，既有預訂的讀取及寫入規則均容許原建立者維護這些欄位。產品規格未指定離團旅客在表單中應可編輯或僅供檢視。[交通與住宿規格](../spec.md#312-交通與住宿資訊) · [資料模型](../data-model.md) · [後端預訂讀寫規則](../../backend/app/preparations.py)

前四個流程在 nginx、Next.js、FastAPI 與 PostgreSQL 的 Compose 部署上操作。投票再採用直接呼叫同一部署的 API，另外三個透過 Chrome 操作表單並比對 API 資料。手機選單使用同一部署與獨立的瀏覽器工作階段。

### 回收區 30 天邊界的測試紀錄

測試以三個獨立的 SQLite 資料庫、旅程與原建立者工作階段重跑同一個流程。每次先將應用程式時鐘固定為 2026-04-01 12:00:00 UTC，建立並刪除旅程，再確認 API 回傳相同的刪除時間。以下各時間點均先查旅程列表，接著由原建立者用同一個旅程 ID 還原，最後重新讀取。

| 測試時刻（UTC） | 回收區列表 | 還原 HTTP | 重讀 HTTP |
| --- | --- | --- | --- |
| 2026-05-01 11:59:59 | 可見 | 200 | 200 |
| 2026-05-01 12:00:00 | 不可見 | 200 | 200 |
| 2026-05-01 12:00:01 | 不可見 | 404 | 404 |

pytest 的應用觀測輸出如下。每筆成功還原也核對了清除刪除時間及版本加一。

```text
offset=-1s visible_in_list=True restore=200 reread=200
.offset=+0s visible_in_list=False restore=200 reread=200
.offset=+1s visible_in_list=False restore=404 reread=404
.
3 passed, 1 warning in 0.19s
```

## 驗證結果

| 範圍 | 本輪觀察 |
| --- | --- |
| 前端 | TypeScript、ESLint、Prettier 與 Next.js 16.4.6 正式建置通過。Vitest 的 2 個檔案、5 個案例全數通過。 |
| 後端 | Python 3.12、Ruff 程式檢查及 59 個檔案的格式檢查通過。SQLite 為 63 個通過。PostgreSQL 17.12 為 62 個通過、1 個 SQLite 專用備份案例略過，該案例已在 SQLite 通過。 |
| 遷移與 API | 兩種資料庫均升級至 Alembic 0010，模型差異檢查通過。比對 OpenAPI，93 個 HTTP 方法與路徑組合全部實際呼叫，且各至少取得一次成功或重新導向回應。文末附逐項狀態與斷言。 |
| Chrome | SQLite 正式建置 23/23 通過，包含分頁關閉後收到真實背景提及推播，以及模擬點擊後定位留言。Compose／PostgreSQL 21 個通過，該配置未開啟的 2 個推播案例略過。 |
| Linux Firefox、WebKit | 兩個引擎分別在 Compose／PostgreSQL 上通過 21 個案例，各略過 2 個 Chromium 專用推播案例。五人協作測試在每個引擎均觀測到 80 次跨頁更新，零逾時。 |
| macOS WebKit | 預設鍵盤設定下，整套為 19 個通過、2 個失敗、2 個略過。只在測試程式啟用完整鍵盤導覽後，鍵盤案例通過，整套為 20 個通過、1 個失敗、2 個略過。詳見下方列印複驗。 |
| 備份與還原 | 6 個 Compose 服務成功啟動。以專案腳本還原含瀏覽器資料的備份，得到 42 張表、22 位合成使用者及 21 筆旅程。還原後的私人 PNG 通過位元組雜湊、訂位關聯與授權檢查。另一次 PostgreSQL CI 演練的 42 張表，還原前後筆數與內容摘要全部相同。 |
| 地圖、天氣、匯率 | 透過實際供應商搜尋「台北101」取得 2 筆具座標的地點，台北當日預報與 USD/EUR 匯率均回傳資料。Chrome 顯示 OSM 圖磚、兩個標記及行程序列線，導航連結目的地與輸入座標一致。 |
| 邀請 | 從畫面截取 QR Code 解碼，結果與產生的邀請網址一致。Email 草稿連結含正確旅程名稱與邀請網址。另以獨立瀏覽器工作階段持邀請加入，完成雙人協作。 |

測試涵蓋帳號、旅伴與邀請、旅程生命週期、景點、每日行程、投票、日期協調、留言與即時重連、行前清單、分帳還款、航班住宿、附件、通知、離線閱讀及列印。程式檢查有相依套件棄用提示，SQLite 遷移有舊的未命名 CHECK 提示，資料庫實查確認相應限制存在。

## 各功能的行為驗證

下表對照使用者操作、實際檢查的結果與案例。通過的範圍限於表中描述的情境。HTTP 操作的狀態碼另外列在文末，以便區分資料、畫面與通訊協定三種證據。

| 功能 | 實際核對的行為與結果 | 可查核案例或證據 |
| --- | --- | --- |
| 首頁、示範與手機導覽 | 桌機篩選、卡片與清單切換、指定行程日、手機點按選單與加入表單通過。390 像素寬的鍵盤選單出現上述焦點錯誤。 | [首頁與手機](../../frontend/tests/workspace.spec.ts)、[鍵盤](../../frontend/tests/accessibility-keyboard.spec.ts)、本輪手機選單步驟 |
| 帳號與工作階段 | 本機登入後可建立旅程，重載保留身分。測試供應商的 Google 登入、訪客合併、工作階段到期與撤銷均通過。 | [本機登入](../../backend/tests/test_local_login.py)、[工作階段及 OIDC](../../backend/tests/test_core.py)、[帳號合併](../../backend/tests/test_guest_merge.py) |
| 個人資料、成員與邀請 | 雙分頁更新暱稱可偵測版本衝突。訪客加入、撤銷邀請、移除成員與移轉擁有權通過。另核對 QR 解碼及 Email 草稿。 | [個人資料與邀請](../../backend/tests/test_review_account_invitations.py)、[雙分頁](../../frontend/tests/review-acceptance.spec.ts)、[成員](../../backend/tests/test_core.py) |
| 旅程管理與複製 | 建立、更新、封存、刪除與復原通過。複製規劃資料時有新 ID 並清除私人訂位資料。瀏覽器在回應中斷後重送會建立重複旅程，回收區另有剛滿 30 天的精確邊界差異。 | [旅程版本及生命週期](../../backend/tests/test_core.py)、[旅程複製](../../backend/tests/test_trip_copy.py)、本輪旅程重送步驟 |
| 候選景點、地圖與天氣 | 已安排的景點在移出候選後保留引用。地點搜尋、圖磚、標記、兩點連線及導航座標通過。天氣實際查詢與供應商失敗時的提示分別驗證。 | [景點保留與搜尋](../../backend/tests/test_planning.py)、[天氣](../../backend/tests/test_planning_extensions.py)、[地圖介面](../../frontend/tests/offline-planner.spec.ts)、本輪實際供應商查詢 |
| 每日行程與異動復原 | 跨日移動、順序與時間重疊、時區切換、刪除活動後從歷史復原通過。Chrome 用滑鼠拖至另一日並調整順序，重新整理後日期與順序皆正確。 | [每日行程](../../backend/tests/test_planning.py)、[時區與復原](../../backend/tests/test_planning_extensions.py) |
| 即時共編 | 五位旅伴留言編輯產生 80 筆跨頁觀測，Chrome、Linux Firefox 與 WebKit 均為零逾時。斷線重新連線後補讀、編輯鎖續期及版本衝突均有獨立案例通過。 | [多人協作](../../frontend/tests/live-collaboration.spec.ts)、[鎖與版本](../../backend/tests/test_planning.py) |
| 投票 | 投票中保密、截止結算、平票重投、評分與排序通過。遇到同名景點或重新採用已刪除活動時，產生上述兩個錯誤。 | [選票規則與結果](../../backend/tests/test_decisions.py)、[評分與排序介面](../../frontend/tests/coordination.spec.ts)、本輪兩個投票重現步驟 |
| 旅遊日期協調 | 單日、區間、共同可用日期，以及套用日期後保留既有活動均通過。 | [日期與既有行程](../../backend/tests/test_availability.py)、[日期協調介面](../../frontend/tests/coordination.spec.ts) |
| 討論與通知 | 留言、回覆、提及、通知已讀與偏好通過。Chrome 暫存設定檔關閉頁面後，瀏覽器仍收到背景通知。 | [留言與提及](../../backend/tests/test_decisions.py)、[通知](../../backend/tests/test_notices.py)、[背景推播](../../frontend/tests/live-push.spec.ts) |
| 任務清單 | 共用／個人任務、分開更新進度、週期完成紀錄與附件保留通過。 | [行前清單](../../frontend/tests/live-preparations.spec.ts)、[重複任務](../../backend/tests/test_files_recurrence.py) |
| 預算與分帳 | 支付與分攤、外幣記帳、超額提醒、分次還款與離團後的財務歷史通過。 | [財務計算](../../backend/tests/test_finance.py)、[雙人分帳還款](../../frontend/tests/live-finance.spec.ts) |
| 交通與住宿 | 多段航班、住宿、不同角色可見欄位、與每日行程連結通過。原作者仍在團內而既有旅客退出時，發現上述編輯表單差異。 | [預訂及角色權限](../../backend/tests/test_preparations.py)、[航段與住宿介面](../../frontend/tests/live-preparations.spec.ts) |
| 旅程檔案與留言圖片 | 批次上傳、預覽、下載、關聯、私人授權、回收還原及配額通過。另從實際備份核對私人附件雜湊與關聯。 | [附件與配額](../../backend/tests/test_files_recurrence.py)、[附件介面](../../frontend/tests/live-files.spec.ts)、[還原斷言](../../deploy/verify-restore-browser.sql) |
| 離線閱讀 | 儲存後斷線、關閉舊頁並由新頁唯讀開啟行程通過。登出與換帳的既有清理案例通過。 | [真實旅程離線讀取](../../frontend/tests/live-offline-planner.spec.ts)、[離線與換帳](../../frontend/tests/offline-planner.spec.ts) |
| 列印與 PDF | Chrome 匯出與文字檢查通過。macOS WebKit 在真實旅程可選日期並產生正確的簡要與詳細預覽。模擬列印案例在該平台整套執行時有失敗，詳見下節。 | [列印日期與隱私](../../frontend/tests/planner-print.spec.ts)、[實際 PDF 文字](../../frontend/tests/live-files.spec.ts)、本輪兩日行程測試 |
| 部署、遷移與還原 | 初始化保留既有設定，Compose 對外首頁與健康檢查可用。兩種資料庫遷移、含應用資料的備份還原及附件核對通過。 | [部署配置](../../compose.yaml)、[還原演練](../../deploy/restore-drill.sh)、[CI 比對](../../.github/workflows/ci.yml) |

## 需要分開判讀的測試

- **macOS WebKit 的列印測試**在完整組合中兩度等不到「匯出行程 PDF」按鈕。使用模擬資料的請求實際抵達後端並收到 401。相同案例單跑通過，在先跑離線測試、再僅對列印測試停用 service worker 的對照組也通過。另在 Compose 正式站以真實登入建立兩日行程，只勾第一天，簡要與詳細兩個預覽均正確顯示第一天，並排除第二天與私人欄位。Chrome 另有驗證產出的 PDF 文字。
- **歷史驗收案例**另抽跑 27 個，24 個通過。3 個失敗的斷言仍預期個人資料更新可省略版本、任務不可設定重複與附件，以及附件 API 不存在。這些預期已與本版契約不同。

## 驗證邊界

macOS Firefox 的測試程式在網站載入前無法開啟暫存設定檔，21 個適用案例改於同版本 Linux Firefox 完成。原生 macOS Safari 27.2 因未啟用 WebDriver 遠端自動化，無法建立工作階段。另嘗試以系統介面操作也在進入網站前逾時，因此原生 Safari 未取得本輪功能結果。

Email 邀請只查核草稿內容，未實際寄送。附件測試驗證設定值及縮小配額下的拒絕與並行寫入，未實際上傳至預設 500 MiB 的旅程上限。另在 Chrome 手機尺寸模擬中，兩度長按拖移均未觸發拖放。第二次已確認起點與終點命中活動及 Day 2，長按 750 毫秒後移動仍未改變日期。兩次改用「移動」表單都成功，重載後資料一致。手機案例以瀏覽器尺寸模擬，未操作實體 iPhone、Android、安裝版 Edge 或完整螢幕閱讀器流程。五頁協作的短時觀測也未涵蓋長時間負載。

Google OIDC 登入、回呼與訪客合併已使用替身供應商測試。真實 Google 帳號同意與公開 HTTPS 站台登入未在本輪操作。推播確認到瀏覽器收到通知，也測過模擬點擊。實體手機作業系統的通知橫幅點擊未驗證。

[專案驗證流程](../../.github/workflows/ci.yml) · [瀏覽器測試](../../frontend/tests) · [後端測試](../../backend/tests)

## HTTP 操作逐項結果

這次獨立的 SQLite 測試記錄了 1,083 次 HTTP 回應。63 個現行測試、22 個與當版契約相符的歷史案例，以及 4 個補充案例，共 89 個通過。這組統計與前面的測試有重疊。30 天邊界另以固定時間測試。

每列對應一個 HTTP 方法及 OpenAPI 路徑。93 個操作各至少取得一次 2xx 或 3xx。「行為」35 列記錄了核對的資料或權限結果。「觸達」58 列只從此表認定方法、路徑及回應狀態。Google 權杖交換、地點搜尋、天氣和匯率在此輪使用受控回應。地點搜尋、天氣、匯率的實際供應商測試另列於前文。

### OpenAPI 與實測紀錄的獨立比對

另從 Git 提交 `aac83bda1d580e8000f62d953a829ab9f65dcd7a` 匯出乾淨後端，載入 `app.main.app.openapi()`，逐一取出 `paths` 下的 HTTP 方法與路徑樣板。匯出的 TSV 依方法與路徑排序，SHA-256 為 `85a5931573a31fd8e72b38be52430ea546101239640f991ffa9fd8a1a28edd60`。[下載當版 OpenAPI 方法與路徑](functional-verification-2026-11-26-openapi.tsv)

| 獨立比對結果 | 數量 |
| --- | ---: |
| OpenAPI 宣告的唯一方法與路徑 | 93 |
| 實際 HTTP 紀錄的唯一方法與路徑 | 93 |
| 寫入下表的唯一方法與路徑 | 93 |
| OpenAPI 宣告但沒有實際請求 | 0 |
| 實測紀錄中沒有對應 OpenAPI 操作 | 0 |
| 實測紀錄與報告表格的對稱差集 | 0 |

WebSocket 另以多人協作與斷線重連案例驗證。

<details>
<summary>展開 93 個操作、HTTP 狀態次數、測試名稱與驗證內容</summary>

| 方法 | OpenAPI 路徑 | HTTP 狀態 × 次數 | 測試案例 | 驗證內容 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/auth/google` | 200 × 6, 503 × 1 | `test_google_oidc_cookie_rotation_and_state_binding` | 行為。Google 權杖交換使用替身。核對 PKCE、state、nonce、303 導回、登入後 Cookie 更換。 |
| GET | `/api/v1/auth/google/callback` | 303 × 5, 401 × 3 | `test_google_oidc_cookie_rotation_and_state_binding` | 行為。Google 權杖交換使用替身。核對 PKCE、state、nonce、303 導回、登入後 Cookie 更換。 |
| POST | `/api/v1/auth/guest` | 200 × 75, 403 × 2 | `test_five_connected_clients_receive_committed_edits_and_revocation` | 觸達 |
| GET | `/api/v1/auth/local-test` | 200 × 6 | `test_local_login_disabled_outside_http_loopback` | 觸達 |
| POST | `/api/v1/auth/local-test` | 200 × 5, 401 × 2, 404 × 5 | `test_simultaneous_first_signins_share_one_subject` | 觸達 |
| POST | `/api/v1/auth/logout` | 204 × 2, 403 × 1 | `test_server_session_revocation_and_expiry` | 觸達 |
| GET | `/api/v1/auth/me` | 200 × 66, 401 × 5 | `test_repeat_two_periods_with_persistent_files` | 觸達 |
| PATCH | `/api/v1/auth/me` | 200 × 2, 409 × 1, 422 × 3 | `test_profile_is_self_only_and_creator_survives_transfer` | 觸達 |
| DELETE | `/api/v1/comments/{comment_id}` | 200 × 3, 403 × 1 | `test_delete_own_comment_preserves_reply` | 行為。核對作者刪留言後保留空內容與原作者，子回覆及其關聯完整。 |
| PATCH | `/api/v1/comments/{comment_id}` | 200 × 4, 403 × 1, 409 × 1 | `test_structured_and_plain_mentions_on_create_edit` | 觸達 |
| POST | `/api/v1/days/{day_id}/items` | 201 × 27, 404 × 1, 422 × 5 | `test_core_time_options_types_and_order` | 觸達 |
| GET | `/api/v1/days/{day_id}/weather` | 200 × 3 | `test_weather_success_and_provider_failure` | 行為。受控氣象服務回應。核對可用天氣與服務失敗結果。 |
| POST | `/api/v1/edit-leases` | 200 × 25, 403 × 1, 423 × 1 | `test_original_place_delete_is_versioned_and_preserves_reference` | 觸達 |
| DELETE | `/api/v1/edit-leases/{lease_id}` | 200 × 1 | `test_core_lease_duration_and_explicit_release` | 行為。核對續租期限延長，釋放後其他成員看見解除且可重新取得。 |
| POST | `/api/v1/edit-leases/{lease_id}/renew` | 200 × 2 | `test_core_lease_duration_and_explicit_release` | 行為。核對續租期限延長，釋放後其他成員看見解除且可重新取得。 |
| DELETE | `/api/v1/files/{file_id}` | 200 × 2, 403 × 1 | `test_attachment_permissions_revocation_copy_and_restore` | 行為。核對權限撤銷、回收後可見性、還原後內容。 |
| PATCH | `/api/v1/files/{file_id}` | 200 × 2, 403 × 1, 409 × 1 | `test_attachment_permissions_revocation_copy_and_restore` | 行為。核對權限撤銷、回收後可見性、還原後內容。 |
| GET | `/api/v1/files/{file_id}/download` | 200 × 13, 401 × 1, 403 × 4, 404 × 1 | `test_all_advertised_image_formats` | 行為。核對 PNG、JPEG、GIF、WebP 的預覽及下載位元組與上傳內容相同。 |
| GET | `/api/v1/files/{file_id}/preview` | 200 × 11, 403 × 3 | `test_all_advertised_image_formats` | 行為。核對 PNG、JPEG、GIF、WebP 的預覽及下載位元組與上傳內容相同。 |
| POST | `/api/v1/files/{file_id}/restore` | 200 × 1 | `test_attachment_permissions_revocation_copy_and_restore` | 行為。核對權限撤銷、回收後可見性、還原後內容。 |
| POST | `/api/v1/invitations/accept` | 200 × 2 | `test_guest_invite_lifecycle` | 觸達 |
| DELETE | `/api/v1/itinerary-items/{item_id}` | 200 × 1 | `test_restore_changed_place_and_deleted_item` | 觸達 |
| PATCH | `/api/v1/itinerary-items/{item_id}` | 200 × 2 | `test_dst_gap_fold_and_date_changes` | 觸達 |
| POST | `/api/v1/itinerary-items/{item_id}/move` | 200 × 3, 403 × 1, 422 × 1 | `test_move_overlap_and_passive_order` | 觸達 |
| GET | `/api/v1/notifications` | 200 × 10 | `test_preferences_read_and_membership` | 觸達 |
| DELETE | `/api/v1/notifications/device` | 204 × 1 | `test_push_device_cannot_reassign_another_active_account` | 行為。模擬推播設定。核對裝置綁定與解除後的註冊狀態。 |
| PUT | `/api/v1/notifications/device` | 204 × 3, 409 × 1, 422 × 1 | `test_push_device_cannot_reassign_another_active_account` | 行為。模擬推播設定。核對裝置綁定與解除後的註冊狀態。 |
| PUT | `/api/v1/notifications/preferences` | 200 × 2, 409 × 1 | `test_preferences_read_and_membership` | 行為。核對通知讀取狀態與更新偏好後的通知清單。 |
| POST | `/api/v1/notifications/{notice_id}/read` | 204 × 1, 404 × 1 | `test_preferences_read_and_membership` | 行為。核對通知讀取狀態與更新偏好後的通知清單。 |
| DELETE | `/api/v1/places/{place_id}` | 200 × 3, 403 × 1, 409 × 1, 423 × 1 | `test_original_place_delete_is_versioned_and_preserves_reference` | 觸達 |
| PATCH | `/api/v1/places/{place_id}` | 200 × 6, 409 × 1, 423 × 1 | `test_core_places_fields_status_author_days` | 觸達 |
| GET | `/api/v1/places/{place_id}/history` | 200 × 3 | `test_core_places_fields_status_author_days` | 觸達 |
| POST | `/api/v1/planner-history/{kind}/{resource_id}/restore` | 200 × 3, 403 × 1, 409 × 1 | `test_restore_changed_place_and_deleted_item` | 行為。核對景點與已刪除活動由修訂紀錄還原。 |
| DELETE | `/api/v1/polls/{poll_id}` | 200 × 2 | `test_remaining_five_http_operations` | 行為。刪除投票及任務後核對清單，預算修改核對金額、權限及版本，刪除結算核對餘額。 |
| PATCH | `/api/v1/polls/{poll_id}` | 200 × 2, 409 × 2 | `test_closing_poll_preserves_existing_items_until_manual_adoption` | 觸達 |
| POST | `/api/v1/polls/{poll_id}/adopt` | 200 × 3, 404 × 1 | `test_closing_poll_preserves_existing_items_until_manual_adoption` | 行為。核對結束投票保留原行程，採用才新增，重開後保留前輪結果。 |
| PUT | `/api/v1/polls/{poll_id}/ballot` | 200 × 16, 409 × 4, 422 × 6 | `test_four_kind_mode_combinations_and_options` | 觸達 |
| POST | `/api/v1/polls/{poll_id}/close` | 200 × 7, 403 × 1 | `test_closing_poll_preserves_existing_items_until_manual_adoption` | 行為。核對結束投票保留原行程，採用才新增，重開後保留前輪結果。 |
| POST | `/api/v1/polls/{poll_id}/options` | 200 × 7 | `test_four_kind_mode_combinations_and_options` | 觸達 |
| POST | `/api/v1/polls/{poll_id}/reopen` | 200 × 5 | `test_closing_poll_preserves_existing_items_until_manual_adoption` | 行為。核對結束投票保留原行程，採用才新增，重開後保留前輪結果。 |
| GET | `/api/v1/trips` | 200 × 1 | `test_core_trip_fields_status_retention` | 觸達 |
| POST | `/api/v1/trips` | 201 × 85, 403 × 1, 409 × 1 | `test_trip_versions_archives_and_idempotency` | 觸達 |
| DELETE | `/api/v1/trips/{trip_id}` | 200 × 3 | `test_core_trip_fields_status_retention` | 行為。核對回收 29 日可還原、31 日不可還原及清單可見性。 |
| GET | `/api/v1/trips/{trip_id}` | 200 × 11, 401 × 2, 403 × 3, 404 × 1 | `test_core_trip_fields_status_retention` | 觸達 |
| PATCH | `/api/v1/trips/{trip_id}` | 200 × 18, 403 × 2, 409 × 2, 422 × 1 | `test_core_trip_fields_status_retention` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/archive` | 200 × 2 | `test_core_trip_fields_status_retention` | 觸達 |
| GET | `/api/v1/trips/{trip_id}/availability` | 200 × 4, 403 × 1 | `test_single_dates_ranges_overlap_and_active_members` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/availability` | 201 × 10, 409 × 1, 422 × 1 | `test_single_dates_ranges_overlap_and_active_members` | 觸達 |
| DELETE | `/api/v1/trips/{trip_id}/availability/{entry_id}` | 204 × 1, 409 × 1 | `test_single_dates_ranges_overlap_and_active_members` | 觸達 |
| PATCH | `/api/v1/trips/{trip_id}/availability/{entry_id}` | 200 × 1, 403 × 1, 409 × 1 | `test_single_dates_ranges_overlap_and_active_members` | 觸達 |
| GET | `/api/v1/trips/{trip_id}/bookings` | 200 × 14, 403 × 2 | `test_creator_can_update_existing_departed_flight_passenger` | 行為。既有旅客自行退出後，原建立者以原版本更新座位及行李，讀回同筆航班、旅客及新版本。 |
| POST | `/api/v1/trips/{trip_id}/bookings` | 201 × 12, 422 × 3 | `test_creator_can_update_existing_departed_flight_passenger` | 行為。既有旅客自行退出後，原建立者以原版本更新座位及行李，讀回同筆航班、旅客及新版本。 |
| DELETE | `/api/v1/trips/{trip_id}/bookings/{booking_id}` | 204 × 1, 403 × 1, 409 × 1 | `test_booking_delete_visible` | 行為。核對刪除回應為空，建立者及另一成員讀回空清單。 |
| PUT | `/api/v1/trips/{trip_id}/bookings/{booking_id}` | 200 × 4, 403 × 1 | `test_creator_can_update_existing_departed_flight_passenger` | 行為。既有旅客自行退出後，原建立者以原版本更新座位及行李，讀回同筆航班、旅客及新版本。 |
| PUT | `/api/v1/trips/{trip_id}/bookings/{booking_id}/public` | 200 × 2, 403 × 3, 409 × 1, 422 × 4 | `test_owner_maintains_departed_creators_public_booking_only` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/budgets` | 201 × 4, 403 × 1 | `test_budgets_settlements_and_idempotence` | 觸達 |
| DELETE | `/api/v1/trips/{trip_id}/budgets/{budget_id}` | 200 × 1, 409 × 1 | `test_remaining_five_http_operations` | 行為。刪除投票及任務後核對清單，預算修改核對金額、權限及版本，刪除結算核對餘額。 |
| PATCH | `/api/v1/trips/{trip_id}/budgets/{budget_id}` | 200 × 1, 403 × 1 | `test_remaining_five_http_operations` | 行為。刪除投票及任務後核對清單，預算修改核對金額、權限及版本，刪除結算核對餘額。 |
| POST | `/api/v1/trips/{trip_id}/candidates` | 200 × 1, 409 × 1 | `test_candidate_restore_roundtrip` | 行為。成員移除再加入候選景點，核對相同景點 ID 及另一成員的可見狀態。 |
| DELETE | `/api/v1/trips/{trip_id}/candidates/{candidate_id}` | 200 × 3 | `test_candidate_restore_roundtrip` | 行為。成員移除再加入候選景點，核對相同景點 ID 及另一成員的可見狀態。 |
| GET | `/api/v1/trips/{trip_id}/comments` | 200 × 11 | `test_delete_own_comment_preserves_reply` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/comments` | 201 × 23, 403 × 1, 409 × 1, 422 × 5 | `test_five_connected_clients_receive_committed_edits_and_revocation` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/copy` | 201 × 5, 403 × 1, 409 × 2, 422 × 1 | `test_copy_planning_snapshot_to_own_trip_only` | 觸達 |
| GET | `/api/v1/trips/{trip_id}/days` | 200 × 47 | `test_original_place_delete_is_versioned_and_preserves_reference` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/days` | 201 × 4 | `test_core_places_fields_status_author_days` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/expenses` | 201 × 9, 409 × 1, 422 × 4 | `test_budgets_settlements_and_idempotence` | 觸達 |
| DELETE | `/api/v1/trips/{trip_id}/expenses/{expense_id}` | 200 × 1 | `test_manual_fx_and_member_validation` | 觸達 |
| PATCH | `/api/v1/trips/{trip_id}/expenses/{expense_id}` | 200 × 2, 403 × 1, 409 × 1, 422 × 1 | `test_fx_snapshot_precision_and_departed_history` | 觸達 |
| GET | `/api/v1/trips/{trip_id}/files` | 200 × 13, 403 × 2 | `test_bound_targets_and_private_booking` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/files` | 201 × 19, 403 × 1, 413 × 30, 415 × 4, 429 × 1 | `test_bound_targets_and_private_booking` | 觸達 |
| GET | `/api/v1/trips/{trip_id}/files/limits` | 200 × 1 | `test_file_quota_counts_recycle_and_rate_limit` | 行為。核對檔案與旅程配額。 |
| GET | `/api/v1/trips/{trip_id}/finance` | 200 × 18, 403 × 1 | `test_remaining_five_http_operations` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/finance/rates` | 200 × 1 | `test_fx_snapshot_precision_and_departed_history` | 行為。受控匯率服務回應。核對幣別換算與保存的匯率快照。 |
| GET | `/api/v1/trips/{trip_id}/invitations` | 200 × 1 | `test_invitation_retries_preserve_one_working_code` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/invitations` | 201 × 72, 409 × 1, 410 × 1 | `test_repeat_two_periods_with_persistent_files` | 觸達 |
| DELETE | `/api/v1/trips/{trip_id}/invitations/{invite_id}` | 204 × 2 | `test_guest_invite_lifecycle` | 觸達 |
| GET | `/api/v1/trips/{trip_id}/members` | 200 × 6, 401 × 1 | `test_guest_invite_lifecycle` | 觸達 |
| DELETE | `/api/v1/trips/{trip_id}/members/{member_id}` | 204 × 9, 409 × 1 | `test_single_dates_ranges_overlap_and_active_members` | 觸達 |
| GET | `/api/v1/trips/{trip_id}/place-search` | 200 × 1, 503 × 1 | `test_search_normalizes_provider_result` | 行為。合成 Wikipedia 回應。核對篩除無座標結果及保留地點名稱、經緯度。 |
| GET | `/api/v1/trips/{trip_id}/places` | 200 × 18 | `test_core_places_fields_status_author_days` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/places` | 201 × 13 | `test_copy_planning_snapshot_to_own_trip_only` | 觸達 |
| GET | `/api/v1/trips/{trip_id}/planner-history` | 200 × 2 | `test_original_place_delete_is_versioned_and_preserves_reference` | 觸達 |
| GET | `/api/v1/trips/{trip_id}/polls` | 200 × 12, 403 × 1 | `test_secret_ballots_and_review_after_new_option` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/polls` | 201 × 16 | `test_four_kind_mode_combinations_and_options` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/restore` | 200 × 2, 404 × 1 | `test_core_trip_fields_status_retention` | 行為。核對回收 29 日可還原、31 日不可還原及清單可見性。 |
| POST | `/api/v1/trips/{trip_id}/settlements` | 201 × 5, 409 × 1, 422 × 1 | `test_budgets_settlements_and_idempotence` | 觸達 |
| DELETE | `/api/v1/trips/{trip_id}/settlements/{settlement_id}` | 200 × 1 | `test_remaining_five_http_operations` | 行為。刪除投票及任務後核對清單，預算修改核對金額、權限及版本，刪除結算核對餘額。 |
| GET | `/api/v1/trips/{trip_id}/tasks` | 200 × 16 | `test_repeat_two_periods_with_persistent_files` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/tasks` | 201 × 14, 422 × 6 | `test_shared_tasks_and_private_lists` | 觸達 |
| DELETE | `/api/v1/trips/{trip_id}/tasks/{task_id}` | 204 × 1 | `test_remaining_five_http_operations` | 行為。刪除投票及任務後核對清單，預算修改核對金額、權限及版本，刪除結算核對餘額。 |
| PUT | `/api/v1/trips/{trip_id}/tasks/{task_id}` | 200 × 2 | `test_original_place_delete_is_versioned_and_preserves_reference` | 觸達 |
| PUT | `/api/v1/trips/{trip_id}/tasks/{task_id}/progress` | 200 × 14, 403 × 1, 404 × 1, 409 × 7, 422 × 1 | `test_repeat_two_periods_with_persistent_files` | 觸達 |
| POST | `/api/v1/trips/{trip_id}/transfer` | 200 × 4, 403 × 1 | `test_core_trip_original_creator_after_transfer` | 觸達 |

</details>

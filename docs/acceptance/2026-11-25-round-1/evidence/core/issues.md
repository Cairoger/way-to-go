# 核心功能問題與驗證界線

## 中等：持有編輯權的作者無法移除原始景點

- 對應 FR-PLACE-07、FR-PLACE-06。前者明列「原始景點資料」，後者另外規範移除候選關聯。此處分別檢驗。
- 重現方式：以持有編輯權的帳號建立景點，取得該景點的有效 Lease 和版本，要求刪除景點本體。也可在「候選景點」檢查同一筆的移除操作，確認對話框描述移出候選。
- 預期：編輯權持有人可移除原始景點，其他人遭拒；移出候選時保有原行程引用。
- 實際：原始景點 `DELETE /api/v1/places/{id}` 回 405。既有候選移除回成功，候選狀態變更後，讀取景點集合仍能取得相同資料與 ID。排入行程的引用正常保留。
- 根因：`backend/app/planning.py:420` 定義原始景點更新，`backend/app/planning.py:462` 定義刪除候選關聯。`frontend/components/Planner.tsx:817、830` 的景點移除對話框提交候選路徑。系統沒有獨立的原始景點移除操作。
- 建議：決定被排程、任務或費用引用時要採的保留策略，再提供持有人可用的移除操作。如果產品決策是永久保留原始景點，應調整規格與用詞。證據見 `probes.log` 的 `test_core_original_place_removal` 與 `pytest.log` 的 `test_place_retained_after_candidate_removal`。

## 中等：真實 Google 首次登入與既有身分升級仍待外部驗收

- 對應 FR-AUTH-01、FR-AUTH-04。這是展示風險與驗收阻礙。
- 重現方式：在未注入 Google 憑證的隔離部署選 Google 登入，或執行 `test_missing_oidc_settings_and_request_origin`。以合成 Google Token 交換回應執行原庫 OIDC 與合併測試，可驗證站內分支。
- 預期：Google 實際同意後回到本站，取得受保護旅程；若先以 Guest 投票、留言，升級後保有對應資料。
- 實際：缺少受控的 Google OAuth 憑證及供互動授權的測試帳戶。未設定時 API 回 503 `OIDC_NOT_CONFIGURED`；合成回呼的身分輪替、成員、選票及留言資料庫驗證皆通過。
- 位置與建議：`backend/app/auth.py:151`、`:213`、`:240`；使用受控 OAuth 測試專案、已登錄的 HTTPS 回呼和專用帳號，分別驗證首次登入及訪客合併。證據見 `pytest.log` 與 `timeout-merge.log`。現有證據不足以歸因為 Google 串接程式缺陷。

## 低：旅程所有權轉移後，使用者無法查到最初建立者

- 對應 TRIP-OPT-06。驗收假設為旅程可選資料能由有資格的成員讀取。
- 重現方式：以 A 建立旅程，邀請 B，將所有權轉移給 B。以 B 呼叫 `GET /api/v1/trips/{id}`。
- 預期：建立者 A、目前 Owner B 及建立時間可以區分。實際：時間與 B 的 `owner_id` 存在，使用者可讀的回應缺少最初建立者。查測試資料庫的 `audit_logs` 確認仍留有 A 的建立紀錄。
- 根因：`backend/app/models.py:86` 的旅程關聯為當任 Owner；`backend/app/trips.py:99` 的旅程回應輸出 `owner_id` 與建立時間；`backend/app/trips.py:307` 轉移時更新該欄。
- 建議：依建立事件提供穩定的建立者資訊，或保存獨立欄位並處理既有資料。若需求僅要求後台稽核，產品方可依實際用途回覆此項。證據見 `probes.log` 的 `test_core_trip_original_creator_after_transfer`。

## 低：五連線既有測試的收尾偶發失敗

- 對應 §9 M4/M5 的測試可重現性。全輪 25 個選定案例中 24 通過，此例第一次在離開 `ExitStack` 時拋出 `concurrent.futures.CancelledError`。不改程式、不改預期，另用全新 SQLite 單獨重跑即通過。
- 重現方式：用下列「既有測試」完整範圍執行，再單獨執行 `test_core.py::test_five_connected_clients_receive_committed_edits_and_revocation`。無法保證每次皆重現。
- 預期：五方收到已提交變更、權限撤銷完成，所有 socket 正常收尾。實際：首輪錯誤出在 context manager 收尾，沒有指出寫入或收件斷言失敗。真 Chrome 雙客戶端實測行程新增、編輯、刪除及斷線重連也成功。
- 可能原因：Starlette TestClient 的背景 coroutine／socket 關閉競態；尚未證實。位置：`backend/tests/test_core.py:209`、`backend/app/realtime.py:67`。建議記錄 close code 與背景任務退出順序，在不同資料庫和網路 WebSocket 路徑重複驗證。證據見 `pytest.log`、`ws-retry.log`、`browser.log`。

## 測試範圍與重跑

執行位置為專案根目錄。使用既有 `.venv`、`frontend/node_modules`。本次 SQLite fixture 依每項測試建立全新檔案，未使用工作區原有 DB 或正式服務；Chrome 主測試使用兩個全新 Context。原始 SQLite 檔案與合成登入資料不在交付證據目錄。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
$env:TEST_DATABASE_URL=''
& .venv/Scripts/python.exe -m pytest -p no:cacheprovider -vv backend/tests/test_core.py backend/tests/test_guest_merge.py backend/tests/test_trip_copy.py backend/tests/test_planning.py backend/tests/test_planning_extensions.py backend/tests/test_local_login.py
$env:PYTHONPATH=(Resolve-Path backend).Path+';'+(Resolve-Path backend/tests).Path
& .venv/Scripts/python.exe -m pytest -p no:cacheprovider -p conftest -v -s --tb=line acceptance-20261125/evidence/core/test_acceptance_core.py
```

`test_core_live_wikipedia` 需要可連線至專案預設 Wikipedia 供應商；本次沙箱內為 503，允許單次對外連線後實測 200。程式內的短暫斷路測試使用測試代理控制一個分頁的 WebSocket。重跑前在獨立部署設定 `WTG_CORE_ORIGIN`、`WTG_UI_CONFIG`（指向含 username/password 的合成資料檔），必要時設定 `CHROME_EXECUTABLE`。以 Node 執行 `browser.cjs` 和 `browser-lifecycle.cjs`。前者操作標題建立、邀請、同步、鎖、拖曳、重連及 Maps 解析，後者觀察跨時區、封存與復原實際畫面。首次補測服務出現逾時；於同一隔離 DB 重啟 API 後補測完成；逾時本身沒有足夠證據可歸因。


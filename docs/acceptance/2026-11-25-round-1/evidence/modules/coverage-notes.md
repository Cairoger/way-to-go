# 第 3 章交叉稽核

以附件 `C:\Users\a0928\Downloads\spec.md` 的粗體 FR 編號逐項比對 core 與 modules 兩份矩陣。109 個原始 FR 均出現一次，缺漏及重複均為 0。合計有 123 列，額外 14 列拆出原需求下的可選欄位、段末條款及業務規則。其中投票公平性、選項變更通知、金額精確度、匯率與時間快照、尾差分配各有獨立列。

| 複合要求 | 各子條件與實測證據 |
|---|---|
| 旅程建立、狀態、原建立者及複製 | 標題必要、各選填欄位、完成後可改及封存／回收分開。建立時間留存，所有權轉移後無法由旅程回應查原建立者，見 `../core/probes.log` 的 `test_core_trip_original_creator_after_transfer`。複製行程與共用安排有測試，未建置的私人文件無從證明複製排除。 |
| 景點與時間 | 逐欄驗證資料、六種活動類型、四種時間配置，見 `../core/probes.log` 的 `test_core_places_fields_status_author_days`、`test_core_time_options_types_and_order`。移除候選與刪除原始景點分別記錄。正常夏季換算通過，但新增 DST 跳時案例已實際失敗，見 `cross-checks.txt`。 |
| 截止、零票、平手、重開 | 不設截止、推進時鐘仍開放、到期拒絕、零票可關、UI 顯示「無結果」分別取自 `probes.txt`、`pytest.txt`、`module-ui.txt`。平手重投保留舊結果，已投票改規則被拒。補測證明關閉沒有更動旅伴既有活動、手動採用只增加新列、重開後才可改方式，見 `cross-checks.txt`。 |
| 費用及分帳 | 自訂、比例、平均，三類預算、預估／實際、超額仍能儲存及三種結清狀態均另有斷言。另單筆測「兩人付款、僅一人分攤」。匯率供應商實查並與變動歷史、幣別精度分開，見 `probes.txt`、`pytest.txt`、`providers-network.txt`、`../browser/chrome-playwright.txt` #3。 |
| 交通住宿與私人文件 | 完整欄位、異乘客多段航班、兩筆住宿、行程關聯、手動改網址及導航各有實測。FR-BOOK-05 的代號授權通過，但私人文件沒有可上傳的物件，整列受阻。FR-FILE-02 的檔案入口回 404，後續預覽、授權、回收及超額阻擋不得推算為已測。 |
| 即時多人與匯出 | 兩人實際同步成功。五人 TestClient 建立事件通過，五個真實 Chrome 的留言編輯在 SQLite 和 Compose/PostgreSQL 皆逾時。FR-COMMENT-03 已改 FAIL。PDF 檔頭、日期、兩種詳略及不輸出私密欄位分別有真 PDF 和欄位斷言。 |
| 地圖與時間預報 | 正常載入 OSM 出現 2 張 HTTP 200 圖磚及一個標記，見 `map-network.txt`、`live-map-online.png`。另在圖磚中斷時驗三種標記、虛線、外連與文字地址。天氣包含真實供應商取數、受控 API 測試與 UI 回應重播，三者證據來源均已標明。 |

## 展示資料與實作範圍

FR-PDF-02 的合成欄位測試傳入 `item.reservation`、`item.notes`、`place.notes` 及 `place.cost`。另以 API 將真實訂位及分攤記錄存入同一趟隔離旅程後讀回，列印詳細與簡表兩份實體 PDF 並以 pypdf 獨立抽取文字。兩者均留下公開活動，均排除訂位代號、費用名稱、分攤對象、125.79 總額及 91.23、34.56 明細，見 `../browser/pdf-private.json` 與 `../browser/pdf-private-text.json`。附件服務未提供，無法建立具真實權限的私人文件；合成的私人備註無法替代該子條件。因此完整的三類資料驗收列為 BLOCKED。

ROLE-12 另外以兩個新 SQLite 個案實測，Owner、Member 均能刪除自己的主留言。兩個身分重讀均得到已刪除標記、空內容、原作者及完整回覆。指令為 `.venv/Scripts/python.exe acceptance-20261125/evidence/modules/test_own_comments.py`，執行結果及臨時資料庫清理記錄見 `own-comments.txt`。

`frontend/lib/samples.ts:37` 定義三趟內建手札，包含固定旅伴、日期、站點，`place_count` 在第 33 行依天數計算。未登入首頁或「示範旅程」使用這組資料，即使無旅行資料可呈現，也可出現精選示範卡。來源切換與標籤位於 `frontend/components/Workspace.tsx:250`、`frontend/components/Workspace.tsx:474`。示範詳情會顯示「唯讀示範」並跳過 API 和 WebSocket，見 `frontend/components/TripDetail.tsx:93`、`frontend/components/TripDetail.tsx:253`。這些固定數字及頁面僅支持驗收示範瀏覽。實際旅程、訂位、投票、兩人同步、檔案缺口與五人失敗均另用真實後端及隔離測資核對。

日期／投票輸入及部分 PDF 的原 Playwright 案例利用 route 攔截，見 `frontend/tests/coordination.spec.ts:58`、`frontend/tests/planner-print.spec.ts:49`。UI 對替身資料的成功不證明後端。財務與行前的 live 案例、補充 `module_ui.cjs`、真 PDF 及 API 測試補足這個缺口。Google OIDC 模擬交換、推播服務商替身未列為真實供應商授權或投遞成功。

本模組獨立建立的暫存資料已清除，包含 4 個 pytest 測試目錄及 26 個合成 SQLite 檔案，見 `cleanup.txt`。先前較早的 per-test 目錄已由 pytest 的保留機制清理。瀏覽器測試共用的隔離工作區及資料庫交由啟動服務的測試程序統一收尾。保留的截圖、HTTP 摘要、斷言與測試程式可重查。

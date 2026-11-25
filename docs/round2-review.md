# 第二輪修正與複驗

此次修正以 `cada651` 的 436 項驗收矩陣為起點。原報告的 14 項失敗來自暱稱覆寫（5 項）、航班提示（1 項）及原始資料表契約（8 項）。本頁記錄各項實際複驗的範圍。

| 項目 | 修正與實測 |
| --- | --- |
| R01 暱稱覆寫 | 兩個 Chrome 分頁同讀版本 1。第一頁將暱稱存為甲，取得 200／版本 2；第二頁送出乙時取得 409，自己的輸入仍在。帳戶及另一位旅伴此時讀到甲。第二頁重讀後可保存乙，取得 200／版本 3，重登後仍是乙。API 亦測過兩個同時提交的請求。SQLite、PostgreSQL 既有帳戶從 0009 升至 0010 後保有原暱稱並取得初始版本 1。[雙分頁與旅伴](../frontend/tests/review-acceptance.spec.ts) · [交易與回歸](../backend/tests/test_review_account_invitations.py) |
| R02 展示版 | 從 GitHub 全新下載候選版，依鎖檔獨立安裝前端套件，空庫升至 0010，得到 42 表、93 個 HTTP 操作。日期、分帳、任務、預訂、通知、天氣、歷史及附件的八個 GET 均回 200，複製旅程與建立評分投票均回 201。Windows 的完整格式檢查及正式 Chrome 的四個 UI 案例均通過，含雙人邀請、留言及跨日同步。[實測提交](https://github.com/Cairoger/way-to-go/tree/87e56359bb2d56fe237c7ee1844536337c28fa4c) · [啟動方式](../README.md#在本機啟動) |
| R03 Google 登入 | 本機缺少已註冊的 OAuth 測試設定。以測試提供者回應驗證首次進站、建立旅程、訪客升級、Session 輪替與資料合併。Google 真人同意及回呼仍待驗。[首次登入](../backend/tests/test_core.py) · [升級與合併](../backend/tests/test_guest_merge.py) |
| R04 跨瀏覽器 | 下表的六個不同案例在 Windows 上用 WebKit 27.2、Firefox 159、Chromium 各跑一次，每個引擎 6/6 通過。macOS 15.8.2 上的正式 Safari 27.2 另已通過登入重載、建立任務、儲存日期、投票，及關閉 HTTP 服務與舊頁後從新分頁離線讀取活動與地址。[正式 Safari 執行紀錄](https://github.com/Cairoger/way-to-go/actions/runs/45650167706/job/139332199261) · [測試程式](../backend/check_safari.py) |
| R05 背景推播 | Windows Chrome 158、Edge 158 分別在 569 ms、2,077 ms 觀測到與站內 ID 相符的背景通知；收件時已關閉所有站內分頁。服務工作執行緒的點擊處理可定位原留言及標為已讀。原生橫幅的實際點擊仍需一則 Windows 能辨識並操作的測試通知。[裝置測試](../frontend/tests/live-push.spec.ts) |
| R06 航班提示 | 地圖、航班清單及新增航班表單均顯示「付費功能開發中」。航班入口也說明可手動輸入，Chrome 實際新增、儲存兩段航班，旅伴可重讀航班號及參與航段。[航班回歸](../frontend/tests/live-preparations.spec.ts) · [地圖與導航](../frontend/tests/offline-planner.spec.ts) |
| R07 資料契約 | 沿用已核定的八項實體儲存結構，將名稱、實際關聯與讀寫方式列入 §7 v1.1。對原始 v1.0 實體名稱執行的檢查仍有八項差異。[§7 v1.1 對照與測試](data-model.md) |

### R04 的七個失敗案例

| 原失敗項目 | 原因與重跑方式 |
| --- | --- |
| WebKit 日期套用 | Service Worker 接手後，日期 GET、POST 繞過原本的分頁 API 替身。此表單測試隔離 Service Worker，仍驗證標記與套用日期。[測試](../frontend/tests/coordination.spec.ts) |
| WebKit 評分、排序與提及 | 投票讀取也繞過分頁替身，畫面取得不同的測試資料。同樣隔離 Service Worker，保留送出選票、排序及留言斷言。[測試](../frontend/tests/coordination.spec.ts) |
| WebKit 儲存離線旅程及登出 | 儲存時成員、景點及每日行程的讀取抵達另一個後端。用獨立 HTTP 測試站供應一致的資料，關站、關頁、重開，再復線登出並核對清除。[測試](../frontend/tests/offline-planner.spec.ts) |
| WebKit 帳號切換 | 身分與快照來自兩種攔截方式，分頁重開後不一致。HTTP 測試站跨頁保存測試身分，驗證換帳後無法讀到舊行程。[測試](../frontend/tests/offline-planner.spec.ts) |
| WebKit 地圖提示及移除 | 候選景點與行程資料繞過替身。由同一個 HTTP 測試站供應資料後，重跑移除原始景點、地圖付費提示及免費導航。[測試](../frontend/tests/offline-planner.spec.ts) |
| Firefox 真實旅程冷啟動 | 原離線模擬仍容許新分頁抵達站台。實際關閉該測試使用的 HTTP 入口，再用新分頁驗證離線唯讀、時間、地址及註記排除。[測試](../frontend/tests/live-offline-planner.spec.ts) |
| Firefox 登出清除 | 有分頁攔截時，模擬離線導航可能先回 `NS_ERROR_OFFLINE`。改為停止並重新啟動測試站，重跑關頁、重開、登出及二次斷線後的資料清除。[測試](../frontend/tests/offline-planner.spec.ts) |

### R08 部署與工具

- **無障礙。** 修正首頁篩選及行程日期的群組名稱、頭像與封面對比，以及關閉對話框後的鍵盤焦點。驗證涵蓋渲染像素、鍵盤操作與可存取性樹，完整的逐項 WCAG 2.2 AA 人工覆核仍待進行。[複驗範圍與量測](accessibility-checks.md)
- **備份。** 2026-11-20 至 11-25 的六份每日備份逐份還原至無網路連接、只讀掛載來源的臨時 PostgreSQL。最早一份有 22 表與 89 個約束，後五份各有 38 表及 169 個約束。六次實際演練都在 11-25 執行。新的獨立服務會驗證後續每日備份，將結果寫入自己的日誌；異地或整台主機故障的復原仍需部署環境驗證。[還原服務](../deploy/restore-drill.sh)
- **HTTPS 與機密。** 現行測試站綁定 loopback HTTP。在 87e5635 交付版本可達的 7 個提交、242 個不同 Git blob 中，比對本機設定的資料庫密碼、登入雜湊、私鑰區塊與已知 GitHub、Google、AWS 識別格式，命中 0 筆。公開網域的憑證鏈、TLS 及部署方其他機密仍需其實際環境及清單。
- **外部服務。** 地圖使用 OSM 出處文字與瀏覽器圖磚快取；離線行程不抓取圖磚。天氣有快取及單一服務程序的分鐘、小時、每日上限，免費 Open-Meteo 端點限非商業用途。搜尋結果保留維基百科來源，匯率可改用手動值。正式部署的用途、跨程序流量與累積用量仍需部署方的實際紀錄。[OSM 圖磚政策](https://operations.osmfoundation.org/policies/tiles/) · [Open-Meteo 使用條款](https://open-meteo.com/en/terms) · [Frankfurter API](https://frankfurter.dev/)
- **Windows 匯出。** Git 對前端文字檔採 LF，避免 Windows 乾淨 checkout 因行尾差異產生大批格式誤報。[Git 設定](../.gitattributes)

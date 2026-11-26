# 瀏覽器驗收與前端建置紀錄

## 環境與重跑

2026-11-25（臺北）。測試版本包括工作區未提交的功能。以 Windows、Node 24.22.3、Python 3.12.14、Next.js 16.4.6 與 Playwright 1.65.1 執行。瀏覽器含系統 Chrome 158.0.8127.36、Edge 158.0.4370.33、攜帶式官方 Firefox 161.0，另有 Playwright 的 Firefox 159.0 與 Windows WebKit 27.2。Safari 正式版和 iPhone、Android 實機仍待驗證。完成後已移除隔離 SQLite、合成帳密、執行中的測試服務、瀏覽器與前端暫存，18731/18732 均無監聽。見 cleanup.txt。

複製前端原始碼、設定及測試至專用資料夾，沿用現有套件。空白 SQLite 經 Alembic 升至 0007。FastAPI 與 Next 正式建置僅監聽 127.0.0.1 的 18732 與 18731 埠。所有帳號、邀請、訂位及費用均為此次產生的合成資料。

1. 在專案根目錄執行「.venv/Scripts/python.exe acceptance-20261125/evidence/browser/run_ui.py」。確認「.local/audit-ui-20261125/ready.txt」出現後，可執行其他自訂案例。該環境只存放本次的合成帳密與資料庫。
2. 執行「node acceptance-20261125/evidence/browser/experience.cjs」產生地圖、畫面、PDF、無障礙及離線結果。使用真實 API。地圖失敗情境攔截外部圖磚，檢查外連時記錄使用者實點後的 Google Maps 目的 URL。
3. 執行「node acceptance-20261125/evidence/browser/collaboration.cjs」。預設五個不同帳號及 Chrome 瀏覽環境。可設定 WTG_AUDIT_CLIENTS=2、WTG_AUDIT_SETUP（origin、username、password 的臨時 JSON）、WTG_AUDIT_RESULT、WTG_AUDIT_STACK。完成編輯量測後觀察六分鐘。
4. 若需其他引擎，下載 Playwright 對應的 Firefox/WebKit 到專用的 pw-browsers 目錄後執行「cross-engine.ps1 -Engine firefox」或「cross-engine.ps1 -Engine webkit」。各套 10 個既有案例。既有 PDF 測試使用僅 Chromium 支援的 page.pdf()，已在 Chrome 與 Edge 各執行一次。
5. 在該暫存資料夾建立名為 stop 的空檔可讓服務監管程式停止。以下證據不含有效憑證。

## 原始輸出與判讀

| 證據 | 驗收條件 | 實測結果與範圍 |
|---|---|---|
| unit.txt、typegen.txt、typecheck.txt、lint.txt、format.txt、build.txt、migrate.txt | 前端工具正常退出、單元測試通過，空資料庫可遷移 | Vitest 2 檔共 5/5；型別、ESLint、Prettier、正式建置及遷移 exit 0。建置提示 standalone 未包含隔離資料夾外的依賴路徑，本次以該正式 build 啟動 Next + FastAPI。在 Docker 內打包的驗收見主報告。 |
| chrome-playwright.txt、edge-playwright.txt | 桌機與手機流程、兩人互相更新，以及財務和訂位回讀 | 各 11/11。6 個案例攔截部分或全部 API（日期協調、評分排序含提及、三個本機登入案例、列印）。2 個操作內建首頁或手機表單。3 個連真實服務與獨立身分，包含邀請、留言、跨日移動、待辦、訂位乘客、提及與重載後的已讀狀態、外幣分攤及兩次還款。各輸出均列出 frontend/tests 的來源檔、行號與測試名稱。 |
| firefox-playwright.txt、firefox-smoke.txt、engine-install-retry.txt | Gecko 引擎可完成相同工作流程 | 官方測試版 Firefox 159.0，10/10 通過。清單頁煙霧測試另外通過。最初受限環境內兩次 browserType.launch 逾時；獲准以獨立設定檔執行後成功。 |
| ../core/firefox-release.log、../core/firefox-release.png | Firefox 正式版可用於展示 | 以官方 Firefox 161.0 和 Marionette 在相同隔離站台完成真實登入及重載、建立旅程、新增活動並重載，以及邀請連結與 QR 圖像。 |
| webkit-playwright.txt、webkit-overlap.txt、webkit-focus.json | 不同引擎的 UI 行為 | Windows WebKit 27.2 在重啟測試服務後獨立重跑 8/10 通過。真實雙人分帳與留言移動通過。live-preparations 超過 150 秒、mockLocalAuth 案例重載後未看見「我的旅程」。較早與其他測試重疊時為 7/10。聚焦測試另以真實 API 證實 WebKit 的本機帳號登入可在重載後保留，收件者在 API 有一則未讀、通知按鈕顯示一則未讀。兩個不通過的自動化案例不能直接推論 Apple Safari 相同行為。 |
| experience.json 的 form、rwd；desktop-home.png、live-mobile.png | 桌機與手機寬度、繁中驗證 | 320、390、768、1280 CSS px 的每日行程頁，其 document scrollWidth 各等於視窗寬。另在 390 px 操作選單與登入。zh-TW 環境中，空帳號提示「請填寫這個欄位。」、錯誤帳密提示「帳號或密碼錯誤。」。 |
| sections.json、sections.cjs | 桌機與手機均能進入所有旅程模組 | 1280 與 390 px 各實點 10 個頁籤，20/20 次均能讀到該區標題且無整頁水平溢出。對每次畫面再跑 axe A/AA 規則，20/20 均出現文字對比不足，桌面每次 5–6 個節點，手機每次 3 個。共用側欄與頁首會重複計入，不宜加總成相異缺陷數。 |
| experience.json 的 map、weather；live-map-fallback.png | FR-MAP-01～03、FR-WEATHER-02、AC-017、BR-014 | 3 類色標「景」「餐」「住」、OSM 出處；Day 1 的兩點有 dash 6 8 的 SVG 線段並明示實際道路請用導航。實點搜尋／導航，在另頁開啟含正確經緯度的兩個 Maps URLs。30 次圖磚請求失敗仍顯示 3 地址，可切回原行程；遠期日期顯示「尚無可用天氣預報」。正常線上圖磚另見 ../modules/map-network.txt。 |
| experience.json 的 pdf；itinerary-brief.pdf、itinerary-details.pdf；unit.txt；planner-print.spec.ts | FR-PDF-01、02，選日期和詳略，排除私人欄位 | 真實 DB 有兩天，取消 Day 2 後各產出 A4 PDF（詳細 31,026 bytes、簡表 24,086 bytes）。兩份檔頭均為 %PDF；詳細有地址與停留時間、簡表無地址，均無第二天與兩個私人備註。單元測試另輸入訂位代號、費用和私人文件描述，確認均未輸出。測試攔截原生列印呼叫，再由同一預覽頁產生 PDF 檔。 |
| pdf-private.json、pdf-private-text.json、pdf-private-details.pdf、pdf-private-brief.pdf | FR-PDF-02 的真實訂位、分帳與私人附件三項子條件 | 在全新 PostgreSQL Compose 建立旅館訂位並關聯要匯出的活動，另建立兩人自訂分帳，以授權 API 確認各欄位已保存。兩種 PDF 的列印 DOM 與 pypdf 6.21.4 獨立解析結果，均包含公開活動代碼、皆未含實際預訂代碼、費用名稱、分攤者暱稱、總額 125.79 或分攤額 91.23、34.56。兩檔各一頁，僅詳細版含公開地址。真實私人文件物件無法建立，授權檔案列表為 404；此子條件 BLOCKED。以 ../system/docker_ui.py pdf、pdf-private.cjs 產出，再以 pdf-private-text.py 核驗，../system/pdf-down.txt 記錄隔離資料卷清理成功。 |
| experience.json 的 offline；frontend/public/sw.js:3、:30 | FR-OFFLINE-01，斷網可重新開啟已讀行程 | FAIL。正式 build 的 Service Worker 已控制頁面，僅快取 7 個圖示與封面。離線開新旅程分頁發生 ERR_INTERNET_DISCONNECTED，畫面找不到行程；恢復網路後可再讀。 |

## 缺陷及影響

### 高：五人留言後跨端編輯逾時

在 SQLite、單一 Uvicorn 與正式 Next.js 下，五個不同帳號各在獨立瀏覽環境開啟同一旅程的討論區。每頁均顯示五人在線，各送一則留言後，以 API 回讀五筆不同 ID。下一次由作者修改其留言，其他四個頁面應在 2 秒內看到變更；第一輪觀察者已報 10 秒逾時。另一個一般登入能力 GET 請求也超過 3 秒。重啟隔離 API 後以同一使用情境再次觀察到。使用正式 Compose 與 PostgreSQL 17.12 重跑，同樣五筆可回讀、第一次編輯等待超過 10 秒。五人案例無足夠成功樣本計算 P95。沒有觀察到這五筆新增資料遺失。

僅 SQLite 那次有服務端堆疊樣本。當時 backend/app/realtime.py:87 在事件迴圈驗證訂閱者，經 identify 和 backend/app/core.py:102 同步等待 SQLAlchemy 連線池。frontend/components/TripDetail.tsx:99、:136 和 frontend/components/Decisions.tsx:811 顯示收到異動後會重新發出多筆讀取。堆疊支持「事件迴圈當時等待連線」，無法單憑此確定所有連線由何者持有，也不能證明 PostgreSQL 是同一阻塞鏈。建議先量測每次連線取用與歸還、將同步資料庫工作移出事件迴圈並檢視重複請求，再以相同五人流程回歸。

證據為 five-clients.json、pool-wait.txt、collaboration-postgres.json 和 collaboration.cjs。兩人同一情境的 20 次編輯至他方 DOM 可見 P95 為 181 ms，40 次一般 GET 旅程 P95 為 14 ms。計時含 Next 代理及 HTTP 回應解析，編輯量測另外包含前端重新讀取和畫面更新；採排序後 ceil(n × 0.95) 的觀測值。逐筆數字、已建立／已關閉連線及取樣時刻見 two-clients.json。

兩頁保持開啟六分鐘，累計觀測 0、2、60、120、180、240、300、360 秒。兩個身分各建立 1 條旅程 WebSocket，期間均維持 1 條，關閉數均為 0，最後兩邊均顯示 2 人在線。這個通過樣本的觀測窗口為六分鐘。

### 中：首頁／行程頁不符 WCAG 2.2 AA

在正式版 Chrome 對旅程總覽和有資料的每日行程頁執行 axe-core 4.14.1 的 WCAG 2.0、2.1、2.2 A/AA 標籤規則。首頁有 5 個對比不足元素、3 張旅程卡的可見文字與 accessible name 不一致。行程頁另有 6 個對比不足元素。共同例子為側欄「工作空間」的字色 #727c71 對 #f2f3ec，實際 3.88:1，此文字尺寸需要 4.5:1。frontend/components/Workspace.tsx:95 的旅程卡以「開啟」加旅程名稱覆寫可存取名稱，按鈕內另含狀態及地點文字；側欄色彩見 frontend/app/globals.css:142。建議調整字色與按鈕的可見／可存取名稱後再以鍵盤、語音與螢幕閱讀器回歸。原始選擇器、HTML、WCAG 標籤與色值均收錄於 experience.json 的 a11y。這兩頁抽樣能判定有缺陷，不能宣告整站 AA 符合。

### 中：離線重開旅程失敗

先連線開啟已有資料的旅程，重新載入確認 Service Worker 接管，再中斷網路、另開原旅程。預期看到已讀的標題及地址，實際為 Chrome 離線錯誤。frontend/public/sw.js:3 的快取白名單只列視覺資產，:30 僅處理白名單路徑。建議提供可由使用者選取的唯讀行程快照，並為授權期限、登出及撤權定義快取處理。重現腳本及原始輸出見 experience.cjs、experience.json。

### 待確認：WebKit 收件匣與登入測例

Windows WebKit 的兩個既有案例在單獨重跑時仍失敗。將流程縮減為真實登入並重載、兩名成員互相提及時，可見真實登入保留，伺服器有一筆未讀通知，收件者的鈴鐺同樣顯示「通知中心，1 則未讀」。點開收件匣後，最新一輪診斷沒有在 70 秒工具期限內完成「看見提及內容」步驟。失敗點落在 frontend/components/NoticeCenter.tsx:151 附近的對話框流程，但目前無法區分 WebKit 自動化驅動、該 Windows 移植版本或產品本身。原始測項另有一項使用攔截回應的登入重載失敗，不能據此推論真實登入 Session 遺失。建議在正式 Safari 的前景分頁複驗同一通知。原始階段、畫面未讀數和可重跑程式見 webkit-focus.json、webkit-focus.cjs。

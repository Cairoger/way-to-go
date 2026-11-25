# 多人旅遊規劃系統
## Product Requirements Document（PRD）& Software Requirements Specification（SRS）

**文件版本：** 1.0  
**建立日期：** 2026-11-19  
**文件狀態：** 正式需求基準初版  
**產品平台：** Responsive Web Application / PWA  
**開發方式：** 多人協作開發  
**部署原則：** Docker、自行部署、零付費外部服務

---

# 1. 產品概述（Product Overview）

## 1.1 產品定位

本系統是一個以多人共同決策與即時協作為核心的旅遊規劃平台，協助旅遊成員從旅程建立、景點蒐集、意見投票到每日行程安排，共同完成旅遊計畫。

產品主要服務 2–5 人的小型旅遊團體，包括朋友、家庭及情侶或伴侶。

2–5 人屬於主要設計與測試規模，而非系統硬性人數上限。

## 1.2 核心價值

1. **共同規劃：** 所有成員能參與景點與每日行程安排。
2. **共同決策：** 透過投票及日期協調解決旅伴意見差異。
3. **即時同步：** 成員不必重新整理網頁即可看見最新變更。
4. **資訊集中：** 統一管理景點、交通、住宿、任務與旅費。
5. **低使用門檻：** 支援免註冊訪客加入。
6. **成本可控：** 不依賴必須付費的外部平台。

## 1.3 成功標準

MVP 的核心成功條件：

- Google 使用者能建立旅程。
- 訪客能透過邀請加入。
- 2–5 位成員能同時共同規劃。
- 成員能提出景點、參與投票並安排每日行程。
- 編輯權限、即時更新及衝突處理正確運作。
- 主要操作流程可在手機與電腦完成。
- 本機可透過 Docker Compose 完整啟動。

---

# 2. 使用者與權限（Users & Permissions）

## 2.1 使用者身分

**Google User**

- 使用 Google 登入。
- 可以建立與參與多個旅程。
- 可管理自己的個人資料與通知偏好。

**Guest User**

- 以暱稱加入旅程。
- 不需要先註冊或登入 Google。
- 可以參與成員允許的操作。
- 不能建立旅程。
- 使用安全 Session 保存身分。
- 之後登入 Google 可合併原有資料。

訪客清除瀏覽器資料或遺失有效 Session 時，可能無法直接恢復身分。系統應明確提示此限制，不提供不安全的暱稱認領機制。

## 2.2 旅程角色

每個旅程只有一位 Owner，其餘為 Member。

| 操作 | Owner | Member |
|---|---|---|
| 建立旅程 | 是 | 否 |
| 修改旅程基本設定 | 是 | 否 |
| 邀請及移除成員 | 是 | 否 |
| 管理邀請期限 | 是 | 否 |
| 轉移所有權 | 是 | 否 |
| 建立景點及行程 | 是 | 是 |
| 編輯自己建立的景點及行程 | 是 | 是 |
| 編輯其他人的景點及行程 | 否 | 否 |
| 移動自己建立的行程 | 是 | 是 |
| 參與及發起投票 | 是 | 是 |
| 新增留言 | 是 | 是 |
| 刪除自己的留言 | 是 | 是 |
| 刪除其他人的留言 | 是 | 否 |
| 封存及刪除旅程 | 是 | 否 |
| 自行退出旅程 | 須先轉移所有權 | 是 |

補充規則：

- 移除成員後，其歷史紀錄保留，原有資料的編輯管理權轉移給 Owner。
- 資料原始建立者與目前可編輯者應分開記錄。
- 所有權限必須由 Backend 驗證，不能只依賴前端隱藏按鈕。
- 任何自動化操作不得繞過上述權限。

---

# 3. 功能需求（Functional Requirements）

需求以 `FR` 編號管理。功能優先級分為 P0（MVP）、P1（第二階段）、P2（第三階段）。

## 3.1 帳號及身分驗證

**FR-AUTH-01 [P0]** 支援 Google OAuth / OpenID Connect 登入。

**FR-AUTH-02 [P0]** 訪客透過有效邀請，輸入暱稱後加入旅程。

**FR-AUTH-03 [P0]** 使用安全 Cookie Session，支援同一瀏覽器恢復登入狀態。

**FR-AUTH-04 [P1]** 訪客登入 Google 後，可將原有身分、旅程、投票與留言合併。

**FR-AUTH-05 [P0]** 訪客不得建立旅程。

**FR-AUTH-06 [P0]** Session 失效、登出或被撤銷時，立即失去受保護資源的存取權限。

## 3.2 旅程管理

**FR-TRIP-01 [P0]** 可建立、讀取、修改、封存與刪除旅程。

**FR-TRIP-02 [P0]** 建立旅程只要求旅程名稱。

其他可選資料包括：

- 多國家及多城市目的地
- 開始及結束日期
- 旅程封面及描述
- 主要幣別
- 旅遊天數
- 建立者及建立時間

**FR-TRIP-03 [P0]** 旅程日期可暫不決定。

**FR-TRIP-04 [P0]** 規劃流程不強制固定順序。

**FR-TRIP-05 [P0]** 旅程狀態包括規劃中、已確認、旅遊中及已完成。

**FR-TRIP-06 [P1]** 封存與旅程狀態分開管理，封存只影響列表顯示，不直接刪除資料。

**FR-TRIP-07 [P1]** 刪除旅程先移入回收區，預設保留 30 日，期間 Owner 可復原。

**FR-TRIP-08 [P1]** 可複製旅程的景點、每日行程與相關安排，不複製原成員、投票、分帳及私人文件。

已完成的旅程仍允許編輯。

## 3.3 成員邀請

**FR-INV-01 [P0]** 支援邀請連結及邀請碼。

**FR-INV-02 [P0]** QR Code 以相同邀請連結生成。

**FR-INV-03 [P1]** 支援 Email 邀請。

**FR-INV-04 [P0]** 邀請具有有效期限，預設 7 天。

**FR-INV-05 [P0]** Owner 可以撤銷邀請、重新產生連結及移除成員。

**FR-INV-06 [P0]** 取得有效邀請的人可直接加入，不需要 Owner 審核。

**FR-INV-07 [P0]** 同一使用者重複接受邀請時，不建立重複成員紀錄。

邀請逾期或撤銷後，已正式加入的成員仍保有原本旅程權限。

## 3.4 景點管理

**FR-PLACE-01 [P0]** 支援手動建立景點及地點搜尋。

**FR-PLACE-02 [P1]** 支援解析可識別的 Google Maps 地點連結，無法取得資料時允許手動補充。

**FR-PLACE-03 [P0]** 景點欄位包括：

- 名稱、地址、經緯度
- 國家及城市
- 分類、標籤及狀態
- 停留時間及預估費用
- 營業時間、官方網站
- 照片與備註
- 建立者及修改紀錄

外部資料無法免費合法取得時，可手動輸入對應欄位。

**FR-PLACE-04 [P0]** 景點狀態包括必去、想去、備選及不考慮。

**FR-PLACE-05 [P0]** 相同景點可出現在多個日期。

**FR-PLACE-06 [P0]** 從候選清單移除景點，不影響已加入每日行程的引用。

**FR-PLACE-07 [P0]** 僅目前擁有編輯權的成員可以修改或移除原始景點資料。

## 3.5 每日行程管理

**FR-PLAN-01 [P0]** 支援 Day 1、Day 2 等沒有實際日期的行程規劃。

**FR-PLAN-02 [P0]** 確認旅遊日期後，可自動對應實際日期。

**FR-PLAN-03 [P0]** 每日行程可加入景點、餐飲、交通、住宿、航班及自訂活動。

**FR-PLAN-04 [P0]** 可拖曳自己建立的行程項目，包括跨日期移動。

**FR-PLAN-05 [P0]** 其他項目可因拖曳被動改變顯示順序，但不得被視為遭到未授權編輯。

**FR-PLAN-06 [P0]** 支援無時間、開始時間、開始及結束時間、開始時間加停留時間等安排方式。

**FR-PLAN-07 [P0]** 時間重疊時顯示警告，但允許儲存。

**FR-PLAN-08 [P1]** 排序調整後重新計算建議時間，不覆寫其他成員手動設定的時間。

**FR-PLAN-09 [P1]** 支援行程所在目的地的 IANA 時區及跨時區顯示。

## 3.6 即時多人協作

**FR-COLLAB-01 [P0]** 新增、修改及刪除行程後，其他在線成員立即收到更新。

**FR-COLLAB-02 [P0]** 顯示在線成員與正在編輯的項目。

**FR-COLLAB-03 [P0]** 同一項目採取編輯鎖定，避免多人同時修改。

**FR-COLLAB-04 [P0]** 編輯鎖定採有限期限的 Lease，預設 90 秒，持續編輯時可續期。

**FR-COLLAB-05 [P0]** 鎖定逾時、離線或離開編輯模式時，允許釋放。

**FR-COLLAB-06 [P0]** 每次修改都須檢查資料版本，避免過期請求覆蓋最新資料。

**FR-COLLAB-07 [P0]** 即時連線中斷後，恢復連線時重新取得最新資料。

## 3.7 投票系統

**FR-VOTE-01 [P0]** 支援景點與日期的單選、多選投票。

**FR-VOTE-02 [P1]** 擴充評分投票及排序投票。

**FR-VOTE-03 [P0]** 所有旅程成員都能建立投票及補充候選選項。

**FR-VOTE-04 [P0]** 發起者可以修改、結束、刪除投票。

**FR-VOTE-05 [P0]** 截止時間為選填；未設定時可保持開放。

**FR-VOTE-06 [P0]** 投票期間可以修改自己的選票。

**FR-VOTE-07 [P0]** 投票結束前不公開即時得票統計或其他人的選擇；結束後公開結果及每位成員的投票。

**FR-VOTE-08 [P0]** 不設最低參與人數，零票結束顯示「無結果」。

**FR-VOTE-09 [P0]** 平票時透過新一輪投票重新決定。

**FR-VOTE-10 [P0]** 結果不自動修改行程；任一有權新增行程的 Member 可手動採用。

**FR-VOTE-11 [P1]** 重新開啟投票時建立新的投票輪次，保留歷史結果及既有行程。

投票開始且已有選票後，會影響公平性的核心規則修改需建立新輪次。新增選項時需明確通知已投票成員重新檢視選票。

## 3.8 旅遊日期協調

**FR-DATE-01 [P1]** 支援單日及日期區間選擇。

**FR-DATE-02 [P1]** 成員可以標記可以、可能、不行。

**FR-DATE-03 [P1]** 統計共同可用日期並推薦重疊度較高的區間。

**FR-DATE-04 [P1]** 日期協調與正式日期投票分開。

**FR-DATE-05 [P1]** 日期確認後可套用至每日行程；再次修改時保留原有行程，必要的個別調整由使用者手動完成。

## 3.9 留言與討論

**FR-COMMENT-01 [P0]** 每個旅程具有共用討論區。

**FR-COMMENT-02 [P0]** 支援留言、回覆、編輯及刪除。

**FR-COMMENT-03 [P0]** 留言即時同步。

**FR-COMMENT-04 [P1]** 支援 @成員 提及通知。

**FR-COMMENT-05 [P2]** 支援留言圖片附件。

**FR-COMMENT-06 [P0]** Member 只能修改或刪除自己的留言；Owner 可以刪除任一留言。

## 3.10 任務管理

**FR-TASK-01 [P1]** 支援共用待辦與個人行前清單。

**FR-TASK-02 [P1]** 任務包含標題、描述、負責人、截止日期、優先程度及狀態。

**FR-TASK-03 [P1]** 一個任務可指定多個負責人。

**FR-TASK-04 [P1]** 只有負責人可以完成自己的任務。

**FR-TASK-05 [P1]** 任務可以關聯景點或行程項目。

**FR-TASK-06 [P2]** 支援重複任務與附件。

## 3.11 預算及多人分帳

**FR-FIN-01 [P1]** 支援旅程、個人及類別預算。

**FR-FIN-02 [P1]** 區分預估支出與實際支出。

**FR-FIN-03 [P1]** 支援多幣別及自動取得參考匯率。

**FR-FIN-04 [P1]** 超出預算時顯示警告，不阻止記帳。

**FR-FIN-05 [P1]** 分帳支援平均、自訂金額及比例分配。

**FR-FIN-06 [P1]** 一筆費用可以有多個付款人，且只由部分成員分攤。

**FR-FIN-07 [P1]** 提供淨額結算及轉帳次數較少的結算建議。

**FR-FIN-08 [P1]** 記錄未結清、部分結清及已結清狀態。

**FR-FIN-09 [P1]** 成員退出後，保留歷史財務資料。

**FR-FIN-10 [P1]** 不直接處理金流，不整合銀行或第三方支付。

所有金額採精確十進位計算，匯率換算須保存使用匯率及時間，並依幣別精度處理尾差。

## 3.12 交通與住宿資訊

**FR-BOOK-01 [P1]** 支援多段航班及不同乘客。

**FR-BOOK-02 [P1]** 記錄航空公司、航班編號、航廈、時間、座位、行李、價格與訂位資訊。

**FR-BOOK-03 [P1]** 支援多間住宿、入住及退房日期、房型、住客、費用與預訂狀態。

**FR-BOOK-04 [P1]** 機票與住宿資訊可關聯每日行程。

**FR-BOOK-05 [P1]** 訂位代號及私人文件僅限授權成員查看。

**FR-BOOK-06 [P1]** 允許手動更新，並提供外部航班資訊或導航連結，不承諾免費即時航班追蹤。

## 3.13 文件與附件

**FR-FILE-01 [P2]** 支援常見圖片、PDF 與 Office 文件。

**FR-FILE-02 [P2]** 支援分類、預覽、下載與批次上傳。

**FR-FILE-03 [P2]** 檔案可關聯旅程、行程、任務或費用。

**FR-FILE-04 [P2]** Member 管理自己的檔案；涉及私人文件時需檢查相關成員存取權。

**FR-FILE-05 [P2]** 刪除附件先進入回收狀態。

**FR-FILE-06 [P2]** 預設每個檔案上限 10 MB，每旅程附件總量 500 MB，採可設定配額，部署時依實際免費儲存空間調整。

## 3.14 地圖、天氣、提醒與匯出

**FR-MAP-01 [P0]** 顯示景點地圖與不同類型的標記。

**FR-MAP-02 [P0]** 提供 Google Maps 搜尋及導航外部連結。

**FR-MAP-03 [P1]** 支援依行程順序顯示景點間連線，但不得將直線距離標示為實際道路路程。

**FR-MAP-04 [P2]** 實際交通路線、預估交通時間及路線最佳化，須有符合免費條件且可穩定使用的方案才能啟用。

**FR-WEATHER-01 [P1]** 顯示每日天氣、氣溫及降雨機率。

**FR-WEATHER-02 [P1]** 尚無預報時顯示「尚無可用天氣預報」。

**FR-NOTIFY-01 [P1]** 提供網站內通知紀錄、已讀狀態及通知偏好。

**FR-NOTIFY-02 [P1]** 支援符合瀏覽器條件的 Web Push。

**FR-NOTIFY-03 [P1]** Email 發送僅使用符合零付費條件的服務，否則改用手動郵件邀請或站內通知。

**FR-PDF-01 [P1]** 提供每日行程 PDF 匯出，可選擇日期與詳細程度。

**FR-PDF-02 [P1]** PDF 預設排除訂位代號、私人文件及分帳細節。

**FR-OFFLINE-01 [P2]** PWA 可離線查看已儲存的行程文字、地址及基本資料。

**FR-OFFLINE-02 [P2]** 不提供離線編輯與離線多人資料合併。

**FR-HISTORY-01 [P1]** 記錄重要資料異動及原始操作者。

**FR-HISTORY-02 [P1]** 允許有權限的成員復原單筆資料，不提供整趟旅程資料庫時間回溯。

---

# 4. 關鍵業務規則（Business Rules）

| 編號 | 規則 |
|---|---|
| BR-001 | 每個旅程恰好有一位有效 Owner |
| BR-002 | Owner 退出前必須先轉移所有權 |
| BR-003 | 成員移除後立即撤銷其旅程存取權 |
| BR-004 | 移除候選景點不連帶刪除已排程項目 |
| BR-005 | 每一行程項目均需保留原作者與目前編輯權持有者 |
| BR-006 | 拖曳只允許移動自己具有編輯權的項目 |
| BR-007 | 編輯鎖定不取代後端授權及版本驗證 |
| BR-008 | 投票結果採用不能直接覆寫其他成員擁有的行程 |
| BR-009 | 投票重新開啟必須保留歷史輪次 |
| BR-010 | 不可因自動時間計算覆寫他人的手動時間 |
| BR-011 | 財務結算不代表已執行實際付款 |
| BR-012 | 封存、回收區與完成狀態必須分開管理 |
| BR-013 | 敏感附件依檔案授權控制，不因屬於旅程成員就可讀取所有私人文件 |
| BR-014 | 外部免費服務失效不能阻止使用者存取已保存的核心旅程資料 |

---

# 5. 非功能需求（Non-Functional Requirements）

## 5.1 效能

以下是 MVP 在 2–5 人測試場景下的驗收目標，不代表正式 SLA。

- 一般 API 請求 P95 回應時間低於 500 ms，不計外部 API 等待。
- 正常測試網路下，即時編輯事件的跨客戶端可見延遲 P95 低於 2 秒。
- 長時間開啟旅程頁面不得產生持續增加的重複 WebSocket 連線。
- 外部服務逾時應提供重試或降級，不得造成核心頁面無限載入。

## 5.2 安全性

- 公開部署使用 HTTPS。
- Session Cookie 使用 HttpOnly、Secure 及適當的 SameSite 設定。
- 登入及身分升級時更新 Session。
- OAuth 憑證與其他 Secrets 不得提交至 Git。
- 每次 API 及 WebSocket 操作均驗證身分與旅程權限。
- 對邀請、登入、搜尋與上傳進行 Rate Limiting。
- 預防 XSS、CSRF、SQL Injection 及未授權物件存取。
- 附件下載應經過權限驗證，並禁止任意檔案路徑存取。
- 紀錄敏感操作，但不在日誌保存 Session Token 或完整訂位代號。

## 5.3 可用性與相容性

- 支援桌面及手機 RWD。
- 優先支援主流 Chrome、Safari、Firefox、Edge 的近期正式版本。
- 主要操作需有清楚的載入、成功、失敗與衝突狀態。
- 表單驗證提供可理解的繁體中文訊息。
- 主要互動遵循 WCAG 2.2 AA 的適用要求。

## 5.4 備份與復原

- PostgreSQL 使用持久化 Volume。
- 正式部署環境預設每日資料庫備份、保留 7 天，容量不足時發出警示。
- 備份應存放在與正式資料分開的位置，並定期測試還原。
- 附件備份與資料庫備份須保持一致。
- 沒有額外備份裝置或儲存位置時，不宣稱系統具備完整災難復原能力。

## 5.5 零付費限制

- 不使用需綁定信用卡才能啟用的 API。
- 不依賴可自動超額扣款的服務。
- 不以短期試用金替代長期免費方案。
- 免費方案的流量、資料使用及授權限制必須遵守。
- 需要付費才能實作的功能不得暗中啟用，介面顯示「付費功能開發中」。
- 免費服務異常時，優先提供手動操作或外部連結。

---

# 6. 系統技術架構（System Architecture）

## 6.1 技術選型

| Layer | Technology |
|---|---|
| Frontend | Next.js + React + TypeScript |
| UI Components | Tailwind CSS + shadcn/ui |
| Backend | Python + FastAPI |
| ORM | SQLAlchemy |
| Migration | Alembic |
| Database | PostgreSQL |
| Authentication | Google OIDC + Server-side Session |
| Real-time | WebSocket |
| Map UI | Leaflet + 合規地圖資料來源 |
| Container | Docker + Docker Compose |
| Testing | Pytest、Vitest、Playwright |
| CI | GitHub Actions |
| API Documentation | OpenAPI |

## 6.2 架構原則

採用模組化單體架構（Modular Monolith）。

**Frontend → FastAPI → PostgreSQL**

- Frontend 負責 UI、狀態管理與 WebSocket 訂閱。
- Backend 集中處理業務邏輯、權限與資料驗證。
- PostgreSQL 負責持久化、交易一致性及異動資料。
- WebSocket 只傳遞已成功提交的異動事件。
- 外部 API 由獨立的 Provider Adapter 封裝，方便替換或停用。

MVP 使用單一 API 執行實例，避免額外引入 Redis、Message Broker、微服務及 Kubernetes。

未來如需多執行實例，再評估跨實例事件傳播機制。

## 6.3 即時協作設計

編輯流程：

1. Client 取得項目鎖定。
2. Backend 驗證目前編輯權及鎖定狀態。
3. Client 提交修改與目前資料版本。
4. Backend 在資料庫交易中驗證並更新。
5. 交易成功後發布 WebSocket 事件。
6. 其他 Client 更新畫面。

鎖定被占用時回傳衝突資訊與目前編輯者。鎖定逾時可重新取得；即使鎖定已過期，舊版請求仍不得覆蓋新資料。

---

# 7. 資料模型（Data Model）

**實體儲存契約 v1.1（2026-11-25）**　下表保留 v1.0 的需求名稱，供歷史驗收追蹤。投票與輪次、任務清單、航班、住宿及參與者的八項實體儲存方式，以專案擁有者核定的 [§7 v1.1 資料模型對照](data-model.md) 為準。其餘欄位及功能需求沿用 v1.0。

所有主要資料表使用 UUID 作為主鍵。時間戳記統一以 UTC 儲存，旅遊當地時間使用 IANA Time Zone 解讀及呈現。

## 7.1 核心資料表

| Entity | 核心欄位 |
|---|---|
| users | id、account_type、nickname、email |
| auth_identities | user_id、provider、provider_subject |
| sessions | user_id、token_hash、expires_at、revoked_at |
| trips | id、owner_id、title、start_date、end_date、currency、status |
| trip_members | trip_id、user_id、role、joined_at、left_at |
| invitations | trip_id、token_hash、expires_at、revoked_at |
| trip_days | trip_id、day_number、title、timezone |
| places | trip_id、created_by、editable_by、name、address、coordinates |
| trip_candidates | trip_id、place_id、status、removed_at |
| itinerary_items | day_id、place_id、item_type、created_by、editable_by、position、version |
| edit_leases | resource_id、user_id、expires_at |
| polls | trip_id、created_by、type、status、deadline |
| poll_rounds | poll_id、round_number、status |
| poll_options | poll_id、option_text、created_by |
| ballots | poll_round_id、user_id、submitted_at |
| ballot_choices | ballot_id、option_id、value、rank |
| comments | trip_id、author_id、parent_id、content |
| audit_logs | trip_id、actor_id、entity_type、entity_id、action、changes |

## 7.2 第二及第三階段資料表

| Entity | 用途 |
|---|---|
| availability_entries | 日期可用性 |
| task_lists、tasks、task_assignees | 共用及個人任務 |
| budgets、expenses、expense_payers、expense_splits | 預算及費用分攤 |
| settlements | 結算與還款紀錄 |
| exchange_rate_snapshots | 匯率與換算依據 |
| flights、flight_passengers | 航班及乘客 |
| accommodations、accommodation_guests | 住宿及入住成員 |
| files、file_permissions、file_links | 檔案儲存及存取 |
| notifications、notification_preferences | 通知紀錄與偏好 |
| push_subscriptions | 瀏覽器推播訂閱 |
| entity_revisions | 單筆資料版本與復原 |

核心資料關聯：

- `users` 與 `trips` 經由 `trip_members` 形成多對多關係。
- 每個 `trip` 具有多個 `trip_days`、`places` 與 `polls`。
- 每個 `trip_day` 具有多個 `itinerary_items`。
- `itinerary_items` 可引用 `places`，但刪除候選清單關聯不得連鎖刪除該引用。
- 一個 `poll` 可有多個 `poll_rounds`。
- 一個 `poll_round` 可有多個 `ballots`。

正式建立 Migration 時需設定 Foreign Key、Unique Constraint、Check Constraint 及必要索引。

---

# 8. API 規格（API Contract）

使用 REST API，路徑版本為 `/api/v1`。

| 模組 | 主要 Endpoint |
|---|---|
| Auth | `POST /auth/google`、`POST /auth/guest`、`GET /auth/me`、`POST /auth/logout` |
| Trips | `GET /trips`、`POST /trips`、`GET /trips/{id}`、`PATCH /trips/{id}` |
| Trip lifecycle | `DELETE /trips/{id}`、`POST /trips/{id}/restore`、`POST /trips/{id}/archive` |
| Invitations | `POST /trips/{id}/invitations`、`POST /invitations/accept` |
| Members | `GET /trips/{id}/members`、`DELETE /trips/{id}/members/{memberId}` |
| Trip days | `GET /trips/{id}/days`、`POST /trips/{id}/days` |
| Places | `GET /trips/{id}/places`、`POST /trips/{id}/places` |
| Candidates | `POST /trips/{id}/candidates`、`DELETE /trips/{id}/candidates/{id}` |
| Itinerary | `POST /days/{id}/items`、`PATCH /itinerary-items/{id}`、`POST /itinerary-items/{id}/move` |
| Edit leases | `POST /edit-leases`、`POST /edit-leases/{id}/renew`、`DELETE /edit-leases/{id}` |
| Polls | `POST /trips/{id}/polls`、`GET /trips/{id}/polls` |
| Ballots | `PUT /polls/{id}/ballot`、`POST /polls/{id}/close` |
| Poll rounds | `POST /polls/{id}/reopen`、`POST /polls/{id}/adopt` |
| Comments | `GET /trips/{id}/comments`、`POST /trips/{id}/comments` |
| Real-time | `WS /ws/trips/{id}` |

後續模組依相同規則擴充 `/tasks`、`/expenses`、`/settlements`、`/bookings`、`/files` 及 `/notifications`。

共同 API 規範：

- 所有受保護端點必須驗證 Session。
- 涉及旅程資料的端點必須檢查有效旅程成員資格。
- 使用 HTTP `403` 表示沒有權限，`409` 表示資料版本衝突，`423` 表示編輯資源已鎖定。
- 編輯請求應附帶資料版本或 `If-Match`。
- 重要建立及財務寫入操作應支援冪等性識別。
- 錯誤回應提供可辨識的 Error Code、訊息及 Request ID。
- OpenAPI 規格由 Backend 維護，前端使用型別化 Client。

---

# 9. MVP 範圍與開發里程碑

## Milestone 1：專案基礎

- GitHub Repository 與 Branch / PR Workflow
- Frontend / Backend 專案架構
- Docker Compose
- PostgreSQL 與 Migration
- CI、Lint、Format、Testing 基礎

**完成條件：** 新開發者能依 README 在本機啟動全部必要服務。

## Milestone 2：帳號與旅程

- Google 登入
- 訪客 Session
- 建立及管理旅程
- Owner / Member 權限
- 邀請連結、邀請碼與 QR Code
- 旅程成員列表

**完成條件：** Google 使用者建立旅程後，訪客可透過邀請加入，且未授權者無法存取資料。

## Milestone 3：景點與每日行程

- 景點新增與候選清單
- 每日行程 CRUD
- 拖曳排序
- 時間設定及衝突警告
- 地圖標記與外部導航

**完成條件：** 成員可建立完整的多日行程，且排序及刪除符合權限規則。

## Milestone 4：即時協作與投票

- WebSocket 同步
- 在線成員狀態
- 編輯鎖定
- 景點及日期投票
- 投票結束、平票重投與手動採用
- 旅程留言

**完成條件：** 五個並行 Client 可以共同規劃，而不發生未授權覆寫或資料遺失。

## Milestone 5：穩定化與展示

- E2E Tests
- 安全性測試
- RWD 與基本無障礙檢查
- API 文件
- README、系統架構與 Demo 資料
- Docker 部署說明

**完成條件：** MVP 可重現、可測試、可展示，並具備清楚的已知限制說明。

第二階段及第三階段在 MVP 穩定後實作，不將全部進階功能列為 MVP 完成的前置條件。

---

# 10. 核心驗收標準（Acceptance Criteria）

| ID | 測試情境 | 預期結果 |
|---|---|---|
| AC-001 | 訪客嘗試建立旅程 | 系統拒絕並提示 Google 登入 |
| AC-002 | 訪客透過有效邀請加入 | 建立 Member 身分，重複加入不產生重複紀錄 |
| AC-003 | 使用過期邀請加入 | 拒絕加入，既有成員不受影響 |
| AC-004 | Member 修改他人的行程內容 | API 拒絕寫入 |
| AC-005 | Member 拖曳自己建立的行程 | 移動成功，其他項目可被動改變排序 |
| AC-006 | 從候選清單移除已排入行程的景點 | 每日行程仍保留該景點 |
| AC-007 | 兩位成員同時編輯同一項目 | 僅一人取得編輯鎖，其他人看到提示 |
| AC-008 | 編輯者異常斷線 | 鎖定逾時後可重新取得 |
| AC-009 | 使用舊版本更新資料 | API 回報版本衝突，不覆蓋最新資料 |
| AC-010 | 投票期間查看結果 | 只能查看自己的選票，不顯示他人選擇 |
| AC-011 | 投票結束後查看結果 | 顯示得票統計與個別成員選擇 |
| AC-012 | 投票平票 | 可建立新輪次，原始結果保留 |
| AC-013 | 已採用投票重新開啟 | 不自動修改既有行程 |
| AC-014 | Owner 企圖修改他人成員的景點 | 未取得合法編輯權時遭拒絕 |
| AC-015 | 成員退出旅程 | 歷史資料保留，存取權撤銷，原資料管理權轉移 Owner |
| AC-016 | 時間重疊 | 顯示警告，但允許儲存 |
| AC-017 | 地圖外部服務失敗 | 已保存景點及行程仍可讀取 |
| AC-018 | 未授權讀取敏感附件 | 回傳權限錯誤，不洩露檔案 |
| AC-019 | 超出預算 | 顯示警告，不阻止合法記帳 |
| AC-020 | 部署必要憑證缺失 | 服務明確回報設定錯誤，不使用不安全預設值 |

---

# 11. 明確不納入目前範圍的功能

為維持產品品質與可維護性，目前不實作：

- 旅遊社群、動態牆與公開貼文
- 商業訂房或機票購買
- 銀行轉帳及第三方支付
- AI 自動生成完整旅遊行程
- 離線編輯及多人離線同步衝突合併
- 自動下載完整離線地圖
- 依賴付費 API 的景點、道路交通及即時航班服務
- 原生 iOS / Android App
- 微服務架構及 Kubernetes

未來如有新增需求，需重新評估優先級、成本及與現有功能的關係。

---

# 12. 參考文件與實作依據

- [Google Maps URLs](https://developers.google.com/maps/documentation/urls/get-started)
- [Google Places API Billing](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing/)
- [OpenStreetMap Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/)
- [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)
- [Open-Meteo](https://open-meteo.com/)
- [Frankfurter Exchange Rate API](https://frankfurter.dev/)
- [Brevo Free Plan](https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet)
- [Apple Web Push Documentation](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

**文件結束：PRD / SRS v1.0**

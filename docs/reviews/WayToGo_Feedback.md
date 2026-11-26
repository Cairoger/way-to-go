# WayToGo 全工作區審查與開發改善清單

> **工作區交付 · 2026-11-26（臺北）**　本檔是補充回饋與驗收依據。工作區 `main` 的 HEAD 與原審查基準同為 `aac83bd`。第 1–11 節保留附件原文，其中的「本次」、行號、勾選框與測試數字均屬原審查。第 12 節記錄這次逐項核對的結果；功能驗收留待實作或部署複驗。
>
> [36 項 WTG 對照](#wtg-matrix) · [8 項產品提案](#x-scope) · [決策與歷史索引](#decision-history) · [本次驗證與重跑](#verification-record)

> WayToGo 已具備完整的小團體旅遊協作基礎；下一階段最有價值的工作，是補齊重試一致性、資料生命週期、部署可靠性與真實環境驗收，再擴充產品體驗。

| 項目 | 審查基準 |
| --- | --- |
| 日期 | 2026-11-26，Asia/Taipei |
| 輸入 | 使用者提供的 `WayToGo.zip`，包含原始碼、Git 歷史、設定及既有驗收資料 |
| 版本 | `aac83bda1d580e8000f62d953a829ab9f65dcd7a`，以下簡稱 `aac83bd` |
| 目的 | 提供開發者可拆成 Issue／PR 的缺陷、風險、改善建議、驗收條件與實作順序 |
| 修改範圍 | 本次未修改專案原始碼；額外驗證使用隔離環境與合成資料 |
| 路徑慣例 | 完整路徑相對於 `WayToGo/`；簡寫 Python domain 檔名位於 `backend/app/`，簡寫 TSX 元件位於 `frontend/components/`；行號對應本次版本 |
| 閱讀順序 | 先讀第 1–4 節掌握結論，再依 WTG 編號實作；第 7–10 節供排程、驗收及交接 |

## 1. 整體判斷

這個專案的強項是業務規則已深入到實際協作情境，包括訪客、帳號合併、離團成員歷史、私密附件、訂位可見範圍、編輯租約、版本衝突、分帳與還原驗證。現有模組化單體及單一 Uvicorn worker，適合目前 2–5 人小團體的定位，沒有足夠理由為了作品集立即改成微服務、Kubernetes 或增加 Redis。

本次沒有確認到 P0 等級的資料外洩或遠端執行問題，也沒有確認私人附件的授權繞過。不過，已重現數個一般成功路徑測試未涵蓋的資料正確性問題，並確認一些公開部署或長期保存資料前應處理的風險。不能把「目前測試通過」解讀成所有使用情境都已驗證。

**建議的工作順序：**

1. 修正重試造成重複建立、同名景點綁錯 ID、重採用已刪除活動、退出旅客欄位隱藏等具體缺陷。
2. 補上跨分頁身分同步、PDF 解析錯誤處理、附件永久清理與可恢復的編輯衝突流程。
3. 在公開部署前，驗證實際代理鏈、容器換 IP、慢資料庫與備份失敗情境。
4. 把 API 契約、帶資料升級測試、CI 失敗證據及還原手冊變成持續可重跑的工程能力。
5. 再依真實使用者需求，加入搜尋篩選、可分享頁籤、資料匯出及更完整的示範流程。

本文件列出 **36 個具體工作項目**及 **8 個產品加值方向**。它是對所提供快照的盡力審查，不代表對所有歷史檔案、外部服務、部署環境或未列出的輸入組合做過窮舉驗證。

## 2. 審查範圍與實際驗證

### 2.1 工作區覆蓋

Git 追蹤檔案共 565 個，包含 398 個歷史驗收檔案。可到達的 Git commits 共 9 個。歷史驗收資料約 13.0 MiB，其中含兩個嵌入 ZIP；這些資料用來理解先前決策及排除已修復問題，沒有把每個歷史附件當作本次重新驗收的結果。

| 區域 | 本次審查內容 |
| --- | --- |
| 後端 | `backend/app/` 的 31 個檔案，涵蓋 auth、trips、planning、decisions、preparations、finance、files、notices、realtime 及共用 models／helpers |
| 資料庫 | 10 個 Alembic revision，模型、FK／CHECK／unique、交易與刪除語意；SQLite 有 41 個應用資料表，另有 `alembic_version` |
| 前端 | `frontend/app/`、31 個 components 區域檔案、4 個 lib 檔案、Service Worker、離線 reader、樣式及靜態資產使用方式 |
| 測試 | 14 個後端 tests 區域檔案、17 個前端 tests 區域檔案、live acceptance runner、native Safari runner 及相關設定 |
| 部署 | Compose、兩個 Dockerfile、nginx、8 個 deploy 檔案、環境變數、備份與還原驗證 |
| 文件與 CI | README、6 個 docs 區域檔案、GitHub Actions workflow、需求／資料模型對照及歷史驗收說明 |
| 契約與依賴 | 執行時 OpenAPI、Python requirements、pnpm lock、套件稽核與少量目前追蹤文字的憑證格式檢查 |

### 2.2 本次執行結果

| 驗證 | 結果 | 可據此判斷的範圍 |
| --- | --- | --- |
| 後端 Ruff check／format check | 通過，59 個檔案格式符合 | 靜態規則及格式 |
| 後端 pytest | **63 passed，1 warning，10.11 秒** | 本次隔離 SQLite 測試環境的現有案例 |
| SQLite Alembic upgrade head／check | 通過，沒有新模型差異 | 空資料庫升級與模型一致性 |
| SQLite CHECK 對照 | 41 個應用資料表的 CHECK expressions 均相符 | 未發現警告所暗示的 constraint 遺失 |
| 前端 typecheck／lint／format | 全部通過 | 型別、靜態規則、格式 |
| Vitest | **2 個檔案、5 個測試通過** | 現有單元測試，不等同完整 UI 覆蓋 |
| Next.js production build | 通過 | 本次依賴組合可產生正式建置 |
| 前端 production dependency audit | 0 筆已知弱點，129 個套件項目 | 生產依賴圖；不包含完整 dev／OS／container 稽核 |
| Python 環境套件 audit | 52 個項目；應用依賴未命中，只有 venv 的 bootstrap `pip 25.0.1` 命中 advisories | 不應把工具環境的 pip advisories 當成 12 個應用弱點 |
| 額外業務探針 | 重現重試鍵改變、同名景點錯綁、退出旅客隱藏、採用已刪除活動、日期上溢；另量測列表查詢數 | 詳見各工作項目的證據等級 |
| Playwright 本次選取案例 | **12 個環境阻擋，0 個完成瀏覽器流程** | 全部在瀏覽器啟動階段停止，尚未進入產品斷言 |
| Docker Compose／PostgreSQL／外部身分服務 | 本次未重跑 | 只能引用原有歷史紀錄及靜態設定分析 |

本次使用 Node `24.22.3`、pnpm `11.25.0`；lockfile 實際解析為 Next.js `16.4.6`、React／ReactDOM `19.3.1`。Python 主要依賴包含 FastAPI `0.165.0`、SQLAlchemy `2.0.58`、pypdf `7.1.1`。不得以 `package.json` 的版本下限直接聲稱實際安裝舊版本有弱點。

驗證限制如下：

- 首次後端測試因本環境 SOCKS proxy 缺少 `socksio`，有一個環境性失敗；僅在隔離 venv 補足工具需求後，63 項全部通過。沒有因此更改專案依賴。
- `/usr/bin/chromium` 是 wrapper，實際 Chromium core binary 缺失；下載又受環境限制。因此 12 個 browser launcher failures 不列為 12 個產品缺陷。
- 本次沒有 Docker／PostgreSQL 服務，也沒有重新做 native Safari、公開 HTTPS、真正 Google consent／callback、實機背景 push、跨主機災難還原或完整螢幕閱讀器驗收。
- 專案已存在 PostgreSQL、還原及 native Safari 的歷史證據。應保留其原始日期與 revision，不說成「完全沒有做過」，也不把它們當作本次新執行結果。
- 本次是人工程式審查、既有測試、套件稽核及局部隔離探針；沒有完整自動化滲透測試或全歷史秘密掃描的結果。

### 2.3 可保留的設計

| 設計 | 保留理由及位置 |
| --- | --- |
| 後端集中授權 | `auth.py`、`core.py` 及各 domain routes 檢查成員、擁有者、作者及私密欄位；前端不是唯一保護 |
| OIDC 與 session | state／PKCE／nonce、ID token 驗證、Session Token 雜湊、HTTPS Secure／HttpOnly cookie、HTTP／WS origin 檢查均已有實作及測試 |
| 私密附件 | 檔案可見性與關聯物件權限共同檢查；擁有者不自動取得私人檔案；BLOB 與 preview text 已設 deferred load |
| 協作 | 編輯租約、版本檢查、commit 後廣播、重連後重新取得資料；不能為了方便修正而取消衝突保護 |
| 財務 | 整數／Decimal 計算、分攤尾差規則、持久化 request_id、離團及帳號合併後的歷史歸屬已有處理 |
| 離線 | 明確 opt-in、欄位 allowlist、清除本機副本、登出清除、Service Worker 不快取私人 API／地圖圖磚 |
| 備份 | atomic rename、`umask 077`、成功後才輪替、隔離且無網路的還原驗證、CI 檢查檔案 bytes／ACL |
| 部署 | API／DB 不直接對外發布、預設 loopback、app 非 root、前端 frozen lockfile、單體結構清楚 |

## 3. 優先度、證據及工作清單

### 3.1 定義

- **P0**：已確認的立即重大危害；本次沒有此等級項目。
- **P1**：會影響重要資料一致性或可用性，應優先處理；標 `*` 的項目在指定部署／使用條件成立時才是發布前門檻。
- **P2**：應安排於近期版本的缺陷、品質與維運改善。
- **P3**：依實際需求、規模或產品承諾再投入。
- **E**：本次執行目前程式的隔離探針／測試已觀察到；不一定是完整瀏覽器或正式環境端到端驗證。
- **S**：目前來源可確認的行為或缺口。
- **C**：設定及控制流程支持的條件性風險，尚未在實際部署重現。
- **A**：改善提案，需先確定產品或維運政策；不等於違反原規格。
- **S／M／L 工作量**：分別代表局部變更、跨層變更、需分階段的生命週期／架構變更，只供拆 PR，並非交付工時承諾。

本文件的 P1／P2 是修正優先度，與原規格的功能里程碑 P0／P1 不同。

### 3.2 總表

| ID | 優先度 | 項目 | 證據 | 建議主責 | 工作量 |
| --- | --- | --- | --- | --- | --- |
| WTG-01 | P1 | 同一新增意圖重試時更換冪等鍵；附件無 receipt | E／S | FE＋BE | M |
| WTG-02 | P2；公開不可信上傳前 P1* | PDF 限制例外及解析資源隔離 | E／S | BE | M |
| WTG-03 | P2 | 跨分頁登出／換帳後私人 UI 未統一失效 | S | FE | M |
| WTG-04 | P1* | async routes 內同步 DB I/O 阻塞單一 event loop | S／C | BE | L |
| WTG-05 | P1* | 外層 TLS proxy 下客戶端 IP 可能合併限流 | S／C | OPS | M |
| WTG-06 | P1* | 容器換 IP 後 nginx upstream 可能過期 | S／C | OPS | S–M |
| WTG-07 | P1* | 備份失敗／過期缺乏可觀測狀態，partial 可累積 | S | OPS | M |
| WTG-08 | P2 | 同名景點投票提交錯誤 place_id | E | FE | S |
| WTG-09 | P2 | 再採用投票結果回傳已刪除活動 | E | BE | S–M |
| WTG-10 | P2 | 航班退出旅客成為隱藏且不可編輯的資料 | E | FE＋BE | S |
| WTG-11 | P2 | 回收附件仍計入配額，沒有釋放容量途徑 | S | BE＋FE | M |
| WTG-12 | P2 | 日期與日數邊界可使已建立旅程讀取 500 | E／S | BE | S–M |
| WTG-13 | P2 | 編輯衝突缺少保留草稿的恢復流程 | S／A | FE | M |
| WTG-14 | P2 | 日期層級編輯／刪除能力及時區語意不完整 | S／A | FE＋BE | M |
| WTG-15 | P2 | 手機選單與切換按鈕的無障礙語意不足 | S | FE＋QA | M |
| WTG-16 | P2 | 上傳進度、取消與結果待確認狀態不完整 | S／A | FE＋BE | M |
| WTG-17 | P2 | N+1、無分頁歷史及過廣即時刷新 | E／S | BE＋FE | M |
| WTG-18 | P2 | 大部分 JSON response 缺少 OpenAPI schema | E／S | BE＋FE | M–L |
| WTG-19 | P2 | 未處理 500 缺一致錯誤契約，request ID 難追蹤 | E／S | BE＋OPS | M |
| WTG-20 | P2；共享主機 P1* | 初始化 `.env` 權限為 0644 | E | OPS | S |
| WTG-21 | P2 | 應用使用 PostgreSQL bootstrap superuser | S | BE＋OPS | M |
| WTG-22 | P2 | CI 未保護帶資料的版本升級路徑 | S | BE＋QA | M |
| WTG-23 | P2 | 可決定性 push 測試被外部測試開關一起略過 | S | FE＋QA | S–M |
| WTG-24 | P2 | CI 缺少失敗 artifacts、工作時間及併發政策 | S | OPS＋QA | S–M |
| WTG-25 | P2 | Python transitive lock 與發布輸入可重現性不足 | S | OPS | M |
| WTG-26 | P2 | 正式還原、升級與金鑰輪替缺可執行手冊 | S／A | OPS | M |
| WTG-27 | P2 | 過期／軟刪資料缺少 retention 與 purge 流程 | S／A | BE＋產品 | L |
| WTG-28 | P2；公開擴大使用前提高 | WebSocket 連線及輸入訊息缺少身分預算 | S／C | BE | M |
| WTG-29 | P2 | 裝置工作階段管理及訪客擁有者復原策略 | S／A | BE＋FE | M |
| WTG-30 | P3；承諾可靠通知時 P2 | 推播只有背景 best-effort，無 durable retry | S／A | BE | M |
| WTG-31 | P2 | 財務修改／刪除缺可閱讀的完整修訂歷程 | S／A | BE＋FE | M |
| WTG-32 | P2 | 缺實測主機容量與程序資源預算 | S／A | OPS＋BE | M |
| WTG-33 | P2 | 部署網路／容器權限／頁面 header 可再收斂 | S／A | OPS＋FE | M |
| WTG-34 | P2 | build-time 設定與上傳跨層限額缺一致契約 | S／C | OPS＋FE＋BE | S–M |
| WTG-35 | P2；歷史附件整理 P3 | 開發交接、授權、驗收索引及發布文件 | S／A | 全體 | M |
| WTG-36 | P2 | 可攜帶匯出與帳號資料生命週期 | S／A | 產品＋BE＋FE | L |

## 4. 資料正確性、協作與前端

### WTG-01：讓同一建立意圖在重試時保持同一冪等鍵

**P1｜E／S｜FE＋BE｜M。** 這是最值得先修的跨模組缺陷。

**證據與影響。** `frontend/lib/api.ts:21–34` 每次 POST 呼叫預設產生新 UUID。`TripForm.tsx:52–59`、`Planner.tsx:333–349`、`Decisions.tsx:946–962`、`Preparation.tsx:388–393`、`Reservations.tsx:620–626` 等新增流程沒有保存重試鍵。後端對應 create routes 已有 receipt，但同一表單在伺服器 commit 後遺失回應，再按一次會被當成新意圖。實際執行目前 api helper 的探針得到 `sameBody=true`、`sameIdempotencyKey=false`。這證明鍵不穩定，並非宣稱本次已做所有流程的完整網路端到端重現。

`Attachments.tsx:44–57` 的 multipart fetch 沒有冪等鍵，`backend/app/files.py:175–217` 也沒有上傳 receipt，重試可能再次占用容量。旅程複製亦有相同問題，見 `TripDetail.tsx:219–226`、`backend/app/trip_copy.py:76–88`。財務 `Finance.tsx:66–80` 已保存 body `request_id`，邀請 `Members.tsx:169–192` 已保存 retry key，這兩者應作為既有正確模式。

**建議修改。** 建立共用 mutation hook，讓同一未確認草稿保存 operation ID，重試沿用，成功後或使用者明確開新草稿才換鍵。修改 payload 時明確建立新意圖，不能用舊鍵偷偷覆蓋；若舊意圖仍結果待確認，先查詢或明確處理舊結果，避免已成功的舊資料與新意圖同時留下兩筆。receipt 需綁使用者、operation、request fingerprint 及結果 ID。附件增加批次 receipt，保留目前交易原子性，對相同使用者及旅程重送回傳原始檔案 IDs；不要以全站檔案雜湊當成跨使用者授權捷徑。

**驗收條件。**

- [ ] 旅程、景點／活動、投票／留言、任務、預訂、旅程複製在 commit 後故意遺失回應，再送同一草稿只產生一筆資料。
- [ ] 相同 key、不同 payload 明確拒絕；明確新增第二筆相同內容可取得新 ID。
- [ ] 三檔上傳批次重試只增加一次配額，沒有重複或孤兒檔案。
- [ ] UI 能區分「尚未送出」「結果待確認」「已成功」；取消本機請求不宣稱後端已回滾。

### WTG-02：處理 PDF 解析限制例外，並限制單次解析工作

**P2；公開接受不可信上傳前 P1｜E／S｜BE｜M。**

**證據與影響。** `backend/app/file_formats.py:104–132` 的 PDF 錯誤捕捉不涵蓋 pypdf `LimitReachedError`；`files.py:128–135` 呼叫解析後，錯誤可一路成為未結構化 500。隔離測試的一個 74,535-byte 檔案觸發函式庫限制時，API 回 500、沒有 `X-Request-ID`；程序峰值 RSS 約 241.8 MiB。這個數值是單次測試程序觀察，不能推算為所有 PDF 的記憶體成本或正式容量。

pypdf **已有**解壓縮限制，問題不是函式庫完全無保護。應用在 `extract_text()` 之後才截取 4,000 字元，不能限制前面的解析工作；解析目前在共用 thread pool 執行，也缺少每項工作 CPU／記憶體／併發預算。官方文件亦提醒文字擷取可能需要處理整段內容流。[S2]、[S6]

**建議修改。** 明確映射預期 parser exceptions 至合適的 413／415／422 與穩定錯誤碼，保留 request ID；非預期錯誤由全域處理並記錄。對解析較重的格式採有上限的隔離 worker／subprocess，設檔案、頁數、處理時間、記憶體、併發及等待佇列預算。逾時後要能停止工作，不能只取消等待的 coroutine；是否保留可下載但無 preview 的檔案需明訂政策。

**驗收條件。**

- [ ] 正常、損壞、加密及超出解析預算的文件皆得到有 request ID 的預期結果。
- [ ] 用 exception injection 測試 `LimitReachedError` 映射；不需要在一般 CI 保存特殊攻擊內容。
- [ ] 隔離環境同時做一般 API 讀取與受限解析時，API 仍可服務，解析逾時後 worker 可回收。
- [ ] 失敗批次不留下半份附件／配額紀錄；既有圖片及 Office 驗證仍通過。

### WTG-03：統一跨分頁、Session 到期與換帳的私人狀態清除

**P2｜S｜FE｜M。**

**證據與影響。** `Workspace.tsx:165–195,225–255,702–709` 沒有 auth 的 `storage`／`BroadcastChannel`／focus 同步；登出清除的是目前分頁。`NoticeCenter.tsx:55–88` 遇到 401 會保存錯誤，但不統一清掉已載入通知。另一分頁登出／換帳後，首頁可能仍顯示舊暱稱、旅程卡及通知。這是 UI／本機快取隱私與一致性問題，不是伺服器授權繞過；本次未以真實瀏覽器重現。

`backend/app/realtime.py:79–101` 會在更新／heartbeat 路徑重新驗證 Session；前端 `TripDetail.tsx:171–179` 收到拒絕 close code 時退出旅程，`104–125` 另處理 HTTP 失權。因此影響最直接的是沒有旅程 WebSocket 的首頁與通知 UI。離線 reader 已有跨分頁清除處理，應延伸其做法。

**建議修改。** 建立共用 auth provider，以不含 token 的身分世代事件同步登出／換帳。所有快取及未完成請求綁 `userId + authEpoch`；舊世代回應不得寫回新身分。focus／pageshow／401 重新確認 session，清掉私人 state、dialog、socket 及舊請求。一般斷網不能一律當作登出。

**驗收條件。**

- [ ] 兩個首頁分頁，任一分頁登出後，另一頁立即不再顯示旅程及通知內容。
- [ ] 換帳、自然過期、BFCache 回復及慢速舊請求，不會把上一個使用者的畫面寫回。
- [ ] 正常網路暫斷能保留合理狀態；API 的原有權限檢查及離線清除仍有效。

### WTG-04：避免同步資料庫 I/O 阻塞單一 async event loop

**P1，公開多人使用／慢 DB 情境需先驗證｜S／C｜BE｜L。**

**證據與影響。** `core.py:80–86` 使用同步 SQLAlchemy engine；多個 `async def` 路由直接執行同步查詢、flush、commit 及 row lock，例如 `finance.py:308–328`、`auth.py:270–345`、`trips.py:256–294`、`preparations.py:216–304`。`finance.py:525–527` 的讀取也取得 trip `FOR UPDATE`。在單一 Uvicorn worker 中，慢查詢或鎖等待可暫停其他 coroutine，包括 HTTP 及 WebSocket。

這項控制流程可從程式確認，但本次沒有 PostgreSQL 鎖等待／deadlock 的執行證據。許多寫入在 await 廣播前已 commit，不能聲稱所有並發寫入都會 deadlock。`realtime.py` 的 session identify 已用 threadpool，不應誤列為同一缺陷。FastAPI 不會自動把 async 路由裡自行呼叫的同步 helper 移到 threadpool。[S1]

**建議修改。** 選擇一條一致路徑：把完整同步 unit of work 移到 worker 執行，包含 Session 建立、查詢、commit／rollback、close，再回到 async 發布事件；或逐模組改成 AsyncSession／async driver。不要讓同一個 Session 在多個 thread 之間零碎傳遞。檢視讀取是否真的需要排他 row lock，設定合理 statement／lock timeout，維持財務 snapshot 一致性。

**驗收條件。**

- [ ] 在專用 PostgreSQL 中讓一個 transaction 正常持鎖，另一個請求等待時，不相關旅程的讀取與 WS heartbeat 仍前進。
- [ ] 同旅程併發更新仍維持版本、分帳及冪等不變量；timeout 得到可重試的結構化錯誤。
- [ ] 失敗 rollback、Session 關閉及 commit 後廣播順序均有測試；沒有跨 thread 共用 Session。
- [ ] 先以現有單 worker 驗證；若未建立跨程序事件傳遞，不直接增加 workers。

### WTG-05：明確定義外層代理與真實客戶端 IP 的信任邊界

**前置 TLS proxy 的公開部署為 P1｜S／C｜OPS｜M。**

**證據與影響。** README 建議前置 TLS proxy；`deploy/nginx.conf:15–21` 卻以 `$remote_addr` 覆寫 X-Forwarded-For；`backend/app/main.py:94–125` 用 `request.client.host` 限流，`backend/Dockerfile:11` 允許所有 forwarded peers。經外層代理時，多名訪客可能被識別成同一 proxy／gateway，分享登入、邀請、搜尋或上傳配額。這是設定衍生風險，本次沒有雙代理實測。

**建議修改。** 對實際信任的 proxy 網段設定 nginx `set_real_ip_from`、`real_ip_header`、適當的 recursive 行為，再向 API 傳遞標準化地址。收斂 Uvicorn 的 forwarded trust。不得為了恢復真實 IP 就接受任意網際網路 XFF。必要時分開 account 與 IP budgets。[S3]

**驗收條件。**

- [ ] 從兩個不同來源經完整 HTTPS 代理鏈連入，A 達限不影響 B。
- [ ] 不可信來源自行夾帶 forwarded headers，不能任意切換限流身分。
- [ ] HTTP、WS origin、Secure cookie 及 callback URL 在同一部署契約下成立。

### WTG-06：讓 nginx 正確處理 API／frontend 重建後的 DNS 變化

**依賴可重複部署更新時 P1｜S／C｜OPS｜S–M。**

**證據與影響。** `deploy/nginx.conf:19,28,30–34` 使用固定 hostname 的 `proxy_pass`，沒有動態 resolver；README 的設定更新範例只重建 API。Docker service 重建可能換 IP，但 nginx 可能持續使用載入設定時的解析結果，導致 502。並非每次重建一定換 IP，本次沒有容器環境重現。[S4]、[S5]

**建議修改。** 針對選定且固定版本的 nginx，使用相容的 upstream zone／resolve／resolver 與 Docker DNS；或把 nginx reload／recreate 列為每次升級的必要且可驗證步驟。選一個清楚的解法，不留下隱含人工補救。

**驗收條件。**

- [ ] 刻意讓 API／frontend 替換成不同 IP：若採動態解析，web 不重建即可恢復；若採部署刷新，依文件 reload／recreate web，並在明訂中斷窗口內恢復首頁、health、授權 API 及 WS 重連。
- [ ] 升級流程記錄舊新 image digest、結果及失敗時的回復步驟。

### WTG-07：讓備份與還原狀態可以被看見，並清理失敗 partial

**依賴此部署保存真實資料時 P1｜S｜OPS｜M。**

**證據與影響。** `deploy/backup.sh:5–18`、`restore-drill.sh:73–84`、`compose.yaml:61–82` 缺少最近成功狀態與 freshness healthcheck。失敗可能留 `.partial`，重啟後持續累積；磁碟空間檢查在 dump 成功後才做，實際磁碟滿時可能到不了這一行。主應用仍健康，不代表當天有有效備份。

**建議修改。** 保存 last-start／last-success／archive age／size／last-restore-success，提供維護者能觀察的狀態與通知管道。失敗或終止只清理目前 partial，加入有上限的重試及 backoff，備份前檢查容量。保留既有 atomic rename、成功後 retention 及獨立 restore drill。

**驗收條件。**

- [ ] 在拋棄式環境測試 DB 無法連線、目的地不可寫、容量不足、損壞 archive，皆有可辨識 unhealthy／告警狀態。
- [ ] 失敗不造成 partial 無限成長，也不刪掉最後可用備份。
- [ ] 維護者明訂允許的備份／還原驗證年齡，例如備份 26 小時、還原驗證 27 小時；這是待選的營運門檻，不是現有保證。
- [ ] 故障恢復後，只有新的成功備份及還原驗證才清除對應異常狀態。

### WTG-08：以 place_id 保存投票景點，不以名稱回推

**P2｜E｜FE｜S。**

**證據與影響。** `frontend/components/Decisions.tsx:179–199,249–263` 選單先以 ID 選景點，接著只保存名稱；送出時 `places.find(p => p.name === text)` 取得第一個同名景點。執行實際 CreatePoll handler，選 `second-cafe` 卻提交 `first-cafe`。兩個不同地址的同名店家／車站會綁錯地點，也不能自然地加入兩個同名選項。

**建議修改。** 選項保存 `{client_id, text, place_id}`，顯示名稱加地址／城市。手動輸入的文字維持 `place_id=null`，不要猜測關聯。若後端要求選項文字唯一，產生可辨識的顯示文字，但不改原地點身分。

**驗收條件。**

- [ ] 同名不同地址可分別選取，送出及採用後保留正確 ID、地址。
- [ ] 修改顯示文字不改 place_id；手動同名文字不自動綁錯。
- [ ] 補選項、編輯及重投流程都使用同一結構化契約。

### WTG-09：定義投票已採用活動被刪除後的再採用行為

**P2｜E｜BE｜S–M。**

**證據與影響。** `backend/app/decisions.py:455–487` 在 adoption 有 item_id 時直接回傳；`planning.py:697–705` 只 soft-delete 活動，因此 FK `SET NULL` 不會觸發。本次依序採用、刪除、再採用，得到 HTTP 200、相同且已刪除 item ID，實際可見活動仍是 0。

**建議修改。** 再採用時檢查 item 狀態及權限。由產品明訂回 409 並提供復原入口，或以授權交易明確復原／建立新項目並更新 adoption。保留正常重送不重複建立的行為，不可默默復活別人移除且使用者無權復原的項目。

**驗收條件。**

- [ ] 一般重送只回原有活動；已刪除活動得到明確復原／再採用結果，不再假成功。
- [ ] 活動被移到其他日期、景點被回收及原建立者離團時，行為仍明確。
- [ ] 並行再採用不產生兩份活動；復原與新建均遵守原有 ACL、版本及 audit。

### WTG-10：航班編輯顯示既有的退出旅客

**P2｜E｜FE＋BE｜S。**

**證據與影響。** `Reservations.tsx:162–209` 只迭代目前 members，既有 `leg.passengers` 卻可包含已離團者。實際 LegFields server render 顯示目前旅伴 checkbox，沒有原退出旅客的 `18B` 座位與 `20kg` 行李欄位。提交可能仍帶著隱藏資料，建立者無法理解或修改。

**建議修改。** 以 active members 與 existing passengers 聯集顯示，標記已退出旅客。沿用住宿編輯已處理 former guests 的做法，允許原授權者保留、修改或明確移除既有旅客，不因此允許加入陌生身分。

**驗收條件。**

- [ ] 退出後原資料可見；只改標題時不意外抹除歷史旅客，明確移除時才變更。
- [ ] 新增其他旅程／陌生使用者仍被拒絕。
- [ ] 未列為旅客且非建立者的擁有者，不因 public-only 編輯權取得私人欄位；若擁有者本來就是旅客，保留本人座位／行李及訂位代號的既有閱讀權。公開編輯 endpoint 不得修改旅客及私人欄位，見 `preparations.py:419–451`。

### WTG-11：補齊附件回收後的永久清理與容量回復

**P2｜S｜BE＋FE｜M；與 WTG-27 共用 retention 設計。**

**證據與影響。** `files.py:187–191` 的 quota SUM 包含 removed files；`files.py:265–280` 只回收／還原。達預設 500 MiB 配額後，就算回收所有附件也沒有釋放容量的途徑。回收期仍計費有其合理性，缺的是最後清除流程及說明。

**建議修改。** 顯示 active／recycled／total usage，增加符合權限的永久刪除或到期 purge。先確認檔案仍被哪些活動、任務、費用或預訂引用，顯示影響後才刪除。區分邏輯配額釋放與 PostgreSQL 實體檔案空間回收，不能承諾刪除後磁碟檔案立刻縮小。

**驗收條件。**

- [ ] 配額接近上限時，回收與永久刪除前後的數值正確；永久刪除後可重新上傳。
- [ ] 使用者永久刪除沿用檔案上傳者的管理權，旅程 owner 不因角色自動取得刪除其他上傳者附件的權限，包含共用附件；系統到期 purge 依明訂 retention 執行。有關聯及無關聯附件皆有明確處理。
- [ ] 重複 purge、並行上傳／刪除不使配額負值、不誤刪有效檔案；還原不繞過配額。

### WTG-12：在寫入前驗證日期、日數與 recurrence 的可表示範圍

**P2｜E／S｜BE｜S–M。**

**證據與影響。** `trips.py:51–60,161–173` 未完整限制 start_date 與 day_count 的合成範圍；`planning.py:524–526` 直接加日期。本次 `start_date=9999-12-31`、`day_count=2` 建立成功，讀取 days 卻回 500 且無 request ID。`planning.py:555–569` 新增一天也沒有套用與建立旅程一致的最大總日數；`preparations.py:286–298` 的 recurrence 類似需要邊界保護。這是低頻邊界缺陷，並非一般日期都失敗。

**建議修改。** 設定符合產品的可接受日期區間，或安全檢查所有 date arithmetic。建立／編輯旅程、增日、日期協調套用、重複任務共用驗證器；無效值在 commit 前回 422。對既有越界資料提供修復方式，避免一讀就 500。

**驗收條件。**

- [ ] 最大日期配合多日行程、閏日、月底／年底 recurrence、最大日數後再新增都得到明確結果。
- [ ] 只填開始日期及未定日期維持既有行為；只有結束日期是否允許須明確決策，前後端驗證一致。現有 `TripForm.tsx:31–33` 不允許只填結束日期。
- [ ] 被拒絕的請求不留下部分 Day／Task／Trip；讀取既有異常資料不使整個旅程頁失效。

### WTG-13：版本衝突後保留草稿，讓使用者有安全的恢復路徑

**P2｜S／A｜FE｜M。**

**證據與影響。** `TripForm.tsx:18–19,50–56` 固定初始 version；Finance、Planner、任務與預訂表單在衝突時主要顯示字串，使用者往往只能重開表單。後端拒絕舊版本是正確的，不能把修正做成自動拿最新 version 強行覆寫。

**建議修改。** 擴充 `ProfileForm.tsx` 已有的保留輸入／重讀模式：同時保存 draft 與最新 server value，顯示衝突欄位，讓使用者選擇重新套用或放棄。租約過期先重新取得；長表單 dirty 時提供合理的離開確認，避免點擊背景即丟失。

**驗收條件。**

- [ ] 兩個分頁編輯同一旅程、費用、預訂，第二個 409 後草稿仍完整，可比較並重新處理。
- [ ] 不自動覆寫其他人的修改；鎖失效與純版本衝突的文案及操作不同。
- [ ] 成功／明確放棄後清除 dirty；背景即時更新不覆蓋尚未送出的輸入。

### WTG-14：補齊日層級編輯，先定義刪日與時區變更語意

**P2｜S／A｜FE＋BE｜M。**

**證據與影響。** `Planner.tsx:418–425,760–790` 只有新增日期；`planning.py:555–571` 有 POST days，沒有 PATCH／DELETE day。`docs/spec.md:616–624` 使用「每日行程 CRUD」，但 API 表只列 GET／POST，需要先對齊定義。錯誤標題、時區或多加的空日，缺少直接修正方式。

**建議修改。** 第一階段提供改標題／時區與刪空日；非空日要求移轉活動或拒絕。明定誰可修改、版本欄位、day_number 重排、預訂／任務關聯及歷史。時區變更要說清楚是保留當地鐘面時間，還是保留 UTC instant，不可無提示地改時刻。調整旅程日期保留原日程是現有意圖，可加差異預覽，不應直接刪掉多出的活動。

**驗收條件。**

- [ ] 不重建旅程即可改錯誤標題／時區、刪空日；非空日不靜默遺失資料。
- [ ] 重編號與日期映射一致，並行修改有版本保護。
- [ ] 跨 DST、跨時區航班及沒有實際日期的 Day 1 行程皆有明確行為。

### WTG-15：補齊手機 drawer 與 toggle 的鍵盤及輔助科技狀態

**P2｜S｜FE＋QA｜M。**

**證據與影響。** `Workspace.tsx:303–307,393–400` 的 mobile drawer trigger 沒有 `aria-expanded`／`aria-controls`，也沒有完整開關焦點及 Escape 流程；Preparation、Reservations 的切換主要依 CSS 呈現選取狀態。現有 keyboard spec 未覆蓋所有業務表單。

**建議修改。** 先決定 drawer 是 modal 還是 disclosure，再使用對應的 focus／ARIA 模式。modal 應具名、轉入及圈住焦點、Escape 關閉、返回 trigger；非 modal 保持正確 focus order。toggle 使用 `aria-pressed`，或真正實作 tablist／tab／tabpanel。[S7]

**驗收條件。**

- [ ] 手機與桌面只用鍵盤可開關選單、切換業務頁、完成投票／費用／訂位／附件表單。
- [ ] 選取、busy、錯誤狀態可由螢幕閱讀器辨識；使用實際填有資料的畫面跑 axe，再做人工鍵盤檢查。
- [ ] 保留既有 Radix Modal focus trap、返回 opener、reduced motion 及鍵盤移動行程的能力。

關閉 sidebar 已有 `visibility:hidden`，不能誤報關閉時仍能 Tab 進入。自動化 axe 通過也不代表完整 WCAG 已驗收。

### WTG-16：把附件上傳建模為可追蹤的工作

**P2｜S／A｜FE＋BE｜M；先完成 WTG-01 的 receipt。**

**證據與影響。** `Attachments.tsx:44–50,88–115,119,170–175` 使用沒有 signal／timeout 的 fetch，busy 與 Modal 關閉未完整協調。慢速連線時使用者可能關掉視窗，伺服器卻之後成功；討論草稿上傳後離開的清理語意也需要定義。現有非 JSON 413 已會轉成可讀錯誤，不是未捕捉 JSON parse 問題。

**建議修改。** 顯示單檔／批次／剩餘配額及傳輸狀態；提供取消要求、可查詢的 operation 狀態、結果待確認及安全重試。不要把大檔上傳一律設成 18 秒即失敗，也不要把 AbortController 中止等同後端回滾。草稿檔案須有獨立的保留及清理規則。

**驗收條件。**

- [ ] 慢速、斷線、伺服器已提交但回應延遲、關閉 dialog、取消後重開皆有明確結果。
- [ ] 無永久 busy；重試不重複占額；配額不足與被代理拒絕時說明正確。
- [ ] 留在草稿、已關聯及回收檔案能被區分，清理不影響已提交內容。

## 5. 契約、資料庫、維運與工程品質

### WTG-17：控制查詢數、集合大小與即時刷新成本

**P2｜E／S｜BE＋FE｜M。**

**證據與影響。** 本次在隔離 SQLite 以 20 筆合成資料量測，旅程列表有 83 次 SQL，任務列表有 46 次 SQL，包含身分／ACL 讀取。來源包括 `trips.py:102–158,176–192`、`preparations.py:107–156,204–213`。這能證明查詢放大的模式，不能直接換算正式環境延遲。

`decisions.py:159–250,524–534` 的投票歷史／留言、`planning.py:712–739` 修訂、`notices.py:232–254` 通知等缺乏分頁；`files.py:69–95` 有逐檔權限與關聯讀取。前端 `TripDetail.tsx:131–145` 多種事件觸發相近的全量刷新。`TripFile.data`／`preview_text` 已是 deferred，不能把此問題說成清單會直接載入 500 MiB 原檔。

**建議修改。** 先以批次 aggregate、selectin loading、預取 ACL 消除明顯 N+1。留言、通知、歷史優先 cursor pagination；歷史輪次按需讀取。WS 事件帶 entity／operation／version，精準失效相關資料，重連仍做完整 resync。小團體不必為此立即更換框架或快取架構。

**驗收條件。**

- [ ] 固定 fixture 下，20 與 100 筆列表的查詢數不再與資料筆數近似線性倍增；記錄查詢及 payload 差異。
- [ ] 留言在同步新增、刪除、跨頁讀取時不漏項／重複，頁面大小有伺服器上限。
- [ ] 為一般旅程與大型 fixture 分別量測 p95、payload、前端 render；先記 baseline 再訂合理預算。
- [ ] 無關事件不重載整個頁籤；背景 refresh 不覆寫表單；重新連線可收斂到完整最新狀態。

### WTG-18：讓 OpenAPI 成為可驗證的前後端契約

**P2｜E／S｜BE＋FE｜M–L，建議按 domain 分 PR。**

**證據與影響。** 本次檢查實際 `app.openapi()`，共有 93 個 HTTP operations，成功 JSON response 定義中有 84 個 schema 為 `{}`。許多路由回傳手工 dict，前端又分散定義 Trip／Day／Place／Booking 型別；`frontend/lib/api.ts` 的 `data as T` 只提供編譯期斷言，無法證明執行時回應符合型別。

**建議修改。** 逐模組補明確 request／response DTO、錯誤碼及空值語意，先從身分、旅程、預訂／附件及財務開始。由 OpenAPI 生成 client／types，保留需要的 domain view model。統一 `VERSION_CONFLICT`／`version_conflict`／`stale_version` 等錯誤差異，補資源 ID、字串、集合、payer／split mapping 的合理邊界及 extra-field 政策。新增 response model 時，必須依權限選擇公開／私人 DTO，避免不小心把 ORM 全欄位序列化。[S8]

**驗收條件。**

- [ ] 主要 JSON endpoints 有具體 schema，CI 可以偵測 client generation drift。
- [ ] 缺欄位、未知 enum、額外欄位及錯誤形狀有明確契約；不只靠 TypeScript assertion。
- [ ] 訂位建立者、旅客、一般成員、擁有者的回應欄位測試證明沒有私密欄位外漏。
- [ ] 契約變更附相容性說明，現有離線快照與舊瀏覽器分頁有可恢復的處理。

### WTG-19：統一非預期錯誤與可追蹤的執行紀錄

**P2｜E／S｜BE＋OPS｜M。**

**證據與影響。** `main.py:128–146` 有 request ID 與部分例外處理，但本次 PDF／日期探針的未處理例外回純文字 500，沒有 `X-Request-ID`。nginx `access_log off`、Uvicorn `--no-access-log`，也沒有等效的完整結構化 request logs。使用者提供 ID 時，維護者可能找不到相關路由、耗時及結果。

**建議修改。** 在可涵蓋未處理例外的層級產生或驗證 request ID，回傳穩定的安全錯誤 envelope，server-side 記錄 stack 及關聯 ID。加入 route template、method、status、duration、結果分類，不記 raw query、Cookie、邀請碼、訂位代號、payload 或私人文字。補基本錯誤率、DB pool／等待、WS 數量、外部服務失敗、備份 freshness 指標。前端提供可恢復的 error boundary，保留安全的支援 ID。

**驗收條件。**

- [ ] 應用層的 400／401／403／409／413／422／429／非預期 500 都有一致可辨識的錯誤及 request ID。nginx 提前拒絕的錯誤另訂 edge ID／log 契約；保留前端安全處理目前 HTML 413 的能力，不假設 FastAPI handler 能處理未到達 API 的請求。
- [ ] 以 ID 找得到一筆相符記錄，內容不含敏感資料，也不向使用者回傳 stack 或 SQL。
- [ ] 人為注入一般例外、DB timeout、外部服務 timeout，可分辨原因且不使日誌無限重複。
- [ ] `/health` 的可服務狀態與備份健康分開，不以單一綠燈代表所有維運功能正常。

### WTG-20：初始化秘密設定時使用私有檔案權限

**P2；共享主機存正式憑證時 P1｜E｜OPS｜S。**

**證據與影響。** `deploy/init_env.py:8–9` 在 POSIX `umask 022` 下建立 mode `0644` 的 `.env`，本次以暫存副本確認。其他能穿越專案目錄的本機帳號可讀取資料庫密碼及後續加入的 OAuth／VAPID secret。是否可被其他人讀到還取決於父目錄權限，不能直接聲稱對網際網路公開。`deploy/create_test_login.py:32–40` 已用私有 temporary file，值得一致化。

**建議修改。** 使用 `os.open` 的 `os.O_WRONLY | os.O_CREAT | os.O_EXCL` 與 `0o600` 原子建立，保留不覆寫既有設定的行為。Windows 提供相應 ACL 說明。忽略常見實際 `.env.*`，明確保留 `.env.example`，不要輸出新秘密內容到一般驗證日誌。

**驗收條件。**

- [ ] `umask 022` 下新檔為 `0600`；原 `.env` 的內容及權限不被意外覆寫。
- [ ] 初始化失敗不留部分秘密檔；本機測試帳號 provisioning 仍正常。
- [ ] 支援的 Windows 部署路徑有可驗證的存取限制。

### WTG-21：拆開 DB bootstrap、migration、runtime 與 backup 權限

**P2，保存真實敏感資料前安排｜S｜BE＋OPS｜M。**

**證據與影響。** `compose.yaml:7–9` 設定 `POSTGRES_USER=waytogo`，API `DATABASE_URL` 及 backup 都使用同一角色；`backend/Dockerfile:11` 在 API startup 自動 migration。官方 PostgreSQL image 會將此初始化角色建立為 superuser，因此 runtime 的資料庫權限超過一般 DML 所需。[S9] 這不是已發現 SQL injection 或入侵的證據。

**建議修改。** 分離 bootstrap／admin、migration、runtime DML、backup principals；migration 移到單次部署 stage，runtime 僅授權必要 schema／table／sequence。新表及新 sequence 的 default privileges 也要處理，否則下次 migration 後會失效。備份／還原流程各用其所需權限，不讓一般 app 自行做管理操作。

**驗收條件。**

- [ ] runtime DSN 下所有應用測試通過，但建立角色／資料庫及破壞 schema 的操作被拒絕。
- [ ] fresh install 與既有安裝升級後 grants 都正確。
- [ ] migration、備份及還原使用專用角色完成，API 重啟不再取得 DDL／superuser。

### WTG-22：把帶資料的 migration 升級做成回歸測試

**P2｜S｜BE＋QA｜M。**

**證據與影響。** `backend/tests/conftest.py:43` 以 `Base.metadata.create_all` 建立最終 schema；CI 的 Alembic 步驟主要驗證空 DB 到 head。這不足以驗證舊資料、FK rebuild、default、資料轉換或 downgrade 限制。先前帶資料升級紀錄有價值，但尚未形成這些路徑的持續回歸門檻。

**建議修改。** 從前一個支援版本建立代表資料，再用 Alembic 升級。涵蓋 users／profile version、邀請、私人 files／grants／links、預訂、投票輪次、財務歸屬及 account merge。SQLite、PostgreSQL 各做必要部分，明訂支援的升級起點及 downgrade 或 backup restore 政策。

**驗收條件。**

- [ ] `0009 → 0010` 保留既有 profile，version 正確初始化；其他受支援 baseline 到 head 有代表性資料測試。
- [ ] 升級前後關係、ACL、檔案 hash、金額與必要筆數不變，核心 API 可讀取。
- [ ] 不支援的 downgrade 條件明確拒絕；空 DB upgrade／`alembic check` 仍通過。

本次已比對 41 個應用表的 CHECK expressions，沒有差異；不要把 unnamed CHECK warning 再開成 constraint 遺失缺陷。

### WTG-23：把可決定性的通知測試從真實 push provider 測試拆開

**P2｜S｜FE＋QA｜S–M。**

**證據與影響。** `frontend/tests/live-push.spec.ts:8–16` 用 `E2E_PUSH_PROBE=1` gate 整個檔案，包括約第 148 行的 deterministic 模擬；一般 CI 未啟用此旗標，runner 只在 `--push` 設定。可在本機驗證的 generic notification、deep link、mark-read 也跟著被略過。

**建議修改。** 拆為例行 CI 必跑的 Service Worker／通知點擊／權限切換測試，以及需要外部 push service、browser permission 或 native banner 的選用驗收。分別呈現 executed、skipped、blocked，不把 optional 測試的存在算成 coverage。

**驗收條件。**

- [ ] 一般 CI 確實執行 deterministic push cases，刻意破壞 click handler 時會失敗。
- [ ] 鎖定畫面只有一般提醒，開啟後依當前身分取得內容；切帳不顯示舊資料。
- [ ] 真實供應商／背景通知案例清楚標為選用或人工驗收，保留獨立證據。

### WTG-24：在 CI 清除環境前保存可用且去識別的失敗證據

**P2｜S｜OPS＋QA｜S–M。**

**證據與影響。** Playwright 設定保留失敗 trace，但 `.github/workflows/ci.yml` 沒有 upload-artifact／服務 log 收集，最後會刪容器與 volumes。backend／browser jobs 也沒有明確 timeout 或 workflow concurrency policy；Safari job 已有 15 分鐘上限。

**建議修改。** 失敗時先收集經去識別的 Compose state／logs、Playwright report／trace、版本 manifest、測試與 skip 數、migration output，再 teardown。設短 retention 及適當存取權限；trace 的 URL、network、screenshot 可能含 session／invite／私人資料，不能假定密碼遮罩已涵蓋全部。依量測設 timeout、同 branch 舊 run 的取消規則。[S10]、[S11]

**驗收條件。**

- [ ] 故意讓一個隔離 E2E assertion 失敗後，可取得足以定位問題的 trace＋logs。
- [ ] artifacts 不含可重用憑證，teardown 即使收集失敗仍會執行。
- [ ] 新 push 取消適當的同 ref 舊工作，不取消無關 branch；每個 job 有合理時間上限。

### WTG-25：固定完整建置輸入，並建立持續更新機制

**P2｜S｜OPS｜M。**

**證據與影響。** Python 直接依賴已精確固定，但沒有完整 transitive resolution／hash lock。Docker base／service images 使用可變 tag，Actions 使用 tag；前端 frozen pnpm lockfile 已做得正確。同一 source 未必產生同一依賴圖或 image bytes。這是可重現性缺口，不是已確認應用 CVE。

**建議修改。** 使用適合專案的 resolver 產生 Python app／dev lock 與 hashes，明訂支援平台。發布記錄 image digest、依賴 manifest／SBOM；Actions 採目前平台支援的 workflow dependency lockfile，未能採用時使用經驗證的完整 commit SHA。依官方更新及自動 PR 持續維護，不能 pin 後永久不更新。[S10]

**驗收條件。**

- [ ] 兩次乾淨安裝有相同套件圖，intentional 更新產生可審查 lock diff。
- [ ] 每個 release 可追到 source SHA、image digest、migration head 及稽核日期／範圍。
- [ ] app、dev tooling、OS／container advisory 分開分級；例外有理由、擁有者與到期日。
- [ ] 不把本次 venv bootstrap pip 的 advisories 當成應用依賴漏洞，也不把 0 findings 稱為安全保證。

### WTG-26：提供可在新主機完成的還原、升級與秘密輪替手冊

**P2｜S／A｜OPS｜M；與 WTG-07、21、25 配合。**

**證據與影響。** README 說明備份及 throwaway restore drill，但沒有完整正式接管／回復流程。`compose.yaml:28` 的 invitation signing key 預設使用 DB password；只改 `.env` 的 `POSTGRES_PASSWORD` 不會改已初始化 PostgreSQL 角色的密碼。[S9] 若依預設改 DB 密碼，也會改邀請 replay key，舊邀請碼 hash 驗證仍可有效，但同鍵重新發邀請可能回 `INVITE_KEY_CHANGED`，見 `trips.py:431–436`。

**建議修改。** 寫出且演練：升級前備份、migration owner、失敗停點、恢復到新 volume、資料／ACL 驗證、切換、反向切換、版本相容性及舊 volume 保留。初始化獨立 invitation signing key，明訂輪替與 replay 相容性。保護並備份必要設定，包括 OAuth／VAPID、origin／provider 及簽章材料；不要把秘密放進一般 Git／CI artifacts。選定 RPO（允許資料落差）及 RTO（恢復時間）。

**驗收條件。**

- [ ] 只憑保留的 archive＋受保護設定，在新主機／新 volume 恢復授權、私人附件、帳務及登入。
- [ ] 記錄實際恢復時間、資料年齡及檢查結果；不只看到 restore command exit 0。
- [ ] 正常 DB 密碼輪替不使連線或無關 invitation replay 意外壞掉；疑似 key compromise 時要撤銷什麼有明文流程。
- [ ] 破壞性切換／刪舊資料步驟明確標示，由維護者在驗證後執行。

### WTG-27：區分回收窗口、永久刪除、歷史保存與備份到期

**P2｜S／A｜BE＋產品｜L。**

**證據與影響。** `trips.py:176–192,281–294` 與 `core.py:167–175` 提供 30 日復原窗口，但過期主要是不可再復原／不顯示，沒有 purge job。旅程附件 BLOB、過期 sessions、creation receipts、通知、歷史等缺少整體清理政策。長期下來資料庫與備份可能持續成長；隱藏記錄不等於實體刪除。

**建議修改。** 以資料種類建立 retention 表，列明目的、可見期限、復原期限、永久清理條件與備份剩餘期限。建立 bounded、idempotent、可 dry-run 的清理命令及排程，按 FK／關聯順序處理，紀錄處理筆數與失敗。財務及離團歷史要明訂匿名化／保留策略，不能為清理帳號直接破壞他人的帳務。receipt 的到期需配合 WTG-01 的可重試窗口。

**驗收條件。**

- [ ] 合成資料推進時間後，expired parent／child／BLOB 按政策清除，active data 不受影響。
- [ ] 重跑安全、分批中斷可續跑，並行 restore／purge 的邊界有定義。
- [ ] 使用者可理解「還能復原」「已永久刪除」「備份仍可能保留至何時」。
- [ ] 刪除歷史不破壞必要的 financial attribution／audit；若需保存，範圍及理由清楚。

這是產品及維運生命週期改善，不代表本次認定有法律違規。

### WTG-28：補 WebSocket 每身分連線及輸入速率預算

**P2，公開擴大使用前完成｜S／C｜BE｜M。**

**證據與影響。** `realtime.py:64–101` 沒有每使用者／session 的同時連線數及 ping 頻率限制，HTTP rate middleware 不會自動涵蓋 WS。每個 ping 會重新查身分；少量正常測試觀察到 25 個 ping 對應 25 次驗證查詢。這不是正式服務壓力測試，也沒有主張已造成 DoS。

既有 outbound queue 32、coalescing、send timeout、heartbeat、只接受 ping 的訊息類型限制及持續撤權驗證值得保留。改善是補輸入與連線預算，不是取消授權重查。[S12]

**建議修改。** 設每身分／session／旅程的合理連線上限、允許的 message type／size、heartbeat 最小間隔及 backoff。對超限有一致 close code，避免同步重連暴增。若只在記憶體統計，要清楚維持單程序適用範圍。

**驗收條件。**

- [ ] 正常多分頁協作不被誤殺；額外連線／不合理訊息被有界處理。
- [ ] Session 撤銷、離團、刪除旅程及正常 heartbeat 的原有權限測試仍通過；封存只影響列表，維持原有授權語意，不把封存當撤權。
- [ ] 在隔離環境證明連線與輸入工作量有上限，並可觀察目前連線及拒絕原因。

### WTG-29：讓使用者能撤銷其他裝置，並避免訪客所有權無法復原

**P2｜S／A｜BE＋FE｜M。**

**證據與影響。** `auth.py:41–60,157–170` 主要是目前 session 的登出及期限；沒有裝置列表／全部登出。`trips.py:317–337` 允許把所有權轉給訪客；若訪客清 Cookie 或失去裝置，缺少可恢復身分的產品流程。允許訪客本身是現有設計，不應直接移除。

**建議修改。** 提供不含 token 的 session metadata、目前裝置標示、撤銷其他裝置／全部登出。將訪客與正式帳號的復原差異說明清楚，轉交所有權時提示風險或要求接收者先連結可復原身分，依產品選擇。帳號合併後同步失效舊 session 與 UI。

**驗收條件。**

- [ ] 撤銷後舊 HTTP／WS 無法繼續，session 清單不洩漏 token 或完整識別資訊。
- [ ] 使用者無法撤銷別人的 session；合併後歸屬、通知及私人附件權限保持正確。
- [ ] 所有權轉交前能看懂復原風險，有明確且不靠維護者手改 DB 的正常路徑。

### WTG-30：依通知承諾決定是否加入 durable outbox

**P3；若承諾可靠提醒則 P2｜S／A｜BE｜M。**

**證據與影響。** `decisions.py:537–561`、`notices.py:171–202` 在資料 commit 後由 background task 發送 push，沒有持久化重試工作。程序在 commit 後停止可能漏掉推播，但站內通知已保存，不能描述成留言或核心通知資料一定遺失。

**建議修改。** 如果產品維持 best-effort push，文件及 UI 清楚描述即可；若要可靠提醒，與站內通知同 transaction 寫 outbox，加入 idempotent delivery、有限重試、下次執行時間、失效 subscription 清理及狀態。小專案可先用 DB outbox 與單一 worker，不必因此引入大型 queue 系統。

若維持 best-effort，驗收通知承諾與推播失敗時留言／inbox 的可用性；以下 durable delivery 條件只適用於選擇實作 outbox 的方案。

**驗收條件。**

- [ ] commit 後重啟可繼續處理未送工作；重試不重複建立站內通知。
- [ ] 永久失效訂閱與短期 provider failure 分開處理，無限重試不累積。
- [ ] 已撤權／換帳後的推播只顯示一般內容，點入再按當前權限讀取。
- [ ] 待送期間若相關裝置 session 撤銷、成員離團、旅程移入回收區或使用者關閉通知，發送前重查授權／偏好並略過不再符合條件的工作；一般通知文案不能取代此檢查。

### WTG-31：為費用更正及刪除保留可理解的歷程

**P2｜S／A｜BE＋FE｜M。**

**證據與影響。** `finance.py:147–155,248–305,331–338` 有 audit action，但未保留完整 before／after；修改會替換 split／payer，刪除採 hard delete。當多人確認過帳目後發生更正，難以回答誰改了哪個金額、為何餘額不同。這是協作可追溯性改善，不是目前金額計算錯誤的證據。

**建議修改。** 增加受權限控制的不可變 expense revisions 或 correction 記錄，保存必要欄位、actor、時間、版本及原因；UI 可查看差異。定義刪除與已結清資料的更正政策，必要時採 reversal／更正而不是靜默改歷史。不要不分權限地把私人備註／附件複製到公開 audit。

**驗收條件。**

- [ ] 修改金額、付款人、分攤、幣別／匯率及刪除可追溯，修改前後餘額符合既有不變量。
- [ ] 非授權成員看不到私密欄位，退出／合併後 attribution 仍正確。
- [ ] 版本衝突及重送不產生重複 revision，匯出能說明更正關係。

旅程主要幣別變更時保留既有 ledger currency 是既有明確測試的決策，不能把它報成自動換算失敗。

### WTG-32：建立符合小型部署的容量與資源預算

**P2｜S／A｜OPS＋BE｜M。**

**證據與影響。** Compose 沒有完整的 CPU／memory／pids／log-size budgets，README 沒有實測最低主機規格。附件放在 DB；API 解析、PostgreSQL、dump 及獨立 restore drill 可能同時占用資源。單檔／單旅程限制不代表全站總儲存與總實體資源有界。

**建議修改。** 以真實部署規模量測平時與「上傳＋備份＋還原驗證」高峰，建立最低／建議 RAM、磁碟、CPU、最大附件量、保留期及預留空間。合理設定 container limits、log rotation、工作佇列及帳號／旅程數量政策。先衡量 DB BLOB 的可接受規模，超出後才評估 object storage；搬移時必須保持 ACL 與備份一致性。

**驗收條件。**

- [ ] 在公布的最低規格重跑代表性 fixture，記錄 peak RSS、CPU、disk growth 及恢復行為。
- [ ] 可預先判斷的大小、配額、併發及佇列限制回可理解錯誤；硬體／container hard limits 保護宿主機，程序被終止時能被觀察及恢復，不能保證 OOM kill 還能回自訂錯誤。備份及 restore drill 的總資源被納入。
- [ ] 多旅程、回收資料、partial、logs 及備份保留都進容量估算，不只計 active files。

### WTG-33：逐步收斂部署權限及瀏覽器安全政策

**P2｜S／A｜OPS＋FE｜M；屬 hardening，不是已確認入侵。**

**證據與影響。** Compose 主要共用 default network，frontend／web 也可到 DB；一般頁面沒有完整 CSP／Permissions-Policy。API／frontend 已非 root，附件回應已有 sandbox CSP，TLS 明確交給外層代理，這些應保留。

**建議修改。** 分離 edge／app／data networks，按實際需求設定 capability reduction、`no-new-privileges`、可行的 read-only filesystem 及必要 writable paths。對 Next／Leaflet／圖片／OIDC 先觀察 CSP Report-Only，再收斂並 enforce；HSTS 放在實際 HTTPS edge，確認網域及子網域政策後才啟用。不要為了硬化切斷必要 provider 網路，或把 localhost HTTP 當 HTTPS 驗收。CSP Report-Only 的觀察與漸進啟用方式參見 [S15]；該 CSP3 文件仍屬 Working Draft，採用功能須核對目標瀏覽器。

**驗收條件。**

- [ ] web／frontend 無法直接到 DB，API、migration、backup 仍有必要連線，restore drill 保持隔離。
- [ ] 正常地圖、圖片、OAuth、WS、離線 shell、列印皆通過選定 CSP。
- [ ] 使用真正的公開 origin 驗證 TLS、Cookie、redirect 及 headers；記錄必要例外及理由。

### WTG-34：讓環境設定的範圍與跨層限制一致

**P2｜S／C｜OPS＋FE＋BE｜S–M。**

**證據與影響。** `frontend/Dockerfile:8–10` 接受 `NEXT_PUBLIC_TILE_URL` build ARG，但 `compose.yaml:42–45` 沒有映射 `build.args`；只把變數加進 `.env` 不會改前端 image。README 正確說明它是 build-time，問題是完整操作路徑不夠清楚，不是完全不支援自訂圖磚。

`files.py:34–37,98–121` 根據最多 10 檔及 `FILE_MAX_BYTES` 決定 request allowance；nginx `client_max_body_size` 固定 110 MiB。預設值相容，但將單檔改成 20 MiB 時，六個滿額檔案可超過代理限制。Compose 的 `/api/` 直接由 nginx 到 FastAPI，Next proxy limit 主要屬開發／替代路由，不能誤說兩者在正式預設路徑串接。

**建議修改。** 建立設定表：變數、預設、範圍、是否秘密、runtime／build-time、restart／rebuild 動作。若要支援 `.env` 圖磚設定，補 `build.args`，或提供正確 `docker compose build --build-arg ... frontend` 指令。統一 API／nginx／開發代理／前端顯示的單檔、批次及旅程額度；必要時自動分批且保持 operation 語意。

**驗收條件。**

- [ ] 自訂圖磚 URL 在重建後實際使用，設定不暴露秘密；runtime 變數與 public build 變數清楚區分。
- [ ] 預設及調高上限的多檔請求均經實際入口測試，顯示限額與可接受範圍一致。
- [ ] 代理 413 顯示合理訊息及修正方法，既有可讀錯誤處理保留。

### WTG-35：把驗收與維護知識整理成可持續使用的開發入口

**P2；歷史大型附件整理可 P3｜S／A｜全體｜M。**

**證據與影響。** 根目錄未見 LICENSE、SECURITY.md、CONTRIBUTING、changelog 或 dependency-update 設定。驗證命令分散，398 個歷史驗收檔混合舊錯誤與後續修正，容易把歷史失敗當成現況。遠端 branch protection／required reviews 無法從 ZIP 判斷，不能說成確定沒設定。

**建議修改。**

- 增加簡潔的開發入口與 `verify`／明確隔離的 `verify-live` 命令，列 prerequisites、執行套件、skip／blocked、清理及禁止連正式 DB 的邊界。
- 決定公開程式授權，加入漏洞回報方式、PR／review 規則、release notes、第三方資料與圖像來源說明；設定 dependency-update PR。
- 建立現況 evidence index，標 revision、日期、環境、實際執行結果、已修正／被取代關係及剩餘手動項目。舊證據保留原貌，不把它改寫成最新結果。
- 未來大型 traces／bundles 移到適當 CI／release artifacts，Git 保留精簡結論、必要 fixtures 及 checksums；不急著重寫 Git 歷史。
- 用少量 ADR 記錄單 worker、DB BLOB、離線 allowlist、幣別保存、訪客所有權及移除／復原語意，讓接手者理解取捨。

**驗收條件。**

- [ ] 新開發者依文件能完成乾淨啟動、一般驗證及隔離 live 測試，知道哪些仍未驗證。
- [ ] 每次 release 有單一最新狀態頁，舊 17／47 項紀錄不會被當成現在 63 項結果。
- [ ] 授權及貢獻政策已由擁有者選定；遠端 CI／review 保護有實際設定證據或標為待確認。

### WTG-36：提供可攜帶資料與明確的帳號生命週期

**P2｜S／A｜產品＋BE＋FE｜L。**

**證據與影響。** 目前有安全的行程列印／PDF 及本機離線快照，但沒有完整、版本化的旅程資料匯出與帳號刪除／退出資料政策。使用者若要移轉服務或處理長期不用的帳號，缺少明確入口。這是產品完整度建議，不是法律違規判定。

**建議修改。** 第一階段提供範圍清楚的 itinerary JSON／CSV 或 ICS，依需求逐步增加預算／費用及附件 manifest。全部由目前授權過濾，保留 schema version、時區、金額精度與 stable IDs。帳號刪除前處理仍持有的旅程、共用財務與歷史署名，區分退出、刪除個人資料及刪除共用旅程。CSV 依支援的試算表及用途處理公式注入，沒有適用所有下游工具的單一 escaping 策略；ICS 遵循日期／時區／換行規則。[S13]、[S14]

**驗收條件。**

- [ ] owner、member、booking passenger、guest 的匯出內容符合各自 ACL，不能因批次匯出擴大權限。
- [ ] JSON 有 schema version；CSV 的惡意公式樣式只作文字；ICS 跨時區／DST／全日行程可正確匯入。
- [ ] 大型匯出可取消或有工作上限，不影響正常 API；重試可追蹤且不重複工作。
- [ ] 帳號移除不讓旅程無主、不破壞其他人的分帳，備份剩餘保存時間可理解。

## 6. 值得新增的產品能力

以下是選擇性的產品提案。應先完成會影響資料與發布的項目，再用一趟真實小團體旅行驗證需求，避免同時增加太多模組。

| ID | 提案 | 最小可交付範圍 | 完成的判準 |
| --- | --- | --- | --- |
| X-01 | 第一趟旅程的引導 | 用輕量 checklist 串起建立旅程、邀請、選景點、排一天、記一筆帳；可略過 | 邀請新使用者實際操作，記錄在哪一步卡住；目標可設約 5 分鐘完成主要流程，但先量測再承諾 |
| X-02 | 更完整的唯讀示範 | 現有示範以 itinerary 為主；增加投票、清單、預算及分帳情境說明 | 無 OAuth 憑證也能理解核心價值；清楚標示示範資料、私人欄位規則及不可編輯狀態 |
| X-03 | 各模組搜尋與篩選 | 費用按類別／付款人／日期，任務按負責人／期限，附件按類型／關聯 | 先在代表性資料量驗證可找到目標；篩選跟 cursor pagination 契約相容，不先引進搜尋引擎 |
| X-04 | 可分享及可恢復的頁籤 URL | 以 allowlist 支援 `?trip=...&section=finance` 等，必要時加 day／item anchor | refresh／Back／Forward 保留位置；無效 section 有 fallback；網址本身不授權。現況來源：`Workspace.tsx:57–74`、`TripDetail.tsx:335–344` |
| X-05 | 離線副本的新鮮度及格式生命週期 | 保留既有儲存時間、清除及 allowlist，再加 stale 提醒、可選期限、schemaVersion／舊格式恢復 | 重新上線後可比較更新；格式損壞／空間不足可恢復；斷網無法立即確認遠端撤權的限制說明清楚；不擴大快取私人欄位 |
| X-06 | 目的地與時區輸入輔助 | 城市／IANA zone 選擇器，航班顯示起訖地的當地時間及明確 offset | 不以今天的裝置 offset 代替旅行當日目的地 offset；DST、跨日、沒有實際日期的規劃可理解 |
| X-07 | 出發前的可操作檢視 | 只列目前使用者可見的未完成任務、尚未確定預訂、時間重疊、待處理分帳 | 每個提醒能直接前往處理，避免只有漂亮數字；不向擁有者透露別人的私人任務／訂位欄位 |
| X-08 | 延伸既有安全複製為旅程起始範本 | 使用現有 trip copy 做可選的景點／日程／共用清單範本，先選範圍再建立 | 不複製乘客、訂位代碼、私人附件、個人清單或舊帳務；範本來源可辨識，與原旅程完全分離 |

### 暫不優先投入

- 現有單 worker 與 DB BLOB 在規模可接受時保留。只有實測容量或可用性需求成立，才安排 broker、多程序或 object storage。
- 自動行程規劃、AI 推薦、航班串接、完整即時聊天與大型 dashboard，先等核心旅程被真實使用。若後續加入生成式建議，須保留來源、使用者確認、成本預算及可撤回的變更，不自動改寫已確認的旅程。
- 原規格明訂的「付費功能開發中」提示，不列為程式缺陷。要改為隱藏或移除，先更新產品決策。
- 不把「測試覆蓋率達某個百分比」當成獨立目標；優先補會造成資料錯誤、權限擴張及復原失敗的狀態轉移。

## 7. 建議的實作順序與 PR 邊界

### 7.1 四個交付階段

| 階段 | 目標 | 主要項目 | 完成門檻 |
| --- | --- | --- | --- |
| A. 正確性與可恢復操作 | 同一操作不重複、選擇不錯綁、狀態錯誤可修復 | WTG-01–03、08–13、16、19、20 | 各缺陷有能證明修復的回歸案例；保留原有 ACL／版本／財務保護 |
| B. 可驗證的公開部署 | 真實代理、慢 DB、上傳及備份故障可控 | WTG-04–07、21、26、28、32–34 | PostgreSQL、完整代理鏈、容器換 IP、故障注入及新主機還原完成 |
| C. 持續維護及資料生命週期 | 升級與長期使用不累積不可控債務 | WTG-17–18、22–25、27、29、31、35–36 | 有效契約、帶資料 migration、retention、精簡現況證據及 release manifest |
| D. 產品體驗 | 提高實際完成旅程的效率 | WTG-14–15、30 及 X-01–08 的已驗證需求 | 用真實旅伴測試驗證改善；無障礙及私密規則仍通過 |

階段可以平行進行；公開部署前須完成對應 P1 條件，不必等所有 P3 建議。每個 PR 應只包含可獨立審查的一個行為變更，避免把 36 項塞進一次重構。

### 7.2 最先可開的六個 PR

| PR | 具體範圍 | 最關鍵驗證 |
| --- | --- | --- |
| PR-01 | WTG-08：結構化保存投票景點選項 | 同名地點選第二個仍是第二個 ID，採用後地址正確 |
| PR-02 | WTG-09：已刪除 adoption 的明確處理 | adopt → remove → adopt 不回不可見項目的假成功；一般 replay 仍唯一 |
| PR-03 | WTG-10：顯示 former passengers | 保留／移除原退出旅客，且 public-only 編輯不擴權 |
| PR-04 | WTG-01：共用 operation key／結果待確認處理，先落一條建立流程 | commit 後失去回應，重試回同一筆；新意圖可建立新筆 |
| PR-05 | WTG-01 後續：套用其餘 JSON creates，再以獨立 PR 補 multipart receipt | 完整操作清單逐項勾選，不能只修 TripForm 就宣稱全站完成 |
| PR-06 | WTG-02、19 的局部錯誤邊界，與後續解析隔離分開 | 預期 parser exception 不再是無 ID 的 500；非預期錯誤可追蹤且不暴露細節 |

WTG-20 是獨立且小型的初始化修正，可同步安排。WTG-04 的 DB execution model 較廣，先以一個完整 domain transaction 驗證方案，不能在其他業務 PR 中順便大量搬動所有 routes。

### 7.3 重要依賴

- 上傳進度／取消（WTG-16）依賴穩定 operation／receipt（WTG-01）；否則取消及重試會增加結果不確定性。
- 附件永久清理（WTG-11）、全站 retention（WTG-27）、帳號刪除／匯出（WTG-36）共用資料生命週期決策。
- API client generation（WTG-18）必須先補 response schema，不能直接從大量 `{}` 生成後聲稱型別安全。
- DB least privilege（WTG-21）必須同時調整 migration／restore（WTG-26），否則新角色無法升級。
- 多程序擴展必須先處理 WS hub、鎖／計數器及其他 process-local 狀態；現在不直接增加 Uvicorn workers。
- CI artifacts（WTG-24）需在失敗 cleanup 前保存，但先處理 redaction／存取範圍。

## 8. 開發者驗收矩陣

### 8.1 重要狀態與角色組合

| 情境 | 必測組合 | 期待結果 | 對應 |
| --- | --- | --- | --- |
| 不確定結果後重試 | JSON create、複製、multipart；同鍵同資料／不同資料／新意圖 | 同意圖唯一，新意圖可新增，修改 payload 不偷換舊結果 | 01、16 |
| 版本及租約衝突 | 同人兩分頁、兩人同改、lease 過期、背景刷新 | 409 不遺失草稿，不靜默覆蓋，安全重新取得 lease | 04、13 |
| 身分失效 | 登出、換帳、session 到期、BFCache、慢速舊回應 | 舊私人資料即時失效，不混入新帳號 | 03、19、29 |
| 旅程成員變更 | member 被移除、自己退出、owner 轉移、guest 合併 | HTTP／WS 與 UI 一致，歷史歸屬與所有權仍正確 | 03、10、29 |
| 預訂私密欄位 | creator、列名旅客、非旅客 owner、一般 member、退出 creator | 各自只取得既有授權欄位，public-only edit 不改私密欄位 | 10、18、36 |
| 附件多重關聯 | private／shared、可見／不可見關聯物件、回收、restore、purge | 保留現有關聯交集權限，不因新功能放寬；配額與 ACL 正確 | 02、11、27、36 |
| 投票狀態 | 同名 place、secret round、reopen、adopt／remove／adopt | 身分不靠名稱還原，輪次／秘密性維持，再採用可理解 | 08、09 |
| 日期與時區 | leap day、月底 recurrence、DST、跨日、最大邊界、未定日期 | 無溢位 500、不靜默移動時刻，前後端同規則 | 12、14、X-06 |
| 財務 | 多付款人、部分分攤、尾差、多幣別、部分還款、退出／合併、修改／刪除 | 原有金額不變量及權限不退步，新 revision 可追溯 | 01、04、18、31 |
| 慢 DB／鎖等待 | 一旅程持鎖，另一旅程 HTTP／WS，有限 timeout | 無全站 event loop 停頓，錯誤可追蹤，可安全重試 | 04、17、19 |
| 大型集合 | 分頁中新增／刪除、重連、事件 burst | 不漏／不重複，不全量重刷無關模組，資源有界 | 17、28、32 |
| 離線生命週期 | opt-in、fresh tab、斷網、過期快照、schema 變更、登出、storage 壞資料 | 只含 allowlist，清除及恢復可用，明示新鮮度 | 03、X-05 |
| 升級及還原 | 空 DB、帶資料前版、SQLite／PG、restore 至新 volume | schema／bytes／ACL／財務一致，錯誤有停點及回復方法 | 21、22、26 |
| 真實入口設定 | 雙 proxy、不同 client IP、偽造 forwarded header、container 換 IP、提高檔案上限 | 信任邊界、限流、DNS 與可接受大小一致 | 05、06、34 |
| 備份故障 | DB 不可達、不可寫、容量不足、損壞 archive、沒有備份、過期備份 | 可見 unhealthy 狀態，不累積 partial，成功後恢復 | 07、26、32 |
| 鍵盤及螢幕閱讀器 | 手機 drawer、切換、對話框、附件、衝突、表單錯誤 | 可完成任務、焦點可預期、狀態可被讀出 | 13、15、16 |

### 8.2 每個修正 PR 的 Definition of Done

- [ ] 指明 WTG 編號、原問題、選擇的語意及不涵蓋範圍。
- [ ] 若是缺陷，新增最小且有意義的失敗案例，驗證修正後行為；不為純文件／格式修改添加鏡像測試。
- [ ] 驗證授權、版本、交易、金額或刪除語意有沒有受影響，必要時補狀態轉移測試。
- [ ] 若改 DTO／DB／設定／操作流程，同步更新 schema、migration、文件及適用的復原說明。
- [ ] 列出本次實際執行的測試、環境及結果，分開 failed、skipped、blocked；不沿用舊報告當新證據。
- [ ] 由另一位開發者 review；是否要求遠端 branch protection 由 repository 管理者確認。

## 9. 發布前門檻與重跑方式

### 9.1 面向小團體真實使用的發布清單

- [ ] 已確認資料正確性缺陷完成對應修正，未完成者有明確的影響、owner 及處置。
- [ ] 在可用 Chromium 上重跑本次被阻擋的 12 個案例，另跑約定的 Firefox／WebKit／native Safari 子集，記錄實際執行數。
- [ ] PostgreSQL fresh install 與帶資料前版升級通過；還原後 private file bytes、links、ACL 及財務不變量通過。
- [ ] 以實際 HTTPS origin 驗證 Google callback、Secure cookies、WS、雙來源 IP 限流及不可信 forwarded headers。
- [ ] API／frontend 換 IP 後代理恢復；預設及提高 upload limit 的入口測試通過。
- [ ] 最新備份及 restore drill 有成功證據，故障／過期可被看見，重要設定已受保護；跨主機恢復時間有紀錄。
- [ ] 公開不可信上傳前，PDF 錯誤映射、解析資源及 WS／一般資源 budgets 已驗證。
- [ ] release manifest 列 source SHA、lock／image inputs、migration head、已知限制、手動／外部未完成項目與回復方法。

不必以所有產品加值項目為發布門檻。對僅供本機展示的版本，可明確保留某些部署風險；一旦開始保存真實旅伴資料，就需啟用對應的備份、復原及隱私要求。

### 9.2 安全的日常驗證命令

以下是供開發者重跑的入口，須使用專用測試環境。先依 README 安裝指定的 Python／Node／pnpm 及依賴；不要在 shell 保留指向正式資料庫的 `DATABASE_URL`／`TEST_DATABASE_URL`。

後端，在 `backend/` 及已啟用的開發 venv 執行：

```bash
task_review_dir="$(mktemp -d)"
export DATABASE_URL="sqlite:///$task_review_dir/review.db"
export PUBLIC_ORIGIN="http://localhost:3000"
unset TEST_DATABASE_URL

python -m ruff check .
python -m ruff format --check .
python -m pytest -q
alembic upgrade head
alembic check
```

`mktemp -d` 產生的絕對路徑在上方組成有效的 SQLite URL。這只驗證拋棄式 SQLite；正式 PostgreSQL 的 row locks、migration 與 restore 須另用獨立測試 DB，不可用這組結果替代。

前端，在 `frontend/` 執行：

```bash
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm format:check
pnpm test
pnpm build
pnpm audit --prod
```

已安裝可用瀏覽器及測試 prerequisites 後，在專案根目錄執行隔離驗收：

```bash
python backend/run_live_acceptance.py --production
```

若指定 `CHROME_EXECUTABLE`，須確認是實際可執行且含 core binary 的瀏覽器，不只是同名 wrapper。Native Safari、外部 push、Google 真實授權及 Compose／PG 仍有獨立 prerequisites；以 runner 現有說明設定，不把缺少服務的 skip 視為通過。Playwright CI 設置可參見 [S11]。

### 9.3 本次額外觀察的最小證據摘要

| 觀察 | 實際輸出／結果 | 解讀限制 |
| --- | --- | --- |
| 新增 POST 重試 | `sameBody=true`，`sameIdempotencyKey=false` | 執行實際 helper 的模擬回應遺失，非所有流程端到端測試 |
| 同名景點 | `selectedId=second-cafe`，`submittedId=first-cafe` | 執行實際 CreatePoll handler，非重新寫一份邏輯來推測 |
| 已退出航班旅客 | 原資料含座位／行李，實際 LegFields render 未呈現 | React server render，未完成瀏覽器互動重測 |
| 再採用已刪除活動 | HTTP 200，同 item ID，`is_deleted=true`，active count 0 | 使用隔離 API＋SQLite 合成資料 |
| 日期上溢 | 建立 201，之後讀 days 500，無 request ID | 單一極端邊界，不推論一般日期失敗 |
| 列表 SQL | 20 trips：83；20 tasks：46 | 含 auth／ACL，非 production latency benchmark |
| PDF 解析限制 | 74,535-byte fixture 回 500；peak RSS 247,588 KiB | 單次有資源邊界的隔離程序；pypdf 已有自己的解壓縮限制 |
| `.env` | `umask 022` 時產生 `0644` | 本機可讀性還取決於父目錄及部署帳號 |
| 瀏覽器 | 12 cases 在 launch 階段受阻 | 0 個 browser workflow 完成，不是 12 個產品失敗 |

本文件不附秘密、特殊解析 payload 或可重用憑證。修復測試優先使用一般合成資料、exception injection 及拋棄式環境。

## 10. 排除項目、待確認決策及交接 Prompt

### 10.1 不應重新列為已確認缺陷的事項

1. 已有穩定 request_id 的 Finance、邀請重試，不屬於「完全沒有冪等」；WTG-01 針對其餘呼叫與 multipart。
2. `TripFile.data`／`preview_text` 為 deferred，metadata 列表沒有一次讀出所有原檔的證據。
3. in-memory WS hub 配合單 worker 是明示限制，尚未部署多程序時不算跨程序同步 bug。
4. pypdf 有解壓縮限制，WTG-02 是應用例外處理與工作資源邊界不足。
5. SQLite 的 users／poll_rounds CHECK warning 經實際比對並未遺失約束。
6. 原資料模型的 8 項名稱差異已在 v1.1 對照文件接受，不是 8 個新缺陷。
7. ProfileForm 的版本衝突、離線 fresh-tab、鍵盤移動行程、Modal 焦點及部分對比問題已有修正；應延伸正確模式。
8. Native Safari 有歷史證據，跨瀏覽器 runner 也有傳 `--browser=...`，不是所有引擎意外都跑 Chromium。
9. 未觀察到可直接證實的私人附件／訂位代號授權繞過；新功能仍需維持原 ACL。
10. 前端 production audit 未命中應用弱點；單看 manifest 下限或工具環境 pip 警告都不能直接下應用漏洞結論。

### 10.2 需由產品／維護者明訂的決策

| 決策 | 建議預設方向 | 影響項目 |
| --- | --- | --- |
| 公開服務或僅自用／展示 | 先以受控小團體使用驗證；公開前完成對應 P1 | 02、04–07、28、32–33 |
| 已刪除 adoption 再採用 | 明確提示原項目已移除，提供有授權的復原或重新建立 | 09 |
| 日時區更改 | 操作前說明保留 local time 或 instant，不靜默變更 | 14、X-06 |
| 永久刪除及保留期限 | 先列 active／recycled／history／backup 四種狀態 | 11、27、31、36 |
| 訪客可否持有唯一 owner | 保留低門檻加入，轉交前要求清楚風險提示或可復原身分 | 29 |
| 推播是否有送達承諾 | 先明示 best-effort；需要可靠提醒再加 outbox | 30 |
| 最低主機、RPO／RTO | 以測試量測決定，不沿用未量測的「足夠快／可還原」 | 07、26、32 |
| 匯出範圍及授權方式 | 先小範圍、server-side allowlist，不能讓匯出增加閱讀權限 | 18、36 |

### 10.3 可直接交給開發者的後續 Prompt

```text
請以 WayToGo_Workspace_Review_2026-11-26.md 為審查基準，
先確認目前 HEAD 與 aac83bd 的差異，避免重做已修復項目。

第一批只處理 WTG-08、WTG-09、WTG-10，分成可獨立審查的變更。
先重現目前行為，再實作最小修正及有意義的回歸測試。
保持既有 ACL、訪客／退出成員歷史、版本檢查、財務與離線規則。
不要進行與這三項無關的大型重構。

每項交付請提供：
1. 根因與採用的產品語意。
2. 修改檔案及主要行為差異。
3. 實際執行的測試與結果，區分 passed、failed、skipped、blocked。
4. 尚未驗證的真實瀏覽器／PostgreSQL 情境。
5. 精簡 PR 說明、相容性與回復方式。

完成後，再提出 WTG-01 的共用 mutation／receipt 設計與逐模組落地順序，
特別處理 server commit 後失去回應，以及結果待確認時修改草稿的情境。
```

## 11. 官方與第一手參考資料

以下來源於 2026-11-26 查核，用來支持框架、部署及驗收方法。專案缺陷的直接證據仍是上述 `aac83bd` 原始碼與本次實際觀察；外部文件不代表已在此專案完成相同驗收。

| 代號 | 官方／第一手來源 | 對應用途 |
| --- | --- | --- |
| S1 | [FastAPI：Concurrency and async / await](https://fastapi.tiangolo.com/async/) | 同步函式與 async 路由的執行模型 |
| S2 | [pypdf 官方 repository：Extract Text](https://github.com/py-pdf/pypdf/blob/main/docs/user/extract-text.md) | 文字解析與記憶體成本，不能以最終字數取代解析預算 |
| S3 | [nginx：ngx_http_realip_module](https://nginx.org/en/docs/http/ngx_http_realip_module.html) | 可信代理與 client address |
| S4 | [Docker Compose：Networking](https://docs.docker.com/compose/how-tos/networking/) | 容器重建與 IP／名稱解析 |
| S5 | [nginx：ngx_http_upstream_module](https://nginx.org/en/docs/http/ngx_http_upstream_module.html) | upstream resolve、resolver 及版本相容性 |
| S6 | [OWASP：File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) | 檔案驗證、上傳及解析資源限制 |
| S7 | [W3C WAI-ARIA APG：Dialog Modal Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) | modal 焦點與鍵盤互動 |
| S8 | [FastAPI：Response Model](https://fastapi.tiangolo.com/tutorial/response-model/) | response schema、驗證及欄位過濾 |
| S9 | [Docker Official Image：Postgres](https://hub.docker.com/_/postgres) | 初始化 superuser 及 existing volume 的環境變數語意 |
| S10 | [GitHub Actions：Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use) | workflow dependencies、最小權限及秘密處理 |
| S11 | [Playwright：Setting up CI](https://playwright.dev/docs/ci-intro) | CI 瀏覽器安裝及測試 artifacts |
| S12 | [OWASP：WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html) | 連線／訊息限制與持續授權 |
| S13 | [OWASP：CSV Injection](https://community.owasp.org/attacks/CSV_Injection) | 匯出至試算表時的公式處理及相容性限制 |
| S14 | [RFC Editor：RFC 5545 iCalendar](https://www.rfc-editor.org/info/rfc5545/) | ICS 日期、時區、格式；實作時一併查閱該頁列出的更新 |
| S15 | [W3C：Content Security Policy Level 3](https://www.w3.org/TR/CSP3/) | Report-Only 與漸進啟用；目前文件為 Working Draft |

[S1]: https://fastapi.tiangolo.com/async/
[S2]: https://github.com/py-pdf/pypdf/blob/main/docs/user/extract-text.md
[S3]: https://nginx.org/en/docs/http/ngx_http_realip_module.html
[S4]: https://docs.docker.com/compose/how-tos/networking/
[S5]: https://nginx.org/en/docs/http/ngx_http_upstream_module.html
[S6]: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
[S7]: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
[S8]: https://fastapi.tiangolo.com/tutorial/response-model/
[S9]: https://hub.docker.com/_/postgres
[S10]: https://docs.github.com/en/actions/reference/security/secure-use
[S11]: https://playwright.dev/docs/ci-intro
[S12]: https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html
[S13]: https://community.owasp.org/attacks/CSV_Injection
[S14]: https://www.rfc-editor.org/info/rfc5545/
[S15]: https://www.w3.org/TR/CSP3/

---

## 12. 工作區補充回饋與驗收依據

### 12.1 交付與判讀方式

2026-11-26（Asia/Taipei），工作區 `main` 的完整 HEAD 為 `aac83bda1d580e8000f62d953a829ab9f65dcd7a`，開始核對時工作樹乾淨。本次依使用者確認只交付這一份文件。產品要求取自現行 PRD／SRS，實體儲存沿用擁有者核定的 v1.1 對照。附件提供審查問題與驗收方法。第 10.3 節保留的是歷史 Prompt 範例，其中的檔名指原審查；本次工作區交付檔名是 `WayToGo_Feedback.md`。[需求規格](../spec.md) · [八項資料模型對照](../data-model.md)

| 處理結果 | 本次適用範圍 |
| --- | --- |
| 本次完成並驗證 | 本檔的 36 項 WTG、8 項選用提案、版本來源與驗收條件；文件檢查見 §12.5。 |
| 先前已修復且本次確認 | §12.4 指定的子行為。確認依據為現行來源、已有案例及帶日期的歷史紀錄。 |
| 已修改但驗證受阻 | 本次沒有此類產品修改。部署環境檢查受阻另列於 §12.5。 |
| 不適用 | 純文件交付的 schema、migration、部署切換及新增回歸測試。 |
| 不在本次範圍 | 以下各列的程式修正、產品擴充、正式環境驗收與發布。右欄是日後的結案標準。 |
| 待決策 | 標記待決策的項目須由產品或維護者決定語意、受眾或營運門檻，見 §12.4。 |

<a id="wtg-matrix"></a>

### 12.2 需求／WTG 對照表

優先度與 E（原審查執行觀察）、S（來源）、C（條件性風險）、A（提案）沿用 §3.1。P1* 僅在該列部署或使用條件成立時作發布門檻。原規格欄指向直接需求或最接近的既有約束，未明訂的新設計仍屬提案。FR／BR／AC、里程碑及功能 P0／P1 有各自的定義。以下的來源均在同一個 `aac83bd` 核對；本表中的「確認」指資料流、現行設定或文件缺口可以定位，原 E 的執行證據仍屬 §2.2、§9.3。每列最後一欄併用 §8.1 的角色及狀態組合。

#### 01–10　重試、部署與旅程內容

| 項目 | 原規格 | 優先度與證據 | 本次判讀 | 現況與查核位置 | 日後驗收條件 |
| --- | --- | --- | --- | --- | --- |
| WTG-01 | §8、FR-TRIP-08、FR-FILE-02 | P1 · E/S | 確認缺陷 | 一般 POST 每次新建 UUID。複製旅程的後端已有 receipt，前端未沿用鍵。附件兩端均缺批次識別。財務與邀請已有各自的穩定鍵。[API](../../frontend/lib/api.ts#L21) · [複製](../../backend/app/trip_copy.py#L76) · [附件](../../frontend/components/Attachments.tsx#L44) | 逐一模擬旅程、景點、活動、投票、留言、任務、預訂、複製及三檔上傳提交後回應遺失。同鍵同內容僅一筆、異內容拒絕，明確新意圖可新增。核對原始 ID、配額、交易與 ACL。 |
| WTG-02 | FR-FILE-01/02、§8 | P2，公開不可信上傳前 P1* · E/S | 確認缺陷；部署門檻有條件 | PDF 首頁擷取後才截短文字，應用的預期例外清單未涵蓋函式庫的限制例外。解析使用共用執行緒池。[格式檢查](../../backend/app/file_formats.py#L104) · [解析入口](../../backend/app/files.py#L128) | 以普通檔案及例外注入檢查狀態、錯誤碼、Request ID 與整批回滾；部署另驗一般讀取仍前進、逾時工作可回收。無預覽時是否保留原件待定。 |
| WTG-03 | FR-AUTH-06、FR-OFFLINE-01 | P2 · S | 確認前端缺口 | 首頁有同分頁請求序號，通知在重獲焦點時更新，但錯誤時可保留舊內容。旅程 WS 會重新授權。跨首頁分頁缺統一身分切換處理。[首頁](../../frontend/components/Workspace.tsx#L165) · [通知](../../frontend/components/NoticeCenter.tsx#L55) | 兩分頁登出或換帳，再驗自然到期、返回快取頁與舊回應晚到。先前的旅程、通知與離線私有資料均須按身分失效；單純斷網仍能使用允許的離線資料。 |
| WTG-04 | §5.1、§6.2–6.3、FR-COLLAB-07 | P1*（公開多人使用／慢 DB）· S/C | 條件性風險 | 單 worker、同步 Session；部分 async 路由同步等待資料庫。WS 身分重查已使用 threadpool。部署中的阻塞幅度待測。[引擎](../../backend/app/core.py#L80) · [財務修改](../../backend/app/finance.py#L322) · [WS](../../backend/app/realtime.py#L64) | 在專用 PG 讓同旅程交易等待鎖，另測其他旅程 HTTP、WS 心跳及逾時；同時核對 rollback、版本、金額及 commit 後廣播。 |
| WTG-05 | §5.2 限流 | P1*（前置 TLS 代理公開部署）· S/C | 條件性風險 | nginx 由直接對端重寫客戶端地址，API 按 client.host 計數；前置 TLS proxy 拓撲會影響辨識。[nginx](../../deploy/nginx.conf#L16) · [限流](../../backend/app/main.py#L118) | 在實際信任邊界，以兩個來源分別驗限額、非信任來源標頭不改身分、HTTPS cookie、WS 與 OAuth callback。須有部署方確認的代理拓撲。 |
| WTG-06 | §5.1、§9 里程碑 1 | P1*（仰賴容器反覆部署更新）· S/C | 條件性風險 | nginx 指向固定名稱的 upstream；README 有只重建 API 的流程。容器替換是否改 IP 取決於部署。[代理路由](../../deploy/nginx.conf#L19) · [部署說明](../../README.md#L35) | 記下更新前後不同的 IP 與映像，在選定的解析或 reload 流程下驗首頁、health、授權 API、WS 重連、中斷時間及回復。 |
| WTG-07 | §5.4 | P1* · S | 確認維運缺口；保存真實資料時為門檻 | 成功備份才輪替，失敗的暫存檔及備份／還原新鮮度缺完整處理；已有獨立還原演練。[備份](../../deploy/backup.sh#L5) · [還原](../../deploy/restore-drill.sh#L73) | 以專用儲存驗寫入失敗、空間不足、損壞或過期備份，以及恢復後的新成功紀錄。保留最後可用備份。允許的備份年齡及告警責任待定。 |
| WTG-08 | FR-VOTE-01/03/10 | P2 · E | 確認缺陷 | 選第二個同名景點後只保存名稱，送出時依名稱取第一筆；重開投票的後端已保留選項 ID。[建立選項](../../frontend/components/Decisions.tsx#L179) · [重開](../../backend/app/decisions.py#L442) | 兩個同名異址地點經新增、補選項、改顯示文字、重投及採用，沿用各自 ID、地址；手打同名文字仍可沒有景點關聯。 |
| WTG-09 | FR-VOTE-10/11、BR-008、AC-013 | P2 · E | 確認缺陷；再採用方式待決策 | 已採用紀錄直接回原活動 ID；移除活動採軟刪除，可能回傳目前看不到的活動。[採用](../../backend/app/decisions.py#L455) · [移除](../../backend/app/planning.py#L698) · [既有測試](../../backend/tests/test_decisions.py#L62) | 一般重送維持唯一；採用→移除→再採用需有明確結果。另驗移日、景點回收、原建立者離團、併發及 ACL。由產品選擇提示衝突、授權復原或重建。 |
| WTG-10 | FR-BOOK-01/02/05、AC-015 | P2 · E | 確認缺陷 | 航段表單只列現役成員。後端讀取依旅客身分過濾，可保留既有退出旅客；公開編輯有獨立入口。[航段欄位](../../frontend/components/Reservations.tsx#L162) · [私密欄位](../../backend/app/preparations.py#L419) · [公開編輯](../../backend/app/preparations.py#L545) | 建立者可辨識、保留或明確移除原退出旅客；單改標題保留座位行李。驗陌生人、新增旅客限制及兼任旅客／非旅客的 owner 各自可見欄位。 |

#### 11–20　資料邊界、表單與 API

| 項目 | 原規格 | 優先度與證據 | 本次判讀 | 現況與查核位置 | 日後驗收條件 |
| --- | --- | --- | --- | --- | --- |
| WTG-11 | FR-FILE-04/05/06、BR-013 | P2 · S | 確認容量缺口；永久清理待決策 | 回收資料仍計入旅程配額，只有回收／還原入口。30 日規定適用旅程。[配額](../../backend/app/files.py#L187) · [回收與還原](../../backend/app/files.py#L265) | 政策確定後核對使用中、回收、總用量與實際可再上傳容量；含關聯附件、併發、重試、還原及上傳者權限。資料庫檔案縮小另行量測。 |
| WTG-12 | FR-TRIP-02/03、FR-PLAN-01/02、FR-DATE-05、FR-TASK-06 | P2 · E/S | 確認缺陷；部分輸入語意待決策 | 建立／延長日數有 3660 天限制；每日日期以加法求值，單獨增日未沿用整體限制，週期計算也有年份邊界。[旅程](../../backend/app/trips.py#L161) · [每日日期](../../backend/app/planning.py#L524) · [任務週期](../../backend/app/preparations.py#L286) | 以最大日期加一天、最大日數再增日、閏日、月底／年底及既有異常資料驗讀寫。拒絕時整筆不變；保留無日期及僅開始日，僅結束日的契約待定。 |
| WTG-13 | FR-COLLAB-03–06、AC-007–009、§5.3 | P2 · S/A | 確認部分缺口；恢復介面屬提案 | 旅程表單固定初始版本；個人暱稱已有保留輸入並重讀的流程。後端已有版本及鎖保護。[旅程表單](../../frontend/components/TripForm.tsx#L18) · [暱稱](../../frontend/components/ProfileForm.tsx#L34) | 兩頁互改旅程、費用、預訂，分別驗舊版 409 與租約失效。應能辨識草稿與最新值、明確重套或放棄，背景更新不可覆蓋輸入。 |
| WTG-14 | §9 里程碑 3、§8、FR-PLAN-09、FR-DATE-05 | P2 · S/A | 規格歧義；待決策 | 里程碑寫「每日行程 CRUD」，API 表只列取得／新增日；現有活動可以修改、移除。修改旅程日期應保留行程。[日層級路由](../../backend/app/planning.py#L530) · [規格](../spec.md#L616) | 先釐清日與活動的 CRUD、權限與版本；才驗改標題、刪空日、非空日關聯及重編。DST、無日期時，須明定保留當地鐘面或同一瞬間。 |
| WTG-15 | §5.3、§9 里程碑 5 | P2 · S | 確認無障礙缺口 | 手機側欄按鈕未揭露展開狀態；部分業務切換只改樣式。既有對話框與收起側欄的焦點保護有各自範圍。[側欄](../../frontend/components/Workspace.tsx#L393) · [切換](../../frontend/components/Reservations.tsx#L490) · [舊複驗](accessibility-checks.md) | 依 modal 或 disclosure 的選擇，在手機／桌面用鍵盤與讀屏驗展開、選取、Escape、焦點返回；於有資料的表單補查 busy 與錯誤。 |
| WTG-16 | FR-FILE-02/06、FR-COMMENT-05、§5.3 | P2 · S/A | 確認狀態缺口；草稿清理待決策 | multipart 上傳期間可關閉視窗；介面對非 JSON 413 已有可讀訊息，尚缺確認結果與安全重試。留言草稿檔之後才綁定。[上傳](../../frontend/components/Attachments.tsx#L44) · [檔案關聯](../../backend/app/file_access.py) | 先驗 01 的批次冪等，再驗慢速、關閉後重開、取消、提交後回應晚到、額度超限。中止等待仍需確認伺服器結果；草稿清理不得波及已關聯內容。 |
| WTG-17 | §5.1、FR-COLLAB-07 | P2 · E/S | 確認查詢放大；實際效能影響待測 | 列表逐旅程／任務補查，部分事件仍廣泛刷新；即時層已有事件合併與分流。檔案原始內容採延遲載入。[旅程摘要](../../backend/app/trips.py#L102) · [任務](../../backend/app/preparations.py#L107) · [刷新](../../frontend/components/TripDetail.tsx#L131) | 同一合成資料分別取 20、100 筆，比查詢數、payload、耗時；另驗分頁期間增刪、私人任務 ACL、事件集中到達及斷線後收斂。 |
| WTG-18 | §8、FR-BOOK-05、BR-013 | P2 · E/S | 確認契約缺口 | 多數 JSON 回應形狀未明訂；前端 api<T> 以型別斷言傳回資料。本次靜態計數見 §12.5。[前端 client](../../frontend/lib/api.ts) · [訂位序列化](../../backend/app/preparations.py#L419) | 驗主要回應與錯誤的具體型別、欄位可空與版本相容；以建立者、列名旅客、非旅客 owner、一般成員分別核對欄位。是否產生 client 是實作選擇。 |
| WTG-19 | §8、§5.2 | P2 · E/S | 確認缺陷 | 已知錯誤有結構化處理；未預期例外可跳過加上 Request ID 的 middleware 返回路徑。代理與 API 關閉一般 access log。[錯誤處理](../../backend/app/main.py#L50) · [middleware](../../backend/app/main.py#L128) · [nginx](../../deploy/nginx.conf#L9) | 隔離環境注入一般例外，核對各類 4xx 與 500 的錯誤碼、ID、去識別記錄；代理提前拒絕的 413 另驗。健康檢查與備份狀態各自判讀。 |
| WTG-20 | §5.2、AC-020 | P2，共享主機存正式憑證時 P1* · E | 確認初始化權限缺口 | 以獨占建立防覆寫，新檔模式受 umask 影響。附件在 POSIX umask 022 觀測為 0644。可讀範圍也取決於父目錄權限。[初始化](../../deploy/init_env.py#L8) · [測試帳號](../../deploy/create_test_login.py#L32) | 以隔離假設定測新檔 0600、既有檔案內容與權限不變、失敗不殘留；Windows 部署另驗 ACL。 |

#### 21–30　維運、資料保存與通知

| 項目 | 原規格 | 優先度與證據 | 本次判讀 | 現況與查核位置 | 日後驗收條件 |
| --- | --- | --- | --- | --- | --- |
| WTG-21 | §5.2/5.4、§6.2、§9 里程碑 1 | P2 · S | 確認部署權限共用；拆分屬改善 | Compose 初始化、API 與備份使用同一資料庫使用者；API 啟動時也執行 migration。既有 volume 的角色權限須實查。[服務身分](../../compose.yaml#L7) · [API 啟動](../../backend/Dockerfile#L11) | 若拆分角色，從空庫及舊 volume 驗升級、runtime 業務讀寫、拒絕 DDL、備份與還原；連同 26 的復原路徑驗新表權限。 |
| WTG-22 | §7、§9 里程碑 1、§5.4 | P2 · S | 確認持續驗證缺口 | 測試 fixture 直接建立最終 schema，例行 CI 從空庫升級。先前曾在 SQLite、PG 驗 0009→0010 的既有帳戶。[fixture](../../backend/tests/conftest.py#L43) · [CI](../../.github/workflows/ci.yml) · [歷史 R01](round2-review.md#L7) | 從已支援的前版植入代表資料再升級，在兩種資料庫比對暱稱版本、私人檔案 hash／ACL／關聯、財務及歷史身分；記明可支援的降版或還原方式。 |
| WTG-23 | FR-NOTIFY-01/02、§9 里程碑 5 | P2 · S | 確認測試缺口 | 模擬通知點擊與真實供應商案例共用 opt-in 開關。已有歷史裝置接收紀錄，原生橫幅點擊有獨立驗收需求。[測試開關](../../frontend/tests/live-push.spec.ts#L8) · [執行器](../../backend/run_live_acceptance.py#L269) | 例行 CI 應能證明模擬事件、定位與已讀有執行；換帳後不得顯示舊內容。另列真實供應商、背景裝置及原生點擊各自的執行狀態。 |
| WTG-24 | §5.2、§9 里程碑 1/5 | P2 · S | 確認 CI 證據缺口 | Playwright 設定 retain-on-failure，隔離 runner 額外指定 --trace=off；CI 清除容器前缺持久化、去識別的失敗證據，Safari job 已有限時。[設定](../../frontend/playwright.config.ts#L10) · [runner](../../backend/run_live_acceptance.py#L269) · [CI](../../.github/workflows/ci.yml) | 在獨立測試 run 驗失敗時先保存可用證據、檢查憑證與隱私資料已排除，再清理；同分支取消與各 job 時限須可觀測。 |
| WTG-25 | §9 里程碑 1/5 | P2 · S | 確認發布輸入缺口 | Python 直接依賴精確釘版，前端有 frozen lock；Python 間接依賴、容器與 workflow 的可變標籤仍影響重現性。[後端依賴](../../backend/requirements.txt) · [前端建置](../../frontend/Dockerfile) · [CI](../../.github/workflows/ci.yml) | 同版兩次乾淨安裝比對依賴圖，發布紀錄串起 SHA、鎖檔、映像 digest、migration head 與稽核日期。分開應用、工具及 OS 稽核結果。 |
| WTG-26 | §5.4、FR-INV-04/05、§9 里程碑 1 | P2 · S/A | 確認手冊缺口；維運目標待決策 | 目前有隔離 restore drill，正式切換、反向切換、異機接管仍缺演練。邀請簽章預設沿用 DB 密碼，影響既有邀請重送。[設定](../../compose.yaml#L28) · [邀請重送](../../backend/app/trips.py#L431) · [還原說明](../../README.md#L99) | 以受保護設定和備份在全新 volume／主機驗登入、金額、檔案 bytes 與 ACL；另演練兩種金鑰輪替及回復。記實測資料年齡、耗時，RPO/RTO 由維護者定。 |
| WTG-27 | FR-TRIP-07、FR-FILE-05、FR-FIN-09、§5.4 | P2 · S/A | 待決策 | 旅程有 30 日可復原窗口；備份預設每日、成功後輪替超過七日的舊檔。資料庫內各類資料的永久清除條件仍待定。[旅程回收](../../backend/app/trips.py#L281) · [可見性](../../backend/app/core.py#L167) · [備份](../../deploy/backup.sh) | 決策表分列使用中、回收、歷史及備份；政策核定後驗批次重跑、恢復與清理競爭、檔案關聯、財務署名及 receipt 可重試窗口。 |
| WTG-28 | §5.1/5.2、FR-COLLAB-07、BR-003 | P2，公開擴大使用前提高 · S/C | 條件性風險 | WS 有輸出佇列 32、合併、傳送逾時與持續授權；身分連線數及輸入預算缺上限。[連線與佇列](../../backend/app/realtime.py#L16) · [收送](../../backend/app/realtime.py#L64) | 隔離環境量正常多分頁與可接受上限。核對撤銷、離團、回收、正常 heartbeat、超限關閉與重連；封存維持既有權限。 |
| WTG-29 | FR-AUTH-03/04/06、BR-001/002、AC-015 | P2 · S/A | 待決策 | 已有本裝置登出、訪客合併及風險提示。接收 owner 的條件是有效成員，訪客可能成為唯一 owner。[登出](../../backend/app/auth.py#L157) · [所有權轉移](../../backend/app/trips.py#L317) · [登入提示](../../frontend/components/AccessDialog.tsx#L162) | 決定其他裝置撤銷與訪客復原／轉交規則後，驗 HTTP/WS 撤權、不可撤他人 session、合併後歷史與附件，以及旅程始終只有一位有效 owner。 |
| WTG-30 | FR-NOTIFY-01/02、FR-COMMENT-04 | P3，承諾可靠通知時 P2 · S/A | 待決策 | 站內通知隨留言提交，推播在 commit 後背景寄送，發送前會篩選資格與偏好。現行交付機制屬 best-effort。[留言](../../backend/app/decisions.py#L537) · [發送](../../backend/app/notices.py#L137) | 先驗推播失敗時留言與站內通知可用。僅在承諾可靠送達時追加 outbox 驗收，含重啟接續、去重、有限重試及發送前撤權／偏好重查。 |

#### 31–36　財務歷程、發布與攜出

| 項目 | 原規格 | 優先度與證據 | 本次判讀 | 現況與查核位置 | 日後驗收條件 |
| --- | --- | --- | --- | --- | --- |
| WTG-31 | FR-HISTORY-01、FR-FIN-05/06/09 | P2 · S/A | 確認稽核粒度；更正政策待決策 | 費用有操作紀錄，修改會替換分攤與付款人，刪除不留完整前後快照；既有帳本幣別及退出成員歸屬有測試。[費用](../../backend/app/finance.py#L282) · [刪除](../../backend/app/finance.py#L332) · [財務回歸](../../backend/tests/test_finance.py) | 核定結清後可否更正及保留範圍後，驗多付款人、尾差、幣別、刪除前後餘額與私人欄位；舊版重送不得增加修訂。 |
| WTG-32 | §5.1/5.4、FR-FILE-06 | P2 · S/A | 容量與營運指標待決策 | 單檔及單旅程配額已設；歷史五人延遲有數據，最低主機與上傳、備份及還原同時發生的高峰待量測。[部署](../../compose.yaml) · [歷史五人量測](../../README.md#L153) | 代表性主機量 CPU、峰值 RSS、磁碟、日誌及恢復時間，包含回收檔案；依數據決定預算、保留期及告警。 |
| WTG-33 | §5.2/5.5、BR-014 | P2 · S/A | 已知設定；部署強化屬提案 | 還原服務無網路；主要服務共用 Compose 網路。nginx 已送部分安全 headers。公開頁面 CSP 及網路隔離仍有改善空間。[網路](../../compose.yaml#L78) · [headers](../../deploy/nginx.conf#L11) | 依部署方案驗資料庫可達範圍與必要服務連線，在實際 HTTPS 入口驗 OAuth、WS、地圖、離線、列印，再決定 CSP 與網域政策。 |
| WTG-34 | FR-FILE-06、FR-MAP-01、§6.1 | P2 · S/C | 確認設定缺口；超額影響有條件 | 圖磚 URL 為公開 build ARG，Compose 未轉入；預設上傳上限相容，調高單檔後批次可能先超過 nginx 110 MiB。正式 Compose 的 API 路徑直達 FastAPI。[建置](../../frontend/Dockerfile#L8) · [Compose](../../compose.yaml#L43) · [入口](../../deploy/nginx.conf#L27) | 實際重建前端看圖磚來源，預設與調高兩種值都經入口傳多檔；分清開發代理與正式路徑，核對 413 文案及安全重試。 |
| WTG-35 | §9 里程碑 1/5 | P2，歷史附件整理 P3 · S/A | 本次完成證據索引；其餘待決策或另案 | README 已有驗證與協作入口；兩輪歷史另有報告。這份文件新增版本與結案範圍索引。授權、貢獻政策、遠端分支保護須分別由擁有者選擇或查證。[開發入口](../../README.md#L112) · [歷史複驗](round2-review.md) | 能從此表找到需求、歷史 revision、來源與待驗流程。乾淨啟動及發布治理應另留實際紀錄，索引交付不代表整個 WTG-35 完成。 |
| WTG-36 | FR-PDF-01/02、FR-OFFLINE-01/02、BR-001/013 | P2 · S/A | 待決策 | 已有行程 PDF 及選用的欄位白名單離線快照；可攜式匯出格式、帳號刪除、共同帳務與所有權處置均需選擇。[列印](../../frontend/components/PlannerTools.tsx) · [離線欄位](../../frontend/lib/offlineTrips.ts#L77) · [原規格](../spec.md#L363) | 決定格式與資料範圍後，以相同帳號對照 API 與匯出可見欄位，驗金額、時區、取消與檔案關聯。刪除帳號不得使旅程無主或破壞共同帳務。 |

<a id="x-scope"></a>

### 12.3 選擇性提案的邊界

八項皆完成文件對照。下表列出已有要求與提案新增的範圍，採用與實作須另行決定。各項若獲採用，以 §6 原列條件驗收。

| 項目 | 現行依據 | 提案新增範圍 |
| --- | --- | --- |
| X-01 | 已有建立、邀請、安排行程與記帳入口。[體驗流程](../../README.md) | 新手引導清單；五分鐘是待量測的構想。 |
| X-02 | 首頁有唯讀旅程及每日行程展示。[示範旅程](../../frontend/lib/samples.ts) | 將投票、任務、分帳情境加入無須登入的展示。 |
| X-03 | 已有旅程與景點篩選。[旅程列表](../../frontend/components/Workspace.tsx) · [景點](../../frontend/components/Planner.tsx) | 費用、任務、附件的跨條件篩選與分頁相容性。 |
| X-04 | 留言通知已有定向入口，其他頁籤狀態多由元件管理。[網址讀取](../../frontend/components/Workspace.tsx#L57) · [頁籤](../../frontend/components/TripDetail.tsx#L335) | 可分享頁籤與前進／後退支援；網址仍須經相同授權。 |
| X-05 | 已有 opt-in、儲存時間、白名單與清除。[本機副本](../../frontend/lib/offlineTrips.ts) · [離線閱讀](../../frontend/public/offline-reader.js) | 新鮮度提示、格式版本、損壞資料復原與可選期限。 |
| X-06 | FR-PLAN-09 及既有航班欄位支援目的地時區／offset。[行程時間](../../backend/app/planning_time.py) · [航班](../../frontend/components/Reservations.tsx) | 城市選擇器與旅行當日 offset 輔助；連同 14 驗 DST 及跨日。 |
| X-07 | 任務、預訂、重疊與分帳分別已有頁面。[旅程頁籤](../../frontend/components/TripDetail.tsx) | 可直接前往處理的行前總覽；提示須按讀取者的 ACL 產生。 |
| X-08 | FR-TRIP-08 的安全複製已實作，有排除私人資料的案例。[複製](../../backend/app/trip_copy.py#L23) · [已有案例](../../backend/tests/test_trip_copy.py) | 可選範圍的旅程起始範本、標示來源與獨立編輯。 |

<a id="decision-history"></a>

### 12.4 決策、依賴與歷史證據

| 待決策事項 | 已確定的界線 | 未決定的具體影響 |
| --- | --- | --- |
| 附件回收、帳號刪除、資料攜出（11、27、31、36） | 旅程有 30 日復原窗口。規格訂每日備份、預設保留 7 日；目前備份腳本在新備份成功後才輪替超過七日的舊檔。若連續失敗，舊備份可能超過七日仍存在。檔案由上傳者管理，離團財務保留歷史歸屬。 | 檔案、草稿、receipt、通知、財務與備份各有不同生命週期。到期、授權、影響預覽、清除順序、匯出格式及欄位未核定，無法驗收永久釋放配額或帳號刪除。 |
| 活動、日期、週期（09、12、14、X-06） | 重投保留舊活動；調整旅程日期保留既有日程。 | 已移除活動如何再採用、是否支援僅結束日、刪空日與非空日的權限、時區保留當地鐘面或同一瞬間，都會改變預期結果。 |
| 訪客與通知（29、30） | 現行允許有效訪客接所有權；推播為背景 best-effort，站內通知有持久紀錄。 | 訪客失去裝置的復原責任、是否限制轉交、是否承諾可靠送達尚待決定，會改變撤銷、轉移及 outbox 的驗收條件。 |
| 部署與容量（02、04–07、21、26、28、32–34） | 單 worker、PostgreSQL 及 DB BLOB 是目前架構。規格 §5.1 的延遲目標適用 2–5 人測試場景。 | 公開入口、信任代理、解析失敗是否保留原件、最低主機、備份新鮮度、RPO 與 RTO 由維護者定。§4 的 26／27 小時為備份及還原新鮮度示例；§10.2 的維運目標待定。 |
| 治理與發布（24、25、35） | README 已要求 PR、CI 與獨立 review。本機有歷史來源與證據。 | 授權條款、私密 trace 的存取／保留與遠端 branch protection 仍需擁有者決定或提供設定佐證。 |

未來若啟動開發，§7.2 的前三批處理 08、09、10；接著是 01 的共用意圖識別、各 JSON 建立入口、multipart，再銜接 16。02／19 可先驗例外邊界，解析預算獨立驗收。§7.3 的其他依賴同樣適用，尤其是 11／27／36 的資料政策、21／26 的升級還原、18 的回應模型與前端契約、24 收集證據前的去識別。以該列的必要角色、狀態轉移與環境結果結案。

| 日期與 revision | 此時能支持的結論 | 如何用於本次交付 |
| --- | --- | --- |
| 2026-11-25，`f398d98` 加當時工作樹 | 第一輪驗收的主要對象含未提交變更，乾淨 HEAD 另行測試。[第一輪交接與環境](../acceptance/2026-11-25-round-1/開發修正交接.md) | 保留原有失敗與未驗項作沿革。 |
| 2026-11-25，`cada651` | 第二輪規格矩陣 436 列，當時 407 passed、14 failed、15 blocked。已核定的八項實體儲存對照另載於 v1.1。[第二輪原報告](../acceptance/2026-11-25-round-2/第二輪功能驗收報告.md) · [資料模型](../data-model.md) | 功能規格與 WTG 分別統計，結案時核對較新的修正紀錄。 |
| 2026-11-25 至 11-26，`d5a9786`、`87e5635`；`29a4b14` 補記 | 暱稱拒絕舊版、保留輸入與重讀；離線 fresh-tab、對話框返回焦點、鍵盤操作各有修正與複驗；正式 Safari 有指定版本的歷史紀錄。[第二輪複驗](round2-review.md) · [鍵盤複驗](accessibility-checks.md) · [暱稱測試](../../backend/tests/test_review_account_invitations.py#L54) | **先前已修復且本次以來源確認**限於這些子行為。它們可作 03、13、15 的參照，各列新增的場景仍應測試。 |
| 2026-11-25 實測；`29a4b14` 可查複驗彙整 | 六份 11-20 至 11-25 備份在 11-25 做了隔離還原。另有 PG 私人檔案 bytes、ACL 及回收狀態的歷史演練。[還原紀錄](round2-review.md#L30) · [第一輪還原](review-fixes.md) | 支持當時的還原情境；07 的新鮮度與 26 的異機切換仍待驗。 |
| 2026-11-26，`aac83bd` 附件原審查 | §2.2 記 SQLite 後端 63 passed、1 warning；Vitest 2 檔共 5 passed；選取的 12 個瀏覽器案例均在啟動受阻，0 個走到產品斷言。§9.3 的 SQL 次數、RSS、狀態碼亦出自該次。 | 行號對應這個版本。附件未列完整 12 個測試標題或 selector，日後若需逐一比對同一批，須補原命令或清單。 |

<a id="verification-record"></a>

### 12.5 本次驗證紀錄與後續重跑

**執行環境**　2026-11-26（臺北），macOS 27.2.1、arm64、zsh，文件檢查使用 Python 3.14.2 標準函式庫。執行位置均為工作區根目錄，前端依賴準備在 `frontend/` 執行。

| 結果 | 本次實際執行或檢查 | 能支持的結論 |
| --- | --- | --- |
| passed | `git rev-parse HEAD`、`git status --short --branch`、`git diff --exit-code aac83bd HEAD --`、`git log --format='%h %ad %s' --date=iso-strict` | 起始工作樹乾淨，HEAD 等於附件版本；後續歷史索引按提交日期與 revision 查核。 |
| passed | `shasum -a 256 ~/Desktop/WayToGo_Feedback.md`；原附件為 82,134 bytes，SHA-256 為 `cafaa8dbf996534c6807a5ed2870beecbf9e6c547b2ef76f86a73daa1d5fd4a7`。 | 核對工作區版本所使用的確切輸入。 |
| passed | `rg` 核對需求、路由、設定與案例；以 `python3 -c` 的 `ast.parse` 掃描 `backend/app/*.py` 中 app／router 的 GET、POST、PUT、PATCH、DELETE，排除明訂 `include_in_schema=False`。 | 共 93 個可見 HTTP 路由宣告、0 個顯式 `response_model`、0 個回傳型別註記。附件所列 84 個空的 JSON 成功回應來自當時的執行時 OpenAPI。 |
| passed | Python 標準函式庫檢查附件正文還原後逐位元組相同、36 個 WTG 與 8 個 X 各自順序且不重複、§8.1 的 16 個情境均保留；核對補充章與開頭導覽共 121 處本機檔案連結、行號或頁內錨點。 | 保留原始工作量／優先度／證據分類、驗收條件與歷史數字。前言與補充章可獨立導覽。 |
| passed | `git diff --exit-code HEAD --`、`git diff --check --no-index -- /dev/null WayToGo_Feedback.md`、`git status --short --untracked-files=all` | 已追蹤內容無差異；新檔與空檔做 no-index 比對回傳 1（內容有差異），無空白錯誤診斷；工作樹交付項僅本檔。 |
| failed | 文件驗收最終未通過項目共 0 項。 | 未以功能測試數作文件分母。 |
| skipped | pytest、Vitest、正式前端建置、Playwright、native Safari、Google 真實登入、裝置推播、正式 HTTPS 及跨主機演練均未於本次執行。 | 本次是文件交付；產品案例沒有新增 passed／failed。附件過去的 Chromium 啟動障礙只屬當時環境。 |
| blocked | `docker info --format '{{.ServerVersion}}'` 回傳 exit 1，無法連線至本機 Docker daemon。 | 只查環境可用性。本次沒有在 Compose 上執行 PostgreSQL、容器換 IP、備份或還原，文件交付可獨立完成。 |

**2026-11-26 的歷史指令**　以下 Git 比對與來源定位指令記錄 `aac83bd` 當時的工作樹狀態。

```sh
git rev-parse HEAD
git diff --exit-code aac83bd HEAD --
git diff --exit-code HEAD --
git status --short --untracked-files=all
rg -n 'Idempotency-Key|randomUUID' frontend/lib/api.ts
rg -n 'creation_id|def copy_trip' backend/app/trip_copy.py
rg -n -- '--trace=off|args.tests or' backend/run_live_acceptance.py
```

**在目前目錄重跑文件驗證**　從儲存庫根目錄執行以下指令。它會從本檔還原原附件正文，以當時記錄的 SHA-256 核對。若另有原附件，也可在 `python3 -` 後加上它的路徑進行比對。通過時第一行會顯示 82,134 bytes、36 項 WTG、8 項提案、16 個情境及 121 處引用。第二行列出目前程式的路由統計。

```sh
python3 - <<'PY'
from pathlib import Path
import ast, hashlib, re, sys

feedback = Path("docs/reviews/WayToGo_Feedback.md")
history, supplement = feedback.read_bytes().split("\n---\n\n## 12. ".encode(), 1)
title = history.split(b"\n", 1)[0]
body_start = history.index("\n\n> WayToGo 已具備".encode())
original = title + history[body_start:]
assert hashlib.sha256(original).hexdigest() == "cafaa8dbf996534c6807a5ed2870beecbf9e6c547b2ef76f86a73daa1d5fd4a7"
if len(sys.argv) > 1:
    assert Path(sys.argv[1]).read_bytes() == original, "原附件與保存的正文不同"
_, rest = original.split(b"\n", 1)
assert history.startswith(title + b"\n") and history.endswith(rest)
guide = history[len(title):-len(rest)].decode()
current = supplement.decode()
old = rest.decode()
matrix = current.split("### 12.2 ", 1)[1].split("### 12.3 ", 1)[0]

def rows(section, prefix):
    return [line.strip("|").split(" | ") for line in section.splitlines()
            if re.match(r"^\| " + prefix + r"-\d{2} \|", line)]

before, after = rows(old, "WTG"), rows(matrix, "WTG")
assert [r[0].strip() for r in before] == [r[0].strip() for r in after] == [
    f"WTG-{n:02}" for n in range(1, 37)]
for a, b in zip(before, after):
    assert re.findall(r"P[123]\*?", a[1]) == re.findall(r"P[123]\*?", b[2])
    assert a[3].replace("／", "/") == b[2].split("·")[-1].strip()
x_section = current.split("### 12.3 ", 1)[1].split("### 12.4 ", 1)[0]
assert [r[0].strip() for r in rows(x_section, "X")] == [f"X-{n:02}" for n in range(1, 9)]
roles = old.split("### 8.1 ", 1)[1].split("### 8.2 ", 1)[0]
assert len([line for line in roles.splitlines() if line.startswith("|")]) - 2 == 16

# 移去程式碼區塊，只核對文件中的補充連結。
prose = re.sub(r"^`{3}[^\n]*\n.*?^`{3}$", "", guide + current, flags=re.M | re.S)
links = re.findall(r"\]\(([^)]+)\)", prose)
for link in links:
    filename, _, anchor = link.partition("#")
    if not filename:
        assert prose.count(f'id="{anchor}"') == 1, link
    else:
        path = feedback.parent / filename
        assert path.resolve().is_relative_to(Path.cwd()) and path.is_file(), link
        if anchor:
            assert re.fullmatch(r"L\d+", anchor) and 0 < int(anchor[1:]) <= len(path.read_bytes().splitlines()), link
print(f"original={len(original)} bytes; WTG={len(after)}; X=8; scenarios=16; references={len(links)}")

routes = []
for module in Path("backend/app").glob("*.py"):
    for node in ast.walk(ast.parse(module.read_text())):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            target = decorator.func
            if not isinstance(target.value, ast.Name) or target.value.id not in {"app", "router"}:
                continue
            if target.attr not in {"get", "post", "put", "patch", "delete"}:
                continue
            keys = {k.arg: k.value for k in decorator.keywords}
            if isinstance(keys.get("include_in_schema"), ast.Constant) and keys["include_in_schema"].value is False:
                continue
            routes.append(("response_model" in keys, node.returns is not None))
print(f"route declarations={len(routes)}; explicit response_model={sum(m for m, _ in routes)}; return annotations={sum(a for _, a in routes)}")
PY
```

**2026-11-26 的原始輸出**　當時兩個 `git diff --exit-code` 都回傳 0。`rg` 命中預設鍵在 `api.ts:22`、複製路由的 `creation_id`，以及 runner 選取預設測試與關閉 trace 的程式行。

```text
aac83bda1d580e8000f62d953a829ab9f65dcd7a
?? WayToGo_Feedback.md
original=82134 bytes; WTG=36; X=8; scenarios=16; references=121
route declarations=93; explicit response_model=0; return annotations=0
```

**核對來源內容**　§12.2 的逐項判讀來自閱讀所連的規格、程式與設定。121 處引用的自動檢查只判定路徑、行號範圍及錨點是否存在。下列摘錄來自固定 revision；可用 `git show aac83bd:路徑` 讀取完整上下文。

| 項目 | `aac83bd` 來源摘錄與判讀 |
| --- | --- |
| 01 冪等 | `docs/spec.md:587` 規定「重要建立及財務寫入操作應支援冪等性識別」。`frontend/lib/api.ts:22` 使用 `idempotencyKey ?? crypto.randomUUID()`；`backend/app/trip_copy.py:88` 已把 `idempotency_key` 傳入 `creation_id`。 |
| 03 跨分頁身分 | `frontend/components/NoticeCenter.tsx:60–64` 成功時呼叫 `setData(result)`，例外分支只有 `setError(errorText(e))`；81–83 行另有 focus、visibilitychange 及站內通知事件。此段支持「重讀失敗仍可保留舊通知」，跨分頁畫面仍待瀏覽器驗收。 |
| 06 容器地址 | `deploy/nginx.conf:19,34` 的目的地分別是 `proxy_pass http://api:8000` 與 `proxy_pass http://frontend:3000`。換 IP 後是否中斷及恢復所需時間，須在部署測量。 |
| 07、27 備份輪替 | `deploy/backup.sh:8–14` 在 `pg_dump` 與 `pg_restore --list` 成功的分支執行 `-mmin +10080` 輪替，失敗分支 `exit 1`。這解釋了舊檔可能超過七日。 |
| 08、09、10 旅程資料 | `frontend/components/Decisions.tsx:198` 用 `places.find((p) => p.name === text)?.id`；`backend/app/decisions.py:470–471` 有既有 adoption 就回 `adoption.item_id`；`frontend/components/Reservations.tsx:165` 迭代 `members.map`。各項的同名、軟刪除及退出成員情境見 §12.2。 |
| 12 日期界線 | `backend/app/trips.py:60` 給日數 `le=3660`；`backend/app/planning.py:525` 直接計算 `trip.start_date + timedelta(days=day.day_number - 1)`；563–564 行新增日使用 `day_number=highest + 1`。驗收需涵蓋實際日曆範圍及合成日數。 |
| 23、24 測試入口 | `backend/run_live_acceptance.py:269,272` 預設選 `tests/live-preparations.spec.ts` 與 `tests/live-finance.spec.ts`，另傳 `--trace=off`。裸命令無法證明其他套件已執行或已保存 trace。 |

範圍確認前曾以 `uv venv --python 3.12 backend/.venv`、`uv pip install --python backend/.venv/bin/python -r backend/requirements-dev.txt` 及 `pnpm install --frozen-lockfile` 準備隔離依賴。兩個本次建立的工作區套件目錄均已清理；準備依賴不計入功能驗收。

**日後重跑入口**　每次先記 revision、環境、所選案例與各狀態數，保存合成資料的可觀察結果。§8.1 是角色、權限與交易的檢查表，單靠既有 suite 的總數無法逐項結案。

| 條件 | 重跑路徑與應留證據 |
| --- | --- |
| SQLite、單元與前端檢查 | 依 §9.2 在拋棄式 DB 執行 Ruff、pytest、Alembic，再於前端執行 typecheck、lint、format、Vitest 與 build。驗收具體 WTG 時列出其負例、預期錯誤、最終資料與修正後斷言。 |
| Chromium／Firefox／WebKit | 先裝相應引擎，以 `python backend/run_live_acceptance.py --production tests/review-acceptance.spec.ts tests/live-files.spec.ts` 選套件；用 `--browser firefox` 或 `--browser webkit` 選對應引擎。裸 `--production` 預設只跑行前與財務兩個測試檔。要比對歷史 12 例，須核對實際 selector 及執行數。[執行器](../../backend/run_live_acceptance.py#L269) |
| 正式 Safari、Google、背景推播、讀屏 | macOS 啟用 Safari WebDriver 後跑 `python backend/run_live_acceptance.py --production --browser safari`。有測試裝置與供應商連線時跑 `python backend/run_live_acceptance.py --production --push tests/live-push.spec.ts`，把模擬點擊、實際接收、原生點擊分開登記。Google 需部署者測試帳號與已登記回呼的 HTTPS 站；適用 WCAG 流程另用實際讀屏與鍵盤。[相容性紀錄](round2-review.md) |
| PostgreSQL、升級、代理、備份及災難復原 | 單元測試使用專用 `TEST_DATABASE_URL`，隔離瀏覽器 runner 使用 loopback `E2E_POSTGRES_TEST_URL`。另在拋棄式 Compose／測試主機，比對前版與升級後真實測試資料、權限、金額、檔案雜湊，在獨立 volume 做還原。代理拓撲、備份失敗與異機切換依 §8.1、§9.1 各留獨立紀錄。[fixture](../../backend/tests/conftest.py) · [CI 步驟](../../.github/workflows/ci.yml) · [還原程式](../../deploy/restore-drill.sh) |

**交付判定**　文件對照與來源核對完成。工作區仍以 `aac83bd` 的產品行為為準；實作修正、政策簽定與相應環境的通過證據，是日後個別 WTG 結案的條件。

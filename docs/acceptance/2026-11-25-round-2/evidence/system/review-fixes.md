# 2026-11-25 修正與驗收

本紀錄對應原檢查的 17 張修正卡。資料庫遷移至 `0009`，OpenAPI 列出 93 個 HTTP 操作。完整後端套件在 SQLite 通過 62 項，在 PostgreSQL 17.12 通過 61 項，另有 1 項專用於 SQLite 備份 API。以下分別列出背景推播、跨瀏覽器與身分驗證實測的範圍。

| 項目 | 結果與回歸方式 |
| --- | --- |
| D01 五人討論 | 五個獨立 Chrome 身分同時留言後，作者編輯 20 次，其餘四頁自動顯示。SQLite 與 PostgreSQL 17.12 各取得 80 筆 DOM 觀測，皆 0 逾時。P95 分別為 195 ms 和 193 ms。兩人斷線期間錯過的編輯也在重連後補上。[測試](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/live-collaboration.spec.ts) |
| D02 展示版本 | 從 GitHub 分支另行乾淨下載後，空庫升至 `0009`，取得 42 張表及 93 個 API 操作。實際登入後讀取日期協調、財務、任務、預訂、通知、天氣、規劃歷史及附件均回 200，複製旅程及建立評分投票均回 201。[草稿 PR](https://github.com/Cairoger/way-to-go/pull/1) · [從空目錄啟動](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/README.md#在本機啟動) |
| D03 Google 登入 | FastAPI 與資料庫測試涵蓋 Google 回應、訪客升級、資料合併及 Session 輪替。外部同意畫面與實際 Google 回呼待取得測試用 OAuth 用戶端後驗證。[身分測試](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/backend/tests/test_core.py) · [訪客合併](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/backend/tests/test_guest_merge.py) |
| D04 夏令時間 | 拒絕當地不存在的時間。秋季重複時段採第一次出現的 UTC 位移；測試覆蓋紐約跳時、重複小時及一般跨時區日期。[測試](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/backend/tests/test_planning_extensions.py) |
| D05 移除原始景點 | 現任編輯者經版本與租約檢查可封存景點。移出候選是另一項操作，歷史行程、任務與討論仍能辨識原景點。正式版瀏覽器測試透過 UI 封存後重載。[操作驗收](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/live-offline-planner.spec.ts) |
| D06 私人附件 | Chrome 實際上傳並重讀旅程、活動、任務、費用、預訂與留言的附件；第二個身分驗證下載及預覽權限。兩種 A4 PDF 的文字都排除私人檔名、訂位及費用標記，旅程副本也排除檔案。API 另驗證配額邊界及回收還原。[瀏覽器](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/live-files.spec.ts) · [API](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/backend/tests/test_files_recurrence.py) |
| D07 無障礙 | 原檢查列出首頁 5 處及行程頁 6 處文字對比失敗、3 張卡片名稱失配。修正後以 1280、390 像素寬度重跑有資料的首頁與行程頁，axe 的 WCAG 2.0／2.1／2.2 A、AA 規則皆為 0 個違規，另驗證鍵盤聚焦及可存取名稱。[測試](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/review-acceptance.spec.ts) |
| D08 離線新分頁 | 主動儲存旅程後斷網，關閉原頁，再用新分頁讀取日期、當地時間、景點與地址。離線副本唯讀，排除註記、私人文件、訂位與財務。登出及身分變更會清除本機副本。[冷啟動](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/live-offline-planner.spec.ts) · [清除與切換](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/offline-planner.spec.ts) |
| D09 個人資料 | 個人帳戶可修改顯示暱稱。以 UI 儲存、登出並重登，確認修改後的名稱也顯示在成員頁。[瀏覽器](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/review-acceptance.spec.ts) · [API](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/backend/tests/test_review_account_invitations.py) |
| D10 邀請重送 | 在同一旅程以相同操作者、冪等鍵與內容重試可取得原邀請和代碼。改用新鍵會產生另一筆。已撤銷或到期的邀請無法藉由重送恢復。[測試](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/backend/tests/test_review_account_invitations.py) |
| D11 原始建立者 | 成員頁同時顯示建立者、建立時間及現任擁有者。轉移所有權後原始身分仍可讀；無建立稽核的舊旅程採最早成員紀錄。[測試](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/backend/tests/test_review_account_invitations.py) |
| D12 重複任務 | 支援每日、每週、每月，每位負責人可更新自己的進度。完成一期後可重讀歷史、本期狀態和附件。[瀏覽器](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/live-files.spec.ts) · [週期與權限](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/backend/tests/test_files_recurrence.py) |
| D13 付費功能提示 | 地圖與航班入口標示受限服務，旅伴仍可開啟免費導航。瀏覽器測試核對顯示文字、連結與外部請求。[測試](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/offline-planner.spec.ts) |
| D14 資料模型 | 依專案擁有者決定保留現行結構。八項規格實體逐項列出實體欄位、關聯及讀寫規則。[八項對照](data-model.md) |
| D15 背景推播 | Windows 11 的 Chrome 158 與 Edge 158 使用一次性測試設定檔，關閉所有該站分頁後由另一位成員提及。在瀏覽器的裝置通知登錄中觀測到同一則提醒，Chrome 兩次分別為 541、552 ms，Edge 為 1,013 ms。自動觸發通知點擊另驗證了定位至原留言及已讀。Windows 通知中心中的人工點擊仍待驗證。[裝置與點擊測試](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/live-push.spec.ts) |
| D16 連線收尾 | 五條 WebSocket 的離線清理與撤權獨立測試通過 17 次，另重跑 4 組回歸、每組 27 項，皆順利收尾。[測試](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/backend/tests/test_core.py) |
| D17 WebKit 與 Safari | Windows WebKit 27.2（Playwright build 2388）對正式建置的登入重載、行前任務、通知及開啟提及留言共 4 項通過。Apple 裝置上的正式 Safari 待實測。[登入](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/local-login.spec.ts) · [行前與通知](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/frontend/tests/live-preparations.spec.ts) |

## 重跑

PostgreSQL 17.12 的兩次還原演練，均以新資料庫接收自訂格式的 `pg_dump`，比對 42 張表的筆數及內容摘要。一組驗證私人文件的原始位元組、授權成員、未授權旅程擁有者及回收狀態；另一組驗證瀏覽器實際上傳的 6 個檔案及其 6 筆關聯。[還原工作流程](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/.github/workflows/ci.yml)

先依 README 安裝前後端依賴，在 `frontend` 執行 `pnpm exec playwright install chromium webkit`。從儲存庫根目錄用已安裝後端依賴的 Python 執行下列指令。工具會建立獨立帳號、資料庫、服務連接埠及瀏覽器資料；可用 `CHROME_EXECUTABLE` 指定已安裝的 Chrome。

```sh
python backend/run_live_acceptance.py tests/live-collaboration.spec.ts
python backend/run_live_acceptance.py tests/review-acceptance.spec.ts tests/live-files.spec.ts
python backend/run_live_acceptance.py --production tests/live-offline-planner.spec.ts
python backend/run_live_acceptance.py --production --browser webkit tests/local-login.spec.ts tests/live-preparations.spec.ts
python backend/run_live_acceptance.py --production --push tests/live-push.spec.ts
```

五人協作預設使用臨時 SQLite；設定 `E2E_POSTGRES_TEST_URL` 指向專用本機 PostgreSQL 測試庫可重跑同一流程。實際背景推播需要瀏覽器供應商的推播服務可連線。正式 Safari 須使用 Apple 裝置，Google 真人首登須使用部署者註冊的 OAuth 回呼與測試帳號。[部署設定](https://github.com/Cairoger/way-to-go/blob/cada651b990923166e8efa6ee20f72885a9c2b92/README.md#google-登入)

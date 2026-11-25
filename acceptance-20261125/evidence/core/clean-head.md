# GitHub 履歷連結能取得的版本

2026-11-25 以匿名 GitHub REST 請求取得 `{"full_name":"Cairoger/way-to-go","visibility":"public","private":false,"default_branch":"main"}`。唯讀 `git ls-remote --heads origin main` 返回 `f398d983b5a2769ca2d06285cbece4fbabc176ab    refs/heads/main`，與本機 `git rev-parse HEAD` 相同。本次網路查詢未更新本機 Git refs。[GitHub 儲存庫](https://github.com/Cairoger/way-to-go) · [固定版次](https://github.com/Cairoger/way-to-go/tree/f398d983b5a2769ca2d06285cbece4fbabc176ab)

從該 SHA 的 86 個已提交檔案建立全新目錄，以 `git archive` 匯出，沒有從工作樹覆蓋任何程式。在該目錄實跑全部後端 pytest，結果為 **23 passed、1 個相依套件棄用警示**。另將乾淨 HEAD 和工作樹版各自升級到 Alembic 最新 migration，在兩個獨立 SQLite 建立臨時本機 Owner、登入並建立旅程，透過 FastAPI ASGI 入口實際送出下列請求。兩版使用同一個現成 Python 3.12.14 環境，檢查 HEAD 列出的所有 Python 生產依賴版本均符合其鎖定值。這一組證據涵蓋無工作樹補丁的後端程式與資料庫初始化。新機下載套件、Docker Compose 全棧及公開部署以總報告各自的驗收結果為準。

| 實測項目 | 公開 main 的 HEAD | 本機工作樹 |
|---|---|---|
| API 文件登錄的 HTTP method + path 組合 | 50 | 83，增加 33，移除 0 |
| Alembic 版本、實際 SQLite 資料表數（含 alembic_version） | 0002、22 | 0007、38 |
| 成員讀景點、每日行程、投票與留言 | 全部 200 | 全部 200 |
| 成員讀日期協調、財務、任務、訂位、站內通知 | 五項全為 404 | 五項全為 200 |
| 成員讀每日天氣、行程版本紀錄 | 兩項 404 | 兩項 200，未填景點時天氣為可用性回應 |
| Owner 複製旅程 | 404 | 201 |
| 建立 rating 評分投票 | 422 | 201 |
| 讀旅程附件集合 | 404 | 404 |

**面試官能重現的範圍。** 公開版包含能實跑的帳號、邀請、旅程、景點、每日行程、投票、討論與 WebSocket 測試。提交後的 26 個已追蹤檔案變更，以及 44 個未追蹤的產品檔案，使本機具備公開版尚無的介面及 API。從 Git tree 及提交內容可確認下列工作樹成果仍在版本差異中。

- 日期協調與評分／排序投票、旅費與分帳，包含資料表與前端控制項。
- 任務／訂位、站內通知及其偏好與瀏覽器推播、已存在 Google 帳號的訪客資料合併。
- 景點／活動的跨時區與建議時間、天氣、版本紀錄與單筆復原、旅程複製、列印工具與 Service Worker 的離線快取規則變更。比較範圍為新增模組與既有檔案差異，個別功能的完整程度須以需求矩陣為準。
- 尚未包含於公開版的後端驗收檔為 `test_availability.py`、`test_finance.py`、`test_guest_merge.py`、`test_notices.py`、`test_planning_extensions.py`、`test_preparations.py`、`test_trip_copy.py`。前端包括 `coordination.spec.ts`、`live-finance.spec.ts`、`live-preparations.spec.ts`、`planner-print.spec.ts`、`planner.test.ts`。獨立 live runner、五個 migration、README 與 CI 配置修改亦屬工作樹版本。

完整清單含每一個公開檔、未提交產品檔、HTTP operation、依賴版本、兩側回應碼與實際資料表名稱。[完整差異與回應](clean-head.json) · [公開版 pytest 原始輸出](clean-head-pytest.log) · [匯出、遷移與實測腳本](clean-head-check.py)

在專案根目錄可用 `git ls-remote --heads origin main`、`git ls-tree -r --name-only HEAD`、`git show HEAD:backend/app/main.py`、`git show HEAD:frontend/components/TripDetail.tsx` 重新核對版次與可見模組。執行 `.venv/Scripts/python.exe acceptance-20261125/evidence/core/clean-head-check.py` 可對目前 HEAD 與目前工作樹重做後端比較。腳本沒有 commit、checkout、push 或 PR 操作。


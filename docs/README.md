# WayToGo 文件索引

| 想找的資料 | 從這裡開始 |
| --- | --- |
| 安裝、部署及執行測試 | [專案使用說明](../README.md) |
| 產品需求與業務規則 | [需求規格與驗收標準](spec.md) |
| 資料表與實體關聯 | [資料模型對照](data-model.md) |
| 審查回饋與改善清單 | [工作區審查與開發回饋](reviews/WayToGo_Feedback.md) |
| 開發修正與複驗 | [第一輪 17 項修正](reviews/review-fixes.md) · [第二輪修正](reviews/round2-review.md) · [無障礙複驗](reviews/accessibility-checks.md) |
| 2026-11-26 功能驗證 | [驗證紀錄](acceptance/functional-verification-2026-11-26.md) · [HTTP 操作清單（TSV）](acceptance/functional-verification-2026-11-26-openapi.tsv) |

## 2026-11-25 兩輪驗收

| 輪次 | 報告與需求矩陣 | 開發交接 | 原始證據 |
| --- | --- | --- | --- |
| 第一輪 | [功能驗收報告（HTML）](acceptance/2026-11-25-round-1/功能驗收報告.html) · [需求矩陣（JSON）](acceptance/2026-11-25-round-1/需求矩陣.json) | [開發修正交接](acceptance/2026-11-25-round-1/開發修正交接.md) | [證據 ZIP](acceptance/2026-11-25-round-1/WayToGo-驗收證據.zip) |
| 第二輪（`cada651`） | [功能驗收報告](acceptance/2026-11-25-round-2/第二輪功能驗收報告.md) · [需求追蹤矩陣](acceptance/2026-11-25-round-2/需求追蹤矩陣.md) · [需求矩陣（JSON）](acceptance/2026-11-25-round-2/需求矩陣.json) | [開發修正交接](acceptance/2026-11-25-round-2/第二輪開發修正交接.md) | [證據 ZIP](acceptance/2026-11-25-round-2/WayToGo-第二輪驗收證據.zip) |

每輪的 `evidence/` 都保存了截圖、測試腳本與執行紀錄。在該輪目錄執行以下指令，即可讀取 Windows 換行格式的清單並核對每個檔案的 SHA-256。

```sh
tr -d '\r' < evidence/system/checksums.sha256 | shasum -a 256 -c -
```

封存腳本沿用當時的路徑。要依交接文件重現舊環境，請將兩輪資料夾複製到對應版本的獨立工作目錄根層，分別命名為 `acceptance-20261125/` 和 `acceptance-retest-cada651/`。目前版本的測試指令見[開發與驗證](../README.md#開發與驗證)。

本機匯出的 `functional-fix-verification-*.zip` 放在 `docs/acceptance/`，內含原始碼快照與測試日誌，由 Git 忽略。

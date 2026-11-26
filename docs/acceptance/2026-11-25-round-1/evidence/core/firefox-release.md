# §5.3 Windows Firefox 正式版

2026-11-25 查詢 Mozilla 的版本服務，`LATEST_FIREFOX_VERSION` 為 **161.0**。選用 win64/en-US 正式發行檔，本次未執行安裝程式，直接將其正式發行內容解壓至隔離目錄。整檔 SHA-512 比對 Mozilla 發布的 SHA512SUMS 相符。執行時 Marionette 回報 `browserName=firefox`、`browserVersion=161.0`、`platformName=windows`、`moz:headless=true`。[Mozilla 官方版本資料](https://product-details.mozilla.org/1.0/firefox_versions.json) · [Windows x64 正式版](https://archive.mozilla.org/pub/firefox/releases/161.0/win64/en-US/Firefox%20Setup%20161.0.exe) · [官方校驗表](https://archive.mozilla.org/pub/firefox/releases/161.0/SHA512SUMS)

| 隔離情境 | 預期 | 實際 |
|---|---|---|
| 首頁 → 建立旅程 → 本機測試帳號登入 | 出現可填寫的建立表單 | 已以 Marionette 原生按鍵輸入合成帳密、點擊登入並成功開啟表單 |
| 只填旅程名稱後送出並重整 | 進入新旅程且保留登入狀態 | 建立後及重整後皆看見同一旅程標題 |
| 新增活動、儲存、重整 | 活動名稱持久化顯示 | 儲存後及重整後均可在每日行程找到「正式版實際活動」 |
| 旅伴 → 產生邀請 | 有邀請連結與 QR 圖 | 偵測到實際邀請碼 URL 及 QR 圖片元素；未對外分享 |

被測基準是含未提交變更的 18731 本機驗收服務。瀏覽器控制透過 Firefox 內建 Marionette，同一個新 profile 跨重整操作。初次沙箱內導覽出現 `Browsing context has been discarded`；改用同一隔離 profile 策略在沙箱外啟動，並修正建立表單的 role=dialog 定位後，完整腳本回傳 0。選定流程通過不代表每個功能或其他作業系統均經正式版驗證。瀏覽器已結束，下載檔、解壓內容及臨時 profiles 均已清除。

- 正式版安裝包大小 96,488,024 bytes；SHA-512 為 `39D71027FF2625A58CF88A7AE03EBF41E37612914637960DD3F1B2609A41465CFC46B1F0E2B23F0E420510A00A0F423E9ECDE96060D359A075D5C7E7E574FC4D`。
- 要重測時，將上列 Firefox 正式版的 core 目錄解壓至新建隔離資料夾，以 `WTG_FIREFOX_STAGE` 指向其父目錄，`WTG_CORE_ORIGIN` 指向隔離站，`WTG_UI_CONFIG` 指向含合成 username、password 的本機測試設定檔。執行 `.venv/Scripts/python.exe acceptance-20261125/evidence/core/firefox-release.py`。[實際輸出](firefox-release.log) · [完整腳本](firefox-release.py) · [Firefox 頁面截圖](firefox-release.png)


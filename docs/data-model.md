# §7 資料模型對照

專案擁有者於 2026-11-25 選擇保留現有實體結構。下表列出規格中的八個實體如何寫入、讀取與維持關聯。本決定適用於規格 §7 的資料儲存格式；使用者可見的功能與存取權仍依各項 FR 和 BR 驗收。

| 驗收項 | 實體資料與關聯 | 讀寫規則 |
| --- | --- | --- |
| DB-POLLS | `polls` 保存旅程、建立者及編輯者；投票類型、規則與截止日期由所選的 `poll_rounds` 取得。 | 新建投票同時建立第一輪；讀取目前投票時採用最新輪次。 |
| DB-POLL-ROUNDS | `poll_rounds.poll_id` 指向投票；`number` 是輪次編號。 | 每輪依自己的截止與結束時間判定狀態。重開投票建立新輪，保留先前選票及結果。 |
| DB-POLL-OPTIONS | `poll_options.round_id → poll_rounds.poll_id → polls.id`。 | 選項和建立者屬於特定輪，投票與重開時檢查所屬輪次。 |
| DB-TASK-LISTS | 同旅程的 `tasks.scope=shared` 形成共用清單；`scope=personal` 搭配 `created_by` 形成個人清單。 | `task_assignees` 紀錄各負責人的進度，個人清單以建立者身分限制讀寫。 |
| DB-FLIGHTS | `bookings.kind=flight` 的 `segments` 按順序保存各段航空公司、班號、航點、時差與航廈。 | 一次版本化的預訂更新可保存多段航班並關聯一個行程項目。 |
| DB-FLIGHT-PASSENGERS | 各航段的 `passengers[]` 保存成員 ID、座位及行李。 | 新指派須為本旅程成員，讀取時依登入者過濾座位、行李及訂位代號。 |
| DB-ACCOMMODATIONS | `bookings.kind=stay` 以 `stay` 保存地址、房型與入住退房日。 | 每間住宿有獨立預訂、金額、版本與關聯活動。 |
| DB-ACCOMMODATION-GUESTS | `bookings.stay.guests[]` 保存住客的成員 ID。 | 管理預訂時驗證人員身分，建立者退出後擁有者可維護公開欄位，原有私人資訊及授權予以保留。 |

此對照沿用既有資料，升版無須重寫歷史選票、分派紀錄或訂位內容。新增附件則透過檔案、授權、關聯資料表存放；詳細規格見 [§7 資料模型](spec.md)。
